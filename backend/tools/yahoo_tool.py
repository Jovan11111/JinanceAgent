import os
import shutil
import tempfile
import threading
import uuid
from base64 import b64decode
from pathlib import Path

from config import Config

# narumiruna/yfmcp. It is a yfinance MCP server and is meant to be started with uvx.
_PACKAGE = "yfmcp==0.14.1"
_TEXT_LIMIT = 8000


class YahooTool:
    """Runs the Yahoo Finance MCP server and exposes its tools to the model."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread = None
        self._loop = None
        self._stdio = None
        self._session_cm = None
        self._session = None
        self._tools = []
        self._error = None

    def warmup(self):
        self._start()

    def specs(self) -> list[dict]:
        self._ensure()
        if self._error or not self._tools:
            return [_down_spec(self._error or "Yahoo Finance MCP is unavailable.")]
        return [_tool_spec(tool) for tool in self._tools]

    def owns(self, name: str) -> bool:
        if name == "yahoo_finance" and (self._error or not self._tools):
            return True
        return any(getattr(tool, "name", None) == name for tool in self._tools)

    def call(self, name: str, arguments: dict) -> dict:
        self._ensure()
        if self._error or self._session is None:
            return _fail(self._error or "Yahoo Finance MCP is unavailable.")
        if name == "yahoo_finance":
            return _fail(self._error or "Yahoo Finance MCP is unavailable.")
        import asyncio

        future = asyncio.run_coroutine_threadsafe(self._call(name, arguments), self._loop)
        try:
            return future.result(timeout=90)
        except Exception as exc:
            return _fail(f"{name} failed: {exc}")

    def _start(self):
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._thread_main, name="yahoo-mcp", daemon=True)
            self._thread.start()

    def _ensure(self):
        self._start()
        if not self._ready.wait(180) and self._error is None:
            self._error = "Yahoo Finance MCP did not start in time."

    def _thread_main(self):
        import asyncio

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._open())
        except Exception as exc:
            self._error = _short(exc)
        finally:
            self._ready.set()
        if self._session is not None:
            try:
                self._loop.run_forever()
            finally:
                self._loop.close()

    def close(self):
        if self._loop is None or self._session is None or not self._loop.is_running():
            return
        import asyncio

        async def _shutdown():
            try:
                if self._session_cm is not None:
                    await self._session_cm.__aexit__(None, None, None)
            finally:
                if self._stdio is not None:
                    await self._stdio.__aexit__(None, None, None)

        future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        try:
            future.result(timeout=5)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    async def _open(self):
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        params = StdioServerParameters(
            command=_uvx(),
            args=[_PACKAGE],
            env={
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "CURL_CA_BUNDLE": _ca_bundle(),
                "SSL_CERT_FILE": _ca_bundle(),
                "REQUESTS_CA_BUNDLE": _ca_bundle(),
            },
        )
        self._stdio = stdio_client(params)
        read, write = await self._stdio.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        listed = await self._session.list_tools()
        self._tools = list(listed.tools)
        if not self._tools:
            raise RuntimeError("Yahoo Finance MCP returned no tools.")
        import atexit

        atexit.register(self.close)

    async def _call(self, name: str, arguments: dict) -> dict:
        result = await self._session.call_tool(name, arguments or {}, read_timeout_seconds=60)
        texts = []
        images = []
        for block in result.content or []:
            kind = getattr(block, "type", "")
            if kind == "text" and getattr(block, "text", None):
                texts.append(block.text)
            elif kind == "image" and getattr(block, "data", None):
                mime = getattr(block, "mimeType", None) or getattr(block, "mime_type", None) or "image/png"
                images.append(_save_image(block.data, mime))
        content = "\n".join(texts).strip() or "No data returned."
        if len(content) > _TEXT_LIMIT:
            content = content[:_TEXT_LIMIT].rstrip() + "\n...[truncated]"
        if getattr(result, "is_error", False):
            content = "Yahoo Finance tool failed. " + content
        return {"content": content, "images": images, "files": []}


def _uvx() -> str:
    scripts = Config.ROOT / "venv" / "Scripts"
    for name in ("uvx.exe", "uvx"):
        path = scripts / name
        if path.is_file():
            return str(path)
    return "uvx"


def _ca_bundle() -> str:
    """curl cannot open a CA file when the path contains non-ASCII characters."""
    import certifi

    source = certifi.where()
    short_path = _short_path(source)
    if short_path and _ascii(short_path) and Path(short_path).is_file():
        return short_path
    destination = Path(tempfile.gettempdir()) / "jinance-cacert.pem"
    if _ascii(str(destination)):
        shutil.copyfile(source, destination)
        return str(destination)
    return source


def _short_path(path: str) -> str:
    if os.name != "nt":
        return path
    import ctypes
    from ctypes import wintypes

    get_short = ctypes.windll.kernel32.GetShortPathNameW
    get_short.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(4096)
    length = get_short(str(path), buffer, 4096)
    return buffer.value if length else path


def _ascii(value: str) -> bool:
    return all(ord(char) < 128 for char in value)


def _save_image(data: str, mime: str) -> str:
    extension = {"image/png": "png", "image/webp": "webp", "image/jpeg": "jpg"}.get(mime, "img")
    filename = f"yahoo_{uuid.uuid4().hex[:8]}.{extension}"
    (Config.IMAGES_DIR / filename).write_bytes(b64decode(data))
    return filename


def _tool_spec(tool) -> dict:
    schema = getattr(tool, "input_schema", None)
    if schema is None:
        schema = getattr(tool, "inputSchema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(exclude_none=True)
    schema = dict(schema or {})
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    description = " ".join((tool.description or "").split())
    if len(description) > 500:
        description = description[:500].rstrip() + "..."
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": description,
            "parameters": schema,
        },
    }


def _down_spec(reason: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": "yahoo_finance",
            "description": f"Yahoo Finance is currently unavailable. {reason}"[:500],
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _fail(content: str) -> dict:
    return {"content": content, "images": [], "files": []}


def _short(exc: Exception) -> str:
    text = str(exc).strip().replace("\n", " ")
    return text[:300] if text else "Yahoo Finance MCP failed to start."

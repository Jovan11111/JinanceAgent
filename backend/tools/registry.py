import inspect


class ToolRegistry:
    """Holds the tools the model is allowed to call."""

    def __init__(self):
        from tools.graph_tool import GraphTool
        from tools.pdf_tool import PDFTool
        from tools.yahoo_tool import YahooTool

        self._graph = GraphTool()
        self._pdf = PDFTool()
        self._yahoo = YahooTool()
        self._local = {self._graph.name: self._graph, self._pdf.name: self._pdf}

    def warmup(self):
        self._yahoo.warmup()

    def specs(self) -> list[dict]:
        return [self._graph.spec(), self._pdf.spec(), *self._yahoo.specs()]

    def execute(self, name: str, arguments: dict | None) -> dict:
        if arguments is None:
            return _result(f"Arguments for {name} were not valid JSON.")
        if not isinstance(arguments, dict):
            return _result(f"Arguments for {name} must be an object.")
        local = self._local.get(name)
        if local is not None:
            accepted = {
                key: value
                for key, value in arguments.items()
                if key in inspect.signature(local.run).parameters
            }
            try:
                result = local.run(**accepted)
            except Exception as exc:
                return _result(f"{name} failed: {exc}")
            if not isinstance(result, dict) or "content" not in result:
                return _result(f"{name} returned an unexpected result.")
            result.setdefault("images", [])
            result.setdefault("files", [])
            return result
        if self._yahoo.owns(name):
            return self._yahoo.call(name, arguments)
        return _result(f"Unknown tool: {name}")


def _result(content: str) -> dict:
    return {"content": content, "images": [], "files": []}

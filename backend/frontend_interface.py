import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import Agent
from config import Config
from database_interface import DataBaseInterface
from llm_interface import GroqLLMInterface
from models.chat import Chat


class MessageIn(BaseModel):
    content: str


def create_app(*, warmup: bool = True) -> FastAPI:
    db = DataBaseInterface()
    agent = Agent(db, GroqLLMInterface())
    if warmup:
        agent.tools.warmup()
    app = FastAPI(title="Jinance Agent")

    @app.middleware("http")
    async def api_not_cached(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/chats")
    def list_chats():
        return {"chats": [_chat_payload(chat) for chat in db.get_all_chats()]}

    @app.post("/api/chats")
    def create_chat():
        return _chat_payload(db.add_chat(Chat(title=Config.UNTITLED_CHAT)))

    @app.get("/api/chats/{chat_id}")
    def get_chat(chat_id: int):
        chat = db.get_chat(chat_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat not found.")
        messages = [_message_payload(message) for message in db.get_messages(chat_id)]
        return {"chat": _chat_payload(chat), "messages": messages}

    @app.delete("/api/chats/{chat_id}")
    def delete_chat(chat_id: int):
        if not db.delete_chat(chat_id):
            raise HTTPException(status_code=404, detail="Chat not found.")
        return {"ok": True}

    @app.post("/api/chats/{chat_id}/messages")
    def post_message(chat_id: int, body: MessageIn):
        if db.get_chat(chat_id) is None:
            raise HTTPException(status_code=404, detail="Chat not found.")
        if not body.content or not body.content.strip():
            raise HTTPException(status_code=400, detail="Message is empty.")
        created = agent.handle_user_message(chat_id, body.content)
        return {"messages": [_message_payload(message) for message in created]}

    @app.post("/api/chats/{chat_id}/close")
    def close_chat(chat_id: int, background: BackgroundTasks):
        chat = agent.close_chat(chat_id, review_preferences=False)
        if chat is not None:
            background.add_task(agent.update_preferences, chat.id)
        return {"chat": None if chat is None else _chat_payload(chat)}

    @app.get("/api/skills")
    def list_skills():
        return {"skills": Config.list_skills()}

    frontend = Config.FRONTEND_DIR

    @app.get("/")
    def index():
        return _frontend_file(frontend / "index.html", "text/html")

    @app.get("/style.css")
    def css():
        return _frontend_file(frontend / "style.css", "text/css")

    @app.get("/markdown.js")
    def markdown_script():
        return _frontend_file(frontend / "markdown.js", "text/javascript")

    @app.get("/app.js")
    def javascript():
        return _frontend_file(frontend / "app.js", "text/javascript")

    app.mount("/images", StaticFiles(directory=str(Config.IMAGES_DIR)), name="images")
    app.mount("/reports", StaticFiles(directory=str(Config.REPORTS_DIR)), name="reports")
    return app


def _frontend_file(path: Path, media_type: str):
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-cache"})


def _chat_payload(chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
        "active_skill": chat.active_skill,
    }


def _message_payload(message) -> dict:
    images = []
    files = []
    for item in message.attachments:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        if item.get("kind") == "image":
            images.append(name)
        elif item.get("kind") == "file":
            files.append(name)
    return {
        "id": message.id,
        "chat_id": message.chat_id,
        "type": message.type,
        "content": message.content,
        "created_at": message.created_at,
        "images": images,
        "files": files,
    }


if __name__ == "__main__":
    import uvicorn

    print(f"Jinance Agent is running at http://{Config.HOST}:{Config.PORT}")
    uvicorn.run(create_app(), host=Config.HOST, port=Config.PORT)

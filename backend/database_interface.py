import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from config import Config
from models.chat import Chat
from models.message import Message


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _chat_from_row(row: sqlite3.Row) -> Chat:
    return Chat(
        id=row["id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        summary=row["summary"],
        summary_until_id=row["summary_until_id"],
        active_skill=row["active_skill"],
    )


def _attachments_from_text(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return parsed


def _message_from_row(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        chat_id=row["chat_id"],
        type=row["type"],
        content=row["content"],
        created_at=row["created_at"],
        attachments=_attachments_from_text(row["attachments"]),
    )


class DataBaseInterface:
    """All database access. Callers pass models in and get models out."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else Config.DB_PATH
        self.connect()

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        Config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        Config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        schema = Config.SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connection() as connection:
            connection.executescript(schema)

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_chat(self, chat_id: int) -> Chat | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        if row is None:
            return None
        return _chat_from_row(row)

    def get_all_chats(self) -> list[Chat]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM chats ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [_chat_from_row(row) for row in rows]

    def get_latest_chat(self) -> Chat | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM chats ORDER BY updated_at DESC, id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return _chat_from_row(row)

    def add_chat(self, chat: Chat) -> Chat:
        timestamp = _now()
        title = (chat.title or "New chat").strip() or "New chat"
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chats (title, created_at, updated_at, summary, summary_until_id, active_skill)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, timestamp, timestamp, chat.summary, chat.summary_until_id, chat.active_skill),
            )
            chat_id = cursor.lastrowid
        return self.get_chat(chat_id)

    def update_chat(self, chat: Chat) -> Chat:
        """Save title, summary, and the active skill. Does not change updated_at."""
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE chats
                SET title = ?, summary = ?, summary_until_id = ?, active_skill = ?
                WHERE id = ?
                """,
                (chat.title, chat.summary, chat.summary_until_id, chat.active_skill, chat.id),
            )
        return self.get_chat(chat.id)

    def delete_chat(self, chat_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            return cursor.rowcount > 0

    def add_message(self, message: Message) -> Message:
        timestamp = message.created_at or _now()
        attachments = json.dumps(message.attachments) if message.attachments else None
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (chat_id, type, content, created_at, attachments)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message.chat_id, message.type, message.content, timestamp, attachments),
            )
            message_id = cursor.lastrowid
            connection.execute(
                "UPDATE chats SET updated_at = ? WHERE id = ?",
                (timestamp, message.chat_id),
            )
        return self.get_message(message_id)

    def get_message(self, message_id: int) -> Message | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            return None
        return _message_from_row(row)

    def get_messages(self, chat_id: int) -> list[Message]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC",
                (chat_id,),
            ).fetchall()
        return [_message_from_row(row) for row in rows]

import re
import threading

from config import Config
from models.message import Message
from tools.registry import ToolRegistry

_preferences_lock = threading.Lock()

_SKILL = re.compile(r"^/([A-Za-z0-9_-]+)(?:\s+([\s\S]+))?$")


class Agent:
    """Shared conversation flow for the CLI and the web API."""

    def __init__(self, db, llm):
        self.db = db
        self.llm = llm
        self.tools = ToolRegistry()

    def handle_user_message(self, chat_id: int, text: str) -> list[Message]:
        text = (text or "").strip()
        if not text:
            raise ValueError("Message is empty.")
        chat = self.db.get_chat(chat_id)
        if chat is None:
            raise ValueError("Chat not found.")

        created = [self.db.add_message(Message(chat_id=chat_id, type="user", content=text))]
        skill_name, remainder = _parse_skill(text)
        if skill_name is not None:
            if Config.load_skill(skill_name) is None:
                created.append(
                    self.db.add_message(
                        Message(
                            chat_id=chat_id,
                            type="agent",
                            content=f"Skill '{skill_name}' was not found.",
                        )
                    )
                )
                return self._with_compaction(created, chat_id)
            chat.active_skill = skill_name
            self.db.update_chat(chat)
            if remainder is None:
                created.append(
                    self.db.add_message(
                        Message(
                            chat_id=chat_id,
                            type="agent",
                            content=f"Loaded skill '{skill_name}'.",
                        )
                    )
                )
                return self._with_compaction(created, chat_id)

        try:
            answer = self._run_model(chat_id)
        except Exception as exc:
            created.append(
                self.db.add_message(
                    Message(
                        chat_id=chat_id,
                        type="agent",
                        content=f"I couldn't complete that request. {_short_error(exc)}",
                    )
                )
            )
            return self._with_compaction(created, chat_id)

        attachments = [{"kind": "image", "name": name} for name in answer.images]
        attachments += [{"kind": "file", "name": name} for name in answer.files]
        created.append(
            self.db.add_message(
                Message(
                    chat_id=chat_id,
                    type="agent",
                    content=answer.content,
                    attachments=attachments,
                )
            )
        )
        return self._with_compaction(created, chat_id)

    def close_chat(self, chat_id: int, *, review_preferences: bool = True):
        """Name an untitled chat. An unused chat is removed.

        Preferences are reviewed here for the CLI. The web handler names the
        chat first and reviews preferences after the response, so the new
        title is visible as soon as the chat is left.
        """
        chat = self.db.get_chat(chat_id)
        if chat is None:
            return None
        messages = self.db.get_messages(chat_id)
        if not any(message.type == "user" for message in messages):
            self.db.delete_chat(chat_id)
            return None
        self.generate_title(chat_id)
        if review_preferences:
            self.update_preferences(chat_id)
        return self.db.get_chat(chat_id)

    def generate_title(self, chat_id: int) -> str | None:
        chat = self.db.get_chat(chat_id)
        if chat is None:
            return None
        if (chat.title or "").strip() != Config.UNTITLED_CHAT:
            return chat.title
        messages = [
            message
            for message in self.db.get_messages(chat_id)
            if message.type in ("user", "agent")
        ]
        if not any(message.type == "user" for message in messages):
            return chat.title
        sample = messages[:4] if len(messages) <= 6 else messages[:3] + messages[-2:]
        transcript = "\n".join(
            ("User: " if message.type == "user" else "Assistant: ") + message.content[:500]
            for message in sample
        )
        prompt = (
            "Write the shortest possible title for this chat. "
            "Maximum 6 words. No quotes. No trailing punctuation.\n\n" + transcript
        )
        try:
            raw = self.llm.ask(prompt)
        except Exception:
            return chat.title
        title = _clean_title(raw)
        if not title:
            return chat.title
        chat.title = title
        self.db.update_chat(chat)
        return title

    def update_preferences(self, chat_id: int) -> bool:
        """Record a lasting preference, and only a lasting preference."""
        with _preferences_lock:
            chat = self.db.get_chat(chat_id)
            if chat is None:
                return False
            messages = [
                message
                for message in self.db.get_messages(chat_id)
                if message.type in ("user", "agent")
            ]
            if not any(message.type == "user" for message in messages):
                return False
            current = _read_preferences()
            transcript = "\n".join(
                ("User: " if message.type == "user" else "Assistant: ") + message.content[:300]
                for message in messages[-30:]
            )
            prompt = (
                "You keep a very small preferences note for a personal finance assistant.\n"
                "Current preferences:\n"
                f"{current or '(none)'}\n\n"
                "Conversation:\n"
                f"{transcript}\n\n"
                "Add something only when the user explicitly states a lasting preference about "
                "how you should behave, such as language, tone, length, units, or currency format.\n"
                "Do not store prices, tickers, holdings, dates, task details, or anything you inferred.\n"
                "If you are unsure, reply with exactly UNCHANGED.\n"
                "If nothing new qualifies, reply with exactly UNCHANGED.\n"
                "Otherwise reply with the full preferences note only, at most 12 lines, with no explanation."
            )
            try:
                raw = self.llm.ask(prompt)
            except Exception:
                return False
            updated = _accept_preferences(raw, current)
            if updated is None:
                return False
            _write_preferences(updated)
            return True

    def maybe_compact(self, chat_id: int) -> Message | None:
        chat = self.db.get_chat(chat_id)
        if chat is None:
            return None
        pending = []
        for message in self.db.get_messages(chat_id):
            if message.type not in ("user", "agent"):
                continue
            if chat.summary_until_id is not None and message.id <= chat.summary_until_id:
                continue
            pending.append(message)
        if len(pending) < Config.COMPACT_AFTER or len(pending) <= Config.KEEP_RECENT:
            return None
        to_fold = pending[: -Config.KEEP_RECENT]
        lines = []
        if chat.summary:
            lines.append("Previous summary:\n" + chat.summary.strip())
        lines.append("Messages:")
        for message in to_fold:
            speaker = "User" if message.type == "user" else "Assistant"
            lines.append(f"{speaker}: {message.content}")
        prompt = (
            "Summarize this personal-finance conversation. "
            "Keep numbers, decisions, symbols, and open questions. "
            "Be factual and shorter than the original.\n\n" + "\n".join(lines)
        )
        try:
            summary = self.llm.ask(prompt).strip()
        except Exception:
            return None
        if not summary:
            return None
        chat.summary = summary
        chat.summary_until_id = to_fold[-1].id
        self.db.update_chat(chat)
        return self.db.add_message(
            Message(
                chat_id=chat_id,
                type="notice",
                content=(
                    "This chat was compacted. Older messages stay visible, "
                    "and a summary is now used so the assistant can remember them."
                ),
            )
        )

    def _run_model(self, chat_id: int):
        chat = self.db.get_chat(chat_id)
        system = self._system_prompt(chat)
        if chat.summary:
            system += "\n\nSummary of the earlier part of this conversation:\n" + chat.summary.strip()
        messages = [{"role": "system", "content": system}]
        for message in self.db.get_messages(chat_id):
            if message.type not in ("user", "agent"):
                continue
            if chat.summary_until_id is not None and message.id <= chat.summary_until_id:
                continue
            role = "user" if message.type == "user" else "assistant"
            messages.append({"role": role, "content": message.content})
        return self.llm.answer(messages, self.tools.specs(), self.tools.execute)

    def _system_prompt(self, chat) -> str:
        try:
            base = Config.load_instruction_file("system.md").strip()
        except (OSError, ValueError):
            base = "You are Jinance Agent, a personal finance assistant."
        parts = [base]
        preferences = _read_preferences()
        if preferences:
            parts.append("User preferences. Follow them.\n" + preferences)
        if chat.active_skill:
            skill = Config.load_skill(chat.active_skill)
            if skill:
                parts.append(f"Active skill ({chat.active_skill}):\n{skill.strip()}")
        return "\n\n".join(parts)

    def _with_compaction(self, created: list[Message], chat_id: int) -> list[Message]:
        notice = self.maybe_compact(chat_id)
        if notice is not None:
            created.append(notice)
        return created


def _parse_skill(text: str) -> tuple[str | None, str | None]:
    match = _SKILL.match(text)
    if not match:
        return None, None
    remainder = match.group(2)
    if remainder is not None:
        remainder = remainder.strip() or None
    return match.group(1), remainder


def _clean_title(raw: str) -> str:
    if not raw:
        return ""
    title = raw.strip().splitlines()[0].strip().strip("\"'")
    title = re.sub(r"^title\s*:\s*", "", title, flags=re.IGNORECASE).strip()
    if len(title) > 80:
        title = title[:80].rstrip()
    return title


def _read_preferences() -> str:
    path = Config.PREFERENCES_PATH
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    body = re.sub(r"^#[^\n]*\n?", "", text, count=1).strip()
    if body.lower() in {"", "none yet.", "none yet"}:
        return ""
    return text


def _write_preferences(text: str):
    path = Config.PREFERENCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".md.tmp")
    temporary.write_text(text.strip() + "\n", encoding="utf-8")
    temporary.replace(path)


def _accept_preferences(raw: str, current: str) -> str | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    first = text.splitlines()[0].strip().strip(".").upper() if text else ""
    if not text or first == "UNCHANGED":
        return None
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 12 or len(text) > 800:
        return None
    if re.search(r"^(User|Assistant):", text, re.MULTILINE):
        return None
    if not text.startswith("#"):
        text = "# User preferences\n\n" + text
    if text.strip() == current.strip():
        return None
    return text


def _short_error(exc: Exception) -> str:
    detail = str(exc).strip().replace("\n", " ")
    if len(detail) > 400:
        detail = detail[:400].rstrip()
    return detail or "The model request failed."

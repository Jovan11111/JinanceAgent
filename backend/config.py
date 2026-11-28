import os
import re
from pathlib import Path


class Config:
    """Static settings and instruction loading. Secrets stay in backend/.env."""

    CLIENT = "GROQ"
    MODEL = "openai/gpt-oss-120b"
    HOST = "127.0.0.1"
    PORT = 8000

    # Compact once a chat has this many messages that are not in the summary yet.
    # The newest KEEP_RECENT messages stay verbatim so the model still sees the
    # latest exchange exactly.
    COMPACT_AFTER = 20
    KEEP_RECENT = 6
    MAX_TOOL_ROUNDS = 8
    UNTITLED_CHAT = "New chat"

    ROOT = Path(__file__).resolve().parent
    DB_PATH = Path(os.environ["JINANCE_DB"]) if os.environ.get("JINANCE_DB") else ROOT / "db" / "db.db"
    SCHEMA_PATH = ROOT / "db" / "create.sql"
    IMAGES_DIR = ROOT / "db" / "images"
    REPORTS_DIR = ROOT / "db" / "reports"
    INSTRUCTIONS_DIR = ROOT / "instructions"
    SKILLS_DIR = INSTRUCTIONS_DIR / "skills"
    PREFERENCES_PATH = (
        Path(os.environ["JINANCE_PREFERENCES"])
        if os.environ.get("JINANCE_PREFERENCES")
        else INSTRUCTIONS_DIR / "instruction_references.md"
    )
    FRONTEND_DIR = ROOT.parent / "frontend"

    _NAME = re.compile(r"^[A-Za-z0-9_-]+$")
    _trust_ready = False

    @staticmethod
    def use_os_certificates():
        """Trust the operating-system certificate store.

        Python's bundled CA list does not validate api.groq.com on this
        machine. The OS store does.
        """
        if Config._trust_ready:
            return
        Config._trust_ready = True
        try:
            import truststore

            truststore.inject_into_ssl()
        except Exception:
            return

    @staticmethod
    def list_skills() -> list[str]:
        if not Config.SKILLS_DIR.exists():
            return []
        return sorted(path.stem for path in Config.SKILLS_DIR.glob("*.md"))

    @staticmethod
    def load_skill(skill_name: str) -> str | None:
        """Return the skill markdown, or None when the name is unknown."""
        if not skill_name or not Config._NAME.fullmatch(skill_name):
            return None
        path = Config.SKILLS_DIR / f"{skill_name}.md"
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    @staticmethod
    def load_instruction_file(file_name: str) -> str:
        """Load one markdown file from the instructions folder."""
        if not file_name or Path(file_name).name != file_name:
            raise ValueError(f"Invalid instruction file name: {file_name}")
        path = Config.INSTRUCTIONS_DIR / file_name
        if not path.is_file():
            raise FileNotFoundError(f"Instruction file not found: {file_name}")
        return path.read_text(encoding="utf-8")

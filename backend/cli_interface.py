import os
import sys

from agent import Agent
from database_interface import DataBaseInterface
from llm_interface import GroqLLMInterface
from markdown_plain import render_cli
from models.chat import Chat

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


class CliInterface:
    """Terminal chat. Agent: is green, You: is red."""

    def __init__(self):
        self.db = DataBaseInterface()
        self.agent = Agent(self.db, GroqLLMInterface())

    def run(self):
        _enable_color()
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stdin.reconfigure(encoding="utf-8")
        except Exception:
            pass
        self.agent.tools.warmup()
        self._welcome()
        chat = None
        try:
            while True:
                try:
                    text = input(f"{RED}You:{RESET} ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not text:
                    continue
                if text.lower() in {"exit", "quit"}:
                    break
                if chat is None:
                    chat = self.db.add_chat(Chat(title="New chat"))
                try:
                    created = self.agent.handle_user_message(chat.id, text)
                except Exception as exc:
                    print(f"{GREEN}Agent:{RESET} {exc}")
                    continue
                for message in created:
                    if message.type == "user":
                        continue
                    print(f"{GREEN}Agent:{RESET} {render_cli(message.content)}")
        finally:
            if chat is not None:
                self.agent.close_chat(chat.id)

    def _welcome(self):
        print("Jinance Agent")
        print("Personal finance assistant.")
        print("Type a message and press Enter. Use /skill_name to load a skill. Type exit to quit.")
        print()


def _enable_color():
    if os.name != "nt":
        return
    import ctypes

    handle = ctypes.windll.kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint()
    if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)

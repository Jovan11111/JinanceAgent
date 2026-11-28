import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from dotenv import load_dotenv
from groq import APIConnectionError, APITimeoutError, AuthenticationError, Groq, RateLimitError

from config import Config


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict | None
    raw_arguments: str


@dataclass
class ModelTurn:
    content: str | None
    tool_calls: list[ToolCall]

    def as_message(self) -> dict:
        message = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.raw_arguments},
                }
                for call in self.tool_calls
            ]
        return message


@dataclass
class Answer:
    content: str
    images: list[str]
    files: list[str]


class LLMInterface(ABC):
    """One model call is abstract. The tool loop is the same for every client."""

    def ask(self, prompt: str) -> str:
        turn = self.complete([{"role": "user", "content": prompt}], None)
        return (turn.content or "").strip()

    def answer(self, messages: list[dict], tool_specs: list[dict], execute_tool) -> Answer:
        conversation = list(messages)
        images: list[str] = []
        files: list[str] = []
        for _ in range(Config.MAX_TOOL_ROUNDS):
            turn = self.complete(conversation, tool_specs)
            if not turn.tool_calls:
                return Answer(_visible_text(turn.content, images, files), images, files)
            conversation.append(turn.as_message())
            for call in turn.tool_calls:
                result = execute_tool(call.name, call.arguments)
                images.extend(result.get("images") or [])
                files.extend(result.get("files") or [])
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result.get("content") or "",
                    }
                )
        turn = self.complete(conversation, None)
        return Answer(_visible_text(turn.content, images, files), images, files)

    @abstractmethod
    def complete(self, messages: list[dict], tools: list[dict] | None) -> ModelTurn:
        """Send one request and return the model's next turn."""


class GroqLLMInterface(LLMInterface):
    def __init__(self):
        Config.use_os_certificates()
        load_dotenv(Config.ROOT / ".env")
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is missing from backend/.env")
        self._client = Groq(api_key=api_key, timeout=90.0)
        self.model = Config.MODEL

    def complete(self, messages: list[dict], tools: list[dict] | None) -> ModelTurn:
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            response = self._client.chat.completions.create(**kwargs)
        except AuthenticationError as exc:
            raise RuntimeError(
                "The Groq API key was rejected. Check GROQ_API_KEY in backend/.env."
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise RuntimeError("Could not reach Groq.") from exc
        except RateLimitError as exc:
            raise RuntimeError("Groq rate limit was reached. Wait a moment and try again.") from exc
        message = response.choices[0].message
        tool_calls = []
        for call in message.tool_calls or []:
            raw = call.function.arguments or "{}"
            if not isinstance(raw, str):
                raw = json.dumps(raw)
            tool_calls.append(
                ToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=_parse_arguments(raw),
                    raw_arguments=raw,
                )
            )
        content = message.content
        if not content and not tool_calls:
            content = getattr(message, "reasoning", None)
        return ModelTurn(content=content, tool_calls=tool_calls)


def _parse_arguments(raw: str) -> dict | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _visible_text(content: str | None, images: list[str], files: list[str]) -> str:
    text = (content or "").strip()
    if text:
        return text
    if images:
        return "Here is the chart."
    if files:
        return "Here is the report."
    return "I don't have a reply for that."

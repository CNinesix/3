"""Agent wrappers for Claude (Anthropic) and Kimi (Moonshot AI).

Each agent keeps its own conversation history. The orchestrator passes
plain-text messages between them, so neither provider's wire format leaks
into the other's context.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic
from openai import OpenAI

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-k2-0905-preview")
# Moonshot's international endpoint; use https://api.moonshot.cn/v1 for the CN platform.
KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.ai/v1")


@dataclass
class Turn:
    agent: str
    role: str
    content: str


@dataclass
class BaseAgent:
    name: str
    system: str
    history: list[dict] = field(default_factory=list)

    def send(self, message: str) -> str:
        raise NotImplementedError

    def reset(self) -> None:
        self.history.clear()


class ClaudeAgent(BaseAgent):
    """Claude via the official Anthropic SDK, with adaptive thinking."""

    def __init__(self, name: str = "Claude", system: str = "", model: str = CLAUDE_MODEL):
        super().__init__(name=name, system=system)
        self.model = model
        self.client = anthropic.Anthropic()

    def send(self, message: str) -> str:
        self.history.append({"role": "user", "content": message})
        with self.client.messages.stream(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=self.system,
            messages=self.history,
        ) as stream:
            response = stream.get_final_message()

        if response.stop_reason == "refusal":
            text = "[Claude declined to answer this request.]"
        else:
            text = "".join(b.text for b in response.content if b.type == "text")
        # Keep the full content (incl. thinking blocks) so multi-turn replay works.
        self.history.append({"role": "assistant", "content": response.content})
        return text


class KimiAgent(BaseAgent):
    """Kimi via Moonshot AI's OpenAI-compatible chat completions API."""

    def __init__(self, name: str = "Kimi", system: str = "", model: str = KIMI_MODEL):
        super().__init__(name=name, system=system)
        self.model = model
        api_key = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
        if not api_key:
            raise RuntimeError("Set MOONSHOT_API_KEY (or KIMI_API_KEY) for the Kimi agent.")
        self.client = OpenAI(api_key=api_key, base_url=KIMI_BASE_URL)

    def send(self, message: str) -> str:
        self.history.append({"role": "user", "content": message})
        messages = [{"role": "system", "content": self.system}] if self.system else []
        messages += self.history
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.6,
        )
        text = completion.choices[0].message.content or ""
        self.history.append({"role": "assistant", "content": text})
        return text

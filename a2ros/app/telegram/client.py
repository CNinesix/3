"""Thin Telegram Bot API client built on `requests` (no async dependency)."""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import config

log = logging.getLogger("a2ros.telegram")

API_ROOT = "https://api.telegram.org"

# The command list registered with BotFather via setMyCommands.
COMMANDS = [
    ("start", "Start / connect the bot"),
    ("help", "Show all commands"),
    ("summary", "CEO summary (revenue, pipeline, hot deals)"),
    ("today", "Today's meetings & follow-ups"),
    ("leads", "New leads to contact"),
    ("hot", "Hot opportunities"),
    ("pipeline", "Pipeline value by stage"),
    ("followup", "Follow-ups due"),
    ("addlead", "Add a lead: /addlead Name, Zone, Scope, contact, value"),
    ("addnote", "Add note: /addnote Account: note text"),
    ("search", "Search an account: /search Name"),
    ("update", "Update stage: /update Account to proposal"),
    ("remind", "Set reminder: /remind call Account tomorrow 10am"),
    ("report", "Send today's full morning report"),
]


class TelegramClient:
    def __init__(self, token: str | None = None, timeout: int | None = None):
        self.token = (token or config.TELEGRAM_BOT_TOKEN).strip()
        self.timeout = timeout or config.TELEGRAM_POLL_TIMEOUT
        self.session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _url(self, method: str) -> str:
        return f"{API_ROOT}/bot{self.token}/{method}"

    def _call(self, method: str, payload: dict | None = None, timeout: int | None = None) -> dict:
        resp = self.session.post(
            self._url(method), json=payload or {}, timeout=timeout or 30
        )
        data = resp.json()
        if not data.get("ok"):
            log.warning("Telegram API %s failed: %s", method, data)
        return data

    # --- core methods ---
    def get_me(self) -> dict:
        return self._call("getMe", timeout=15)

    def get_updates(self, offset: int | None = None) -> list[dict]:
        payload = {"timeout": self.timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        data = self._call("getUpdates", payload, timeout=self.timeout + 15)
        return data.get("result", []) if data.get("ok") else []

    def send_message(self, chat_id: int | str, text: str, parse_mode: str | None = "HTML") -> dict:
        # Telegram caps messages at 4096 chars.
        text = text[:4090]
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._call("sendMessage", payload, timeout=20)

    def set_my_commands(self) -> dict:
        commands = [{"command": c, "description": d} for c, d in COMMANDS]
        return self._call("setMyCommands", {"commands": commands}, timeout=15)

    def get_file_path(self, file_id: str) -> str | None:
        data = self._call("getFile", {"file_id": file_id}, timeout=20)
        if data.get("ok"):
            return data["result"].get("file_path")
        return None

    def download_file(self, file_path: str) -> bytes | None:
        url = f"{API_ROOT}/file/bot{self.token}/{file_path}"
        try:
            resp = self.session.get(url, timeout=60)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:  # pragma: no cover - network
            log.warning("Failed to download Telegram file: %s", exc)
            return None

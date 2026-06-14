"""Telegram message dispatch: commands + natural language + voice notes."""
from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import SessionLocal
from app.models import TelegramLog, User
from app.services import crm, parsing
from app.services import settings as settings_svc
from app.telegram import formatting
from app.telegram.client import TelegramClient
from app.telegram.transcribe import transcribe
from config import config

log = logging.getLogger("a2ros.telegram.handlers")
TZ = ZoneInfo(config.TIMEZONE)


class Dispatcher:
    def __init__(self, client: TelegramClient | None = None):
        self.client = client or TelegramClient()

    # ------------------------------------------------------------------ #
    def handle_update(self, update: dict) -> None:
        message = update.get("message")
        if not message:
            return
        chat_id = message["chat"]["id"]
        sender = message.get("from", {})
        user_id = sender.get("id")
        username = sender.get("username") or sender.get("first_name") or ""

        session = SessionLocal()
        try:
            allowed_ids = settings_svc.allowed_telegram_ids(session)
            # If no whitelist is configured at all, deny everyone (secure default).
            is_allowed = bool(allowed_ids) and user_id in allowed_ids

            text = message.get("text", "") or message.get("caption", "")
            has_voice = "voice" in message or "audio" in message

            if not is_allowed:
                self._log(session, user_id, username, "denied", text, "Access denied", allowed=False)
                self.client.send_message(
                    chat_id,
                    "⛔️ Access denied. Your Telegram ID "
                    f"<code>{user_id}</code> is not whitelisted.\n"
                    "Ask the admin to add it under Dashboard → Telegram.",
                )
                return

            if has_voice:
                self._handle_voice(session, chat_id, user_id, username, message)
                return

            if not text:
                self.client.send_message(chat_id, "Send /help to see what I can do.")
                return

            response = self._route(session, user_id, text)
            self._log(session, user_id, username, _command_of(text), text, response[:400])
            self.client.send_message(chat_id, response)
        except Exception as exc:  # pragma: no cover - safety net
            log.exception("Error handling update")
            try:
                self.client.send_message(chat_id, f"⚠️ Error: {exc}")
            except Exception:
                pass
        finally:
            SessionLocal.remove()

    # ------------------------------------------------------------------ #
    def _route(self, session, user_id: int, text: str) -> str:
        raw = text.strip()
        low = raw.lower()
        cmd = _command_of(raw)
        arg = _arg_of(raw)

        # --- slash commands ---
        if cmd == "/start":
            return (
                "👋 <b>A2 Sales Assistant connected.</b>\n"
                "I help you run your Johor sales pipeline from your phone.\n\n"
                + formatting.HELP_TEXT
            )
        if cmd == "/help":
            return formatting.HELP_TEXT
        if cmd == "/summary":
            return formatting.summary_text(session)
        if cmd == "/today":
            return formatting.today_text(session)
        if cmd == "/leads":
            return formatting.leads_text(session)
        if cmd == "/hot":
            return formatting.hot_text(session)
        if cmd == "/pipeline":
            return formatting.pipeline_text(session)
        if cmd == "/followup":
            return formatting.followup_text(session)
        if cmd == "/report":
            return formatting.morning_report_text(session)
        if cmd == "/addlead":
            return self._do_addlead(session, user_id, arg or raw)
        if cmd == "/addnote":
            return self._do_addnote(session, user_id, arg)
        if cmd == "/search":
            return self._do_search(session, arg)
        if cmd == "/update":
            return self._do_update(session, user_id, arg)
        if cmd == "/remind":
            return self._do_remind(session, user_id, arg)

        # --- natural language (no slash) ---
        if low.startswith("new lead") or low.startswith("lead:") or low.startswith("add lead"):
            return self._do_addlead(session, user_id, raw)
        if low.startswith("meeting note") or low.startswith("note "):
            return self._do_addnote(session, user_id, raw)
        if low.startswith("update ") or low.startswith("move "):
            return self._do_update(session, user_id, raw)
        if low.startswith("remind"):
            return self._do_remind(session, user_id, raw)
        if low.startswith("search "):
            return self._do_search(session, raw[len("search "):])

        return (
            "🤔 I didn't recognise that. Try /help.\n"
            "Tip: “New lead: ABC Factory, Johor, CCTV upgrade, contact Mr Tan, value RM80k”."
        )

    # ------------------------------------------------------------------ #
    def _user_pk(self, session, telegram_user_id: int) -> int | None:
        user = session.scalars(
            select(User).where(User.telegram_user_id == telegram_user_id)
        ).first()
        return user.id if user else None

    def _do_addlead(self, session, user_id: int, text: str) -> str:
        parsed = parsing.parse_lead(text)
        if not parsed["name"]:
            return "Please include a company name. e.g. /addlead ABC Factory, Johor, CCTV, value RM80k"
        account, opp = crm.create_lead(
            session,
            name=parsed["name"],
            title=parsed["title"],
            zone=parsed["zone"],
            contact_name=parsed["contact_name"],
            contact_phone=parsed["contact_phone"],
            value=parsed["value"],
            owner_id=self._user_pk(session, user_id),
            created_by=f"tg:{user_id}",
            source="telegram",
        )
        val = f"\n💵 Value: RM{parsed['value']:,.0f}" if parsed["value"] else ""
        return (
            f"✅ Lead saved.\n<b>{account.name}</b>\n"
            f"📋 {opp.title}\n📍 {account.zone or '-'}"
            f"\n👤 {account.contact_name or '-'} {account.contact_phone}".rstrip()
            + val
        )

    def _do_addnote(self, session, user_id: int, text: str) -> str:
        name, note = parsing.parse_note(text)
        if not name or not note:
            return "Format: /addnote ABC Factory: they need 64 CCTV, budget RM120k, decide July"
        act = crm.add_note(
            session,
            account_name=name,
            note=note,
            type="meeting_note",
            created_by=f"tg:{user_id}",
            source="telegram",
        )
        if act is None:
            return f"❓ I couldn't find an account matching “{name}”. Add it first with /addlead."
        return f"📝 Note saved to <b>{name}</b>:\n“{note[:300]}”"

    def _do_search(self, session, query: str) -> str:
        query = (query or "").strip()
        if not query:
            return "Usage: /search ABC Factory"
        account = crm.find_account(session, query)
        if account is None:
            matches = crm.search_accounts(session, query)
            if not matches:
                return f"❓ No account found for “{query}”."
            lines = ["Did you mean:"] + [f"• {a.name}" for a in matches]
            return "\n".join(lines)
        return formatting.account_detail_text(session, account)

    def _do_update(self, session, user_id: int, text: str) -> str:
        name, stage = parsing.parse_update(text)
        if not name:
            return "Usage: /update ABC Factory to proposal"
        if not stage:
            return "I couldn't tell the stage. Use: New, Qualified, Meeting, Proposal, Negotiation, Won, Lost."
        opp = crm.update_stage(
            session,
            account_name=name,
            stage=stage,
            created_by=f"tg:{user_id}",
            source="telegram",
        )
        if opp is None:
            return f"❓ No account found for “{name}”."
        return f"✅ <b>{opp.account.name}</b> → stage <b>{stage}</b>."

    def _do_remind(self, session, user_id: int, text: str) -> str:
        clean, due = parsing.parse_reminder(text)
        # try to match an account name mentioned inside the reminder text
        account = crm.find_account(session, clean)
        account_name = account.name if account else None
        reminder = crm.add_reminder(
            session,
            text=clean,
            due_at=due,
            user_id=self._user_pk(session, user_id),
            account_name=account_name,
        )
        local = due.astimezone(TZ) if due.tzinfo else due.replace(tzinfo=dt.timezone.utc).astimezone(TZ)
        return f"⏰ Reminder set for <b>{local:%a %d %b %H:%M}</b>:\n“{clean}”"

    # ------------------------------------------------------------------ #
    def _handle_voice(self, session, chat_id, user_id, username, message) -> None:
        media = message.get("voice") or message.get("audio") or {}
        file_id = media.get("file_id")
        self.client.send_message(chat_id, "🎤 Got your voice note, processing…")
        text = None
        if file_id:
            path = self.client.get_file_path(file_id)
            if path:
                audio = self.client.download_file(path)
                if audio:
                    text = transcribe(audio, filename=path.split("/")[-1])

        if not text:
            note = "Voice note received (transcription disabled or failed)."
            crm.log_activity(
                session, account=None, opportunity=None, type="voice_note",
                note=note, created_by=f"tg:{user_id}", source="telegram",
            )
            self._log(session, user_id, username, "voice", "", note)
            self.client.send_message(
                chat_id,
                "🎤 Saved as an unassigned voice note. "
                "Transcription is off — enable it in .env to auto-transcribe.",
            )
            return

        # Try to attach to an account if the transcript names one ("... ABC Factory: ...").
        name, note = parsing.parse_note("meeting note " + text)
        attached = None
        if name:
            attached = crm.find_account(session, name)
        if attached:
            crm.add_note(
                session, account_name=attached.name, note=note or text,
                type="meeting_note", created_by=f"tg:{user_id}", source="telegram",
            )
            reply = f"🎤📝 Transcribed & saved to <b>{attached.name}</b>:\n“{(note or text)[:400]}”"
        else:
            crm.log_activity(
                session, account=None, opportunity=None, type="voice_note",
                note=text, created_by=f"tg:{user_id}", source="telegram",
            )
            reply = (
                "🎤📝 Transcribed:\n"
                f"“{text[:400]}”\n\n"
                "Saved as an unassigned note. To attach it, send:\n"
                "<i>/addnote AccountName: " + text[:60] + "…</i>"
            )
        self._log(session, user_id, username, "voice", text[:200], reply[:300])
        self.client.send_message(chat_id, reply)

    # ------------------------------------------------------------------ #
    def _log(self, session, user_id, username, command, raw, summary, allowed=True) -> None:
        session.add(
            TelegramLog(
                telegram_user_id=user_id,
                username=username or "",
                command=command or "",
                raw_text=raw or "",
                response_summary=summary or "",
                allowed=allowed,
            )
        )
        session.commit()


def _command_of(text: str) -> str:
    text = text.strip()
    if not text.startswith("/"):
        return ""
    token = text.split()[0]
    return token.split("@")[0].lower()  # strip @botname


def _arg_of(text: str) -> str:
    text = text.strip()
    if not text.startswith("/"):
        return text
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""

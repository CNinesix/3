"""Optional voice-note transcription via an OpenAI-compatible audio endpoint.

Enabled only when TRANSCRIBE_API_BASE and TRANSCRIBE_API_KEY are configured.
When disabled, voice notes are still saved (as untranscribed) by the handler.
"""
from __future__ import annotations

import logging

import requests

from config import config

log = logging.getLogger("a2ros.transcribe")


def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> str | None:
    if not config.transcription_enabled():
        return None
    url = config.TRANSCRIBE_API_BASE.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {config.TRANSCRIBE_API_KEY}"}
    files = {"file": (filename, audio_bytes, "audio/ogg")}
    data = {"model": config.TRANSCRIBE_MODEL}
    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=120)
        resp.raise_for_status()
        payload = resp.json()
        return (payload.get("text") or "").strip() or None
    except requests.RequestException as exc:  # pragma: no cover - network
        log.warning("Transcription failed: %s", exc)
        return None
    except ValueError:  # pragma: no cover - bad json
        log.warning("Transcription returned non-JSON response")
        return None

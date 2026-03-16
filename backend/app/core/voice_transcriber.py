import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"

async def download_whatsapp_media(media_id: str) -> bytes:
    """
    Download media from WhatsApp via Meta API.
    Step 1: Get media URL   Step 2: Download the binary
    """
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:

        url_resp = await client.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}",
            headers=headers,
        )
        media_url = url_resp.json().get("url")
        if not media_url:
            raise ValueError(f"Could not get media URL for {media_id}")

        media_resp = await client.get(media_url, headers=headers)
        return media_resp.content

async def transcribe_voice(media_id: str) -> str:
    """
    Transcribe a WhatsApp voice note using OpenAI Whisper API.
    Supports Indian languages — Whisper auto-detects the language.

    Args:
        media_id: WhatsApp media ID from the incoming audio message

    Returns:
        Transcribed text string
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if not openai_key:
        logger.warning("OPENAI_API_KEY not set — returning placeholder")
        return "[Voice note received — transcription unavailable]"

    try:

        audio_bytes = await download_whatsapp_media(media_id)
        logger.info(f"Downloaded voice note: {len(audio_bytes)} bytes")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {openai_key}"},
                files={"file": ("voice.ogg", audio_bytes, "audio/ogg")},
                data={"model": "whisper-1"},
            )

            if resp.status_code == 200:
                text = resp.json().get("text", "")
                logger.info(f"Transcription: {text[:100]}...")
                return text
            else:
                logger.error(f"Whisper API error: {resp.status_code} {resp.text}")
                return "[Could not transcribe voice note]"

    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        return "[Voice note transcription failed]"

async def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """
    Transcribe raw audio bytes directly (for testing or non-WhatsApp sources).
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        return "[OPENAI_API_KEY not configured]"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {openai_key}"},
            files={"file": (filename, audio_bytes, "audio/ogg")},
            data={"model": "whisper-1"},
        )
        if resp.status_code == 200:
            return resp.json().get("text", "")
        return "[Transcription failed]"

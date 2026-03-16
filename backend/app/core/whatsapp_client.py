import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def _get_token() -> str:
    return os.getenv("WHATSAPP_ACCESS_TOKEN", "")

def _get_phone_id() -> str:
    return os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }

async def _send_request(payload: dict) -> dict:
    """Send a message via Meta Cloud API. Never raises — always returns dict."""
    if not _get_token():
        logger.warning("⚠️ WHATSAPP_ACCESS_TOKEN not set — cannot send message")
        return {"error": "no_token"}
    url = f"{GRAPH_API_BASE}/{_get_phone_id()}/messages"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=_headers())
            if resp.status_code != 200:
                logger.error(f"WhatsApp API error {resp.status_code}: {resp.text}")
            else:
                logger.info(f"✅ Message sent to {payload.get('to', '?')}")
            return resp.json()
    except Exception as e:
        logger.error(f"WhatsApp request failed: {e}")
        return {"error": str(e)}

class WhatsAppClient:
    """Send messages back to citizens via WhatsApp Business API."""

    @staticmethod
    async def send_text(phone: str, text: str) -> dict:
        """Send a plain text message."""
        return await _send_request({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        })

    @staticmethod
    async def send_buttons(phone: str, body: str, buttons: list[dict]) -> dict:
        """
        Send interactive quick-reply buttons (max 3 buttons).
        buttons: [{"id": "btn_1", "title": "Farmer"}, ...]
        """
        button_rows = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
            for b in buttons[:3]
        ]
        return await _send_request({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": button_rows},
            },
        })

    @staticmethod
    async def send_list(phone: str, body: str, button_text: str, items: list[dict]) -> dict:
        """
        Send a list/dropdown message (max 10 items).
        items: [{"id": "item_1", "title": "Bihar", "description": ""}, ...]
        """
        rows = [
            {
                "id": i.get("id", f"item_{idx}"),
                "title": i["title"][:24],
                "description": i.get("description", "")[:72],
            }
            for idx, i in enumerate(items[:10])
        ]
        return await _send_request({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "action": {
                    "button": button_text[:20],
                    "sections": [{"title": "Options", "rows": rows}],
                },
            },
        })

    @staticmethod
    async def send_document(phone: str, doc_url: str, filename: str, caption: str = "") -> dict:
        """Send a document (PDF, image, etc.)."""
        return await _send_request({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "document",
            "document": {
                "link": doc_url,
                "filename": filename,
                "caption": caption,
            },
        })

    @staticmethod
    async def send_link_button(phone: str, body: str, button_text: str, url: str) -> dict:
        """Send a message with a CTA URL button."""
        return await _send_request({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "body": {"text": body},
                "action": {
                    "name": "cta_url",
                    "parameters": {
                        "display_text": button_text[:20],
                        "url": url,
                    },
                },
            },
        })

    @staticmethod
    async def mark_read(message_id: str) -> None:
        """Mark a message as read (blue ticks). Silently ignores errors."""
        if not message_id or not _get_token():
            return
        try:
            url = f"{GRAPH_API_BASE}/{_get_phone_id()}/messages"
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(url, json={
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id,
                }, headers=_headers())
        except Exception as e:
            logger.debug(f"mark_read failed (non-critical): {e}")

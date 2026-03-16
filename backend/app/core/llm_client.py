import os
import logging
from typing import Optional
import httpx

log = logging.getLogger(__name__)

CLAUDE_API_KEY    = os.getenv("CLAUDE_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
CLAUDE_MODEL      = "claude-3-haiku-20240307"
OPENAI_MODEL      = "gpt-3.5-turbo"

async def _call_claude(system_prompt: str, user_message: str, max_tokens: int = 512) -> Optional[str]:
    """Call Claude API."""
    if not CLAUDE_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Claude API error: {e}")
        return None

async def _call_openai(system_prompt: str, user_message: str, max_tokens: int = 512) -> Optional[str]:
    """Call OpenAI GPT API."""
    if not OPENAI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": OPENAI_MODEL,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"OpenAI API error: {e}")
        return None

async def _llm(system_prompt: str, user_message: str, max_tokens: int = 512) -> Optional[str]:
    """Try Claude first, fall back to OpenAI."""
    result = await _call_claude(system_prompt, user_message, max_tokens)
    if result:
        return result
    return await _call_openai(system_prompt, user_message, max_tokens)

async def explain_scheme(scheme_name: str, benefits: str, user_profile: dict, language: str = "en") -> str:
    """
    Generate a friendly 2-3 sentence explanation of why this scheme suits the user.
    Falls back to a formatted rule-based string if LLM not available.
    """
    lang_instruction = "Respond in Hindi (Devanagari script)." if language == "hi" else "Respond in simple English (under 8th grade reading level)."

    system = f"""You are a helpful Indian government scheme assistant. 
{lang_instruction}
Keep responses concise, warm, and under 60 words. 
Do not use jargon. Focus on what the citizen gets and why they qualify."""

    user_msg = f"""Explain why {scheme_name} is a good match for this citizen.
Benefits: {benefits}
Citizen profile: {user_profile}
Write 2 short sentences: (1) what they get, (2) why they specifically qualify."""

    result = await _llm(system, user_msg, max_tokens=150)
    if result:
        return result

    return f"You qualify for *{scheme_name}*! This scheme offers: {benefits}."

async def generate_apply_guide(scheme_name: str, apply_steps: list, documents: list, language: str = "en") -> str:
    """
    Generate a personalised step-by-step apply guide in the user's language.
    Falls back to formatted static steps if LLM not available.
    """
    lang_instruction = "Respond in Hindi (Devanagari script)." if language == "hi" else "Respond in simple English."

    system = f"""You are a helpful Indian government scheme assistant.
{lang_instruction}
Format the apply guide as a numbered WhatsApp message with emojis.
Use *bold* for important terms. Keep it under 200 words."""

    steps_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(apply_steps)])
    docs_text  = ", ".join(documents) if documents else "Aadhaar, Bank Passbook"

    user_msg = f"""Create a WhatsApp-friendly apply guide for {scheme_name}.
Steps: {steps_text}
Documents needed: {docs_text}
Format as numbered steps with a documents section."""

    result = await _llm(system, user_msg, max_tokens=300)
    if result:
        return result

    lines = [f"📋 *How to apply for {scheme_name}*\n"]
    for i, step in enumerate(apply_steps, 1):
        lines.append(f"{i}. {step}")
    lines.append(f"\n📄 *Documents needed:* {docs_text}")
    return "\n".join(lines)

async def generate_followup_response(question: str, user_profile: dict, language: str = "en") -> str:
    """
    Handle free-text follow-up questions from the citizen using LLM.
    Falls back to a generic response if LLM not available.
    """
    lang_instruction = "Respond in Hindi (Devanagari script)." if language == "hi" else "Respond in simple English."

    system = f"""You are a helpful Indian government scheme advisor.
{lang_instruction}
Answer questions about government schemes concisely (under 80 words).
If you don't know the exact answer, direct them to the official portal."""

    user_msg = f"Citizen's question: {question}\nCitizen profile context: {user_profile}"

    result = await _llm(system, user_msg, max_tokens=200)
    if result:
        return result

    return ("I'm not sure about that specific detail. "
            "Please visit myscheme.gov.in or call the helpline 1800-NO-HELPLINE for accurate information.")

async def detect_language(text: str) -> str:
    """
    Detect language from first message. Returns 'hi' for Hindi, 'en' for English.
    Uses simple heuristic first, LLM as fallback for edge cases.
    """

    devanagari_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    if devanagari_chars > 0:
        return "hi"

    hindi_keywords = ["namaste", "namaskar", "haan", "nahi", "kya", "mera", "meri",
                      "hai", "hoon", "main", "aap", "kisan", "gaon", "ghar"]
    text_lower = text.lower()
    if any(kw in text_lower for kw in hindi_keywords):
        return "hi"

    return "en"

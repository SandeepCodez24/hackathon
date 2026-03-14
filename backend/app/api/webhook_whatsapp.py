"""
WhatsApp Webhook — Meta Cloud API integration point.
Handles the full conversation flow:
  greeting → questions → results → apply guide → HELP

GET  /webhook/whatsapp — Meta verification handshake
POST /webhook/whatsapp — Incoming message handler
"""

import os
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, Response, HTTPException, Query

from app.core.session_manager import SessionManager
from app.core.eligibility_engine import EligibilityEngine
from app.core.adaptive_engine import AdaptiveQuestionEngine, QUESTIONS
from app.core.whatsapp_client import WhatsAppClient
from app.core.whatsapp_formatter import (
    format_welcome_message,
    format_question_buttons,
    format_question_list,
    format_results_message,
    format_apply_guide,
    format_help_message,
    should_use_list,
)
from app.core.voice_transcriber import transcribe_voice
from app.core.language_handler import detect_language_from_text, get_welcome_message
from app.core.fraud_detector import check_fraud, get_fraud_flag_message
from app.core.llm_client import detect_language, generate_apply_guide
from app.db.scheme_orm import get_all_schemes, get_scheme_by_id
from app.models.session import SessionState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])


# ============================================================
# Webhook Verification (GET)
# ============================================================

@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification handshake.
    Meta sends: GET /webhook/whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
    We must return the challenge if the token matches.
    """
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "govscheme_verify_2025")

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("✅ Webhook verified successfully")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning(f"❌ Webhook verification failed: mode={hub_mode}, token={hub_verify_token}")
    raise HTTPException(status_code=403, detail="Verification failed")


# ============================================================
# Incoming Message Handler (POST)
# ============================================================

@router.post("/webhook/whatsapp")
async def handle_incoming(request: Request):
    """
    Handle incoming WhatsApp messages.
    Parses message type (text, button_reply, list_reply, audio) and routes to handler.
    """
    body = await request.json()

    # Verify webhook signature (optional but recommended)
    # _verify_signature(request, body)

    # Extract message data from the Meta wrapper
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            # Status update (delivered, read, etc.) — ignore
            return {"status": "ok"}

        msg = messages[0]
        phone = msg["from"]  # e.g. "919876543210"
        msg_type = msg["type"]
        msg_id = msg.get("id", "")

        logger.info(f"📩 Incoming [{msg_type}] from {phone}")

        # Mark as read (blue ticks)
        if msg_id:
            await WhatsAppClient.mark_read(msg_id)

        # Extract text based on message type
        text = _extract_text(msg, msg_type)

        # Route to conversation handler
        await handle_conversation(phone, text, msg_type, msg)

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)

    return {"status": "ok"}


def _extract_text(msg: dict, msg_type: str) -> str:
    """Extract user's text/selection from different message types."""
    if msg_type == "text":
        return msg.get("text", {}).get("body", "").strip()

    elif msg_type == "interactive":
        interactive = msg.get("interactive", {})
        itype = interactive.get("type", "")

        if itype == "button_reply":
            return interactive.get("button_reply", {}).get("id", "")
        elif itype == "list_reply":
            return interactive.get("list_reply", {}).get("id", "")

    elif msg_type == "audio":
        return "__VOICE__:" + msg.get("audio", {}).get("id", "")

    return msg.get("text", {}).get("body", "")


# ============================================================
# Conversation Orchestrator
# ============================================================

async def handle_conversation(phone: str, text: str, msg_type: str, raw_msg: dict):
    """
    Full conversation state machine:
    GREETING → QUESTIONING → RESULTS → APPLY_GUIDE

    Commands:
    - HI/HELLO/START → Restart session
    - HELP → Show help
    - 1,2,3... → Show apply guide for that scheme
    - BACK → Return to results
    - Button/list reply → Process answer
    - Voice note → Transcribe + process
    """
    session_id = f"wa_{phone}"
    session = await SessionManager.get_or_create(session_id, channel="whatsapp")
    text_upper = text.upper().strip()

    # ---- Handle voice notes ----
    if text.startswith("__VOICE__:"):
        media_id = text.replace("__VOICE__:", "")
        transcribed = await transcribe_voice(media_id)
        logger.info(f"🎤 Voice transcription: {transcribed}")
        await WhatsAppClient.send_text(
            phone, f"🎤 _I heard:_ \"{transcribed}\"\n\n_Processing..._"
        )
        text = transcribed
        text_upper = text.upper().strip()

    # ---- HELP command ----
    if text_upper in ("HELP", "MENU", "?"):
        session.state = SessionState.GREETING
        await SessionManager.save(session)
        await WhatsAppClient.send_text(phone, format_help_message(session.language))
        # Send restart button
        await WhatsAppClient.send_buttons(phone, "Would you like to start over?", [
            {"id": "cmd_start", "title": "Start Over"},
        ])
        return

    # ---- GREETING state: Start/restart ----
    if text_upper in ("HI", "HELLO", "START", "NAMASTE", "हाँ", "शुरू", "HAI", "HEY") or \
       text_upper == "CMD_START" or session.state == SessionState.GREETING:

        # Detect language from first message
        detected_lang = detect_language_from_text(text)
        if detected_lang == "en":
            detected_lang = await detect_language(text)  # LLM fallback for romanised Hindi

        # Reset session for fresh start
        await SessionManager.delete(session_id)
        session = await SessionManager.get_or_create(session_id, channel="whatsapp")
        session.language = detected_lang
        session.state = SessionState.QUESTIONING
        await SessionManager.save(session)

        # Send language-aware welcome
        welcome = get_welcome_message(detected_lang)
        await WhatsAppClient.send_text(phone, welcome)

        # Send first question using info gain
        all_schemes = await get_all_schemes()
        candidate_schemes = [s for s in all_schemes if s.id in session.candidates]
        first_q = AdaptiveQuestionEngine.select_next_question(session, candidate_schemes)

        if first_q:
            await _send_question(phone, first_q, session.language)
        return

    # ---- RESULTS state: User selects a scheme number ----
    if session.state == SessionState.RESULTS:
        if text_upper == "BACK":
            # Re-show results
            results_msg = format_results_message(session.recommendations, session.language)
            await WhatsAppClient.send_text(phone, results_msg)
            return

        # Check if user typed a scheme number (1, 2, 3...)
        try:
            idx = int(text.strip()) - 1
            if 0 <= idx < len(session.recommendations):
                rec = session.recommendations[idx]
                scheme = await get_scheme_by_id(rec.scheme_id)
                if scheme:
                    session.state = SessionState.APPLY_GUIDE
                    await SessionManager.save(session)

                    # Use LLM for personalised guide (falls back to static)
                    guide = await generate_apply_guide(
                        scheme.name,
                        scheme.apply_steps or [],
                        scheme.documents or [],
                        session.language,
                    )
                    await WhatsAppClient.send_text(phone, guide)

                    # Send link button if portal URL exists
                    if scheme.portal_url:
                        await WhatsAppClient.send_link_button(
                            phone,
                            f"Apply for {scheme.name}",
                            "Apply Now 🔗",
                            scheme.portal_url,
                        )
                    return
        except (ValueError, IndexError):
            pass

        # Unknown input in results state
        await WhatsAppClient.send_text(
            phone,
            "📝 Reply with a *number* (1, 2, 3...) to see apply guide.\nOr *HELP* to restart."
        )
        return

    # ---- APPLY_GUIDE state ----
    if session.state == SessionState.APPLY_GUIDE:
        if text_upper == "BACK":
            session.state = SessionState.RESULTS
            await SessionManager.save(session)
            results_msg = format_results_message(session.recommendations, session.language)
            await WhatsAppClient.send_text(phone, results_msg)
            return

        # Any other input → show help
        await WhatsAppClient.send_text(
            phone, "Reply *BACK* for results or *HELP* to restart."
        )
        return

    # ---- QUESTIONING state: Process answers ----
    if session.state == SessionState.QUESTIONING:
        await _process_answer(phone, text, session)
        return

    # Fallback
    await WhatsAppClient.send_text(phone, "Say *Hi* to start! 🙏")


async def _process_answer(phone: str, text: str, session):
    """
    Process a question answer:
    1. Map button/list reply ID to question + answer value
    2. Update profile
    3. Prune candidates
    4. Select next question or show results
    """
    all_schemes = await get_all_schemes()

    # Parse the reply — could be a button ID like "q_occupation_2"
    question, answer_value = _parse_reply(text)

    if question is None:
        # Free text — try to match to current question
        if session.current_question:
            question = AdaptiveQuestionEngine.get_question_by_id(session.current_question)
            answer_value = text

        if question is None:
            await WhatsAppClient.send_text(
                phone, "🤔 Please use the buttons to answer, or type *HELP* to restart."
            )
            return

    # Apply answer to profile
    session.profile = AdaptiveQuestionEngine.apply_answer_to_profile(
        session.profile, question, str(answer_value)
    )
    session.questions_asked.append(question["id"])
    session.question_count += 1

    # Prune candidates
    session.candidates = EligibilityEngine.prune_candidates(
        session.profile, all_schemes, session.candidates
    )

    # Check if we should stop
    candidate_schemes = [s for s in all_schemes if s.id in session.candidates]

    if session.is_complete() or len(candidate_schemes) <= 5:
        # ── Fraud check (Phase 5) ─────────────────────────────────────────────
        is_suspicious, risk_score, rules_triggered = check_fraud(session.profile)
        if is_suspicious:
            logger.warning(f"🚩 Fraud flag for {phone}: score={risk_score}, rules={rules_triggered}")
            await WhatsAppClient.send_text(phone, get_fraud_flag_message(session.language))

        # Generate recommendations
        session.recommendations = EligibilityEngine.score_and_rank(
            session.profile, candidate_schemes, min_confidence=20.0
        )
        session.state = SessionState.RESULTS
        await SessionManager.save(session)

        results_msg = format_results_message(session.recommendations, session.language)
        await WhatsAppClient.send_text(phone, results_msg)
        return

    # Select next question via info gain
    next_q = AdaptiveQuestionEngine.select_next_question(session, candidate_schemes)

    if next_q is None:
        # No more useful questions — show results
        session.recommendations = EligibilityEngine.score_and_rank(
            session.profile, candidate_schemes, min_confidence=20.0
        )
        session.state = SessionState.RESULTS
        await SessionManager.save(session)

        results_msg = format_results_message(session.recommendations, session.language)
        await WhatsAppClient.send_text(phone, results_msg)
        return

    session.current_question = next_q["id"]
    await SessionManager.save(session)

    # Send progress indicator
    progress = f"_{session.question_count}/{session.max_questions} questions answered • {len(session.candidates)} schemes left_"
    await WhatsAppClient.send_text(phone, progress)

    # Send next question
    await _send_question(phone, next_q, session.language)


def _parse_reply(text: str) -> tuple:
    """
    Parse a button/list reply ID into (question_dict, answer_value).
    IDs look like: "q_occupation_2" → question q_occupation, option index 2
    """
    if not text:
        return None, None

    parts = text.rsplit("_", 1)
    if len(parts) == 2:
        q_id_candidate = parts[0]
        try:
            option_idx = int(parts[1])
        except ValueError:
            return None, None

        question = AdaptiveQuestionEngine.get_question_by_id(q_id_candidate)
        if question:
            options = question.get("options", [])
            if 0 <= option_idx < len(options):
                opt = options[option_idx]
                return question, opt.get("value", opt.get("label", ""))

    # Try matching without index — maybe it's a full question ID
    question = AdaptiveQuestionEngine.get_question_by_id(text)
    if question:
        return question, None

    return None, None


async def _send_question(phone: str, question: dict, language: str = "en"):
    """Send a question as buttons or list based on option count."""
    if should_use_list(question):
        fmt = format_question_list(question, language)
        await WhatsAppClient.send_list(
            phone, fmt["body"], fmt["button_text"], fmt["items"]
        )
    else:
        fmt = format_question_buttons(question, language)
        buttons = fmt["buttons"][:3]  # WhatsApp max 3 buttons
        await WhatsAppClient.send_buttons(phone, fmt["body"], buttons)


# ============================================================
# Signature Verification (for production)
# ============================================================

def _verify_signature(request: Request, body: bytes) -> bool:
    """
    Verify Meta webhook signature to prevent replay attacks.
    """
    app_secret = os.getenv("META_APP_SECRET", "")
    if not app_secret:
        return True  # Skip in development

    signature = request.headers.get("x-hub-signature-256", "")
    if not signature.startswith("sha256="):
        return False

    expected_hash = hmac.new(
        app_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature[7:], expected_hash)

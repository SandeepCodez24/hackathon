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

@router.post("/webhook/whatsapp")
async def handle_incoming(request: Request):
    """
    Handle incoming WhatsApp messages.
    Parses message type (text, button_reply, list_reply, audio) and routes to handler.
    """
    body = await request.json()

    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:

            return {"status": "ok"}

        msg = messages[0]
        phone = msg["from"]
        msg_type = msg["type"]
        msg_id = msg.get("id", "")

        logger.info(f"📩 Incoming [{msg_type}] from {phone}")

        if msg_id:
            await WhatsAppClient.mark_read(msg_id)

        text = _extract_text(msg, msg_type)

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

    if text.startswith("__VOICE__:"):
        media_id = text.replace("__VOICE__:", "")
        transcribed = await transcribe_voice(media_id)
        logger.info(f"🎤 Voice transcription: {transcribed}")
        await WhatsAppClient.send_text(
            phone, f"🎤 _I heard:_ \"{transcribed}\"\n\n_Processing..._"
        )
        text = transcribed
        text_upper = text.upper().strip()

    if text_upper in ("HELP", "MENU", "?"):
        session.state = SessionState.GREETING
        await SessionManager.save(session)
        await WhatsAppClient.send_text(phone, format_help_message(session.language))

        await WhatsAppClient.send_buttons(phone, "Would you like to start over?", [
            {"id": "cmd_start", "title": "Start Over"},
        ])
        return

    if text_upper in ("HI", "HELLO", "START", "NAMASTE", "हाँ", "शुरू", "HAI", "HEY") or \
       text_upper == "CMD_START" or session.state == SessionState.GREETING:

        detected_lang = detect_language_from_text(text)
        if detected_lang == "en":
            detected_lang = await detect_language(text)

        await SessionManager.delete(session_id)
        session = await SessionManager.get_or_create(session_id, channel="whatsapp")
        session.language = detected_lang
        session.state = SessionState.QUESTIONING
        await SessionManager.save(session)

        welcome = get_welcome_message(detected_lang)
        await WhatsAppClient.send_text(phone, welcome)

        all_schemes = await get_all_schemes()
        candidate_schemes = [s for s in all_schemes if s.id in session.candidates]
        first_q = AdaptiveQuestionEngine.select_next_question(session, candidate_schemes)

        if first_q:
            await _send_question(phone, first_q, session.language)
        return

    if session.state == SessionState.RESULTS:
        if text_upper == "BACK":

            results_msg = format_results_message(session.recommendations, session.language)
            await WhatsAppClient.send_text(phone, results_msg)
            return

        try:
            idx = int(text.strip()) - 1
            if 0 <= idx < len(session.recommendations):
                rec = session.recommendations[idx]
                scheme = await get_scheme_by_id(rec.scheme_id)
                if scheme:
                    session.state = SessionState.APPLY_GUIDE
                    await SessionManager.save(session)

                    guide = await generate_apply_guide(
                        scheme.name,
                        scheme.apply_steps or [],
                        scheme.documents or [],
                        session.language,
                    )
                    await WhatsAppClient.send_text(phone, guide)

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

        await WhatsAppClient.send_text(
            phone,
            "📝 Reply with a *number* (1, 2, 3...) to see apply guide.\nOr *HELP* to restart."
        )
        return

    if session.state == SessionState.APPLY_GUIDE:
        if text_upper == "BACK":
            session.state = SessionState.RESULTS
            await SessionManager.save(session)
            results_msg = format_results_message(session.recommendations, session.language)
            await WhatsAppClient.send_text(phone, results_msg)
            return

        await WhatsAppClient.send_text(
            phone, "Reply *BACK* for results or *HELP* to restart."
        )
        return

    if session.state == SessionState.QUESTIONING:
        await _process_answer(phone, text, session)
        return

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

    question, answer_value = _parse_reply(text)

    if question is None:

        if session.current_question:
            question = AdaptiveQuestionEngine.get_question_by_id(session.current_question)
            answer_value = text

        if question is None:
            await WhatsAppClient.send_text(
                phone, "🤔 Please use the buttons to answer, or type *HELP* to restart."
            )
            return

    session.profile = AdaptiveQuestionEngine.apply_answer_to_profile(
        session.profile, question, str(answer_value)
    )
    session.questions_asked.append(question["id"])
    session.question_count += 1

    session.candidates = EligibilityEngine.prune_candidates(
        session.profile, all_schemes, session.candidates
    )

    candidate_schemes = [s for s in all_schemes if s.id in session.candidates]

    if session.is_complete() or len(candidate_schemes) <= 5:

        is_suspicious, risk_score, rules_triggered = check_fraud(session.profile)
        if is_suspicious:
            logger.warning(f"🚩 Fraud flag for {phone}: score={risk_score}, rules={rules_triggered}")
            await WhatsAppClient.send_text(phone, get_fraud_flag_message(session.language))

        session.recommendations = EligibilityEngine.score_and_rank(
            session.profile, candidate_schemes, min_confidence=20.0
        )
        session.state = SessionState.RESULTS
        await SessionManager.save(session)

        results_msg = format_results_message(session.recommendations, session.language)
        await WhatsAppClient.send_text(phone, results_msg)
        return

    next_q = AdaptiveQuestionEngine.select_next_question(session, candidate_schemes)

    if next_q is None:

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

    progress = f"_{session.question_count}/{session.max_questions} questions answered • {len(session.candidates)} schemes left_"
    await WhatsAppClient.send_text(phone, progress)

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
        buttons = fmt["buttons"][:3]
        await WhatsAppClient.send_buttons(phone, fmt["body"], buttons)

def _verify_signature(request: Request, body: bytes) -> bool:
    """
    Verify Meta webhook signature to prevent replay attacks.
    """
    app_secret = os.getenv("META_APP_SECRET", "")
    if not app_secret:
        return True

    signature = request.headers.get("x-hub-signature-256", "")
    if not signature.startswith("sha256="):
        return False

    expected_hash = hmac.new(
        app_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature[7:], expected_hash)

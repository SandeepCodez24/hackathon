from typing import Optional
from app.models.session import Session, SchemeRecommendation

def format_welcome_message(language: str = "en") -> str:
    """Welcome message sent on first 'Hi'."""
    if language == "hi":
        return (
            "🙏 *नमस्ते! GovScheme Assistant में स्वागत है*\n\n"
            "मैं आपको सरकारी योजनाओं के बारे में बताऊँगा जिनके लिए आप पात्र हैं।\n\n"
            "बस कुछ सवालों के जवाब दें — 3 मिनट से कम समय लगेगा! 🕐\n\n"
            "_आप कभी भी *HELP* लिखकर दोबारा शुरू कर सकते हैं_"
        )
    return (
        "🙏 *Welcome to GovScheme Assistant!*\n\n"
        "I'll help you discover government schemes you are eligible for.\n\n"
        "Just answer a few quick questions — it takes less than 3 minutes! 🕐\n\n"
        "_Type *HELP* anytime to restart_"
    )

def format_question_buttons(question: dict, language: str = "en") -> dict:
    """
    Format a question as WhatsApp interactive buttons.
    Returns: {"body": str, "buttons": [{"id": ..., "title": ...}]}
    """
    text_key = "text_hi" if language == "hi" and "text_hi" in question else "text"
    body = f"❓ *{question[text_key]}*"

    options = question.get("options", [])
    buttons = []

    for i, opt in enumerate(options):
        label = opt.get(f"label_hi", opt["label"]) if language == "hi" else opt["label"]
        buttons.append({
            "id": f"{question['id']}_{i}",
            "title": label[:20],
            "value": opt.get("value", opt["label"]),
        })

    return {"body": body, "buttons": buttons}

def format_question_list(question: dict, language: str = "en") -> dict:
    """
    Format a question as a WhatsApp list message (for >3 options).
    Returns: {"body": str, "button_text": str, "items": [...]}
    """
    text_key = "text_hi" if language == "hi" and "text_hi" in question else "text"
    body = f"❓ *{question[text_key]}*"

    options = question.get("options", [])
    items = []

    for i, opt in enumerate(options):
        label = opt.get(f"label_hi", opt["label"]) if language == "hi" else opt["label"]
        items.append({
            "id": f"{question['id']}_{i}",
            "title": label[:24],
            "description": "",
            "value": opt.get("value", opt["label"]),
        })

    return {
        "body": body,
        "button_text": "Select" if language == "en" else "चुनें",
        "items": items,
    }

def should_use_list(question: dict) -> bool:
    """Check if this question needs a list (>3 options) or buttons (≤3)."""
    return len(question.get("options", [])) > 3

def format_results_message(
    recommendations: list[SchemeRecommendation],
    language: str = "en",
) -> str:
    """
    Format scheme recommendations as a WhatsApp results message.
    Matches the format from Section 4.1 of the project doc.
    """
    if not recommendations:
        if language == "hi":
            return "😔 क्षमा करें, आपकी प्रोफ़ाइल से मेल खाने वाली कोई योजना नहीं मिली।\n\n*HELP* लिखकर दोबारा शुरू करें।"
        return "😔 Sorry, no matching schemes found for your profile.\n\nType *HELP* to restart."

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    count = min(len(recommendations), 8)

    if language == "hi":
        header = f"✅ आपकी प्रोफ़ाइल के अनुसार, आप *{count} योजनाओं* के लिए पात्र हैं:\n\n"
    else:
        header = f"✅ Based on your profile, you qualify for *{count} schemes:*\n\n"

    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    lines = []
    for i, rec in enumerate(recommendations[:count]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(
            f"{medal} *{rec.scheme_name}* — {rec.confidence:.0f}% match\n"
            f"   {rec.benefit[:80]}\n"
            f"   👉 {rec.portal_url}" if rec.portal_url else
            f"{medal} *{rec.scheme_name}* — {rec.confidence:.0f}% match\n"
            f"   {rec.benefit[:80]}"
        )

    body = "\n\n".join(lines)

    if language == "hi":
        footer = (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "योजना के बारे में विस्तार से जानने के लिए *1, 2, 3...* लिखें 📋\n"
            "दोबारा शुरू करने के लिए *HELP* लिखें"
        )
    else:
        footer = (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Reply *1, 2, 3...* for step-by-step apply guide 📋\n"
            "Reply *HELP* anytime to restart"
        )

    return header + body + footer

def format_apply_guide(scheme_data: dict, language: str = "en") -> str:
    """
    Format the step-by-step apply guide for a specific scheme.
    """
    name = scheme_data.get("name", "Scheme")
    steps = scheme_data.get("application_steps", [])
    docs = scheme_data.get("eligibility", {}).get("documents_required", [])
    portal = scheme_data.get("portal_url", "")

    lines = [f"📋 *How to Apply: {name}*\n"]

    if steps:
        lines.append("*Steps:*")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")

    if docs:
        lines.append("\n*Documents Required:*")
        for doc in docs:
            lines.append(f"📄 {doc}")

    if portal:
        lines.append(f"\n🔗 *Apply here:* {portal}")

    lines.append("\n_Reply *BACK* for results or *HELP* to restart_")

    return "\n".join(lines)

def format_help_message(language: str = "en") -> str:
    """HELP command response."""
    if language == "hi":
        return (
            "ℹ️ *सहायता*\n\n"
            "• *Hi* — नई शुरुआत\n"
            "• *HELP* — यह संदेश\n"
            "• सवालों के बटन दबाएं जवाब देने के लिए\n"
            "• वॉइस नोट भेजें अगर टाइप नहीं कर सकते\n\n"
            "_क्या आप दोबारा शुरू करना चाहते हैं?_"
        )
    return (
        "ℹ️ *Help*\n\n"
        "• *Hi* — Start fresh\n"
        "• *HELP* — Show this message\n"
        "• Tap buttons to answer questions\n"
        "• Send a voice note if you can't type\n\n"
        "_Would you like to start over?_"
    )

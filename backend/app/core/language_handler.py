"""
Language Handler — Phase 4
Bhashini API integration for 10+ Indian languages.
Translates scheme content and bot responses to the user's language.
Falls back gracefully to English if Bhashini is unavailable.
"""

import os
import logging
import httpx

log = logging.getLogger(__name__)

BHASHINI_API_KEY    = os.getenv("BHASHINI_API_KEY", "")
BHASHINI_USER_ID    = os.getenv("BHASHINI_USER_ID", "")
BHASHINI_BASE_URL   = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

# Supported languages (BCP-47 codes → display names)
SUPPORTED_LANGUAGES = {
    "en":  "English",
    "hi":  "हिंदी (Hindi)",
    "bn":  "বাংলা (Bengali)",
    "ta":  "தமிழ் (Tamil)",
    "te":  "తెలుగు (Telugu)",
    "mr":  "मराठी (Marathi)",
    "gu":  "ગુજરાતી (Gujarati)",
    "kn":  "ಕನ್ನಡ (Kannada)",
    "ml":  "മലയാളം (Malayalam)",
    "pa":  "ਪੰਜਾਬੀ (Punjabi)",
    "or":  "ଓଡ଼ିଆ (Odia)",
}

# Pre-translated welcome messages for instant response (no API needed)
WELCOME_MESSAGES = {
    "en": "🙏 Welcome to GovScheme Assistant!\n\nI'll help you find government schemes you qualify for in under 3 minutes.\n\nReply *HINDI* for Hindi, or let's continue in English.",
    "hi": "🙏 GovScheme सहायक में आपका स्वागत है!\n\nमैं आपको 3 मिनट में सरकारी योजनाओं का पता लगाने में मदद करूंगा।",
    "bn": "🙏 GovScheme সহকারীতে আপনাকে স্বাগতম!\n\nআমি আপনাকে 3 মিনিটে সরকারি প্রকল্প খুঁজে পেতে সাহায্য করব।",
    "ta": "🙏 GovScheme உதவியாளரில் வரவேற்கிறோம்!\n\nநான் 3 நிமிடங்களில் அரசு திட்டங்களை கண்டறிய உதவுவேன்।",
    "te": "🙏 GovScheme అసిస్టెంట్‌కు స్వాగతం!\n\nనేను 3 నిమిషాల్లో ప్రభుత్వ పథకాలు కనుగొనడంలో సహాయం చేస్తాను।",
    "mr": "🙏 GovScheme सहाय्यकामध्ये आपले स्वागत आहे!\n\nमी 3 मिनिटांत सरकारी योजना शोधण्यात मदत करेन।",
    "gu": "🙏 GovScheme સહાયકમાં આપનું સ્વાગત છે!\n\nહું 3 મિનિટમાં સરકારી યોજનાઓ શોધવામાં મદદ કરીશ।",
    "kn": "🙏 GovScheme ಸಹಾಯಕಕ್ಕೆ ಸ್ವಾಗತ!\n\nನಾನು 3 ನಿಮಿಷಗಳಲ್ಲಿ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳನ್ನು ಹುಡುಕಲು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ.",
    "ml": "🙏 GovScheme അസിസ്റ്റന്റിലേക്ക് സ്വാഗതം!\n\nഞാൻ 3 മിനിറ്റിൽ സർക്കാർ പദ്ധതികൾ കണ്ടെത്താൻ സഹായിക്കും।",
    "pa": "🙏 GovScheme ਸਹਾਇਕ ਵਿੱਚ ਆਪਦਾ ਸੁਆਗਤ ਹੈ!\n\nਮੈਂ 3 ਮਿੰਟਾਂ ਵਿੱਚ ਸਰਕਾਰੀ ਯੋਜਨਾਵਾਂ ਲੱਭਣ ਵਿੱਚ ਮਦਦ ਕਰਾਂਗਾ।",
    "or": "🙏 GovScheme ସହାୟକରେ ଆପଣଙ୍କୁ ସ୍ୱାଗତ!\n\nମୁଁ 3 ମିନିଟ୍ ମଧ୍ୟରେ ସରକାରୀ ଯୋଜନା ଖୋଜିବାରେ ସାହାଯ୍ୟ କରିବି।",
}

# Language selection prompt for WhatsApp buttons
LANGUAGE_SELECT_PROMPT = "🌐 *Choose your language / भाषा चुनें:*"
LANGUAGE_BUTTONS = [
    {"id": "lang_en", "title": "English"},
    {"id": "lang_hi", "title": "हिंदी"},
    {"id": "lang_more", "title": "More Languages"},
]

MORE_LANGUAGES_LIST = [
    {"id": "lang_bn", "title": "বাংলা"},
    {"id": "lang_ta", "title": "தமிழ்"},
    {"id": "lang_te", "title": "తెలుగు"},
    {"id": "lang_mr", "title": "मराठी"},
    {"id": "lang_gu", "title": "ગુજરાતી"},
    {"id": "lang_kn", "title": "ಕನ್ನಡ"},
    {"id": "lang_ml", "title": "മലയാളം"},
    {"id": "lang_pa", "title": "ਪੰਜਾਬੀ"},
]


async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate text using Bhashini API.
    Falls back to original text if API unavailable or same language.
    """
    if source_lang == target_lang or target_lang == "en":
        return text

    if not BHASHINI_API_KEY or not BHASHINI_USER_ID:
        log.debug("Bhashini API not configured — using original text")
        return text

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                BHASHINI_BASE_URL,
                headers={
                    "userID": BHASHINI_USER_ID,
                    "ulcaApiKey": BHASHINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "pipelineTasks": [{
                        "taskType": "translation",
                        "config": {
                            "language": {
                                "sourceLanguage": source_lang,
                                "targetLanguage": target_lang,
                            }
                        }
                    }],
                    "inputData": {
                        "input": [{"source": text}]
                    }
                }
            )
            resp.raise_for_status()
            data = resp.json()
            translated = data["pipelineResponse"][0]["output"][0]["target"]
            log.info(f"Translated {source_lang}→{target_lang}: {len(text)} chars")
            return translated
    except Exception as e:
        log.warning(f"Bhashini translation failed: {e} — returning original")
        return text


def get_welcome_message(language: str) -> str:
    """Get pre-translated welcome message for a language."""
    return WELCOME_MESSAGES.get(language, WELCOME_MESSAGES["en"])


def parse_language_from_button(button_id: str) -> str:
    """Parse language code from button ID like 'lang_hi' → 'hi'."""
    if button_id.startswith("lang_"):
        lang = button_id.replace("lang_", "")
        if lang in SUPPORTED_LANGUAGES and lang != "more":
            return lang
    return "en"


def detect_language_from_text(text: str) -> str:
    """
    Fast heuristic language detection from script ranges.
    Returns BCP-47 language code.
    """
    text = text.strip()

    # Script-based detection (most reliable)
    script_ranges = {
        "hi": ('\u0900', '\u097F'),  # Devanagari (Hindi/Marathi)
        "bn": ('\u0980', '\u09FF'),  # Bengali
        "gu": ('\u0A80', '\u0AFF'),  # Gujarati
        "pa": ('\u0A00', '\u0A7F'),  # Gurmukhi (Punjabi)
        "or": ('\u0B00', '\u0B7F'),  # Odia
        "ta": ('\u0B80', '\u0BFF'),  # Tamil
        "te": ('\u0C00', '\u0C7F'),  # Telugu
        "kn": ('\u0C80', '\u0CFF'),  # Kannada
        "ml": ('\u0D00', '\u0D7F'),  # Malayalam
    }

    char_counts = {lang: 0 for lang in script_ranges}
    for char in text:
        for lang, (start, end) in script_ranges.items():
            if start <= char <= end:
                char_counts[lang] += 1

    # Return language with most matching characters
    max_lang = max(char_counts, key=char_counts.get)
    if char_counts[max_lang] > 0:
        # Marathi also uses Devanagari — keep as 'hi' for simplicity
        return max_lang

    return "en"

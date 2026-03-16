import math
import logging
from typing import Optional
from app.models.scheme import Scheme, SchemeEligibilityRules
from app.models.session import Session, CitizenProfile, SessionState, SchemeRecommendation
from app.core.eligibility_engine import EligibilityEngine

logger = logging.getLogger(__name__)

QUESTIONS = {
    "q_occupation": {
        "id": "q_occupation",
        "text": "What is your occupation?",
        "text_hi": "आपका व्यवसाय क्या है?",
        "field": "occupation",
        "type": "choice",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Farmer", "value": "Farmer"},
            {"label": "Student", "value": "Student"},
            {"label": "Self-employed", "value": "Self-employed"},
            {"label": "Salaried", "value": "Salaried"},
            {"label": "Unemployed", "value": "Unemployed"},
            {"label": "Daily Wage Worker", "value": "Daily Wage Worker"},
            {"label": "Business Owner", "value": "Business Owner"},
        ],
    },
    "q_age": {
        "id": "q_age",
        "text": "What is your age?",
        "text_hi": "आपकी उम्र क्या है?",
        "field": "age",
        "type": "range",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Below 18", "value": 16},
            {"label": "18-25", "value": 22},
            {"label": "26-35", "value": 30},
            {"label": "36-45", "value": 40},
            {"label": "46-60", "value": 53},
            {"label": "Above 60", "value": 65},
        ],
    },
    "q_gender": {
        "id": "q_gender",
        "text": "What is your gender?",
        "text_hi": "आपका लिंग क्या है?",
        "field": "gender",
        "type": "choice",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Male", "value": "Male"},
            {"label": "Female", "value": "Female"},
            {"label": "Other", "value": "Other"},
        ],
    },
    "q_income": {
        "id": "q_income",
        "text": "What is your annual family income?",
        "text_hi": "आपकी वार्षिक पारिवारिक आय क्या है?",
        "field": "annual_income",
        "type": "range",
        "whatsapp_type": "list",
        "options": [
            {"label": "Below ₹1 Lakh", "value": 80000},
            {"label": "₹1-2 Lakh", "value": 150000},
            {"label": "₹2-5 Lakh", "value": 350000},
            {"label": "₹5-10 Lakh", "value": 750000},
            {"label": "Above ₹10 Lakh", "value": 1500000},
        ],
    },
    "q_residence": {
        "id": "q_residence",
        "text": "Do you live in a rural or urban area?",
        "text_hi": "आप ग्रामीण या शहरी क्षेत्र में रहते हैं?",
        "field": "residence_type",
        "type": "choice",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Rural", "value": "rural"},
            {"label": "Urban", "value": "urban"},
        ],
    },
    "q_state": {
        "id": "q_state",
        "text": "Which state do you live in?",
        "text_hi": "आप किस राज्य में रहते हैं?",
        "field": "state",
        "type": "choice",
        "whatsapp_type": "list",
        "options": [
            {"label": s, "value": s}
            for s in [
                "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Gujarat",
                "Haryana", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
                "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu",
                "Telangana", "Uttar Pradesh", "West Bengal", "Other",
            ]
        ],
    },
    "q_caste": {
        "id": "q_caste",
        "text": "What is your caste category?",
        "text_hi": "आपकी जाति श्रेणी क्या है?",
        "field": "caste",
        "type": "choice",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "General", "value": "General"},
            {"label": "OBC", "value": "OBC"},
            {"label": "SC", "value": "SC"},
            {"label": "ST", "value": "ST"},
            {"label": "Minority", "value": "Minority"},
        ],
    },
    "q_bpl": {
        "id": "q_bpl",
        "text": "Does your family hold a BPL card?",
        "text_hi": "क्या आपके परिवार के पास BPL कार्ड है?",
        "field": "bpl_household",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_land": {
        "id": "q_land",
        "text": "Do you own agricultural land?",
        "text_hi": "क्या आपके पास कृषि भूमि है?",
        "field": "owns_agricultural_land",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_tax_payer": {
        "id": "q_tax_payer",
        "text": "Are you an income tax payer?",
        "text_hi": "क्या आप आयकर दाता हैं?",
        "field": "is_income_tax_payer",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_bank_account": {
        "id": "q_bank_account",
        "text": "Do you have a bank account?",
        "text_hi": "क्या आपका बैंक खाता है?",
        "field": "has_bank_account",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_aadhaar": {
        "id": "q_aadhaar",
        "text": "Is your bank account linked to Aadhaar?",
        "text_hi": "क्या आपका बैंक खाता आधार से जुड़ा है?",
        "field": "aadhaar_linked",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_house": {
        "id": "q_house",
        "text": "Do you own a pucca (permanent) house?",
        "text_hi": "क्या आपके पास पक्का मकान है?",
        "field": "owns_pucca_house",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_girl_child": {
        "id": "q_girl_child",
        "text": "Do you have a girl child (below 10 years)?",
        "text_hi": "क्या आपकी 10 वर्ष से कम उम्र की बेटी है?",
        "field": "has_girl_child",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_disability": {
        "id": "q_disability",
        "text": "Do you or a family member have a disability?",
        "text_hi": "क्या आपको या परिवार के किसी सदस्य को विकलांगता है?",
        "field": "has_disability",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_pregnant": {
        "id": "q_pregnant",
        "text": "Are you or a family member currently pregnant or lactating?",
        "text_hi": "क्या आप या परिवार की कोई सदस्य गर्भवती हैं?",
        "field": "is_pregnant_or_lactating",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
    "q_govt_employee": {
        "id": "q_govt_employee",
        "text": "Are you a government employee?",
        "text_hi": "क्या आप सरकारी कर्मचारी हैं?",
        "field": "is_government_employee",
        "type": "boolean",
        "whatsapp_type": "quick_reply",
        "options": [
            {"label": "Yes", "value": True},
            {"label": "No", "value": False},
        ],
    },
}

def _entropy(counts: list[int]) -> float:
    """
    Calculate Shannon entropy: H = -Σ p(x) * log2(p(x))
    Higher entropy = more uncertainty = more candidate schemes still in play.
    """
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log2(p)
    return entropy

def _simulate_answer(
    profile: CitizenProfile,
    question: dict,
    answer_value,
    candidate_schemes: list[Scheme],
) -> list[str]:
    """
    Simulate: if the user gives this answer, which schemes remain eligible?
    Returns list of remaining scheme IDs.
    """

    sim_profile = profile.model_copy()
    field = question["field"]

    if hasattr(sim_profile, field):
        setattr(sim_profile, field, answer_value)

    remaining = []
    for scheme in candidate_schemes:
        is_eligible, _ = EligibilityEngine.check_eligibility(sim_profile, scheme)
        if is_eligible:
            remaining.append(scheme.id)

    return remaining

def calculate_information_gain(
    profile: CitizenProfile,
    question: dict,
    candidate_schemes: list[Scheme],
) -> float:
    """
    Calculate information gain for a question.

    Information Gain = H(before) - H(after)

    Where H(after) is the weighted average entropy across all possible answers.
    Higher = better question (reduces more uncertainty).
    """
    n_candidates = len(candidate_schemes)
    if n_candidates <= 1:
        return 0.0

    h_before = math.log2(n_candidates)

    answer_groups = []
    for option in question["options"]:
        value = option["value"]
        remaining = _simulate_answer(profile, question, value, candidate_schemes)
        answer_groups.append(len(remaining))

    if all(g == n_candidates for g in answer_groups):
        return 0.0

    total_outcomes = sum(answer_groups) if sum(answer_groups) > 0 else 1
    h_after = 0.0
    for count in answer_groups:
        if count > 0:
            weight = count / total_outcomes

            group_entropy = math.log2(count) if count > 1 else 0.0
            h_after += weight * group_entropy

    info_gain = h_before - h_after
    return max(0.0, info_gain)

class AdaptiveQuestionEngine:
    """
    Selects the optimal next question using information gain.

    At each step:
    1. Calculate info gain for every un-asked question
    2. Pick the question with highest info gain
    3. This minimizes the expected number of questions to reach a recommendation

    Like a game of 20 Questions, but optimized by Shannon entropy.
    """

    @staticmethod
    def select_next_question(
        session: Session,
        candidate_schemes: list[Scheme],
    ) -> Optional[dict]:
        """
        Select the best next question using information gain.

        Returns the question dict with highest info gain, or None if
        all questions have been asked or candidates are narrow enough.
        """
        asked = set(session.questions_asked)
        available = [
            q for q_id, q in QUESTIONS.items()
            if q_id not in asked
        ]

        if not available:
            return None

        if len(candidate_schemes) <= 3:

            return None

        scored = []
        for q in available:
            ig = calculate_information_gain(
                session.profile, q, candidate_schemes
            )
            scored.append((ig, q))

        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            best_ig, best_q = scored[0]
            logger.info(
                f"🧠 Best question: {best_q['id']} (info gain: {best_ig:.3f})"
            )

            for ig, q in scored[:3]:
                logger.debug(f"   {q['id']}: IG={ig:.3f}")

            if best_ig <= 0.001:
                logger.info("No question provides meaningful info gain. Stopping.")
                return None

            return best_q

        return None

    @staticmethod
    def get_question_by_id(question_id: str) -> Optional[dict]:
        """Get a question by its ID."""
        return QUESTIONS.get(question_id)

    @staticmethod
    def apply_answer_to_profile(
        profile: CitizenProfile,
        question: dict,
        answer: str,
    ) -> CitizenProfile:
        """
        Apply a user's answer to update their profile.
        Handles type conversion for each question type.
        """
        field = question["field"]
        q_type = question["type"]
        updated = profile.model_copy()

        if q_type == "boolean":
            value = answer.lower() in ("yes", "true", "1", "haan", "ha", "हाँ")
            setattr(updated, field, value)

        elif q_type == "range":

            for opt in question["options"]:
                if opt["label"].lower() == answer.lower() or str(opt["value"]) == answer:
                    setattr(updated, field, opt["value"])
                    break
            else:

                try:
                    setattr(updated, field, int(answer))
                except ValueError:
                    setattr(updated, field, answer)

        elif q_type == "choice":

            if field == "residence_type":
                setattr(updated, field, answer.lower())
            else:
                setattr(updated, field, answer)

        return updated

    @staticmethod
    def get_all_questions() -> list[dict]:
        """Return all available questions."""
        return list(QUESTIONS.values())

    @staticmethod
    def compute_question_gains(
        session: Session,
        candidate_schemes: list[Scheme],
    ) -> list[dict]:
        """
        Compute info gain for ALL un-asked questions.
        Useful for debugging and analytics.
        """
        asked = set(session.questions_asked)
        results = []

        for q_id, q in QUESTIONS.items():
            if q_id not in asked:
                ig = calculate_information_gain(
                    session.profile, q, candidate_schemes
                )
                results.append({
                    "question_id": q_id,
                    "text": q["text"],
                    "information_gain": round(ig, 4),
                    "field": q["field"],
                })

        results.sort(key=lambda x: x["information_gain"], reverse=True)
        return results

"""
Session API — Start eligibility session, answer questions, get recommendations.
Core endpoints: POST /api/session/start, POST /api/session/answer, GET /api/session/{id}/recommend
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.session_manager import SessionManager
from app.core.eligibility_engine import EligibilityEngine
from app.db.scheme_orm import get_all_schemes
from app.models.session import SessionState, SchemeRecommendation

router = APIRouter(prefix="/api/session", tags=["session"])


class StartSessionRequest(BaseModel):
    phone: Optional[str] = None
    channel: str = "web"
    language: str = "en"


class StartSessionResponse(BaseModel):
    session_id: str
    total_schemes: int
    first_question: dict


class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


class AnswerResponse(BaseModel):
    session_id: str
    candidates_remaining: int
    questions_asked: int
    is_complete: bool
    next_question: Optional[dict] = None
    recommendations: Optional[list[SchemeRecommendation]] = None


# Simple question definitions for adaptive flow
QUESTIONS = {
    "q_occupation": {
        "id": "q_occupation",
        "text": "What is your occupation?",
        "field": "occupation",
        "options": ["Farmer", "Student", "Self-employed", "Salaried", "Unemployed", "Daily Wage Worker", "Business Owner"],
        "type": "choice",
    },
    "q_age": {
        "id": "q_age",
        "text": "What is your age?",
        "field": "age",
        "options": ["Below 18", "18-25", "26-35", "36-45", "46-60", "Above 60"],
        "type": "range",
        "range_map": {
            "Below 18": 16, "18-25": 22, "26-35": 30,
            "36-45": 40, "46-60": 53, "Above 60": 65,
        },
    },
    "q_gender": {
        "id": "q_gender",
        "text": "What is your gender?",
        "field": "gender",
        "options": ["Male", "Female", "Other"],
        "type": "choice",
    },
    "q_income": {
        "id": "q_income",
        "text": "What is your annual family income?",
        "field": "annual_income",
        "options": ["Below ₹1 Lakh", "₹1-2 Lakh", "₹2-5 Lakh", "₹5-10 Lakh", "Above ₹10 Lakh"],
        "type": "range",
        "range_map": {
            "Below ₹1 Lakh": 80000, "₹1-2 Lakh": 150000,
            "₹2-5 Lakh": 350000, "₹5-10 Lakh": 750000, "Above ₹10 Lakh": 1500000,
        },
    },
    "q_state": {
        "id": "q_state",
        "text": "Which state do you live in?",
        "field": "state",
        "options": [
            "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Gujarat",
            "Haryana", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
            "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu",
            "Telangana", "Uttar Pradesh", "West Bengal", "Other"
        ],
        "type": "choice",
    },
    "q_residence": {
        "id": "q_residence",
        "text": "Do you live in a rural or urban area?",
        "field": "residence_type",
        "options": ["Rural", "Urban"],
        "type": "choice",
    },
    "q_caste": {
        "id": "q_caste",
        "text": "What is your caste category?",
        "field": "caste",
        "options": ["General", "OBC", "SC", "ST", "Minority"],
        "type": "choice",
    },
    "q_land": {
        "id": "q_land",
        "text": "Do you own agricultural land?",
        "field": "owns_agricultural_land",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_bpl": {
        "id": "q_bpl",
        "text": "Does your family hold a BPL (Below Poverty Line) card?",
        "field": "bpl_household",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_aadhaar": {
        "id": "q_aadhaar",
        "text": "Is your bank account linked to Aadhaar?",
        "field": "aadhaar_linked",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_tax_payer": {
        "id": "q_tax_payer",
        "text": "Are you an income tax payer?",
        "field": "is_income_tax_payer",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_bank_account": {
        "id": "q_bank_account",
        "text": "Do you have a bank account?",
        "field": "has_bank_account",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_disability": {
        "id": "q_disability",
        "text": "Do you or a family member have a disability?",
        "field": "has_disability",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_girl_child": {
        "id": "q_girl_child",
        "text": "Do you have a girl child (below 10 years)?",
        "field": "has_girl_child",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_pregnant": {
        "id": "q_pregnant",
        "text": "Are you or a family member currently pregnant or lactating?",
        "field": "is_pregnant_or_lactating",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
    "q_house": {
        "id": "q_house",
        "text": "Do you own a pucca (permanent) house?",
        "field": "owns_pucca_house",
        "options": ["Yes", "No"],
        "type": "boolean",
    },
}

# Question priority order (highest information gain first)
QUESTION_ORDER = [
    "q_occupation", "q_age", "q_gender", "q_income", "q_residence",
    "q_state", "q_caste", "q_bpl", "q_land", "q_tax_payer",
    "q_bank_account", "q_aadhaar", "q_house", "q_girl_child",
    "q_disability", "q_pregnant",
]


def get_next_question(asked: list[str]) -> Optional[dict]:
    """Get the next question that hasn't been asked yet."""
    for q_id in QUESTION_ORDER:
        if q_id not in asked:
            return QUESTIONS[q_id]
    return None


def apply_answer(profile_dict: dict, question: dict, answer: str) -> dict:
    """Apply an answer to the profile dict."""
    field = question["field"]
    q_type = question["type"]

    if q_type == "boolean":
        profile_dict[field] = answer.lower() in ("yes", "true", "1", "haan", "ha")
    elif q_type == "range" and "range_map" in question:
        profile_dict[field] = question["range_map"].get(answer, answer)
    elif q_type == "choice":
        value = answer.lower()
        if field == "residence_type":
            value = answer.lower()
        profile_dict[field] = answer

    return profile_dict


@router.post("/start", response_model=StartSessionResponse)
async def start_session(req: StartSessionRequest):
    """Start a new eligibility assessment session."""
    import uuid
    session_id = req.phone or f"web_{uuid.uuid4().hex[:12]}"
    session = await SessionManager.get_or_create(session_id, channel=req.channel)
    session.language = req.language
    session.state = SessionState.QUESTIONING
    await SessionManager.save(session)

    first_q = get_next_question([])
    return StartSessionResponse(
        session_id=session.session_id,
        total_schemes=len(session.candidates),
        first_question=first_q,
    )


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(req: AnswerRequest):
    """Submit an answer and get the next question or recommendations."""
    session = await SessionManager.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get question details
    question = QUESTIONS.get(req.question_id)
    if not question:
        raise HTTPException(status_code=400, detail=f"Unknown question: {req.question_id}")

    # Apply answer to profile
    profile_dict = session.profile.model_dump()
    profile_dict = apply_answer(profile_dict, question, req.answer)
    from app.models.session import CitizenProfile
    session.profile = CitizenProfile(**profile_dict)

    # Record question
    session.questions_asked.append(req.question_id)
    session.question_count += 1

    # Prune candidates
    all_schemes = await get_all_schemes()
    session.candidates = EligibilityEngine.prune_candidates(
        session.profile, all_schemes, session.candidates
    )

    # Check if we should stop
    should_stop = session.is_complete()

    if should_stop:
        # Generate recommendations
        candidate_schemes = [s for s in all_schemes if s.id in session.candidates]
        session.recommendations = EligibilityEngine.score_and_rank(
            session.profile, candidate_schemes, min_confidence=20.0
        )
        session.state = SessionState.RESULTS
        await SessionManager.save(session)

        return AnswerResponse(
            session_id=session.session_id,
            candidates_remaining=len(session.candidates),
            questions_asked=session.question_count,
            is_complete=True,
            recommendations=session.recommendations[:10],
        )

    # Get next question
    next_q = get_next_question(session.questions_asked)
    if not next_q:
        # No more questions — generate results
        candidate_schemes = [s for s in all_schemes if s.id in session.candidates]
        session.recommendations = EligibilityEngine.score_and_rank(
            session.profile, candidate_schemes, min_confidence=20.0
        )
        session.state = SessionState.RESULTS
        await SessionManager.save(session)

        return AnswerResponse(
            session_id=session.session_id,
            candidates_remaining=len(session.candidates),
            questions_asked=session.question_count,
            is_complete=True,
            recommendations=session.recommendations[:10],
        )

    session.current_question = next_q["id"]
    await SessionManager.save(session)

    return AnswerResponse(
        session_id=session.session_id,
        candidates_remaining=len(session.candidates),
        questions_asked=session.question_count,
        is_complete=False,
        next_question=next_q,
    )


@router.get("/{session_id}/recommend")
async def get_recommendations(session_id: str):
    """Get current recommendations for a session (can be called at any point)."""
    session = await SessionManager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    all_schemes = await get_all_schemes()
    candidate_schemes = [s for s in all_schemes if s.id in session.candidates]
    recommendations = EligibilityEngine.score_and_rank(
        session.profile, candidate_schemes, min_confidence=20.0
    )

    return {
        "session_id": session_id,
        "questions_asked": session.question_count,
        "total_candidates": len(session.candidates),
        "recommendations": [r.model_dump() for r in recommendations[:10]],
    }


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session = await SessionManager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump(mode="json")

"""
Session API — Start eligibility session, answer questions, get recommendations.
Uses AdaptiveQuestionEngine with information gain for optimal question selection.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.session_manager import SessionManager
from app.core.eligibility_engine import EligibilityEngine
from app.core.adaptive_engine import AdaptiveQuestionEngine
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


class EligibilityDirectRequest(BaseModel):
    """Direct eligibility check — skip questions, provide full profile."""
    age: Optional[int] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    occupation: Optional[str] = None
    annual_income: Optional[int] = None
    residence_type: Optional[str] = None
    caste: Optional[str] = None
    bpl_household: Optional[bool] = None
    owns_agricultural_land: Optional[bool] = None
    is_income_tax_payer: Optional[bool] = None
    has_bank_account: Optional[bool] = None
    has_disability: Optional[bool] = None
    has_girl_child: Optional[bool] = None
    is_pregnant_or_lactating: Optional[bool] = None
    owns_pucca_house: Optional[bool] = None
    is_government_employee: Optional[bool] = None


@router.post("/start", response_model=StartSessionResponse)
async def start_session(req: StartSessionRequest):
    """Start a new eligibility assessment session."""
    import uuid
    session_id = req.phone or f"web_{uuid.uuid4().hex[:12]}"
    session = await SessionManager.get_or_create(session_id, channel=req.channel)
    session.language = req.language
    session.state = SessionState.QUESTIONING
    await SessionManager.save(session)

    # Use info-gain engine to pick the BEST first question
    all_schemes = await get_all_schemes()
    candidate_schemes = [s for s in all_schemes if s.id in session.candidates]
    first_q = AdaptiveQuestionEngine.select_next_question(session, candidate_schemes)

    if not first_q:
        # Fallback — shouldn't happen with 52+ schemes
        first_q = AdaptiveQuestionEngine.get_question_by_id("q_occupation")

    return StartSessionResponse(
        session_id=session.session_id,
        total_schemes=len(session.candidates),
        first_question=first_q,
    )


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(req: AnswerRequest):
    """
    Submit an answer and get the next question (selected by info gain) or recommendations.

    Flow:
    1. Apply answer to citizen profile
    2. Prune candidate schemes
    3. If narrow enough → return recommendations
    4. Otherwise → select next question with highest information gain
    """
    session = await SessionManager.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get question details
    question = AdaptiveQuestionEngine.get_question_by_id(req.question_id)
    if not question:
        raise HTTPException(status_code=400, detail=f"Unknown question: {req.question_id}")

    # Apply answer to profile using adaptive engine
    session.profile = AdaptiveQuestionEngine.apply_answer_to_profile(
        session.profile, question, req.answer
    )

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
    candidate_schemes = [s for s in all_schemes if s.id in session.candidates]

    if should_stop:
        # Generate recommendations
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

    # Use information gain to select the BEST next question
    next_q = AdaptiveQuestionEngine.select_next_question(session, candidate_schemes)

    if not next_q:
        # No more informative questions — generate results
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


@router.get("/{session_id}/question-gains")
async def get_question_gains(session_id: str):
    """
    Debug endpoint: Show information gain for all un-asked questions.
    Useful for understanding why the engine picks certain questions.
    """
    session = await SessionManager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    all_schemes = await get_all_schemes()
    candidate_schemes = [s for s in all_schemes if s.id in session.candidates]
    gains = AdaptiveQuestionEngine.compute_question_gains(session, candidate_schemes)

    return {
        "session_id": session_id,
        "candidates": len(candidate_schemes),
        "questions_asked": session.questions_asked,
        "question_gains": gains,
    }


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session = await SessionManager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump(mode="json")


@router.post("/eligibility/direct")
async def direct_eligibility(req: EligibilityDirectRequest):
    """
    Skip questions, provide full profile, get recommendations instantly.
    Endpoint: POST /api/session/eligibility/direct
    """
    from app.models.session import CitizenProfile

    profile = CitizenProfile(**req.model_dump(exclude_none=True))
    all_schemes = await get_all_schemes()
    recommendations = EligibilityEngine.score_and_rank(
        profile, all_schemes, min_confidence=20.0
    )

    return {
        "total_schemes": len(all_schemes),
        "matched": len(recommendations),
        "recommendations": [r.model_dump() for r in recommendations[:15]],
    }

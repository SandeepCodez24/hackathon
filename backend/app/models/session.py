"""
Pydantic models for citizen session data.
Sessions are ephemeral (24hr TTL in Redis) — no permanent PII storage.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class SessionState(str, Enum):
    """Conversation state machine."""
    GREETING = "greeting"
    QUESTIONING = "questioning"
    RESULTS = "results"
    APPLY_GUIDE = "apply_guide"
    COMPLETED = "completed"


class CitizenProfile(BaseModel):
    """Profile built incrementally from adaptive questions."""
    age: Optional[int] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    occupation: Optional[str] = None
    annual_income: Optional[int] = None
    monthly_income: Optional[int] = None
    land_acres: Optional[float] = None
    ration_card: Optional[str] = None
    aadhaar_linked: Optional[bool] = None
    family_size: Optional[int] = None
    caste: Optional[str] = None
    residence_type: Optional[str] = None  # "rural" or "urban"
    has_bank_account: Optional[bool] = None
    is_income_tax_payer: Optional[bool] = None
    is_government_employee: Optional[bool] = None
    has_disability: Optional[bool] = None
    disability_percentage: Optional[int] = None
    has_girl_child: Optional[bool] = None
    is_pregnant_or_lactating: Optional[bool] = None
    owns_agricultural_land: Optional[bool] = None
    owns_pucca_house: Optional[bool] = None
    has_lpg_connection: Optional[bool] = None
    education_level: Optional[str] = None
    employment_status: Optional[str] = None
    bpl_household: Optional[bool] = None


class SchemeRecommendation(BaseModel):
    """A single scheme recommendation with confidence score."""
    scheme_id: str
    scheme_name: str
    confidence: float  # 0-100 percentage
    benefit: str
    portal_url: str = ""
    category: str = ""


class Session(BaseModel):
    """Citizen conversation session — stored in Redis with 24hr TTL."""
    session_id: str  # "wa_+91XXXXXXXXXX" or "web_{uuid}"
    channel: str = "whatsapp"  # "whatsapp" or "web"
    language: str = "en"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    profile: CitizenProfile = Field(default_factory=CitizenProfile)
    candidates: list[str] = Field(default_factory=list)  # scheme IDs still in play
    questions_asked: list[str] = Field(default_factory=list)
    current_question: Optional[str] = None
    state: SessionState = SessionState.GREETING
    recommendations: list[SchemeRecommendation] = Field(default_factory=list)
    question_count: int = 0
    max_questions: int = 12

    def is_complete(self) -> bool:
        """Check if we should stop asking questions."""
        return (
            self.state == SessionState.RESULTS
            or self.question_count >= self.max_questions
            or (len(self.candidates) <= 5 and self.question_count >= 3)
        )

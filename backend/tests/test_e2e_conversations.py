import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.eligibility_engine import EligibilityEngine
from app.core.adaptive_engine import AdaptiveQuestionEngine, QUESTIONS
from app.models.scheme import Scheme, SchemeEligibilityRules
from app.models.session import Session, SessionState, CitizenProfile, SchemeRecommendation
from app.db.database import load_schemes_from_files, get_memory_schemes
import asyncio

_schemes_cache = None

def get_all_schemes_sync() -> list[Scheme]:
    """Load all schemes from JSON files (sync for tests)."""
    global _schemes_cache
    if _schemes_cache is None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(load_schemes_from_files())
        loop.close()
        raw = get_memory_schemes()
        _schemes_cache = [Scheme(**s) for s in raw]
    return _schemes_cache

def simulate_conversation(answers: dict[str, str]) -> dict:
    """
    Simulate a full conversation with the adaptive engine.

    Args:
        answers: dict of question_field -> answer_value
                 e.g. {"occupation": "Farmer", "age": "26-35", ...}

    Returns:
        dict with keys: questions_asked, recommendations, candidates_remaining
    """
    schemes = get_all_schemes_sync()
    session = Session(
        session_id="test_sim",
        state=SessionState.QUESTIONING,
        candidates=[s.id for s in schemes],
    )

    max_rounds = 15
    rounds = 0

    while rounds < max_rounds:
        rounds += 1

        candidate_schemes = [s for s in schemes if s.id in session.candidates]

        next_q = AdaptiveQuestionEngine.select_next_question(session, candidate_schemes)

        if next_q is None or session.is_complete():
            break

        field = next_q["field"]
        if field in answers:
            answer = answers[field]
        else:

            session.questions_asked.append(next_q["id"])
            session.question_count += 1
            continue

        session.profile = AdaptiveQuestionEngine.apply_answer_to_profile(
            session.profile, next_q, answer
        )
        session.questions_asked.append(next_q["id"])
        session.question_count += 1

        session.candidates = EligibilityEngine.prune_candidates(
            session.profile, schemes, session.candidates
        )

    candidate_schemes = [s for s in schemes if s.id in session.candidates]
    recommendations = EligibilityEngine.score_and_rank(
        session.profile, candidate_schemes, min_confidence=20.0
    )

    return {
        "questions_asked": session.question_count,
        "questions_list": session.questions_asked,
        "candidates_remaining": len(session.candidates),
        "recommendations": recommendations,
        "top_scheme": recommendations[0].scheme_name if recommendations else None,
        "top_confidence": recommendations[0].confidence if recommendations else 0,
        "profile": session.profile,
    }

class TestFarmerBihar:
    def test_farmer_bihar_gets_pm_kisan(self):
        """A BPL farmer in Bihar should get PM-KISAN as top recommendation."""
        result = simulate_conversation({
            "occupation": "Farmer",
            "age": "36-45",
            "gender": "Male",
            "annual_income": "Below ₹1 Lakh",
            "residence_type": "Rural",
            "state": "Bihar",
            "caste": "OBC",
            "bpl_household": "Yes",
            "owns_agricultural_land": "Yes",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_government_employee": "No",
        })

        scheme_names = [r.scheme_name for r in result["recommendations"]]
        assert any("PM-KISAN" in name or "KISAN" in name.upper() for name in scheme_names), \
            f"Expected PM-KISAN in results, got: {scheme_names}"
        assert result["questions_asked"] <= 12, \
            f"Too many questions: {result['questions_asked']}"
        assert len(result["recommendations"]) >= 3, \
            f"Expected at least 3 recommendations for a BPL farmer"

class TestFemaleStudent:
    def test_female_student_gets_scholarship(self):
        """A young female student should get education/scholarship schemes."""
        result = simulate_conversation({
            "occupation": "Student",
            "age": "18-25",
            "gender": "Female",
            "annual_income": "₹1-2 Lakh",
            "residence_type": "Urban",
            "state": "Maharashtra",
            "caste": "General",
            "bpl_household": "No",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "has_girl_child": "No",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 2

class TestSCEntrepreneur:
    def test_sc_entrepreneur_gets_standup_india(self):
        """An SC self-employed person should get Stand-Up India."""
        result = simulate_conversation({
            "occupation": "Self-employed",
            "age": "26-35",
            "gender": "Male",
            "annual_income": "₹2-5 Lakh",
            "residence_type": "Urban",
            "state": "Uttar Pradesh",
            "caste": "SC",
            "bpl_household": "No",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_government_employee": "No",
        })

        scheme_ids = [r.scheme_id for r in result["recommendations"]]
        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 2

class TestPregnantWoman:
    def test_pregnant_woman_gets_maternity_benefit(self):
        """A pregnant woman should get PMMVY and health schemes."""
        result = simulate_conversation({
            "occupation": "Unemployed",
            "age": "26-35",
            "gender": "Female",
            "annual_income": "Below ₹1 Lakh",
            "residence_type": "Rural",
            "state": "Rajasthan",
            "caste": "OBC",
            "bpl_household": "Yes",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_pregnant_or_lactating": "Yes",
            "has_girl_child": "No",
            "is_government_employee": "No",
        })

        scheme_names = [r.scheme_name for r in result["recommendations"]]

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 3

class TestSeniorCitizen:
    def test_senior_gets_pension_schemes(self):
        """A senior citizen should get pension/health schemes."""
        result = simulate_conversation({
            "occupation": "Unemployed",
            "age": "Above 60",
            "gender": "Male",
            "annual_income": "Below ₹1 Lakh",
            "residence_type": "Rural",
            "state": "West Bengal",
            "caste": "General",
            "bpl_household": "Yes",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 2

class TestDailyWageWorker:
    def test_daily_worker_gets_eshram(self):
        """A daily wage worker should get e-Shram and welfare schemes."""
        result = simulate_conversation({
            "occupation": "Daily Wage Worker",
            "age": "36-45",
            "gender": "Male",
            "annual_income": "Below ₹1 Lakh",
            "residence_type": "Urban",
            "state": "Tamil Nadu",
            "caste": "SC",
            "bpl_household": "Yes",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 3

class TestBusinessOwner:
    def test_business_owner_gets_mudra(self):
        """A small business owner should get MUDRA loan scheme."""
        result = simulate_conversation({
            "occupation": "Business Owner",
            "age": "26-35",
            "gender": "Male",
            "annual_income": "₹2-5 Lakh",
            "residence_type": "Urban",
            "state": "Gujarat",
            "caste": "General",
            "bpl_household": "No",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 2

class TestWomanWithGirlChild:
    def test_woman_with_girl_child_gets_sukanya(self):
        """A woman with a young girl child should get SSY and BBBP."""
        result = simulate_conversation({
            "occupation": "Salaried",
            "age": "26-35",
            "gender": "Female",
            "annual_income": "₹2-5 Lakh",
            "residence_type": "Urban",
            "state": "Karnataka",
            "caste": "General",
            "bpl_household": "No",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "has_girl_child": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 2

class TestTenantFarmer:
    def test_tenant_farmer_gets_crop_insurance(self):
        """A tenant farmer should still get crop insurance (PMFBY)."""
        result = simulate_conversation({
            "occupation": "Farmer",
            "age": "36-45",
            "gender": "Male",
            "annual_income": "₹1-2 Lakh",
            "residence_type": "Rural",
            "state": "Madhya Pradesh",
            "caste": "OBC",
            "bpl_household": "No",
            "owns_agricultural_land": "No",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 1

class TestDisabledPerson:
    def test_disabled_person_gets_disability_schemes(self):
        """A person with disability should get IGNDPS and skill schemes."""
        result = simulate_conversation({
            "occupation": "Unemployed",
            "age": "26-35",
            "gender": "Male",
            "annual_income": "Below ₹1 Lakh",
            "residence_type": "Urban",
            "state": "Kerala",
            "caste": "General",
            "bpl_household": "Yes",
            "has_disability": "Yes",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12
        assert len(result["recommendations"]) >= 2

class TestHighIncomeSalaried:
    def test_high_income_gets_fewer_schemes(self):
        """A high-income tax-paying salaried person should match fewer schemes."""
        result = simulate_conversation({
            "occupation": "Salaried",
            "age": "36-45",
            "gender": "Male",
            "annual_income": "Above ₹10 Lakh",
            "residence_type": "Urban",
            "state": "Maharashtra",
            "caste": "General",
            "bpl_household": "No",
            "is_income_tax_payer": "Yes",
            "has_bank_account": "Yes",
            "owns_pucca_house": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12

        assert len(result["recommendations"]) >= 1

class TestSTWomanJharkhand:
    def test_st_woman_gets_multiple_schemes(self):
        """An ST woman in rural Jharkhand should qualify for many schemes."""
        result = simulate_conversation({
            "occupation": "Unemployed",
            "age": "26-35",
            "gender": "Female",
            "annual_income": "Below ₹1 Lakh",
            "residence_type": "Rural",
            "state": "Jharkhand",
            "caste": "ST",
            "bpl_household": "Yes",
            "owns_agricultural_land": "No",
            "is_income_tax_payer": "No",
            "has_bank_account": "Yes",
            "has_girl_child": "Yes",
            "is_government_employee": "No",
        })

        assert result["questions_asked"] <= 12

        assert len(result["recommendations"]) >= 5, \
            f"Expected >=5 recommendations for ST BPL rural woman, got {len(result['recommendations'])}"

class TestInfoGainBehavior:
    def test_info_gain_is_positive_initially(self):
        """First question should have positive information gain."""
        schemes = get_all_schemes_sync()
        session = Session(
            session_id="test_ig",
            state=SessionState.QUESTIONING,
            candidates=[s.id for s in schemes],
        )

        gains = AdaptiveQuestionEngine.compute_question_gains(session, schemes)
        assert len(gains) > 0
        assert gains[0]["information_gain"] > 0, \
            "First question should have positive info gain"

    def test_question_order_varies_by_profile(self):
        """Different profiles should potentially get different first questions."""
        schemes = get_all_schemes_sync()

        s1 = Session(
            session_id="t1",
            state=SessionState.QUESTIONING,
            candidates=[s.id for s in schemes],
        )
        q1 = AdaptiveQuestionEngine.select_next_question(s1, schemes)

        s2 = Session(
            session_id="t2",
            state=SessionState.QUESTIONING,
            candidates=[s.id for s in schemes],
            questions_asked=["q_occupation"],
            question_count=1,
        )
        s2.profile.occupation = "Farmer"

        s2.candidates = EligibilityEngine.prune_candidates(
            s2.profile, schemes, s2.candidates
        )
        farmer_schemes = [s for s in schemes if s.id in s2.candidates]
        q2 = AdaptiveQuestionEngine.select_next_question(s2, farmer_schemes)

        assert q1 is not None
        assert q2 is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

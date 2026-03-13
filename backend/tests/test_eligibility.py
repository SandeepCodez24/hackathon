"""
Unit tests for the Eligibility Engine.
Tests: rule matching, scoring, ranking, and candidate pruning.
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.eligibility_engine import EligibilityEngine
from app.models.scheme import Scheme, SchemeEligibilityRules
from app.models.session import CitizenProfile


def make_scheme(id: str, name: str, category: str, rules: dict) -> Scheme:
    """Helper to create a test scheme."""
    return Scheme(
        id=id,
        name=name,
        ministry="Test Ministry",
        category=category,
        benefit="Test benefit",
        eligibility_rules=SchemeEligibilityRules(**rules),
    )


# ============================================================
# Test: Basic eligibility checks
# ============================================================

class TestBasicEligibility:
    def test_farmer_matches_farmer_scheme(self):
        scheme = make_scheme("S1", "Farmer Scheme", "Agriculture", {
            "occupation": "farmer",
            "age_min": 18,
        })
        profile = CitizenProfile(occupation="Farmer", age=35)
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is True
        assert confidence >= 80

    def test_student_does_not_match_farmer_scheme(self):
        scheme = make_scheme("S1", "Farmer Scheme", "Agriculture", {
            "occupation": "farmer",
        })
        profile = CitizenProfile(occupation="Student")
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is False

    def test_age_too_young(self):
        scheme = make_scheme("S1", "Adult Scheme", "General", {
            "age_min": 18,
        })
        profile = CitizenProfile(age=15)
        is_eligible, _ = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is False

    def test_age_too_old(self):
        scheme = make_scheme("S1", "Youth Scheme", "General", {
            "age_min": 18, "age_max": 40,
        })
        profile = CitizenProfile(age=50)
        is_eligible, _ = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is False

    def test_age_in_range(self):
        scheme = make_scheme("S1", "Youth Scheme", "General", {
            "age_min": 18, "age_max": 40,
        })
        profile = CitizenProfile(age=30)
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is True
        assert confidence == 100.0


# ============================================================
# Test: Income-based rules
# ============================================================

class TestIncomeRules:
    def test_income_within_limit(self):
        scheme = make_scheme("S1", "BPL Scheme", "Welfare", {
            "annual_income_max": 200000,
        })
        profile = CitizenProfile(annual_income=150000)
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is True
        assert confidence == 100.0

    def test_income_exceeds_limit(self):
        scheme = make_scheme("S1", "BPL Scheme", "Welfare", {
            "annual_income_max": 200000,
        })
        profile = CitizenProfile(annual_income=500000)
        is_eligible, _ = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is False

    def test_unknown_income_gets_partial_credit(self):
        scheme = make_scheme("S1", "BPL Scheme", "Welfare", {
            "annual_income_max": 200000,
        })
        profile = CitizenProfile()  # No income info
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is True
        assert 40 <= confidence <= 60  # Partial credit


# ============================================================
# Test: Boolean exclusion rules
# ============================================================

class TestExclusionRules:
    def test_tax_payer_excluded(self):
        scheme = make_scheme("S1", "No-Tax Scheme", "Finance", {
            "is_income_tax_payer": False,
        })
        profile = CitizenProfile(is_income_tax_payer=True)
        is_eligible, _ = EligibilityEngine.check_eligibility(profile, scheme)
        # Tax payer = True but scheme requires False → should mismatch
        # Note: the rule checks if profile matches rule value
        assert is_eligible is False

    def test_non_tax_payer_eligible(self):
        scheme = make_scheme("S1", "No-Tax Scheme", "Finance", {
            "is_income_tax_payer": False,
        })
        profile = CitizenProfile(is_income_tax_payer=False)
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is True


# ============================================================
# Test: Gender-specific schemes
# ============================================================

class TestGenderRules:
    def test_female_scheme_for_female(self):
        scheme = make_scheme("S1", "Women Scheme", "Women", {
            "gender": "female",
        })
        profile = CitizenProfile(gender="Female")
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is True
        assert confidence >= 80

    def test_female_scheme_for_male(self):
        scheme = make_scheme("S1", "Women Scheme", "Women", {
            "gender": "female",
        })
        profile = CitizenProfile(gender="Male")
        is_eligible, _ = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is False


# ============================================================
# Test: Scoring and ranking
# ============================================================

class TestScoringAndRanking:
    def test_ranking_order(self):
        schemes = [
            make_scheme("S1", "Scheme A", "General", {"age_min": 18}),
            make_scheme("S2", "Scheme B", "Agriculture", {"occupation": "farmer", "age_min": 18}),
            make_scheme("S3", "Scheme C", "Women", {"gender": "female"}),
        ]
        profile = CitizenProfile(age=30, occupation="Farmer", gender="Male")
        results = EligibilityEngine.score_and_rank(profile, schemes)

        # S1 and S2 should be eligible, S3 should not (male)
        result_ids = [r.scheme_id for r in results]
        assert "S1" in result_ids
        assert "S2" in result_ids
        assert "S3" not in result_ids

    def test_scheme_with_no_rules_gets_default_score(self):
        scheme = make_scheme("S1", "Universal Scheme", "General", {})
        profile = CitizenProfile()
        is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
        assert is_eligible is True
        assert confidence == 70.0  # Default for no rules


# ============================================================
# Test: Candidate pruning
# ============================================================

class TestCandidatePruning:
    def test_pruning_removes_ineligible(self):
        schemes = [
            make_scheme("S1", "General", "General", {}),
            make_scheme("S2", "Farmer Only", "Agriculture", {"occupation": "farmer"}),
            make_scheme("S3", "Women Only", "Women", {"gender": "female"}),
        ]
        profile = CitizenProfile(occupation="Student", gender="Male")
        candidates = ["S1", "S2", "S3"]

        remaining = EligibilityEngine.prune_candidates(profile, schemes, candidates)
        assert "S1" in remaining  # Universal
        assert "S2" not in remaining  # Not a farmer
        assert "S3" not in remaining  # Not female


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

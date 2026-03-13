"""
Eligibility Engine — Rule matching, scoring, and ranking.
Core Phase 1 component that matches citizen profiles against scheme eligibility rules.
"""

import logging
from typing import Optional
from app.models.scheme import Scheme
from app.models.session import CitizenProfile, SchemeRecommendation

logger = logging.getLogger(__name__)


class EligibilityEngine:
    """
    Matches citizen profiles against scheme eligibility rules.

    Scoring logic:
    - Hard rules: binary pass/fail (if fails → scheme excluded)
    - Soft rules: weighted matching (contributes to confidence %)
    - Confidence = matched_criteria / total_criteria × 100
    - Ranking: sort by confidence, tie-break by category relevance
    """

    @staticmethod
    def check_eligibility(profile: CitizenProfile, scheme: Scheme) -> tuple[bool, float]:
        """
        Check if a citizen is eligible for a scheme.

        Returns:
            (is_eligible, confidence_score)
            is_eligible: False if any hard rule fails
            confidence_score: 0-100 percentage of matched criteria
        """
        rules = scheme.eligibility_rules
        total_checks = 0
        passed_checks = 0
        hard_fail = False

        # --- Age checks ---
        if rules.age_min is not None:
            total_checks += 1
            if profile.age is not None:
                if profile.age >= rules.age_min:
                    passed_checks += 1
                else:
                    hard_fail = True
            else:
                passed_checks += 0.5  # Unknown = partial credit

        if rules.age_max is not None:
            total_checks += 1
            if profile.age is not None:
                if profile.age <= rules.age_max:
                    passed_checks += 1
                else:
                    hard_fail = True
            else:
                passed_checks += 0.5

        # --- Income checks ---
        if rules.annual_income_max is not None:
            total_checks += 1
            if profile.annual_income is not None:
                if profile.annual_income <= rules.annual_income_max:
                    passed_checks += 1
                else:
                    hard_fail = True
            else:
                passed_checks += 0.5

        if rules.monthly_income_max is not None:
            total_checks += 1
            monthly = profile.monthly_income or (
                profile.annual_income // 12 if profile.annual_income else None
            )
            if monthly is not None:
                if monthly <= rules.monthly_income_max:
                    passed_checks += 1
                else:
                    hard_fail = True
            else:
                passed_checks += 0.5

        # --- Occupation ---
        if rules.occupation is not None:
            total_checks += 1
            if profile.occupation is not None:
                occ_lower = profile.occupation.lower()
                if isinstance(rules.occupation, str):
                    if occ_lower == rules.occupation.lower() or occ_lower in rules.occupation.lower():
                        passed_checks += 1
                    else:
                        hard_fail = True
                elif isinstance(rules.occupation, list):
                    if any(occ_lower in o.lower() or o.lower() in occ_lower for o in rules.occupation):
                        passed_checks += 1
                    else:
                        hard_fail = True
            else:
                passed_checks += 0.3  # Occupation is important — less partial credit

        # --- Gender ---
        if rules.gender is not None or rules.applicant_gender is not None:
            total_checks += 1
            required_gender = rules.gender or rules.applicant_gender
            if profile.gender is not None:
                if profile.gender.lower() == required_gender.lower():
                    passed_checks += 1
                else:
                    hard_fail = True
            else:
                passed_checks += 0.5

        # --- Residence type ---
        if rules.residence_type is not None and rules.residence_type != "rural_or_urban":
            total_checks += 1
            if profile.residence_type is not None:
                if profile.residence_type.lower() == rules.residence_type.lower():
                    passed_checks += 1
                else:
                    hard_fail = True
            else:
                passed_checks += 0.5

        # --- Boolean checks ---
        bool_checks = [
            (rules.is_income_tax_payer, profile.is_income_tax_payer, True),
            (rules.is_government_employee, profile.is_government_employee, True),
            (rules.owns_agricultural_land, profile.owns_agricultural_land, False),
            (rules.owns_pucca_house, profile.owns_pucca_house, True),
            (rules.has_lpg_connection, profile.has_lpg_connection, True),
            (rules.bpl_household, profile.bpl_household, False),
            (rules.has_disability, profile.has_disability, False),
            (rules.has_girl_child, profile.has_girl_child, False),
            (rules.is_pregnant_or_lactating, profile.is_pregnant_or_lactating, False),
            (rules.has_bank_account, profile.has_bank_account, False),
            (rules.has_savings_account, profile.has_bank_account, False),  # Map to same field
        ]

        for rule_val, profile_val, is_exclusion in bool_checks:
            if rule_val is not None:
                total_checks += 1
                if profile_val is not None:
                    if profile_val == rule_val:
                        passed_checks += 1
                    elif is_exclusion:
                        hard_fail = True
                    else:
                        # Soft fail for non-exclusion rules
                        pass
                else:
                    passed_checks += 0.5  # Unknown

        # --- State check ---
        if rules.state is not None:
            total_checks += 1
            if profile.state is not None:
                if isinstance(rules.state, list):
                    if any(profile.state.lower() in s.lower() or s.lower() in profile.state.lower()
                           for s in rules.state):
                        passed_checks += 1
                    else:
                        hard_fail = True
                elif isinstance(rules.state, str) and rules.state != "ALL":
                    if profile.state.lower() in rules.state.lower():
                        passed_checks += 1
                    else:
                        hard_fail = True
                else:
                    passed_checks += 1  # "ALL" states
            else:
                passed_checks += 0.5

        # --- Category / caste check ---
        if rules.category is not None:
            total_checks += 1
            if profile.caste is not None:
                if isinstance(rules.category, list):
                    caste_lower = profile.caste.lower()
                    gender_lower = (profile.gender or "").lower()
                    if any(
                        caste_lower in c.lower() or c.lower() in caste_lower
                        or (c.lower() == "female" and gender_lower == "female")
                        for c in rules.category
                    ):
                        passed_checks += 1
                    else:
                        hard_fail = True
            else:
                passed_checks += 0.5

        # Calculate confidence
        if total_checks == 0:
            # No specific rules — scheme is broadly available
            confidence = 70.0
        elif hard_fail:
            confidence = 0.0
        else:
            confidence = round((passed_checks / total_checks) * 100, 1)

        is_eligible = not hard_fail
        return is_eligible, confidence

    @staticmethod
    def _extract_benefit_value(benefit_text: str) -> float:
        """
        Extract approximate monetary value from benefit description.
        Used for tie-breaking when confidence scores are equal.
        E.g. "₹6,000/year" → 6000, "₹5 lakh" → 500000
        """
        import re
        text = benefit_text.lower().replace(",", "")
        
        # Match patterns like ₹6000, Rs. 5000, ₹5 lakh, ₹1 crore
        patterns = [
            (r'₹\s*([\d.]+)\s*crore', 10_000_000),
            (r'₹\s*([\d.]+)\s*lakh', 100_000),
            (r'₹\s*([\d.]+)\s*l\b', 100_000),
            (r'rs\.?\s*([\d.]+)\s*crore', 10_000_000),
            (r'rs\.?\s*([\d.]+)\s*lakh', 100_000),
            (r'₹\s*([\d.]+)', 1),
            (r'rs\.?\s*([\d.]+)', 1),
        ]
        
        max_value = 0.0
        for pattern, multiplier in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                try:
                    val = float(m) * multiplier
                    max_value = max(max_value, val)
                except ValueError:
                    pass
        
        return max_value

    @staticmethod
    def score_and_rank(
        profile: CitizenProfile,
        schemes: list[Scheme],
        min_confidence: float = 30.0,
    ) -> list[SchemeRecommendation]:
        """
        Score all schemes against a profile and return ranked recommendations.

        Ranking logic:
        1. Primary sort: confidence score (descending)
        2. Tie-break: benefit monetary value (descending)
        3. Final tie-break: scheme name (alphabetical)

        Args:
            profile: Citizen profile with known attributes
            schemes: List of all schemes to match against
            min_confidence: Minimum confidence to include in results

        Returns:
            List of SchemeRecommendation sorted by confidence (descending)
        """
        recommendations = []

        for scheme in schemes:
            is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)

            if is_eligible and confidence >= min_confidence:
                recommendations.append(
                    SchemeRecommendation(
                        scheme_id=scheme.id,
                        scheme_name=scheme.name,
                        confidence=confidence,
                        benefit=scheme.benefit,
                        portal_url=scheme.portal_url,
                        category=scheme.category,
                    )
                )

        # Sort: confidence desc → benefit value desc → name asc
        recommendations.sort(
            key=lambda r: (
                r.confidence,
                EligibilityEngine._extract_benefit_value(r.benefit),
                -ord(r.scheme_name[0]) if r.scheme_name else 0,
            ),
            reverse=True,
        )
        return recommendations

    @staticmethod
    def prune_candidates(
        profile: CitizenProfile,
        schemes: list[Scheme],
        current_candidates: list[str],
    ) -> list[str]:
        """
        Prune candidate scheme set based on current profile.
        Used after each answer to narrow down schemes.

        Returns:
            Updated list of scheme IDs still eligible
        """
        candidate_schemes = [s for s in schemes if s.id in current_candidates]
        remaining = []

        for scheme in candidate_schemes:
            is_eligible, confidence = EligibilityEngine.check_eligibility(profile, scheme)
            if is_eligible:
                remaining.append(scheme.id)

        logger.info(
            f"Pruned candidates: {len(current_candidates)} → {len(remaining)}"
        )
        return remaining

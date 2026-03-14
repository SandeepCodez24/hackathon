"""
Fraud Detector — Phase 5
Isolation Forest anomaly detector + rule-based consistency checker.
Silently flags suspicious profiles without blocking honest citizens.
"""

import logging
import math
from typing import Tuple

log = logging.getLogger(__name__)

# ── Rule-based consistency checks ─────────────────────────────────────────────
# Each rule is (description, lambda that returns True if SUSPICIOUS)
CONSISTENCY_RULES = [
    ("Farmer with no land and very high income",
     lambda p: p.get("occupation") == "Farmer"
               and p.get("annual_income", 0) > 600000
               and not p.get("land_owned", True)),

    ("Student aged over 35",
     lambda p: p.get("occupation") == "Student"
               and p.get("age", 0) > 35),

    ("Senior citizen claiming student status",
     lambda p: p.get("occupation") == "Student"
               and p.get("age", 0) > 60),

    ("Claims disabled but also claims no disability certificate",
     lambda p: p.get("disability") == True
               and p.get("disability_certificate") == False
               and p.get("annual_income", 0) < 50000),

    ("Claims SC/ST and very high income (>10L) simultaneously",
     lambda p: p.get("caste") in ["SC", "ST"]
               and p.get("annual_income", 0) > 1000000),

    ("Tenant farmer with large owned land",
     lambda p: p.get("land_tenure") == "Tenant"
               and p.get("land_acres", 0) > 10),

    ("Pregnant woman male profile",
     lambda p: p.get("gender") == "Male"
               and p.get("pregnant") == True),

    ("No income but owns property worth crores",
     lambda p: p.get("annual_income", 999999) < 10000
               and p.get("property_value", 0) > 5000000),
]


def _profile_to_vector(profile: dict) -> list:
    """
    Convert profile to numeric feature vector for Isolation Forest.
    Handles missing values gracefully.
    """
    occupation_map = {
        "Farmer": 1, "Agricultural Labourer": 2, "Self-employed": 3,
        "Student": 4, "Daily Wage Worker": 5, "Government Employee": 6,
        "Private Sector": 7, "Business Owner": 8, "Unemployed": 9, "Other": 10
    }
    caste_map = {"General": 1, "OBC": 2, "SC": 3, "ST": 4, "Minority": 5}
    gender_map = {"Male": 1, "Female": 2, "Other": 3}

    return [
        float(profile.get("age", 30)),
        float(profile.get("annual_income", 200000)) / 100000,   # normalised to lakhs
        float(profile.get("land_acres", 0)),
        float(profile.get("family_size", 4)),
        float(occupation_map.get(profile.get("occupation", "Other"), 10)),
        float(caste_map.get(profile.get("caste", "General"), 1)),
        float(gender_map.get(profile.get("gender", "Male"), 1)),
        1.0 if profile.get("disability") else 0.0,
        1.0 if profile.get("aadhaar_linked") else 0.0,
        1.0 if profile.get("pregnant") else 0.0,
    ]


def _isolation_score(vector: list) -> float:
    """
    Lightweight Isolation Forest approximation without scikit-learn dependency.
    Uses a simplified scoring based on statistical distance from typical profiles.
    
    Returns: anomaly score 0.0 (normal) → 1.0 (highly anomalous)
    """
    # Representative means and std devs from typical Indian citizen profiles
    # [age, income_lakh, land, family_size, occupation, caste, gender, disabled, aadhaar, pregnant]
    MEANS    = [32.0, 2.0, 1.2, 4.0, 4.5,  2.0, 1.3, 0.1, 0.7, 0.05]
    STD_DEVS = [12.0, 1.5, 2.0, 2.0, 2.5,  1.2, 0.5, 0.3, 0.45, 0.22]

    # Compute normalised Euclidean distance (Mahalanobis-lite)
    total = 0.0
    for i, (v, mean, std) in enumerate(zip(vector, MEANS, STD_DEVS)):
        if std > 0:
            z = abs(v - mean) / std
            total += z * z

    distance = math.sqrt(total / len(vector))

    # Sigmoid-like normalisation: score 0–1
    score = 1 - (1 / (1 + distance / 3))
    return min(score, 1.0)


def check_fraud(profile: dict) -> Tuple[bool, float, list]:
    """
    Main fraud detection entry point.
    
    Returns:
        (is_suspicious: bool, risk_score: float 0–1, triggered_rules: list[str])
    """
    triggered_rules = []

    # ── Rule-based consistency checks ─────────────────────────────────────────
    for description, rule_fn in CONSISTENCY_RULES:
        try:
            if rule_fn(profile):
                triggered_rules.append(description)
                log.warning(f"🚩 Fraud rule triggered: {description} | profile={profile}")
        except Exception:
            pass  # Never crash on fraud check

    # ── Isolation Forest approximation ────────────────────────────────────────
    vector = _profile_to_vector(profile)
    anomaly_score = _isolation_score(vector)

    # ── Combined risk score ────────────────────────────────────────────────────
    rule_score   = min(len(triggered_rules) * 0.25, 1.0)   # each rule +25%, max 1.0
    combined     = max(anomaly_score * 0.4 + rule_score * 0.6, rule_score)

    is_suspicious = combined > 0.5 or len(triggered_rules) >= 2

    if is_suspicious:
        log.warning(f"⚠️  Profile flagged as suspicious | score={combined:.2f} | rules={triggered_rules}")
    else:
        log.debug(f"✅ Profile OK | anomaly_score={anomaly_score:.2f} | combined={combined:.2f}")

    return is_suspicious, round(combined, 3), triggered_rules


def get_fraud_flag_message(language: str = "en") -> str:
    """
    Returns a non-alarming message shown when a suspicious profile is detected.
    We don't block the citizen — just add a disclaimer.
    """
    if language == "hi":
        return ("⚠️ *नोट:* आपकी जानकारी असामान्य लगती है। "
                "कृपया सुनिश्चित करें कि आपने सही जानकारी दी है। "
                "सभी योजनाओं के लिए Aadhaar सत्यापन आवश्यक है।")
    return ("⚠️ *Note:* Some details in your profile seem unusual. "
            "Please ensure all information is accurate — Aadhaar "
            "verification is required for all scheme applications. "
            "Providing false information is a punishable offence.")

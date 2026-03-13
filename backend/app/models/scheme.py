"""
Pydantic models for Government Scheme data.
Matches the schema from schemes_eligibility.json and schemes_part2.json.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


class SchemeEligibilityRules(BaseModel):
    """Machine-readable eligibility rules for automated matching."""
    # Age constraints
    age_min: Optional[int] = None
    age_max: Optional[int] = None

    # Income constraints
    annual_income_max: Optional[int] = None
    monthly_income_max: Optional[int] = None
    annual_parental_income_max: Optional[int] = None

    # Occupation / sector
    occupation: Optional[Any] = None  # str or list
    business_sector: Optional[str] = None
    sector: Optional[str] = None

    # Identity / status flags
    nationality: Optional[str] = None
    gender: Optional[str] = None
    applicant_gender: Optional[str] = None
    category: Optional[Any] = None  # list like ["SC", "ST", "female"]
    residence_type: Optional[str] = None
    state: Optional[Any] = None  # str or list

    # Boolean conditions
    has_bank_account: Optional[bool] = None
    has_savings_account: Optional[bool] = None
    is_income_tax_payer: Optional[bool] = None
    is_government_employee: Optional[bool] = None
    is_bank_defaulter: Optional[bool] = None
    owns_agricultural_land: Optional[bool] = None
    owns_pucca_house: Optional[bool] = None
    has_lpg_connection: Optional[bool] = None
    has_tap_connection: Optional[bool] = None
    has_toilet: Optional[bool] = None
    has_disability: Optional[bool] = None
    has_girl_child: Optional[bool] = None
    bpl_household: Optional[bool] = None
    bpl_or_near_poor: Optional[bool] = None
    secc_listed: Optional[bool] = None
    is_nfsa_listed: Optional[bool] = None
    is_pregnant_or_lactating: Optional[bool] = None
    is_first_enterprise: Optional[bool] = None
    is_new_enterprise: Optional[bool] = None
    is_innovative: Optional[bool] = None
    willing_for_manual_labour: Optional[bool] = None
    is_digitally_literate: Optional[bool] = None

    # Pension / special
    pension_monthly_max: Optional[int] = None
    age_70_plus_auto_eligible: Optional[bool] = None
    disability_pct_min: Optional[int] = None
    disability_pct_min_for_disability_pension: Optional[int] = None
    girl_child_age_max: Optional[int] = None

    # Ration card
    ration_card_type: Optional[Any] = None  # list

    # Education
    education_min_standard: Optional[int] = None
    enrolled_in_govt_school: Optional[bool] = None
    enrolled_in_govt_institution: Optional[bool] = None

    # Scheme-specific
    grows_notified_crops: Optional[bool] = None
    previously_availed_housing_scheme: Optional[bool] = None
    entity_age_years_max: Optional[int] = None
    annual_turnover_max_crore: Optional[int] = None
    is_epfo_esic_member: Optional[bool] = None
    is_nrlm_shg_member: Optional[bool] = None
    is_dairy_cooperative_member: Optional[bool] = None

    class Config:
        extra = "allow"  # Allow additional fields we haven't explicitly modeled


class Scheme(BaseModel):
    """Full scheme record matching the JSON data files."""
    id: str
    name: str
    ministry: str
    type: str = "central"
    category: str
    portal_url: str = ""
    benefit: str
    eligibility: dict = Field(default_factory=dict)
    eligibility_rules: SchemeEligibilityRules = Field(default_factory=SchemeEligibilityRules)
    application_steps: list[str] = Field(default_factory=list)

    @property
    def documents_required(self) -> list[str]:
        """Extract documents_required from eligibility dict."""
        return self.eligibility.get("documents_required", [])


class SchemeListResponse(BaseModel):
    """API response for scheme listing."""
    total: int
    schemes: list[Scheme]


class SchemeSearchQuery(BaseModel):
    """Search/filter query for schemes."""
    category: Optional[str] = None
    state: Optional[str] = None
    occupation: Optional[str] = None
    keyword: Optional[str] = None

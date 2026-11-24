"""Rule set and reference values for the synthetic general practice.

Point value and group averages are placeholders, not official figures.
"""

from decimal import Decimal

from praxis_check.rules import GroupAverageDeviation, MissingCompanion, Rule, SameDayExclusion
from praxis_check.sample_data import (
    CHRONIC_CARE_1,
    CHRONIC_CARE_2,
    CONVERSATION,
    FLAT_RATE,
    GERIATRIC_ASSESSMENT,
    PRIMARY_CARE_SUPPLEMENT,
)

POINT_VALUE = Decimal("0.127404")
"""Euros per point."""

GROUP_AVERAGE_PER_CASE = {
    CHRONIC_CARE_1: Decimal("0.35"),
    CHRONIC_CARE_2: Decimal("0.30"),
    CONVERSATION: Decimal("0.60"),
    GERIATRIC_ASSESSMENT: Decimal("0.15"),
}

RULES: tuple[Rule, ...] = (
    MissingCompanion("missing-primary-care-supplement", FLAT_RATE, PRIMARY_CARE_SUPPLEMENT),
    MissingCompanion("missing-chronic-care-2", CHRONIC_CARE_1, CHRONIC_CARE_2, min_visit_days=2),
    SameDayExclusion("conversation-on-assessment-day", GERIATRIC_ASSESSMENT, CONVERSATION),
    GroupAverageDeviation("group-average-deviation", GROUP_AVERAGE_PER_CASE),
)

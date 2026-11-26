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
    MissingCompanion(
        name="missing-primary-care-supplement",
        title="Zuschlag zur Versichertenpauschale fehlt",
        explanation="Fälle mit Versichertenpauschale, in denen der Zuschlag nicht abgerechnet wurde.",
        trigger=FLAT_RATE,
        companion=PRIMARY_CARE_SUPPLEMENT,
    ),
    MissingCompanion(
        name="missing-chronic-care-2",
        title="Chronikerpauschale 2 fehlt",
        explanation=(
            "Chroniker mit mindestens zwei Kontakten im Quartal, bei denen nur die erste "
            "Pauschale abgerechnet wurde."
        ),
        trigger=CHRONIC_CARE_1,
        companion=CHRONIC_CARE_2,
        min_visit_days=2,
    ),
    SameDayExclusion(
        name="conversation-on-assessment-day",
        title="Gespräch am Tag des geriatrischen Assessments",
        explanation="Das Gespräch ist neben dem Basisassessment am selben Tag nicht berechnungsfähig.",
        primary=GERIATRIC_ASSESSMENT,
        excluded=CONVERSATION,
    ),
    GroupAverageDeviation(
        name="group-average-deviation",
        title="Abweichung vom Fachgruppenschnitt",
        explanation="Leistungen, die je Fall um mehr als 25 % häufiger oder seltener abgerechnet werden.",
        reference=GROUP_AVERAGE_PER_CASE,
    ),
)

RULE_BY_NAME: dict[str, Rule] = {rule.name: rule for rule in RULES}

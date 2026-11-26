from datetime import date
from decimal import Decimal

import pytest

from praxis_check.billed_service import BilledService
from praxis_check.billing_code import BillingCode
from praxis_check.quarter import Quarter
from praxis_check.rules import (
    Finding,
    FindingKind,
    GroupAverageDeviation,
    MissingCompanion,
    SameDayExclusion,
    check,
    german_number,
)
from praxis_check.treatment_case import TreatmentCase

QUARTER = Quarter(2026, 4)
POINT_VALUE = Decimal("0.1")  # 10 cents per point keeps the arithmetic readable
DAY_1 = date(2026, 10, 5)
DAY_2 = date(2026, 11, 9)

FLAT_RATE = BillingCode("03000", "Flat rate", 100)  # 10.00
SUPPLEMENT = BillingCode("03040", "Supplement", 50)  # 5.00
CHRONIC_1 = BillingCode("03220", "Chronic 1", 100)
CHRONIC_2 = BillingCode("03221", "Chronic 2", 40)  # 4.00
ASSESSMENT = BillingCode("03360", "Assessment", 120)
CONVERSATION = BillingCode("03230", "Conversation", 128)  # 12.80


def case(patient_id: str, *services: tuple[BillingCode, date] | tuple[BillingCode, date, int]):
    return TreatmentCase(patient_id, QUARTER, tuple(BilledService(*s) for s in services))


# MissingCompanion


def test_missing_companion_is_found() -> None:
    rule = MissingCompanion("supplement", "t", "e", FLAT_RATE, SUPPLEMENT)

    findings = list(rule([case("p1", (FLAT_RATE, DAY_1))], POINT_VALUE))

    assert findings == [
        Finding(
            rule="supplement",
            kind=FindingKind.LOST_REVENUE,
            message="03000 abgerechnet, 03040 (Supplement) fehlt",
            amount=Decimal("5.00"),
            patient_id="p1",
        )
    ]


def test_present_companion_gives_no_finding() -> None:
    rule = MissingCompanion("supplement", "t", "e", FLAT_RATE, SUPPLEMENT)
    cases = [case("p1", (FLAT_RATE, DAY_1), (SUPPLEMENT, DAY_1))]

    assert list(rule(cases, POINT_VALUE)) == []


def test_case_without_trigger_gives_no_finding() -> None:
    rule = MissingCompanion("supplement", "t", "e", FLAT_RATE, SUPPLEMENT)

    assert list(rule([case("p1", (CONVERSATION, DAY_1))], POINT_VALUE)) == []


@pytest.mark.parametrize(("days", "expected"), [((DAY_1,), 0), ((DAY_1, DAY_2), 1)])
def test_min_visit_days_is_respected(days: tuple[date, ...], expected: int) -> None:
    rule = MissingCompanion("chronic", "t", "e", CHRONIC_1, CHRONIC_2, min_visit_days=2)
    services = [(CHRONIC_1, DAY_1)] + [(FLAT_RATE, day) for day in days]

    assert len(list(rule([case("p1", *services)], POINT_VALUE))) == expected


# SameDayExclusion


def test_excluded_code_on_same_day_is_found() -> None:
    rule = SameDayExclusion("exclusion", "t", "e", ASSESSMENT, CONVERSATION)
    cases = [case("p1", (ASSESSMENT, DAY_1), (CONVERSATION, DAY_1, 2))]

    findings = list(rule(cases, POINT_VALUE))

    assert len(findings) == 1
    assert findings[0].kind is FindingKind.AUDIT_RISK
    assert findings[0].amount == Decimal("25.60")
    assert findings[0].patient_id == "p1"


def test_excluded_code_on_other_day_is_fine() -> None:
    rule = SameDayExclusion("exclusion", "t", "e", ASSESSMENT, CONVERSATION)
    cases = [case("p1", (ASSESSMENT, DAY_1), (CONVERSATION, DAY_2))]

    assert list(rule(cases, POINT_VALUE)) == []


# GroupAverageDeviation


def cases_with_conversations(counts: list[int]) -> list[TreatmentCase]:
    return [
        case(f"p{i}", (FLAT_RATE, DAY_1), *([(CONVERSATION, DAY_1, n)] if n else []))
        for i, n in enumerate(counts)
    ]


def test_value_within_tolerance_gives_no_finding() -> None:
    rule = GroupAverageDeviation("avg", "t", "e", {CONVERSATION: Decimal("1.0")})

    # 4 conversations over 4 cases: exactly the average
    assert list(rule(cases_with_conversations([1, 1, 1, 1]), POINT_VALUE)) == []


def test_value_above_average_is_an_audit_risk() -> None:
    rule = GroupAverageDeviation("avg", "t", "e", {CONVERSATION: Decimal("0.5")})

    # 4 conversations over 4 cases = 1.0 per case, expected 0.5 -> 2 too many
    [finding] = rule(cases_with_conversations([1, 1, 1, 1]), POINT_VALUE)

    assert finding.kind is FindingKind.AUDIT_RISK
    assert finding.amount == Decimal("25.60")
    assert finding.patient_id is None
    assert "100 % über" in finding.message


def test_value_below_average_is_lost_revenue() -> None:
    rule = GroupAverageDeviation("avg", "t", "e", {CONVERSATION: Decimal("1.0")})

    # 1 conversation over 4 cases, expected 4 -> 3 missing
    [finding] = rule(cases_with_conversations([1, 0, 0, 0]), POINT_VALUE)

    assert finding.kind is FindingKind.LOST_REVENUE
    assert finding.amount == Decimal("38.40")
    assert "75 % unter" in finding.message


def test_no_cases_give_no_finding() -> None:
    rule = GroupAverageDeviation("avg", "t", "e", {CONVERSATION: Decimal("1.0")})

    assert list(rule([], POINT_VALUE)) == []


# check


def test_check_runs_all_rules_and_sorts_by_amount() -> None:
    rules = [
        MissingCompanion("supplement", "t", "e", FLAT_RATE, SUPPLEMENT),
        SameDayExclusion("exclusion", "t", "e", ASSESSMENT, CONVERSATION),
    ]
    cases = [
        case("p1", (FLAT_RATE, DAY_1)),
        case(
            "p2",
            (FLAT_RATE, DAY_1),
            (SUPPLEMENT, DAY_1),
            (ASSESSMENT, DAY_2),
            (CONVERSATION, DAY_2),
        ),
    ]

    findings = check(cases, POINT_VALUE, rules)

    assert [(f.rule, f.patient_id) for f in findings] == [("exclusion", "p2"), ("supplement", "p1")]


def test_check_without_rules_finds_nothing() -> None:
    assert check([case("p1", (FLAT_RATE, DAY_1))], POINT_VALUE, []) == []


@pytest.mark.parametrize(
    ("value", "places", "text"),
    [(Decimal("1234.5"), 2, "1.234,50"), (Decimal("0.6"), 2, "0,60"), (Decimal("80.4"), 0, "80")],
)
def test_german_number(value: Decimal, places: int, text: str) -> None:
    assert german_number(value, places) == text

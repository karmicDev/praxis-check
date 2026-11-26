"""Rule engine: finds irregularities in a quarter's treatment cases.

The rules are deliberately simplified. They show the approach, they do not replace a
real billing audit against the current EBM. Finding messages and rule titles are German,
because they are shown to the users of the application.
"""

from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from praxis_check.billing_code import BillingCode
from praxis_check.treatment_case import TreatmentCase


class FindingKind(StrEnum):
    LOST_REVENUE = "lost_revenue"
    """A service that was probably performed but not billed."""

    AUDIT_RISK = "audit_risk"
    """A billed service that an audit would probably strike."""


@dataclass(frozen=True)
class Finding:
    rule: str
    kind: FindingKind
    message: str
    amount: Decimal
    patient_id: str | None = None
    """None for findings about the whole practice rather than a single case."""


def german_number(value: Decimal, places: int = 2) -> str:
    """1234.5 -> '1.234,50'"""
    text = f"{value:,.{places}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


class Rule(Protocol):
    name: str
    """Stable identifier, stored with every finding."""

    title: str
    """Short German heading for reports."""

    explanation: str
    """One German sentence on what the rule looks for."""

    def __call__(
        self, cases: Sequence[TreatmentCase], point_value: Decimal
    ) -> Iterable[Finding]: ...


@dataclass(frozen=True)
class MissingCompanion:
    """Every case with ``trigger`` should also contain ``companion``.

    ``min_visit_days`` covers codes that need more than one contact in the quarter.
    """

    name: str
    title: str
    explanation: str
    trigger: BillingCode
    companion: BillingCode
    min_visit_days: int = 1

    def __call__(self, cases: Sequence[TreatmentCase], point_value: Decimal) -> Iterator[Finding]:
        for case in cases:
            codes = case.codes()
            visit_days = {s.service_date for s in case.services}
            if (
                self.trigger.code in codes
                and self.companion.code not in codes
                and len(visit_days) >= self.min_visit_days
            ):
                yield Finding(
                    rule=self.name,
                    kind=FindingKind.LOST_REVENUE,
                    message=(
                        f"{self.trigger.code} abgerechnet, {self.companion.code} "
                        f"({self.companion.description}) fehlt"
                    ),
                    amount=self.companion.amount(point_value),
                    patient_id=case.patient_id,
                )


@dataclass(frozen=True)
class SameDayExclusion:
    """``excluded`` must not be billed on the same day as ``primary``."""

    name: str
    title: str
    explanation: str
    primary: BillingCode
    excluded: BillingCode

    def __call__(self, cases: Sequence[TreatmentCase], point_value: Decimal) -> Iterator[Finding]:
        for case in cases:
            days_by_code: dict[str, set[date]] = {}
            for service in case.services:
                days_by_code.setdefault(service.billing_code.code, set()).add(service.service_date)
            for day in sorted(
                days_by_code.get(self.primary.code, set())
                & days_by_code.get(self.excluded.code, set())
            ):
                quantity = sum(
                    s.quantity
                    for s in case.services
                    if s.service_date == day and s.billing_code == self.excluded
                )
                yield Finding(
                    rule=self.name,
                    kind=FindingKind.AUDIT_RISK,
                    message=(
                        f"{self.excluded.code} am {day:%d.%m.%Y} neben {self.primary.code} "
                        f"abgerechnet, am selben Tag ausgeschlossen"
                    ),
                    amount=self.excluded.amount(point_value) * quantity,
                    patient_id=case.patient_id,
                )


@dataclass(frozen=True)
class GroupAverageDeviation:
    """Compares how often each code is billed per case with the specialty group average.

    ``reference`` maps a code to its average count per case in the group. A deviation of
    more than ``tolerance`` (0.25 means 25 %) in either direction becomes a finding.
    """

    name: str
    title: str
    explanation: str
    reference: Mapping[BillingCode, Decimal]
    tolerance: Decimal = Decimal("0.25")

    def __call__(self, cases: Sequence[TreatmentCase], point_value: Decimal) -> Iterator[Finding]:
        if not cases:
            return
        counts: Counter[str] = Counter()
        for case in cases:
            for service in case.services:
                counts[service.billing_code.code] += service.quantity

        case_count = len(cases)
        for code, expected_per_case in self.reference.items():
            actual_per_case = Decimal(counts[code.code]) / case_count
            if expected_per_case == 0:
                continue
            deviation = (actual_per_case - expected_per_case) / expected_per_case
            if abs(deviation) <= self.tolerance:
                continue
            difference = abs(counts[code.code] - expected_per_case * case_count)
            kind = FindingKind.AUDIT_RISK if deviation > 0 else FindingKind.LOST_REVENUE
            direction = "über" if deviation > 0 else "unter"
            percent = german_number(abs(deviation) * 100, 0)
            yield Finding(
                rule=self.name,
                kind=kind,
                message=(
                    f"{code.code} ({code.description}) {german_number(actual_per_case)}-mal je "
                    f"Fall abgerechnet, {percent} % {direction} dem Fachgruppenschnitt von "
                    f"{german_number(expected_per_case)}"
                ),
                amount=(code.amount(point_value) * difference).quantize(Decimal("0.01")),
            )


def check(
    cases: Sequence[TreatmentCase], point_value: Decimal, rules: Iterable[Rule]
) -> list[Finding]:
    """Run every rule over the cases; the largest amounts at stake come first."""
    findings = [finding for rule in rules for finding in rule(cases, point_value)]
    return sorted(findings, key=lambda f: (-f.amount, f.rule, f.patient_id or ""))

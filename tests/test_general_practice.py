import random
from collections import Counter
from datetime import date

from praxis_check.billed_service import BilledService
from praxis_check.general_practice import POINT_VALUE, RULES
from praxis_check.quarter import Quarter
from praxis_check.rules import check
from praxis_check.sample_data import SAMPLE_CATALOG, generate_rows
from praxis_check.treatment_case import TreatmentCase

QUARTER = Quarter(2026, 4)


def sample_cases(patients: int = 400) -> list[TreatmentCase]:
    services: dict[str, list[BilledService]] = {}
    for row in generate_rows(random.Random(42), QUARTER, patients):
        service = BilledService(
            SAMPLE_CATALOG[row["code"]],
            date.fromisoformat(row["service_date"]),
            int(row["quantity"]),
        )
        services.setdefault(row["patient_id"], []).append(service)
    return [TreatmentCase(p, QUARTER, tuple(s)) for p, s in sorted(services.items())]


def test_every_rule_fires_on_the_sample_practice() -> None:
    findings = check(sample_cases(), POINT_VALUE, RULES)

    fired = Counter(f.rule for f in findings)

    assert set(fired) == {rule.name for rule in RULES}


def test_rule_names_are_unique() -> None:
    names = [rule.name for rule in RULES]
    assert len(names) == len(set(names))

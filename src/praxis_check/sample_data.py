"""Synthetic billing data for a general practice.

The codes, points and probabilities are placeholders inspired by the EBM chapter for
general practitioners. They are not the current fee schedule and not real billing data.
"""

import csv
import random
from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from pathlib import Path

from praxis_check.billing_code import BillingCode
from praxis_check.importer import REQUIRED_COLUMNS
from praxis_check.quarter import Quarter

FLAT_RATE = BillingCode("03000", "Flat-rate fee per insured patient", 150)
PRIMARY_CARE_SUPPLEMENT = BillingCode("03040", "Supplement for primary care provision", 140)
CHRONIC_CARE_1 = BillingCode("03220", "Chronic care flat rate 1", 130)
CHRONIC_CARE_2 = BillingCode("03221", "Chronic care flat rate 2", 40)
CONVERSATION = BillingCode("03230", "Problem-oriented conversation", 128)
GERIATRIC_ASSESSMENT = BillingCode("03360", "Geriatric basic assessment", 120)
EXERCISE_ECG = BillingCode("03321", "Exercise ECG", 200)

SAMPLE_CODES = (
    FLAT_RATE,
    PRIMARY_CARE_SUPPLEMENT,
    CHRONIC_CARE_1,
    CHRONIC_CARE_2,
    CONVERSATION,
    GERIATRIC_ASSESSMENT,
    EXERCISE_ECG,
)

SAMPLE_CATALOG: dict[str, BillingCode] = {code.code: code for code in SAMPLE_CODES}

# Probabilities that shape the synthetic practice. The "missing" and "same day" values
# plant the irregularities the rule engine is meant to find.
CHRONIC_SHARE = 0.35
GERIATRIC_SHARE = 0.15
MISSING_SUPPLEMENT_RATE = 0.12
MISSING_CHRONIC_2_RATE = 0.20
CONVERSATION_PER_VISIT = 0.35
CONVERSATION_ON_ASSESSMENT_DAY = 0.25
EXERCISE_ECG_RATE = 0.05


def _visit_days(rng: random.Random, quarter: Quarter) -> list[date]:
    """One to four distinct, sorted visit days inside the quarter."""
    length = (quarter.end - quarter.start).days + 1
    offsets = rng.sample(range(length), k=rng.randint(1, 4))
    return [quarter.start + timedelta(days=offset) for offset in sorted(offsets)]


def _row(patient_id: str, day: date, code: BillingCode, quantity: int = 1) -> dict[str, str]:
    return {
        "patient_id": patient_id,
        "service_date": day.isoformat(),
        "code": code.code,
        "quantity": str(quantity),
    }


def _case_rows(rng: random.Random, quarter: Quarter, patient_id: str) -> Iterator[dict[str, str]]:
    """All rows for one patient in one quarter."""
    days = _visit_days(rng, quarter)
    first = days[0]

    yield _row(patient_id, first, FLAT_RATE)
    if rng.random() >= MISSING_SUPPLEMENT_RATE:
        yield _row(patient_id, first, PRIMARY_CARE_SUPPLEMENT)

    if rng.random() < CHRONIC_SHARE:
        yield _row(patient_id, first, CHRONIC_CARE_1)
        if len(days) > 1 and rng.random() >= MISSING_CHRONIC_2_RATE:
            yield _row(patient_id, days[1], CHRONIC_CARE_2)

    assessment_day = rng.choice(days) if rng.random() < GERIATRIC_SHARE else None
    if assessment_day is not None:
        yield _row(patient_id, assessment_day, GERIATRIC_ASSESSMENT)

    for day in days:
        if day == assessment_day:
            if rng.random() < CONVERSATION_ON_ASSESSMENT_DAY:
                yield _row(patient_id, day, CONVERSATION)
        elif rng.random() < CONVERSATION_PER_VISIT:
            yield _row(patient_id, day, CONVERSATION, rng.choice((1, 1, 2)))

    if rng.random() < EXERCISE_ECG_RATE:
        yield _row(patient_id, rng.choice(days), EXERCISE_ECG)


def _corrupt(rng: random.Random, row: dict[str, str]) -> dict[str, str]:
    """Damage one field the way real exports go wrong."""
    broken = dict(row)
    match rng.choice(("date", "code", "quantity", "patient")):
        case "date":
            broken["service_date"] = broken["service_date"].replace("-", ".")
        case "code":
            broken["code"] = "99999"
        case "quantity":
            broken["quantity"] = "0"
        case _:
            broken["patient_id"] = ""
    return broken


def generate_rows(
    rng: random.Random,
    quarter: Quarter,
    patient_count: int,
    invalid_row_rate: float = 0.0,
) -> Iterator[dict[str, str]]:
    """Yield the billing rows of a synthetic quarter, patient by patient.

    Pass a seeded ``random.Random`` to get the same data on every run.
    """
    if patient_count < 0:
        raise ValueError(f"Patient count must not be negative: {patient_count}")
    if not 0.0 <= invalid_row_rate <= 1.0:
        raise ValueError(f"Invalid row rate must be between 0 and 1: {invalid_row_rate}")

    for number in range(1, patient_count + 1):
        for row in _case_rows(rng, quarter, f"p{number:04d}"):
            yield _corrupt(rng, row) if rng.random() < invalid_row_rate else row


def write_rows(path: Path, rows: Iterable[dict[str, str]]) -> int:
    """Write rows as CSV with the import header; return the number of data rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count

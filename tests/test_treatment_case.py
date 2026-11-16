from datetime import date
from decimal import Decimal

import pytest

from praxis_check.billed_service import BilledService
from praxis_check.billing_code import BillingCode
from praxis_check.quarter import Quarter
from praxis_check.treatment_case import TreatmentCase

QUARTER = Quarter(2026, 4)
PATIENT_ID = "p1"
POINT_VALUE = Decimal("0.127404")

CONSULTATION = BillingCode("03000", "Consultation", 250)  # 31.85 at POINT_VALUE
CONVERSATION = BillingCode("03230", "Conversation", 128)  # 16.31 at POINT_VALUE

DAY = date(2026, 11, 16)


@pytest.mark.parametrize("patient_id", ["", " ", "  "])
def test_empty_patient_id_is_rejected(patient_id: str) -> None:
    with pytest.raises(ValueError):
        TreatmentCase(patient_id, QUARTER)


def test_fields_keep_given_values() -> None:
    services = (BilledService(CONSULTATION, DAY),)
    case = TreatmentCase(PATIENT_ID, QUARTER, services)
    assert case.patient_id == PATIENT_ID
    assert case.quarter == QUARTER
    assert case.services == services


def test_services_default_to_empty_tuple() -> None:
    assert TreatmentCase(PATIENT_ID, QUARTER).services == ()


def test_services_cannot_be_changed_after_creation() -> None:
    case = TreatmentCase(PATIENT_ID, QUARTER)
    outside = BilledService(CONSULTATION, date(2020, 1, 1))
    with pytest.raises(AttributeError):
        case.services.append(outside)  # type: ignore[attr-defined]


@pytest.mark.parametrize("day", [QUARTER.start, QUARTER.end])
def test_service_on_quarter_boundary_is_accepted(day: date) -> None:
    TreatmentCase(PATIENT_ID, QUARTER, (BilledService(CONSULTATION, day),))


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 9, 30),  # day before the quarter
        date(2027, 1, 1),  # day after the quarter
    ],
)
def test_service_outside_quarter_is_rejected(day: date) -> None:
    with pytest.raises(ValueError, match="outside quarter 2026Q4"):
        TreatmentCase(PATIENT_ID, QUARTER, (BilledService(CONSULTATION, day),))


def test_total_of_empty_case_is_decimal_zero() -> None:
    result = TreatmentCase(PATIENT_ID, QUARTER).total(POINT_VALUE)
    assert result == Decimal(0)
    assert isinstance(result, Decimal)


def test_total_sums_all_services_with_quantities() -> None:
    case = TreatmentCase(
        PATIENT_ID,
        QUARTER,
        (BilledService(CONSULTATION, DAY), BilledService(CONVERSATION, DAY, 2)),
    )
    # 31.85 + 2 * 16.31
    assert case.total(POINT_VALUE) == Decimal("64.47")


def test_codes_are_unique() -> None:
    case = TreatmentCase(
        PATIENT_ID,
        QUARTER,
        (
            BilledService(CONSULTATION, DAY),
            BilledService(CONVERSATION, DAY),
            BilledService(CONVERSATION, date(2026, 12, 1)),
        ),
    )
    assert case.codes() == {"03000", "03230"}


def test_codes_of_empty_case_are_empty() -> None:
    assert TreatmentCase(PATIENT_ID, QUARTER).codes() == set()


def test_count_of_adds_up_quantities() -> None:
    case = TreatmentCase(
        PATIENT_ID,
        QUARTER,
        (
            BilledService(CONSULTATION, DAY),
            BilledService(CONVERSATION, DAY, 2),
            BilledService(CONVERSATION, date(2026, 12, 1), 3),
        ),
    )
    assert case.count_of("03230") == 5
    assert case.count_of("03000") == 1


def test_count_of_missing_code_is_zero() -> None:
    case = TreatmentCase(PATIENT_ID, QUARTER, (BilledService(CONSULTATION, DAY),))
    assert case.count_of("99999") == 0

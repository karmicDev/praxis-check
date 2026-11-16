from datetime import date
from decimal import Decimal

import pytest

from praxis_check.billed_service import BilledService
from praxis_check.billing_code import BillingCode

CONSULTATION = BillingCode("03000", "Consultation", 250)
POINT_VALUE = Decimal("0.127404")
DAY = date(2026, 11, 16)


def test_fields_keep_given_values() -> None:
    service = BilledService(CONSULTATION, DAY, 2)
    assert service.billing_code == CONSULTATION
    assert service.service_date == DAY
    assert service.quantity == 2


def test_quantity_defaults_to_one() -> None:
    assert BilledService(CONSULTATION, DAY).quantity == 1


@pytest.mark.parametrize("quantity", [0, -1])
def test_invalid_quantity_is_rejected(quantity: int) -> None:
    with pytest.raises(ValueError):
        BilledService(CONSULTATION, DAY, quantity)


def test_amount_with_quantity_one_equals_code_amount() -> None:
    assert BilledService(CONSULTATION, DAY).amount(POINT_VALUE) == Decimal("31.85")


def test_amount_multiplies_by_quantity() -> None:
    assert BilledService(CONSULTATION, DAY, 3).amount(POINT_VALUE) == Decimal("95.55")


def test_amount_rounds_per_code_before_multiplying() -> None:
    # 0.125 rounds to 0.13 per code, times 3 is 0.39 (not 0.375 rounded to 0.38).
    single_point = BillingCode("03000", "Consultation", 1)
    assert BilledService(single_point, DAY, 3).amount(Decimal("0.125")) == Decimal("0.39")

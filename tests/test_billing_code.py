from decimal import Decimal

import pytest

from praxis_check.billing_code import BillingCode


def test_valid_billing_code_keeps_leading_zero() -> None:
    billing_code = BillingCode("01234", "test", 10)
    assert billing_code.code == "01234"
    assert billing_code.description == "test"
    assert billing_code.points == 10


def test_zero_points_are_accepted() -> None:
    assert BillingCode("01234", "test", 0).points == 0


@pytest.mark.parametrize("code", ["1234", "", " ", "123456", "03O00", " 3000", "0300²"])
def test_invalid_code_is_rejected(code: str) -> None:
    with pytest.raises(ValueError):
        BillingCode(code, "test", 10)


@pytest.mark.parametrize("description", ["", " ", "  "])
def test_empty_description_is_rejected(description: str) -> None:
    with pytest.raises(ValueError):
        BillingCode("01234", description, 10)


def test_negative_points_are_rejected() -> None:
    with pytest.raises(ValueError):
        BillingCode("01234", "test", -1)


def test_amount_multiplies_points_by_point_value() -> None:
    amount = BillingCode("03000", "test", 250).amount(Decimal("0.127404"))
    assert amount == Decimal("31.85")


def test_amount_rounds_half_up() -> None:
    amount = BillingCode("03000", "test", 1).amount(Decimal("0.125"))
    assert amount == Decimal("0.13")

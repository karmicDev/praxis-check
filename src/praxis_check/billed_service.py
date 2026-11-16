from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from praxis_check.billing_code import BillingCode


@dataclass(frozen=True)
class BilledService:
    billing_code: BillingCode
    service_date: date
    quantity: int = 1

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise ValueError(f"Quantity must be at least 1: {self.quantity}")

    def amount(self, point_value: Decimal) -> Decimal:
        """Amount of the billing code, rounded per code, times the quantity."""
        return self.billing_code.amount(point_value) * self.quantity

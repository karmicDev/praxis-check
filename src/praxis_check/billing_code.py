from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class BillingCode:
    code: str
    description: str
    points: int

    def __post_init__(self) -> None:
        if len(self.code) != 5 or not self.code.isdecimal():
            raise ValueError(f"Code must be exactly 5 digits: {self.code!r}")
        if not self.description.strip():
            raise ValueError(f"Description must not be empty: {self.description!r}")
        if self.points < 0:
            raise ValueError(f"Points must not be negative: {self.points}")

    def amount(self, point_value: Decimal) -> Decimal:
        """Points times point value, rounded half up to whole cents."""
        return (self.points * point_value).quantize(CENT, rounding=ROUND_HALF_UP)

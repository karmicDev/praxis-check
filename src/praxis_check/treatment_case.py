from dataclasses import dataclass, field
from decimal import Decimal

from praxis_check.billed_service import BilledService
from praxis_check.quarter import Quarter


@dataclass(frozen=True)
class TreatmentCase:
    patient_id: str
    quarter: Quarter
    services: list[BilledService] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.patient_id.strip():
            raise ValueError(f"Patient ID must not be empty: {self.patient_id!r}")
        for service in self.services:
            if service.service_date not in self.quarter:
                raise ValueError(
                    f"Service date {service.service_date} is outside quarter {self.quarter}"
                )

    def total(self, point_value: Decimal) -> Decimal:
        """Sum of all service amounts; an empty case is Decimal 0."""
        return sum((s.amount(point_value) for s in self.services), Decimal(0))

    def codes(self) -> set[str]:
        """All billing codes that occur in this case, without duplicates."""
        return {s.billing_code.code for s in self.services}

    def count_of(self, code: str) -> int:
        """How often a billing code was performed, counting quantities."""
        return sum(s.quantity for s in self.services if s.billing_code.code == code)

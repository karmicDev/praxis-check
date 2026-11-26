import csv
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from praxis_check.billed_service import BilledService
from praxis_check.billing_code import BillingCode
from praxis_check.quarter import Quarter
from praxis_check.treatment_case import TreatmentCase

REQUIRED_COLUMNS = ("patient_id", "service_date", "code", "quantity")


class CsvFormatError(Exception):
    """Raised when a file cannot be imported at all, e.g. a required column is missing."""


@dataclass(frozen=True)
class RowError:
    line_number: int
    message: str


@dataclass(frozen=True)
class ImportResult:
    cases: tuple[TreatmentCase, ...] = ()
    errors: tuple[RowError, ...] = ()


def _required(row: Mapping[str, str | None], column: str) -> str:
    """Return the stripped value of a column, or raise if it is missing or blank."""
    value = (row.get(column) or "").strip()
    if not value:
        raise ValueError(f"Wert fehlt in Spalte {column!r}")
    return value


def _parse_row(
    row: Mapping[str, str | None], quarter: Quarter, catalog: Mapping[str, BillingCode]
) -> tuple[str, BilledService]:
    """Turn one CSV row into (patient_id, service); raise ValueError with a readable German message."""
    patient_id = _required(row, "patient_id")

    date_text = _required(row, "service_date")
    try:
        service_date = date.fromisoformat(date_text)
    except ValueError as err:
        raise ValueError(f"ungültiges Leistungsdatum {date_text!r}") from err
    if service_date not in quarter:
        raise ValueError(f"Leistungsdatum {service_date} liegt außerhalb von Quartal {quarter}")

    code = _required(row, "code")
    if code not in catalog:
        raise ValueError(f"unbekannte Gebührenordnungsposition {code!r}")

    quantity_text = _required(row, "quantity")
    try:
        quantity = int(quantity_text)
    except ValueError as err:
        raise ValueError(f"ungültige Anzahl {quantity_text!r}") from err
    if quantity < 1:
        raise ValueError(f"ungültige Anzahl {quantity_text!r}")

    return patient_id, BilledService(catalog[code], service_date, quantity)


def import_services(
    path: Path, quarter: Quarter, catalog: Mapping[str, BillingCode]
) -> ImportResult:
    """Read a services CSV, group valid rows into cases per patient, collect invalid rows."""
    services_by_patient: defaultdict[str, list[BilledService]] = defaultdict(list)
    errors: list[RowError] = []

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or ())]
        if missing:
            raise CsvFormatError(f"{path.name}: Pflichtspalten fehlen: {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            try:
                patient_id, service = _parse_row(row, quarter, catalog)
            except ValueError as err:
                errors.append(RowError(line_number, str(err)))
                continue
            services_by_patient[patient_id].append(service)

    cases = tuple(
        TreatmentCase(patient_id, quarter, tuple(services))
        for patient_id, services in sorted(services_by_patient.items())
    )
    return ImportResult(cases=cases, errors=tuple(errors))

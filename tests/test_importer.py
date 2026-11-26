from datetime import date
from pathlib import Path

import pytest

from praxis_check.billed_service import BilledService
from praxis_check.billing_code import BillingCode
from praxis_check.importer import CsvFormatError, ImportResult, RowError, import_services
from praxis_check.quarter import Quarter

QUARTER = Quarter(2026, 4)
CONSULTATION = BillingCode("03000", "Consultation", 250)
CONVERSATION = BillingCode("03230", "Conversation", 128)
CATALOG = {
    CONSULTATION.code: CONSULTATION,
    CONVERSATION.code: CONVERSATION,
}
HEADER = "patient_id,service_date,code,quantity"


def write_csv(tmp_path: Path, *rows: str) -> Path:
    """Write HEADER plus the given data rows to a CSV file and return its path."""
    path = tmp_path / "services.csv"
    path.write_text("\n".join((HEADER, *rows)), encoding="utf-8")
    return path


def test_valid_rows_are_grouped_into_cases(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "p1,2026-10-05,03000,1",
        "p1,2026-10-05,03230,2",
        "p2,2026-11-14,03000,1",
    )

    result = import_services(path, QUARTER, CATALOG)

    assert result.errors == ()
    assert tuple(case.patient_id for case in result.cases) == ("p1", "p2")
    assert len(result.cases[0].services) == 2


def test_cases_are_sorted_by_patient_id(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "p2,2026-11-14,03000,1",
        "p1,2026-10-05,03000,1",
    )

    result = import_services(path, QUARTER, CATALOG)

    assert tuple(case.patient_id for case in result.cases) == ("p1", "p2")


def test_services_keep_their_values(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "p1,2026-10-05,03230,2")

    service = import_services(path, QUARTER, CATALOG).cases[0].services[0]

    assert service == BilledService(CONVERSATION, date(2026, 10, 5), 2)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (",2026-10-05,03000,1", "Wert fehlt in Spalte 'patient_id'"),
        ("  ,2026-10-05,03000,1", "Wert fehlt in Spalte 'patient_id'"),
        ("p1,kein-datum,03000,1", "ungültiges Leistungsdatum 'kein-datum'"),
        ("p1,2026-09-30,03000,1", "Leistungsdatum 2026-09-30 liegt außerhalb von Quartal 2026Q4"),
        ("p1,2027-01-01,03000,1", "Leistungsdatum 2027-01-01 liegt außerhalb von Quartal 2026Q4"),
        ("p1,2026-10-05,99999,1", "unbekannte Gebührenordnungsposition '99999'"),
        ("p1,2026-10-05,03000,abc", "ungültige Anzahl 'abc'"),
        ("p1,2026-10-05,03000,0", "ungültige Anzahl '0'"),
        ("p1,2026-10-05", "Wert fehlt in Spalte 'code'"),
    ],
)
def test_invalid_row_is_reported(tmp_path: Path, row: str, message: str) -> None:
    path = write_csv(tmp_path, row)

    result = import_services(path, QUARTER, CATALOG)

    assert result.cases == ()
    assert result.errors == (RowError(2, message),)


def test_invalid_row_does_not_stop_the_import(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "p1,2026-10-05,03000,1",
        "p1,kein-datum,03000,1",
        "p2,2026-11-14,03000,1",
    )

    result = import_services(path, QUARTER, CATALOG)

    assert tuple(case.patient_id for case in result.cases) == ("p1", "p2")
    assert tuple(error.line_number for error in result.errors) == (3,)


def test_header_only_gives_empty_result(tmp_path: Path) -> None:
    path = write_csv(tmp_path)

    assert import_services(path, QUARTER, CATALOG) == ImportResult()


def test_missing_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "services.csv"
    path.write_text("patient_id,service_date,code\np1,2026-10-05,03000\n", encoding="utf-8")

    with pytest.raises(CsvFormatError, match="quantity"):
        import_services(path, QUARTER, CATALOG)


def test_empty_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "services.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(CsvFormatError):
        import_services(path, QUARTER, CATALOG)

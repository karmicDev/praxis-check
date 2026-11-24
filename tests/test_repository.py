import random
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy.orm import Session

from praxis_check.billed_service import BilledService
from praxis_check.db import alembic_config
from praxis_check.general_practice import POINT_VALUE, RULES
from praxis_check.importer import CsvFormatError, RowError
from praxis_check.pipeline import process_file
from praxis_check.quarter import Quarter
from praxis_check.repository import get_run, list_runs, load_cases, save_run, to_finding
from praxis_check.rules import Finding, FindingKind, check
from praxis_check.sample_data import (
    CONVERSATION,
    FLAT_RATE,
    SAMPLE_CATALOG,
    generate_rows,
    write_rows,
)
from praxis_check.treatment_case import TreatmentCase

QUARTER = Quarter(2026, 4)
DAY = date(2026, 10, 5)
CASE = TreatmentCase(
    "p1", QUARTER, (BilledService(FLAT_RATE, DAY), BilledService(CONVERSATION, DAY, 2))
)
FINDING = Finding("rule", FindingKind.LOST_REVENUE, "message", Decimal("17.84"), "p1")


def save(session: Session, practice: str = "Praxis Dr. Muster", **overrides) -> int:
    values = {
        "practice_name": practice,
        "quarter": QUARTER,
        "file_name": "services.csv",
        "point_value": POINT_VALUE,
        "cases": [CASE],
        "errors": [RowError(3, "unknown billing code '99999'")],
        "findings": [FINDING],
    }
    values.update(overrides)
    run = save_run(session, **values)
    session.commit()
    return run.id


def test_migrations_match_the_models(database_url: str) -> None:
    command.check(alembic_config(database_url))


def test_saved_run_round_trips(session: Session) -> None:
    run_id = save(session)
    session.expunge_all()

    run = get_run(session, run_id)

    assert run is not None
    assert run.practice.name == "Praxis Dr. Muster"
    assert run.quarter == "2026Q4"
    assert run.case_count == 1
    assert run.revenue == CASE.total(POINT_VALUE)
    assert isinstance(run.revenue, Decimal)
    assert [to_finding(f) for f in run.findings] == [FINDING]
    assert [(e.line_number, e.message) for e in run.row_errors] == [
        (3, "unknown billing code '99999'")
    ]


def test_cases_are_rebuilt_from_the_database(session: Session) -> None:
    run_id = save(session)
    session.expunge_all()

    run = get_run(session, run_id)
    assert run is not None

    assert load_cases(session, run, SAMPLE_CATALOG) == [CASE]


def test_practice_is_reused_by_name(session: Session) -> None:
    first = save(session)
    second = save(session)

    runs = {run.id: run for run in list_runs(session)}

    assert runs[first].practice_id == runs[second].practice_id


def test_empty_practice_name_is_rejected(session: Session) -> None:
    with pytest.raises(ValueError):
        save(session, practice=" ")


def test_runs_are_listed_newest_first(session: Session) -> None:
    older = save(session, imported_at=datetime(2026, 1, 1))
    newer = save(session, imported_at=datetime(2026, 6, 1))

    assert [run.id for run in list_runs(session)] == [newer, older]


def test_missing_run_is_none(session: Session) -> None:
    assert get_run(session, 999) is None


def test_process_file_stores_import_and_findings(session: Session, tmp_path: Path) -> None:
    path = tmp_path / "practice.csv"
    write_rows(path, generate_rows(random.Random(42), QUARTER, 100, invalid_row_rate=0.02))

    run = process_file(
        session,
        path,
        practice_name="Praxis Dr. Muster",
        quarter=QUARTER,
        catalog=SAMPLE_CATALOG,
        point_value=POINT_VALUE,
        rules=RULES,
    )
    session.commit()

    assert run.case_count > 0
    assert run.row_errors
    assert run.findings
    # The rules give the same result when they read the cases back from the database.
    reloaded = check(load_cases(session, run, SAMPLE_CATALOG), POINT_VALUE, RULES)
    assert reloaded == [to_finding(f) for f in run.findings]


def test_unreadable_file_stores_nothing(session: Session, tmp_path: Path) -> None:
    path = tmp_path / "broken.csv"
    path.write_text("nothing,useful\n", encoding="utf-8")

    with pytest.raises(CsvFormatError):
        process_file(
            session,
            path,
            practice_name="Praxis",
            quarter=QUARTER,
            catalog=SAMPLE_CATALOG,
            point_value=POINT_VALUE,
            rules=RULES,
        )

    assert list_runs(session) == []

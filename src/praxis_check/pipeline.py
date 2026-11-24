"""The whole process in one call: import a file, check it, store the result."""

from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from praxis_check.billing_code import BillingCode
from praxis_check.db import ImportRun
from praxis_check.importer import import_services
from praxis_check.quarter import Quarter
from praxis_check.repository import save_run
from praxis_check.rules import Rule, check


def process_file(
    session: Session,
    path: Path,
    *,
    practice_name: str,
    quarter: Quarter,
    catalog: Mapping[str, BillingCode],
    point_value: Decimal,
    rules: Iterable[Rule],
    file_name: str | None = None,
) -> ImportRun:
    """Import ``path``, run the rules and save everything as one import run.

    Raises ``CsvFormatError`` if the file cannot be read at all. Invalid rows are stored
    with the run instead.
    """
    result = import_services(path, quarter, catalog)
    findings = check(result.cases, point_value, rules)
    return save_run(
        session,
        practice_name=practice_name,
        quarter=quarter,
        file_name=file_name or path.name,
        point_value=point_value,
        cases=result.cases,
        errors=result.errors,
        findings=findings,
    )

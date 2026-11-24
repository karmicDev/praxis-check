"""Saving and loading import runs. Functions take a Session; the caller owns the transaction."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from praxis_check.billed_service import BilledService
from praxis_check.billing_code import BillingCode
from praxis_check.db import (
    FindingRecord,
    ImportRun,
    Practice,
    RowErrorRecord,
    ServiceRecord,
)
from praxis_check.importer import RowError
from praxis_check.quarter import Quarter
from praxis_check.rules import Finding, FindingKind
from praxis_check.treatment_case import TreatmentCase


def get_or_create_practice(session: Session, name: str) -> Practice:
    name = name.strip()
    if not name:
        raise ValueError("Practice name must not be empty")
    practice = session.scalar(select(Practice).where(Practice.name == name))
    if practice is None:
        practice = Practice(name=name)
        session.add(practice)
    return practice


def save_run(
    session: Session,
    *,
    practice_name: str,
    quarter: Quarter,
    file_name: str,
    point_value: Decimal,
    cases: Sequence[TreatmentCase],
    errors: Sequence[RowError],
    findings: Sequence[Finding],
    imported_at: datetime | None = None,
) -> ImportRun:
    run = ImportRun(
        practice=get_or_create_practice(session, practice_name),
        quarter=str(quarter),
        file_name=file_name,
        imported_at=imported_at or datetime.now(),
        point_value=point_value,
        case_count=len(cases),
        revenue=sum((case.total(point_value) for case in cases), Decimal(0)),
        services=[
            ServiceRecord(
                patient_id=case.patient_id,
                service_date=service.service_date,
                code=service.billing_code.code,
                quantity=service.quantity,
            )
            for case in cases
            for service in case.services
        ],
        findings=[
            FindingRecord(
                rule=f.rule,
                kind=f.kind.value,
                message=f.message,
                amount=f.amount,
                patient_id=f.patient_id,
            )
            for f in findings
        ],
        row_errors=[RowErrorRecord(line_number=e.line_number, message=e.message) for e in errors],
    )
    session.add(run)
    session.flush()
    return run


def list_runs(session: Session) -> list[ImportRun]:
    """All runs, newest first, with practice and findings loaded."""
    statement = (
        select(ImportRun)
        .options(selectinload(ImportRun.practice), selectinload(ImportRun.findings))
        .order_by(ImportRun.imported_at.desc(), ImportRun.id.desc())
    )
    return list(session.scalars(statement))


def get_run(session: Session, run_id: int) -> ImportRun | None:
    statement = (
        select(ImportRun)
        .where(ImportRun.id == run_id)
        .options(
            selectinload(ImportRun.practice),
            selectinload(ImportRun.findings),
            selectinload(ImportRun.row_errors),
        )
    )
    return session.scalar(statement)


def load_cases(
    session: Session, run: ImportRun, catalog: Mapping[str, BillingCode]
) -> list[TreatmentCase]:
    """Rebuild the domain cases of a run from the database, e.g. to re-run the rules."""
    quarter = Quarter.parse(run.quarter)
    statement = (
        select(ServiceRecord)
        .where(ServiceRecord.import_run_id == run.id)
        .order_by(ServiceRecord.patient_id, ServiceRecord.service_date, ServiceRecord.id)
    )
    services: defaultdict[str, list[BilledService]] = defaultdict(list)
    for record in session.scalars(statement):
        services[record.patient_id].append(
            BilledService(catalog[record.code], record.service_date, record.quantity)
        )
    return [TreatmentCase(p, quarter, tuple(s)) for p, s in services.items()]


def to_finding(record: FindingRecord) -> Finding:
    return Finding(
        rule=record.rule,
        kind=FindingKind(record.kind),
        message=record.message,
        amount=record.amount,
        patient_id=record.patient_id,
    )

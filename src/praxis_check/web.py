"""Web application: a JSON API under /api and server-rendered pages with Jinja2."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from praxis_check import general_practice
from praxis_check.db import ImportRun, make_engine, make_session_factory, upgrade
from praxis_check.importer import CsvFormatError
from praxis_check.pipeline import process_file
from praxis_check.quarter import Quarter
from praxis_check.repository import get_run, list_runs
from praxis_check.rules import FindingKind
from praxis_check.sample_data import SAMPLE_CATALOG

DEFAULT_DATABASE_URL = "sqlite:///praxis_check.db"
TEMPLATES = Path(__file__).parent / "templates"


# API models


class RunSummary(BaseModel):
    id: int
    practice: str
    quarter: str
    file_name: str
    imported_at: datetime
    case_count: int
    revenue: Decimal
    finding_count: int
    lost_revenue: Decimal
    audit_risk: Decimal

    @classmethod
    def of(cls, run: ImportRun) -> RunSummary:
        def total(kind: FindingKind) -> Decimal:
            return sum((f.amount for f in run.findings if f.kind == kind), Decimal(0))

        return cls(
            id=run.id,
            practice=run.practice.name,
            quarter=run.quarter,
            file_name=run.file_name,
            imported_at=run.imported_at,
            case_count=run.case_count,
            revenue=run.revenue,
            finding_count=len(run.findings),
            lost_revenue=total(FindingKind.LOST_REVENUE),
            audit_risk=total(FindingKind.AUDIT_RISK),
        )


class FindingOut(BaseModel):
    rule: str
    kind: FindingKind
    message: str
    amount: Decimal
    patient_id: str | None


class RowErrorOut(BaseModel):
    line_number: int
    message: str


class RunDetail(RunSummary):
    findings: list[FindingOut]
    row_errors: list[RowErrorOut]

    @classmethod
    def of(cls, run: ImportRun) -> RunDetail:
        return cls(
            **RunSummary.of(run).model_dump(),
            findings=[
                FindingOut(
                    rule=f.rule,
                    kind=FindingKind(f.kind),
                    message=f.message,
                    amount=f.amount,
                    patient_id=f.patient_id,
                )
                for f in sorted(run.findings, key=lambda f: -f.amount)
            ],
            row_errors=[
                RowErrorOut(line_number=e.line_number, message=e.message)
                for e in sorted(run.row_errors, key=lambda e: e.line_number)
            ],
        )


# Formatting for the templates


def euro(value: Decimal) -> str:
    """German money format: 1.234,56 €"""
    text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{text} €"


def default_quarter(today: datetime) -> str:
    """The quarter that was billed last: the one before today's."""
    current = Quarter(today.year, (today.month - 1) // 3 + 1)
    previous = (
        Quarter(current.year - 1, 4)
        if current.number == 1
        else Quarter(current.year, current.number - 1)
    )
    return str(previous)


def create_app(database_url: str | None = None) -> FastAPI:
    url = database_url or os.environ.get("PRAXIS_CHECK_DATABASE_URL", DEFAULT_DATABASE_URL)
    upgrade(url)
    session_factory = make_session_factory(make_engine(url))

    app = FastAPI(
        title="Praxis-Check",
        description="Billing controlling for medical practices (synthetic data only).",
    )
    templates = Jinja2Templates(directory=TEMPLATES)
    templates.env.filters["euro"] = euro

    def get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    SessionDep = Annotated[Session, Depends(get_session)]

    def run_or_404(session: Session, run_id: int) -> ImportRun:
        run = get_run(session, run_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Import run {run_id} not found")
        return run

    def import_upload(session: Session, upload: UploadFile, practice: str, quarter: str) -> int:
        """Shared by the HTML form and the API. Raises ValueError with a readable message."""
        parsed_quarter = Quarter.parse(quarter.strip())
        if not upload.filename:
            raise ValueError("Please choose a CSV file")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upload.csv"
            with path.open("wb") as target:
                shutil.copyfileobj(upload.file, target)
            try:
                run = process_file(
                    session,
                    path,
                    practice_name=practice,
                    quarter=parsed_quarter,
                    catalog=SAMPLE_CATALOG,
                    point_value=general_practice.POINT_VALUE,
                    rules=general_practice.RULES,
                    file_name=upload.filename,
                )
            except (CsvFormatError, UnicodeDecodeError) as err:
                raise ValueError(f"The file could not be read: {err}") from err
        session.commit()
        return run.id

    # JSON API

    @app.get("/api/runs", response_model=list[RunSummary], tags=["api"])
    def api_list_runs(session: SessionDep) -> list[RunSummary]:
        return [RunSummary.of(run) for run in list_runs(session)]

    @app.get("/api/runs/{run_id}", response_model=RunDetail, tags=["api"])
    def api_get_run(run_id: int, session: SessionDep) -> RunDetail:
        return RunDetail.of(run_or_404(session, run_id))

    @app.post(
        "/api/runs", response_model=RunDetail, status_code=status.HTTP_201_CREATED, tags=["api"]
    )
    def api_create_run(
        session: SessionDep,
        file: UploadFile,
        practice: Annotated[str, Form()],
        quarter: Annotated[str, Form()],
    ) -> RunDetail:
        try:
            run_id = import_upload(session, file, practice, quarter)
        except ValueError as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(err)) from err
        return RunDetail.of(run_or_404(session, run_id))

    # HTML pages

    def page(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
        return templates.TemplateResponse(request, name, context, status_code=status_code)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard(request: Request, session: SessionDep) -> HTMLResponse:
        return page(request, "dashboard.html", runs=[RunSummary.of(r) for r in list_runs(session)])

    @app.get("/upload", response_class=HTMLResponse, include_in_schema=False)
    def upload_form(request: Request) -> HTMLResponse:
        return page(
            request, "upload.html", practice="", quarter=default_quarter(datetime.now()), error=None
        )

    @app.post("/upload", response_class=HTMLResponse, include_in_schema=False, response_model=None)
    def upload(
        request: Request,
        session: SessionDep,
        file: UploadFile,
        practice: Annotated[str, Form()],
        quarter: Annotated[str, Form()],
    ) -> HTMLResponse | RedirectResponse:
        try:
            run_id = import_upload(session, file, practice, quarter)
        except ValueError as err:
            session.rollback()
            return page(
                request,
                "upload.html",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                practice=practice,
                quarter=quarter,
                error=str(err),
            )
        return RedirectResponse(f"/runs/{run_id}", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/runs/{run_id}", response_class=HTMLResponse, include_in_schema=False)
    def report(request: Request, run_id: int, session: SessionDep) -> HTMLResponse:
        run = RunDetail.of(run_or_404(session, run_id))
        return page(
            request,
            "report.html",
            run=run,
            lost_revenue=[f for f in run.findings if f.kind is FindingKind.LOST_REVENUE],
            audit_risk=[f for f in run.findings if f.kind is FindingKind.AUDIT_RISK],
        )

    return app

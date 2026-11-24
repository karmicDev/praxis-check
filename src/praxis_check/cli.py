"""Command line: the whole check without a single click, e.g. in a nightly job."""

import logging
import os
import random
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer

from praxis_check import general_practice
from praxis_check.db import make_engine, make_session_factory, upgrade
from praxis_check.importer import CsvFormatError
from praxis_check.pipeline import process_file
from praxis_check.quarter import Quarter
from praxis_check.rules import FindingKind
from praxis_check.sample_data import SAMPLE_CATALOG, generate_rows, write_rows
from praxis_check.web import DEFAULT_DATABASE_URL, euro

log = logging.getLogger("praxis_check")

app = typer.Typer(help="Billing controlling for medical practices.", no_args_is_help=True)

EXIT_UNREADABLE_FILE = 2
EXIT_FINDINGS = 3


def parse_quarter(text: str) -> Quarter:
    try:
        return Quarter.parse(text)
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err


QuarterOption = Annotated[str, typer.Option(help="Billing quarter, e.g. 2026Q4.")]
DatabaseOption = Annotated[
    str,
    typer.Option(envvar="PRAXIS_CHECK_DATABASE_URL", help="SQLAlchemy database URL."),
]


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def generate_sample(
    output: Path,
    quarter: QuarterOption = "2026Q4",
    patients: int = 400,
    seed: int = 42,
    invalid_row_rate: float = 0.005,
) -> None:
    """Write a synthetic quarterly billing export to OUTPUT."""
    parsed = parse_quarter(quarter)
    count = write_rows(
        output, generate_rows(random.Random(seed), parsed, patients, invalid_row_rate)
    )
    typer.echo(f"Wrote {count} rows for {patients} patients in {quarter} to {output}")


@app.command()
def run(
    csv_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    practice: Annotated[str, typer.Option(help="Practice name.")],
    quarter: QuarterOption,
    database: DatabaseOption = DEFAULT_DATABASE_URL,
    fail_on_findings: Annotated[
        bool, typer.Option(help=f"Exit with code {EXIT_FINDINGS} if anything was found.")
    ] = False,
) -> None:
    """Import CSV_FILE, check it and store the result in the database."""
    log.info("Migrating database %s", database)
    upgrade(database)
    engine = make_engine(database)
    with make_session_factory(engine)() as session:
        try:
            result = process_file(
                session,
                csv_file,
                practice_name=practice,
                quarter=parse_quarter(quarter),
                catalog=SAMPLE_CATALOG,
                point_value=general_practice.POINT_VALUE,
                rules=general_practice.RULES,
            )
        except CsvFormatError as err:
            typer.echo(f"Error: {err}", err=True)
            raise typer.Exit(EXIT_UNREADABLE_FILE) from err
        session.commit()

        def total(kind: FindingKind) -> Decimal:
            return sum((f.amount for f in result.findings if f.kind == kind), Decimal(0))

        typer.echo(f"Import run {result.id}: {result.practice.name}, {result.quarter}")
        typer.echo(f"  Cases:          {result.case_count}")
        typer.echo(f"  Revenue:        {euro(result.revenue)}")
        typer.echo(f"  Rows skipped:   {len(result.row_errors)}")
        typer.echo(f"  Findings:       {len(result.findings)}")
        typer.echo(f"  Lost revenue:   {euro(total(FindingKind.LOST_REVENUE))}")
        typer.echo(f"  Audit risk:     {euro(total(FindingKind.AUDIT_RISK))}")
        has_findings = bool(result.findings)
    engine.dispose()

    if fail_on_findings and has_findings:
        raise typer.Exit(EXIT_FINDINGS)


@app.command()
def serve(
    database: DatabaseOption = DEFAULT_DATABASE_URL,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Start the web application."""
    import uvicorn

    os.environ["PRAXIS_CHECK_DATABASE_URL"] = database
    uvicorn.run("praxis_check.web:create_app", factory=True, host=host, port=port, reload=reload)

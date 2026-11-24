"""Database schema (SQLAlchemy 2.0, declarative with ``Mapped``) and engine setup."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Date, DateTime, Dialect, ForeignKey, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator

MIGRATIONS = Path(__file__).parent / "migrations"


class DecimalText(TypeDecorator[Decimal]):
    """Stores Decimal as text: SQLite has no exact decimal type and would fall back to float."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> str | None:
        return None if value is None else str(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(value)


class Base(DeclarativeBase):
    pass


class Practice(Base):
    __tablename__ = "practice"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)

    import_runs: Mapped[list[ImportRun]] = relationship(back_populates="practice")


class ImportRun(Base):
    """One imported billing file for one practice and quarter, with its check results."""

    __tablename__ = "import_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    practice_id: Mapped[int] = mapped_column(ForeignKey("practice.id"))
    quarter: Mapped[str] = mapped_column(String(6))
    file_name: Mapped[str] = mapped_column(String(255))
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    point_value: Mapped[Decimal] = mapped_column(DecimalText)
    case_count: Mapped[int]
    revenue: Mapped[Decimal] = mapped_column(DecimalText)

    practice: Mapped[Practice] = relationship(back_populates="import_runs")
    services: Mapped[list[ServiceRecord]] = relationship(
        back_populates="import_run", cascade="all, delete-orphan"
    )
    findings: Mapped[list[FindingRecord]] = relationship(
        back_populates="import_run", cascade="all, delete-orphan"
    )
    row_errors: Mapped[list[RowErrorRecord]] = relationship(
        back_populates="import_run", cascade="all, delete-orphan"
    )


class ServiceRecord(Base):
    __tablename__ = "billed_service"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_run.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(50))
    service_date: Mapped[date] = mapped_column(Date)
    code: Mapped[str] = mapped_column(String(5))
    quantity: Mapped[int]

    import_run: Mapped[ImportRun] = relationship(back_populates="services")


class FindingRecord(Base):
    __tablename__ = "finding"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_run.id"), index=True)
    rule: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(DecimalText)
    patient_id: Mapped[str | None] = mapped_column(String(50))

    import_run: Mapped[ImportRun] = relationship(back_populates="findings")


class RowErrorRecord(Base):
    __tablename__ = "import_error"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_run.id"), index=True)
    line_number: Mapped[int]
    message: Mapped[str] = mapped_column(String(500))

    import_run: Mapped[ImportRun] = relationship(back_populates="row_errors")


def make_engine(url: str) -> Engine:
    return create_engine(url)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def upgrade(url: str) -> None:
    """Bring the database at ``url`` to the latest schema via Alembic migrations."""
    command.upgrade(alembic_config(url), "head")

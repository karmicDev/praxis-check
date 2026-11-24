# Praxis-Check

A small billing-controlling tool for medical practices: it imports a quarterly
billing export, checks it against a set of transparent rules, and turns the
findings into a readable report.

The idea behind it: a practice bills several thousand individual services per
quarter. Supplements that were never claimed go unnoticed, and combinations of
billing codes that exclude each other only surface during an audit. Both can be
found automatically.

## What it does

1. **Import** a quarterly billing export from CSV. Broken lines are reported, not fatal.
2. **Check** it with a rule engine, looking for
   - companion codes that are missing (lost revenue),
   - codes billed on the same day although they exclude one another (audit risk),
   - notable deviations from the specialty group average, in either direction.
3. **Store** every import run with its services, findings and skipped lines in SQLite.
4. **Report** the results on a dashboard and in a printable report per practice and quarter,
   with the estimated amount at stake for every finding.
5. **Automate** the whole process from the command line, e.g. in a nightly job.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). Python itself is provisioned by uv in
the pinned version.

```bash
uv sync
uv run praxis-check serve          # http://127.0.0.1:8000
```

Open *Check a quarter*, upload `sample_data/practice_2026Q4.csv`, and you get the
report. The JSON API is documented at `/docs`.

Without the browser:

```bash
uv run praxis-check generate-sample export.csv --patients 400 --seed 42
uv run praxis-check run export.csv --practice "Praxis Dr. Muster" --quarter 2026Q4
```

`run` prints a summary and exits with `2` if the file cannot be read, and with `3`
if `--fail-on-findings` is set and something was found. The database defaults to
`praxis_check.db` in the working directory; set `PRAXIS_CHECK_DATABASE_URL` or
`--database` to change it.

## How it is built

```
src/praxis_check/
├── quarter.py, billing_code.py,      domain model: immutable dataclasses
│   billed_service.py,                that validate themselves
│   treatment_case.py
├── importer.py                       CSV → treatment cases, per-row errors
├── rules.py                          Finding, Rule protocol, three generic rule types, check()
├── general_practice.py               point value, group averages and the concrete rule set
├── sample_data.py                    synthetic data generator with planted irregularities
├── db.py, migrations/                SQLAlchemy 2.0 schema, Alembic migrations
├── repository.py, pipeline.py        save and load runs; import → check → store
├── web.py, templates/                FastAPI: JSON API and Jinja2 pages
└── cli.py                            typer command line
```

Design decisions:

- **The domain model has no dependencies.** Rules work on plain `TreatmentCase`
  objects, not on database rows, so they are tested without a database, and the
  same rules give the same result on cases loaded back from SQLite (there is a test
  for exactly that).
- **Rules are data plus a small type.** `MissingCompanion`, `SameDayExclusion` and
  `GroupAverageDeviation` are generic; which codes they apply to lives in
  `general_practice.py`. A new rule of a known kind is one line.
- **Money is `Decimal`, never `float`**, rounded per billing code to whole cents.
  SQLite has no exact decimal type, so amounts are stored as text through a small
  `TypeDecorator`.
- **Server-side rendering, no JavaScript framework.** The application targets a
  handful of users in their daily work; Jinja2 and a classless stylesheet keep it
  small and maintainable.
- **Schema changes go through Alembic.** The app migrates on start, and a test
  fails if the models and the migrations drift apart.

## Stack

| Area | Used |
|---|---|
| Language | Python 3.14 |
| Web | FastAPI, Pydantic |
| UI | Jinja2, server-rendered, Pico.css |
| Storage | SQLite with SQLAlchemy 2.0, migrations via Alembic |
| Command line | typer |
| Tests | pytest |
| Format and lint | ruff |
| Project and environment | uv |
| CI | GitHub Actions |

## Development

```bash
uv run pytest                                                # tests
uv run pytest --cov=praxis_check --cov-report=term-missing   # with coverage
uv run ruff format .                                          # format
uv run ruff check .                                           # lint
uv run alembic revision --autogenerate -m "..."               # new migration
```

Every push to `main` and every pull request runs the same checks on GitHub
Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Working with an AI assistant

I wrote the foundation by hand to refresh my Python: the project setup, the domain
model and the CSV import. From the sample data generator onwards, Claude wrote the
code following [`CLAUDE.md`](CLAUDE.md), one step at a time; I reviewed every change,
asked for corrections where needed, and committed it myself.

## Data and privacy

This project works exclusively with **synthetic data**. It contains no real
billing, practice, or patient data; the sample file is generated by
`praxis-check generate-sample`.

Billing codes, points, point value and group averages are **placeholders** inspired
by the EBM, not the current fee schedule. The rules are intentionally simplified.
They demonstrate the approach and are not a substitute for an actual billing audit.

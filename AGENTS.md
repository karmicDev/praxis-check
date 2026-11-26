# AGENTS.md

Guidance for AI coding assistants working on this repository (Claude Code reads it via CLAUDE.md, Codex reads it directly).

## Project

Praxis-Check imports a practice's quarterly billing export (CSV), checks it with a rule
engine and shows the findings in a web UI. Synthetic data only. See README.md.

## Commands

- `uv sync`: set up the environment
- `uv run pytest`: run all tests; must pass before a change is done
- `uv run ruff format . && uv run ruff check .`: format and lint; must be clean
- `uv run praxis-check serve`: run the web app locally
- `uv run alembic revision --autogenerate -m "<message>"`: new migration after a model change

## Rules

- One task at a time. No refactorings outside the task; mention them instead.
- Plan first for anything beyond a small fix, and wait for approval.
- Every behaviour change comes with tests. Use `pytest.mark.parametrize` for variants.
- Do not run git commands. The maintainer reviews, commits and pushes.
- English identifiers, comments and docs. Domain terms are translated, e.g.
  GOP → `BillingCode`, Behandlungsfall → `TreatmentCase`, Befund → `Finding`.
- User-facing text is German: templates, rule titles and explanations, finding messages
  and import errors. Numbers and money in German format (`euro`, `german_number`).

## Architecture

- Domain types (`quarter`, `billing_code`, `billed_service`, `treatment_case`) are frozen
  dataclasses without dependencies. They validate in `__post_init__`.
- Rules operate on domain types only, never on database rows or HTTP objects.
- New rules: prefer configuring an existing rule type in `general_practice.py`; add a
  new rule type in `rules.py` only if none fits.
- Money is always `Decimal`. Round per billing code with `BillingCode.amount`. Never `float`.
- Database access goes through `repository.py`, with SQLAlchemy 2.0 style
  (`Mapped`, `mapped_column`, `select()`). Never 1.x `session.query`.
- Every model change needs an Alembic migration; `test_migrations_match_the_models` checks it.
- The web layer (`web.py`) stays thin: parse input, call `pipeline`/`repository`, render.
- Styling lives in `static/app.css`, no CSS framework and no JavaScript framework.

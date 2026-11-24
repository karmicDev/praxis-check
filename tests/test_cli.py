from pathlib import Path

from typer.testing import CliRunner

from praxis_check.cli import EXIT_FINDINGS, EXIT_UNREADABLE_FILE, app

runner = CliRunner()


def test_generate_sample_then_run(tmp_path: Path, database_url: str) -> None:
    csv_file = tmp_path / "export.csv"

    generated = runner.invoke(app, ["generate-sample", str(csv_file), "--patients", "50"])
    checked = runner.invoke(
        app,
        [
            "run",
            str(csv_file),
            "--practice",
            "Praxis",
            "--quarter",
            "2026Q4",
            "--database",
            database_url,
        ],
    )

    assert generated.exit_code == 0, generated.output
    assert checked.exit_code == 0, checked.output
    assert "Cases:          50" in checked.output


def test_fail_on_findings_sets_exit_code(tmp_path: Path, database_url: str) -> None:
    csv_file = tmp_path / "export.csv"
    runner.invoke(app, ["generate-sample", str(csv_file)])

    result = runner.invoke(
        app,
        [
            "run",
            str(csv_file),
            "--practice",
            "Praxis",
            "--quarter",
            "2026Q4",
            "--database",
            database_url,
            "--fail-on-findings",
        ],
    )

    assert result.exit_code == EXIT_FINDINGS


def test_unreadable_file_sets_exit_code(tmp_path: Path, database_url: str) -> None:
    csv_file = tmp_path / "broken.csv"
    csv_file.write_text("nothing,useful\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run",
            str(csv_file),
            "--practice",
            "Praxis",
            "--quarter",
            "2026Q4",
            "--database",
            database_url,
        ],
    )

    assert result.exit_code == EXIT_UNREADABLE_FILE


def test_invalid_quarter_is_rejected(tmp_path: Path) -> None:
    result = runner.invoke(app, ["generate-sample", str(tmp_path / "x.csv"), "--quarter", "Q4"])

    assert result.exit_code != 0

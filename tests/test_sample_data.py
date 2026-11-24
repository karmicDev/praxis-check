import random
from pathlib import Path

import pytest

from praxis_check.importer import import_services
from praxis_check.quarter import Quarter
from praxis_check.sample_data import (
    SAMPLE_CATALOG,
    SAMPLE_CODES,
    generate_rows,
    write_rows,
)

QUARTER = Quarter(2026, 4)


def rows(seed: int = 42, patients: int = 200, invalid_row_rate: float = 0.0) -> list[dict]:
    return list(generate_rows(random.Random(seed), QUARTER, patients, invalid_row_rate))


def test_catalog_contains_every_sample_code() -> None:
    assert len(SAMPLE_CATALOG) == len(SAMPLE_CODES) == 7


def test_catalog_key_equals_code() -> None:
    for code, billing_code in SAMPLE_CATALOG.items():
        assert code == billing_code.code


def test_same_seed_gives_same_rows() -> None:
    assert rows(seed=7) == rows(seed=7)


def test_different_seed_gives_different_rows() -> None:
    assert rows(seed=7) != rows(seed=8)


def test_every_patient_gets_the_flat_rate() -> None:
    generated = rows(patients=50)
    patients = {row["patient_id"] for row in generated}
    with_flat_rate = {row["patient_id"] for row in generated if row["code"] == "03000"}
    assert len(patients) == 50
    assert with_flat_rate == patients


def test_zero_patients_give_no_rows() -> None:
    assert rows(patients=0) == []


def test_negative_patient_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        list(generate_rows(random.Random(1), QUARTER, -1))


@pytest.mark.parametrize("rate", [-0.1, 1.1])
def test_invalid_row_rate_out_of_range_is_rejected(rate: float) -> None:
    with pytest.raises(ValueError):
        list(generate_rows(random.Random(1), QUARTER, 10, rate))


def test_generated_file_imports_without_errors(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    count = write_rows(path, generate_rows(random.Random(42), QUARTER, 200))

    result = import_services(path, QUARTER, SAMPLE_CATALOG)

    assert result.errors == ()
    assert len(result.cases) == 200
    assert sum(len(case.services) for case in result.cases) == count


def test_corrupted_rows_are_reported_by_the_importer(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    write_rows(path, generate_rows(random.Random(42), QUARTER, 200, invalid_row_rate=0.05))

    result = import_services(path, QUARTER, SAMPLE_CATALOG)

    assert len(result.errors) > 0


def test_planted_irregularities_are_present() -> None:
    generated = rows(patients=400)
    codes_by_patient: dict[str, set[str]] = {}
    for row in generated:
        codes_by_patient.setdefault(row["patient_id"], set()).add(row["code"])

    assert any("03040" not in codes for codes in codes_by_patient.values())
    assert any("03220" in codes and "03221" not in codes for codes in codes_by_patient.values())

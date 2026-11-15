from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from praxis_check.quarter import Quarter


@pytest.mark.parametrize("number", [1, 4])
def test_valid_number_is_accepted(number: int) -> None:
    assert Quarter(2026, number).number == number


@pytest.mark.parametrize("number", [0, 5, -1])
def test_number_out_of_range_raises(number: int) -> None:
    with pytest.raises(ValueError):
        Quarter(2026, number)


def test_quarter_is_immutable() -> None:
    quarter = Quarter(2026, 4)
    with pytest.raises(FrozenInstanceError):
        quarter.year = 2027  # type: ignore[misc]


def test_parse_reads_year_and_number() -> None:
    assert Quarter.parse("2026Q4") == Quarter(2026, 4)


@pytest.mark.parametrize(
    "text", ["", "26Q3", "2026-3", "2026q3", "abcdQ3", "2026Q²", " 2026Q3", "2026Q3 ", "2026Q0"]
)
def test_parse_invalid_format_raises(text: str) -> None:
    with pytest.raises(ValueError):
        Quarter.parse(text)


def test_str_round_trips_with_parse() -> None:
    assert str(Quarter.parse("2026Q3")) == "2026Q3"


@pytest.mark.parametrize(
    ("number", "start", "end"),
    [
        (1, date(2026, 1, 1), date(2026, 3, 31)),
        (2, date(2026, 4, 1), date(2026, 6, 30)),
        (3, date(2026, 7, 1), date(2026, 9, 30)),
        (4, date(2026, 10, 1), date(2026, 12, 31)),
    ],
)
def test_start_and_end(number: int, start: date, end: date) -> None:
    quarter = Quarter(2026, number)
    assert quarter.start == start
    assert quarter.end == end


@pytest.mark.parametrize("day", [date(2026, 10, 1), date(2026, 11, 15), date(2026, 12, 31)])
def test_date_in_quarter(day: date) -> None:
    assert day in Quarter(2026, 4)


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 9, 30),  # day before
        date(2027, 1, 1),  # day after
        date(2025, 10, 1),  # same month, previous year
    ],
)
def test_date_not_in_quarter(day: date) -> None:
    assert day not in Quarter(2026, 4)


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (Quarter(2026, 1), Quarter(2026, 2)),
        (Quarter(2026, 2), Quarter(2026, 3)),
        (Quarter(2026, 3), Quarter(2026, 4)),
        (Quarter(2026, 4), Quarter(2027, 1)),
    ],
)
def test_next(current: Quarter, expected: Quarter) -> None:
    assert current.next() == expected

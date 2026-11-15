from dataclasses import dataclass
from datetime import date, timedelta
from typing import Self


@dataclass(frozen=True)
class Quarter:
    year: int
    number: int

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 4:
            raise ValueError(f"Quarter number must be between 1 and 4: {self.number}")

    @classmethod
    def parse(cls, text: str) -> Self:
        """Create a Quarter from text like '2026Q3'."""
        if len(text) != 6 or text[4] != "Q" or not text[:4].isdecimal() or not text[5].isdecimal():
            raise ValueError(f"Expected format YYYYQn, got {text!r}")

        return cls(year=int(text[:4]), number=int(text[5]))

    def __str__(self) -> str:
        return f"{self.year}Q{self.number}"

    def __contains__(self, day: date) -> bool:
        return self.start <= day <= self.end

    @property
    def start(self) -> date:
        return date(self.year, 3 * (self.number - 1) + 1, 1)

    @property
    def end(self) -> date:
        return self.next().start - timedelta(days=1)

    def next(self) -> Self:
        if self.number == 4:
            return type(self)(self.year + 1, 1)
        return type(self)(self.year, self.number + 1)

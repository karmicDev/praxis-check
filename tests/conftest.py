from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from praxis_check.db import make_engine, make_session_factory, upgrade


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'test.db'}"
    upgrade(url)
    return url


@pytest.fixture
def session(database_url: str) -> Iterator[Session]:
    engine = make_engine(database_url)
    with make_session_factory(engine)() as session:
        yield session
    engine.dispose()

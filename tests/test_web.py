from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from praxis_check.web import create_app, default_quarter, euro

SAMPLE = Path(__file__).parent.parent / "sample_data" / "practice_2026Q4.csv"


@pytest.fixture
def client(database_url: str) -> TestClient:
    return TestClient(create_app(database_url))


def upload(client: TestClient, path: str = "/api/runs", **form: str):
    data = {"practice": "Praxis Dr. Muster", "quarter": "2026Q4", **form}
    with SAMPLE.open("rb") as file:
        return client.post(path, data=data, files={"file": ("export.csv", file, "text/csv")})


def test_api_lists_no_runs_initially(client: TestClient) -> None:
    assert client.get("/api/runs").json() == []


def test_api_upload_creates_a_run(client: TestClient) -> None:
    response = upload(client)

    assert response.status_code == 201
    run = response.json()
    assert run["practice"] == "Praxis Dr. Muster"
    assert run["file_name"] == "export.csv"
    assert run["case_count"] == 400
    assert run["finding_count"] == len(run["findings"]) > 0
    assert run["row_errors"]
    assert client.get("/api/runs").json()[0]["id"] == run["id"]
    assert client.get(f"/api/runs/{run['id']}").json() == run


def test_api_rejects_invalid_quarter(client: TestClient) -> None:
    response = upload(client, quarter="Q4/2026")

    assert response.status_code == 422
    assert client.get("/api/runs").json() == []


def test_api_rejects_unreadable_file(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        data={"practice": "Praxis", "quarter": "2026Q4"},
        files={"file": ("x.csv", b"just,nonsense\n", "text/csv")},
    )

    assert response.status_code == 422
    assert "could not be read" in response.json()["detail"]


def test_api_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/api/runs/999").status_code == 404


def test_html_upload_redirects_to_report(client: TestClient) -> None:
    response = upload(client, "/upload")

    assert response.status_code == 200
    assert response.url.path.startswith("/runs/")
    assert "Praxis Dr. Muster, 2026Q4" in response.text
    assert "Lost revenue" in response.text


def test_html_upload_error_keeps_the_form_values(client: TestClient) -> None:
    response = upload(client, "/upload", quarter="2026Q9")

    assert response.status_code == 422
    assert "Could not import" in response.text
    assert 'value="Praxis Dr. Muster"' in response.text


def test_dashboard_lists_runs(client: TestClient) -> None:
    assert "No quarter has been checked yet" in client.get("/").text

    upload(client)

    assert "Praxis Dr. Muster" in client.get("/").text


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Decimal(0), "0,00 €"),
        (Decimal("1234.5"), "1.234,50 €"),
        (Decimal(1000000), "1.000.000,00 €"),
    ],
)
def test_euro(value: Decimal, text: str) -> None:
    assert euro(value) == text


@pytest.mark.parametrize(
    ("today", "quarter"),
    [(datetime(2026, 11, 24), "2026Q3"), (datetime(2026, 2, 1), "2025Q4")],
)
def test_default_quarter_is_the_previous_one(today: datetime, quarter: str) -> None:
    assert default_quarter(today) == quarter

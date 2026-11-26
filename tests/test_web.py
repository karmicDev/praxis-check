from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from praxis_check.rules import FindingKind
from praxis_check.web import (
    Balance,
    FindingOut,
    RunSummary,
    create_app,
    default_quarter,
    euro,
    group_by_rule,
    quarter_label,
)

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
    assert "konnte nicht gelesen werden" in response.json()["detail"]


def test_api_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/api/runs/999").status_code == 404


def test_html_upload_redirects_to_report(client: TestClient) -> None:
    response = upload(client, "/upload")

    assert response.status_code == 200
    assert response.url.path.startswith("/runs/")
    assert "Praxis Dr. Muster" in response.text
    assert "4. Quartal 2026" in response.text
    assert "Zuschlag zur Versichertenpauschale fehlt" in response.text


def test_html_upload_error_keeps_the_form_values(client: TestClient) -> None:
    response = upload(client, "/upload", quarter="2026Q9")

    assert response.status_code == 422
    assert "Import fehlgeschlagen" in response.text
    assert 'value="Praxis Dr. Muster"' in response.text


def test_dashboard_lists_runs(client: TestClient) -> None:
    assert "Noch kein Quartal geprüft" in client.get("/").text

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


def test_quarter_label() -> None:
    assert quarter_label("2026Q4") == "4. Quartal 2026"


def test_static_stylesheet_is_served(client: TestClient) -> None:
    assert client.get("/static/app.css").status_code == 200


def summary(revenue: str, lost: str, risk: str) -> RunSummary:
    return RunSummary(
        id=1,
        practice="P",
        quarter="2026Q4",
        file_name="f.csv",
        imported_at=datetime(2026, 11, 1),
        case_count=1,
        revenue=Decimal(revenue),
        finding_count=0,
        lost_revenue=Decimal(lost),
        audit_risk=Decimal(risk),
    )


def test_balance_splits_the_bar() -> None:
    balance = Balance.of(summary("75", "25", "25"))

    assert (balance.secure, balance.at_risk, balance.missing) == (50.0, 25.0, 25.0)


def test_balance_caps_risk_at_revenue_and_handles_zero() -> None:
    assert Balance.of(summary("10", "0", "50")).at_risk == 100.0
    assert Balance.of(summary("0", "0", "0")).secure == 0


def test_findings_are_grouped_by_rule_largest_total_first() -> None:
    def finding(rule: str, amount: str, patient: str | None = "p1") -> FindingOut:
        return FindingOut(
            rule=rule,
            kind=FindingKind.LOST_REVENUE,
            message="m",
            amount=Decimal(amount),
            patient_id=patient,
        )

    groups = group_by_rule(
        [
            finding("missing-primary-care-supplement", "5"),
            finding("missing-chronic-care-2", "8"),
            finding("missing-primary-care-supplement", "5"),
        ]
    )

    assert [(g.rule, g.total, len(g.findings)) for g in groups] == [
        ("missing-primary-care-supplement", Decimal(10), 2),
        ("missing-chronic-care-2", Decimal(8), 1),
    ]
    assert groups[0].title == "Zuschlag zur Versichertenpauschale fehlt"
    assert groups[0].per_case

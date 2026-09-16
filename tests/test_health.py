from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import health
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_returns_200_with_build_info(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["environment"] == "test"
    assert response.headers["X-Correlation-Id"]


def test_health_echoes_supplied_correlation_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Correlation-Id": "abc-123"})

    assert response.headers["X-Correlation-Id"] == "abc-123"


def test_ready_returns_200_when_database_reachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "check_database", lambda: None)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["database"] == "up"


def test_ready_returns_503_when_database_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail() -> None:
        raise RuntimeError("no database")

    monkeypatch.setattr(health, "check_database", fail)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["database"] == "down"


def test_readiness_failure_is_documented_in_openapi(client: TestClient) -> None:
    responses = client.get("/openapi.json").json()["paths"]["/ready"]["get"]["responses"]

    assert set(responses) >= {"200", "503"}

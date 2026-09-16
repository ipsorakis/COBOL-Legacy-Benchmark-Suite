import json
import logging
from collections.abc import Iterator
from io import StringIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter
from app.core.middleware import CorrelationIdMiddleware


@pytest.fixture
def failing_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("exploded")

    return app


@pytest.fixture
def json_logs() -> Iterator[StringIO]:
    """Capture records as rendered JSON, i.e. formatted while the log context is still bound."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app.core.middleware")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)


def test_failed_request_is_logged_with_correlation_context(
    failing_app: FastAPI, json_logs: StringIO
) -> None:
    client = TestClient(failing_app, raise_server_exceptions=False)

    response = client.get("/boom", headers={"X-Correlation-Id": "cid-err"})

    assert response.status_code == 500
    payload = json.loads(json_logs.getvalue().splitlines()[-1])
    assert payload["level"] == "ERROR"
    assert payload["correlation_id"] == "cid-err"
    assert payload["program_id"] == "BOOM"
    assert payload["http_status"] is None
    assert "RuntimeError: exploded" in payload["exception"]

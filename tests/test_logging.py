import json
import logging

from app.core.context import log_context
from app.core.logging import JsonFormatter


def test_json_formatter_includes_errlog_context() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="position update failed for %s",
        args=("P0001",),
        exc_info=None,
    )

    with log_context(correlation_id="cid-1", program_id="POSUPD00", user_id="USER0001"):
        payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "position update failed for P0001"
    assert payload["correlation_id"] == "cid-1"
    assert payload["program_id"] == "POSUPD00"
    assert payload["user_id"] == "USER0001"
    assert payload["severity"] == 3
    assert payload["process_date"] and payload["process_time"]


def test_log_context_is_restored_on_exit() -> None:
    with log_context(program_id="INQPORT"):
        pass

    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "done", None, None)
    assert json.loads(JsonFormatter().format(record))["program_id"] is None

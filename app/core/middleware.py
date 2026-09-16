import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import log_context

CORRELATION_ID_HEADER = "X-Correlation-Id"

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Binds a correlation id and the route's program identifier to the log context."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid4())
        started = time.perf_counter()
        with log_context(correlation_id=correlation_id, program_id=_program_id(request)):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "%s %s failed",
                    request.method,
                    request.url.path,
                    extra=_request_fields(request, started, None),
                )
                raise
            logger.info(
                "%s %s %s",
                request.method,
                request.url.path,
                response.status_code,
                extra=_request_fields(request, started, response.status_code),
            )
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response


def _request_fields(request: Request, started: float, status_code: int | None) -> dict[str, object]:
    return {
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _program_id(request: Request) -> str:
    """Derive an 8-character program-equivalent identifier from the request path."""
    segments = [segment for segment in request.url.path.split("/") if segment]
    return segments[0][:8].upper() if segments else "ROOT"

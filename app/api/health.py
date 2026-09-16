import logging

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.database import check_database
from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    name: str
    version: str
    environment: str


class ReadinessResponse(HealthResponse):
    database: str


def _build_info(settings: Settings, status_value: str) -> dict[str, str]:
    return {
        "status": status_value,
        "name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
    }


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(**_build_info(get_settings(), "ok"))


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "The database is unreachable.",
        }
    },
)
def ready(response: Response) -> ReadinessResponse:
    settings = get_settings()
    try:
        check_database()
    except Exception:
        logger.exception("Readiness check failed: database unavailable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(**_build_info(settings, "unavailable"), database="down")
    return ReadinessResponse(**_build_info(settings, "ok"), database="up")

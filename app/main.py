import logging

from fastapi import FastAPI

from app.api import health
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.version)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)

    logging.getLogger(__name__).info(
        "Application initialised",
        extra={"environment": settings.environment, "log_level": settings.log_level},
    )
    return app


app = create_app()

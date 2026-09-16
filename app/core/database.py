from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.core.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_pre_ping=True,
    )


def check_database() -> None:
    """Raise if the database is unreachable."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))

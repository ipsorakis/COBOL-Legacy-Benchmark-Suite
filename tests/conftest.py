import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

os.environ.setdefault("IPMS_ENVIRONMENT", "test")
os.environ.setdefault("IPMS_LOG_LEVEL", "WARNING")

from app.models import Base, PortfolioMaster  # noqa: E402
from tests.factories import DataFactory, DataSet, ErrorScenario, error_scenarios  # noqa: E402


@pytest.fixture
def data_factory() -> DataFactory:
    """Seeded generator of canonical-model rows (TSTGEN00 port)."""
    return DataFactory()


@pytest.fixture
def portfolio(data_factory: DataFactory) -> PortfolioMaster:
    """A single active portfolio."""
    return data_factory.portfolio(status="A")


@pytest.fixture
def scenarios() -> list[ErrorScenario]:
    """Every error condition TSTGEN00 generates under CFG-TEST-TYPE 'ERROR'."""
    return error_scenarios()


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    """In-memory SQLite engine with the canonical schema and foreign keys enforced."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(connection: DBAPIConnection, record: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session


class Persist:
    """Callable that writes a generated data set to the test database."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self, data_set: DataSet) -> DataSet:
        self.session.add_all(data_set.rows())
        self.session.commit()
        return data_set


@pytest.fixture
def persist(db_session: Session) -> Persist:
    return Persist(db_session)

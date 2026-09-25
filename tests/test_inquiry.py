from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_session
from app.main import create_app
from app.models import Base, InvestmentPosition, PortfolioMaster
from app.services.portfolio_inquiry import (
    POSITION_NOT_FOUND_MESSAGE,
    PositionNotFoundError,
    inquire_portfolio,
)

PORTFOLIO_ID = "PORT0001"
EARLIER = date(2024, 3, 19)
LATEST = date(2024, 3, 20)


def _portfolio(portfolio_id: str = PORTFOLIO_ID) -> PortfolioMaster:
    return PortfolioMaster(
        portfolio_id=portfolio_id,
        account_type="IN",
        branch_id="01",
        client_id="CLIENT0001",
        portfolio_name="Growth portfolio",
        currency_code="USD",
        risk_level="M",
        status="A",
        open_date=date(2024, 1, 1),
        close_date=None,
        last_maint_date=datetime(2024, 3, 20, 9, 30),
        last_maint_user="USER0001",
    )


def _position(
    investment_id: str,
    position_date: date,
    *,
    portfolio_id: str = PORTFOLIO_ID,
    quantity: str = "100.0000",
    cost_basis: str = "1000.00",
    market_value: str = "1250.00",
) -> InvestmentPosition:
    return InvestmentPosition(
        portfolio_id=portfolio_id,
        investment_id=investment_id,
        position_date=position_date,
        quantity=Decimal(quantity),
        cost_basis=Decimal(cost_basis),
        market_value=Decimal(market_value),
        currency_code="USD",
        last_maint_date=datetime(2024, 3, 20, 9, 30),
        last_maint_user="USER0001",
    )


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add(_portfolio())
        session.add(_portfolio("PORT0002"))
        session.add_all(
            [
                _position("FUND000002", LATEST, cost_basis="2000.00", market_value="1800.00"),
                _position("FUND000001", LATEST),
                _position("FUND000001", EARLIER, market_value="1100.00"),
            ]
        )
        session.commit()
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as active_session:
        yield active_session


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app()

    def override_session() -> Iterator[Session]:
        with session_factory() as active_session:
            yield active_session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client


def test_inquiry_defaults_to_the_latest_position_date(session: Session) -> None:
    inquiry = inquire_portfolio(session, PORTFOLIO_ID)

    assert inquiry.position_date == LATEST
    assert [position.investment_id for position in inquiry.positions] == [
        "FUND000001",
        "FUND000002",
    ]


def test_inquiry_reads_an_explicit_position_date(session: Session) -> None:
    inquiry = inquire_portfolio(session, PORTFOLIO_ID, EARLIER)

    assert [position.market_value for position in inquiry.positions] == [Decimal("1100.00")]


def test_inquiry_totals_use_decimal_arithmetic(session: Session) -> None:
    inquiry = inquire_portfolio(session, PORTFOLIO_ID)

    assert inquiry.total_cost_basis == Decimal("3000.00")
    assert inquiry.total_market_value == Decimal("3050.00")


def test_inquiry_ignores_other_portfolios(session: Session) -> None:
    with pytest.raises(PositionNotFoundError):
        inquire_portfolio(session, "PORT0002")


def test_inquiry_raises_when_the_date_has_no_positions(session: Session) -> None:
    with pytest.raises(PositionNotFoundError):
        inquire_portfolio(session, PORTFOLIO_ID, date(2024, 1, 2))


def test_endpoint_returns_current_positions(client: TestClient) -> None:
    response = client.get(f"/inquiry/portfolio/{PORTFOLIO_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["position_date"] == LATEST.isoformat()
    assert body["response_code"] == 0
    assert body["total_market_value"] == "3050.00"
    assert [position["investment_id"] for position in body["positions"]] == [
        "FUND000001",
        "FUND000002",
    ]


def test_endpoint_filters_by_position_date(client: TestClient) -> None:
    response = client.get(
        f"/inquiry/portfolio/{PORTFOLIO_ID}", params={"position_date": EARLIER.isoformat()}
    )

    assert response.status_code == 200
    assert response.json()["positions"][0]["market_value"] == "1100.00"


def test_endpoint_returns_notfnd_payload_for_unknown_portfolio(client: TestClient) -> None:
    response = client.get("/inquiry/portfolio/NOSUCH01")

    assert response.status_code == 404
    assert response.json() == {
        "response_code": 13,
        "error_message": POSITION_NOT_FOUND_MESSAGE,
    }


def test_endpoint_rejects_a_portfolio_id_longer_than_the_legacy_key(client: TestClient) -> None:
    response = client.get("/inquiry/portfolio/PORT00012")

    assert response.status_code == 422


def test_endpoint_is_documented_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/inquiry/portfolio/{portfolio_id}"]["get"]["responses"]) >= {"200", "404"}

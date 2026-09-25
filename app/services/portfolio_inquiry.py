"""Portfolio position inquiry, ported from the CICS program INQPORT."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InvestmentPosition

POSITION_NOT_FOUND_MESSAGE = "Position not found for account"


class PositionNotFoundError(Exception):
    """No position row exists for the requested portfolio, equivalent to CICS NOTFND."""

    def __init__(self, portfolio_id: str, position_date: date | None = None) -> None:
        super().__init__(POSITION_NOT_FOUND_MESSAGE)
        self.portfolio_id = portfolio_id
        self.position_date = position_date


@dataclass(frozen=True)
class PortfolioInquiry:
    portfolio_id: str
    position_date: date
    positions: list[InvestmentPosition]

    @property
    def total_cost_basis(self) -> Decimal:
        return sum((position.cost_basis for position in self.positions), Decimal("0"))

    @property
    def total_market_value(self) -> Decimal:
        return sum((position.market_value for position in self.positions), Decimal("0"))


def inquire_portfolio(
    session: Session, portfolio_id: str, position_date: date | None = None
) -> PortfolioInquiry:
    """Read the positions of one portfolio for a single position date.

    Replaces the keyed VSAM ``READ FILE('POSFILE') RIDFLD(...)`` with a keyed
    ``SELECT``. Without an explicit date the most recent position date on file is used,
    matching INQPORT's "current positions" inquiry.
    """
    effective_date = position_date or _latest_position_date(session, portfolio_id)
    if effective_date is None:
        raise PositionNotFoundError(portfolio_id)

    positions = list(
        session.scalars(
            select(InvestmentPosition)
            .where(
                InvestmentPosition.portfolio_id == portfolio_id,
                InvestmentPosition.position_date == effective_date,
            )
            .order_by(InvestmentPosition.investment_id)
        )
    )
    if not positions:
        raise PositionNotFoundError(portfolio_id, effective_date)

    return PortfolioInquiry(
        portfolio_id=portfolio_id, position_date=effective_date, positions=positions
    )


def _latest_position_date(session: Session, portfolio_id: str) -> date | None:
    return session.scalar(
        select(InvestmentPosition.position_date)
        .where(InvestmentPosition.portfolio_id == portfolio_id)
        .order_by(InvestmentPosition.position_date.desc())
        .limit(1)
    )

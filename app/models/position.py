from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Date, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, LastMaintenanceMixin

if TYPE_CHECKING:
    from app.models.portfolio import PortfolioMaster


class InvestmentPosition(LastMaintenanceMixin, Base):
    """INVESTMENT_POSITIONS: one row per portfolio, investment and position date."""

    __tablename__ = "investment_positions"
    __table_args__ = (Index("idx_positions_date", "position_date", "portfolio_id"),)

    portfolio_id: Mapped[str] = mapped_column(
        CHAR(8), ForeignKey("portfolio_master.portfolio_id"), primary_key=True
    )
    investment_id: Mapped[str] = mapped_column(CHAR(10), primary_key=True)
    position_date: Mapped[date] = mapped_column(Date, primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)

    portfolio: Mapped["PortfolioMaster"] = relationship(back_populates="positions")

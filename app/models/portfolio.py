from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Date, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, LastMaintenanceMixin

if TYPE_CHECKING:
    from app.models.position import InvestmentPosition
    from app.models.transaction import TransactionHistory


class PortfolioMaster(LastMaintenanceMixin, Base):
    """PORTFOLIO_MASTER: portfolio root record.

    STATUS: A=Active, C=Closed, S=Suspended.
    """

    __tablename__ = "portfolio_master"
    __table_args__ = (Index("idx_port_master_client", "client_id", "status"),)

    portfolio_id: Mapped[str] = mapped_column(CHAR(8), primary_key=True)
    account_type: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    branch_id: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    client_id: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    portfolio_name: Mapped[str] = mapped_column(String(50), nullable=False)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    risk_level: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    open_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_date: Mapped[date | None] = mapped_column(Date)

    positions: Mapped[list["InvestmentPosition"]] = relationship(back_populates="portfolio")
    transactions: Mapped[list["TransactionHistory"]] = relationship(back_populates="portfolio")

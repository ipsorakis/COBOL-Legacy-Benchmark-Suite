from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, TIMESTAMP, Date, ForeignKey, Index, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.portfolio import PortfolioMaster


class TransactionHistory(Base):
    """TRANSACTION_HISTORY: posted portfolio transactions.

    TRANSACTION_ID format: YYYYMMDDHHMMSS + 6-digit sequence.
    TRANSACTION_TYPE: BU=Buy, SL=Sell, TR=Transfer, FE=Fee.
    STATUS: P=Processed, F=Failed, R=Reversed.
    """

    __tablename__ = "transaction_history"
    __table_args__ = (
        Index("idx_trans_hist_port", "portfolio_id", "transaction_date"),
        Index("idx_trans_hist_date", "transaction_date", "portfolio_id"),
    )

    transaction_id: Mapped[str] = mapped_column(CHAR(20), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        CHAR(8), ForeignKey("portfolio_master.portfolio_id"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_time: Mapped[time] = mapped_column(Time, nullable=False)
    investment_id: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    transaction_type: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    process_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    process_user: Mapped[str] = mapped_column(String(8), nullable=False)

    portfolio: Mapped["PortfolioMaster"] = relationship(back_populates="transactions")

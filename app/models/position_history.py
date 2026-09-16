from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import CHAR, TIMESTAMP, Date, Index, Numeric, Time, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PositionHistory(Base):
    """POSHIST: partitioned DB2 history of every position-affecting transaction.

    TRANS_TYPE: BU=Buy, SL=Sell, TR=Transfer.
    """

    __tablename__ = "poshist"
    __table_args__ = (
        Index("poshist_ix1", "security_id", "trans_date"),
        Index("poshist_ix2", "process_date", "program_id"),
    )

    account_no: Mapped[str] = mapped_column(CHAR(8), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(CHAR(10), primary_key=True)
    trans_date: Mapped[date] = mapped_column(Date, primary_key=True)
    trans_time: Mapped[time] = mapped_column(Time, primary_key=True)
    trans_type: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    security_id: Mapped[str] = mapped_column(CHAR(12), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, server_default=text("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    gain_loss: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    process_date: Mapped[date] = mapped_column(Date, nullable=False)
    process_time: Mapped[time] = mapped_column(Time, nullable=False)
    program_id: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    user_id: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    audit_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )

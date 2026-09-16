"""ORM model for INVESTMENT_POSITIONS.

The VSAM copybook's POS-STATUS domain (A/C/P) has no DDL counterpart.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, TIMESTAMP, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvestmentPosition(Base):
    __tablename__ = "INVESTMENT_POSITIONS"

    portfolio_id: Mapped[str] = mapped_column(
        "PORTFOLIO_ID",
        CHAR(8),
        ForeignKey("PORTFOLIO_MASTER.PORTFOLIO_ID"),
        primary_key=True,
        nullable=False,
    )
    investment_id: Mapped[str] = mapped_column(
        "INVESTMENT_ID",
        CHAR(10),
        primary_key=True,
        nullable=False,
    )
    position_date: Mapped[date] = mapped_column(
        "POSITION_DATE",
        Date,
        primary_key=True,
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        "QUANTITY",
        Numeric(18, 4),
        nullable=False,
    )
    cost_basis: Mapped[Decimal] = mapped_column(
        "COST_BASIS",
        Numeric(18, 2),
        nullable=False,
    )
    market_value: Mapped[Decimal] = mapped_column(
        "MARKET_VALUE",
        Numeric(18, 2),
        nullable=False,
    )
    currency_code: Mapped[str] = mapped_column(
        "CURRENCY_CODE",
        CHAR(3),
        nullable=False,
    )
    last_maint_date: Mapped[datetime] = mapped_column(
        "LAST_MAINT_DATE",
        TIMESTAMP,
        nullable=False,
    )
    last_maint_user: Mapped[str] = mapped_column(
        "LAST_MAINT_USER",
        String(8),
        nullable=False,
    )

    __table_args__ = (Index("IDX_POSITIONS_DATE", "POSITION_DATE", "PORTFOLIO_ID"),)

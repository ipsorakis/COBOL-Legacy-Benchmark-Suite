"""SQLAlchemy model for the legacy DB2 PORTFOLIO_MASTER table."""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PortfolioStatus(str, enum.Enum):  # noqa: UP042
    """Legacy PORTFOLIO_MASTER.STATUS domain (db2-definitions.sql note 3)."""

    ACTIVE = "A"
    CLOSED = "C"
    SUSPENDED = "S"


class PortfolioMaster(Base):
    """Portfolio master record (DB2 table PORTFOLIO_MASTER)."""

    __tablename__ = "PORTFOLIO_MASTER"

    portfolio_id: Mapped[str] = mapped_column("PORTFOLIO_ID", CHAR(8), primary_key=True)
    account_type: Mapped[str] = mapped_column("ACCOUNT_TYPE", CHAR(2), nullable=False)
    branch_id: Mapped[str] = mapped_column("BRANCH_ID", CHAR(2), nullable=False)
    client_id: Mapped[str] = mapped_column("CLIENT_ID", CHAR(10), nullable=False)
    portfolio_name: Mapped[str] = mapped_column("PORTFOLIO_NAME", String(50), nullable=False)
    currency_code: Mapped[str] = mapped_column("CURRENCY_CODE", CHAR(3), nullable=False)
    risk_level: Mapped[str] = mapped_column("RISK_LEVEL", CHAR(1), nullable=False)
    status: Mapped[str] = mapped_column("STATUS", CHAR(1), nullable=False)
    open_date: Mapped[date] = mapped_column("OPEN_DATE", Date, nullable=False)
    close_date: Mapped[date | None] = mapped_column("CLOSE_DATE", Date, nullable=True)
    last_maint_date: Mapped[datetime] = mapped_column("LAST_MAINT_DATE", DateTime, nullable=False)
    last_maint_user: Mapped[str] = mapped_column("LAST_MAINT_USER", String(8), nullable=False)

    __table_args__ = (Index("IDX_PORT_MASTER_CLIENT", "CLIENT_ID", "STATUS"),)

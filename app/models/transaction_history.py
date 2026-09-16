"""ORM model for the legacy DB2 table TRANSACTION_HISTORY.

Mapped from ``src/database/db2/db2-definitions.sql`` (table definition and the
``IDX_TRANS_HIST_*`` indexes) and the VSAM copybook
``src/copybook/common/TRNREC.cpy``.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from enum import StrEnum
from typing import Final

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

TRANSACTION_ID_LENGTH: Final = 20
TRANSACTION_ID_TIMESTAMP_FORMAT: Final = "%Y%m%d%H%M%S"
TRANSACTION_ID_SEQUENCE_DIGITS: Final = 6
TRANSACTION_ID_MAX_SEQUENCE: Final = 10**TRANSACTION_ID_SEQUENCE_DIGITS - 1
TRANSACTION_ID_PATTERN: Final = re.compile(r"^\d{14}\d{6}$")


class TransactionType(StrEnum):
    """TRANSACTION_TYPE domain, enforced by PORTTRAN 2120-CHECK-TRANSACTION-TYPE."""

    BUY = "BU"
    SELL = "SL"
    TRANSFER = "TR"
    FEE = "FE"


class TransactionStatus(StrEnum):
    """STATUS domain.

    The DB2 DDL notes document 'P'=Processed, 'F'=Failed, 'R'=Reversed, while
    TRNREC.cpy documents 'P'=Pending, 'D'=Done, 'F'=Failed, 'R'=Reversed. Both
    sets are accepted so records migrated from VSAM round-trip unchanged.
    """

    PENDING = "P"
    DONE = "D"
    FAILED = "F"
    REVERSED = "R"


class InvalidTransactionIdError(ValueError):
    """Raised when a TRANSACTION_ID does not match the legacy format."""


def format_transaction_id(moment: dt.datetime, sequence: int) -> str:
    """Build a TRANSACTION_ID as YYYYMMDDHHMMSS followed by a 6-digit sequence."""
    if not 0 <= sequence <= TRANSACTION_ID_MAX_SEQUENCE:
        raise InvalidTransactionIdError(
            f"sequence must be between 0 and {TRANSACTION_ID_MAX_SEQUENCE}, got {sequence}"
        )
    timestamp = moment.strftime(TRANSACTION_ID_TIMESTAMP_FORMAT)
    return f"{timestamp}{sequence:0{TRANSACTION_ID_SEQUENCE_DIGITS}d}"


def parse_transaction_id(transaction_id: str) -> tuple[dt.datetime, int]:
    """Split a TRANSACTION_ID into its timestamp and sequence number."""
    value = transaction_id.strip()
    if not TRANSACTION_ID_PATTERN.match(value):
        raise InvalidTransactionIdError(
            f"TRANSACTION_ID must be 14 timestamp digits plus a "
            f"{TRANSACTION_ID_SEQUENCE_DIGITS}-digit sequence, got {transaction_id!r}"
        )
    try:
        moment = dt.datetime.strptime(
            value[:-TRANSACTION_ID_SEQUENCE_DIGITS], TRANSACTION_ID_TIMESTAMP_FORMAT
        )
    except ValueError as exc:
        raise InvalidTransactionIdError(
            f"TRANSACTION_ID has an invalid timestamp: {transaction_id!r}"
        ) from exc
    return moment, int(value[-TRANSACTION_ID_SEQUENCE_DIGITS:])


def is_valid_transaction_id(transaction_id: str) -> bool:
    """Return whether ``transaction_id`` matches the legacy TRANSACTION_ID format."""
    try:
        parse_transaction_id(transaction_id)
    except InvalidTransactionIdError:
        return False
    return True


class TransactionHistory(Base):
    """A processed portfolio transaction, keyed by the legacy TRANSACTION_ID."""

    __tablename__ = "TRANSACTION_HISTORY"
    __table_args__ = (
        CheckConstraint(
            "TRANSACTION_TYPE IN ('BU', 'SL', 'TR', 'FE')",
            name="CK_TRANS_HIST_TYPE",
        ),
        Index("IDX_TRANS_HIST_PORT", "PORTFOLIO_ID", "TRANSACTION_DATE"),
        Index("IDX_TRANS_HIST_DATE", "TRANSACTION_DATE", "PORTFOLIO_ID"),
    )

    transaction_id: Mapped[str] = mapped_column(
        "TRANSACTION_ID", CHAR(TRANSACTION_ID_LENGTH), primary_key=True
    )
    portfolio_id: Mapped[str] = mapped_column(
        "PORTFOLIO_ID",
        CHAR(8),
        ForeignKey("PORTFOLIO_MASTER.PORTFOLIO_ID"),
        nullable=False,
    )
    transaction_date: Mapped[dt.date] = mapped_column("TRANSACTION_DATE", Date, nullable=False)
    transaction_time: Mapped[dt.time] = mapped_column("TRANSACTION_TIME", Time, nullable=False)
    investment_id: Mapped[str] = mapped_column("INVESTMENT_ID", CHAR(10), nullable=False)
    transaction_type: Mapped[str] = mapped_column("TRANSACTION_TYPE", CHAR(2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column("QUANTITY", Numeric(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column("PRICE", Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column("AMOUNT", Numeric(18, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column("CURRENCY_CODE", CHAR(3), nullable=False)
    status: Mapped[str] = mapped_column("STATUS", CHAR(1), nullable=False)
    process_date: Mapped[dt.datetime] = mapped_column("PROCESS_DATE", DateTime, nullable=False)
    process_user: Mapped[str] = mapped_column("PROCESS_USER", String(8), nullable=False)

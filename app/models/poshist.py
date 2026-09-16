"""POSHIST - position (transaction) history table.

Legacy sources:
* ``src/database/db2/POSHIST.sql`` (DB2 DDL, tablespace + table + indexes)
* ``src/copybook/db2/DBTBLS.cpy`` lines 10-27 (``POSHIST-RECORD`` host variable)
* ``src/programs/batch/HISTLD00.cbl`` (``INSERT INTO POSHIST``)

Two legacy issues are resolved here; see the module comments below and the PR
description for the reasoning.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    Time,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.models.base import Base

# Identifier widths.
#
# POSHIST.sql declares ACCOUNT_NO CHAR(8) / PORTFOLIO_ID CHAR(10), the opposite
# of every other definition in the repository:
#   * db2-definitions.sql       PORTFOLIO_ID CHAR(8), CLIENT_ID CHAR(10)
#   * src/copybook/common/POSREC.cpy   POS-PORTFOLIO-ID X(08)
#   * src/copybook/common/HISTREC.cpy  HIST-PORTFOLIO-ID X(08)
#   * src/copybook/common/AUDITLOG.cpy AUD-PORTFOLIO-ID X(8), AUD-ACCOUNT-NO X(10)
# The canonical model (KAN-13) is still open, so we follow the majority and the
# sibling models: the portfolio identifier is 8 characters and the account
# number is 10.
ACCOUNT_NO_LENGTH = 10
PORTFOLIO_ID_LENGTH = 8


class TransactionType(enum.StrEnum):
    """POSHIST.TRANS_TYPE domain (``src/copybook/common/TRNREC.cpy`` 88-levels)."""

    BUY = "BU"
    SELL = "SL"
    TRANSFER = "TR"
    FEE = "FE"


class PositionHistory(Base):
    """One historical portfolio transaction, loaded by HISTLD00 and read by INQHIST."""

    __tablename__ = "POSHIST"

    account_no: Mapped[str] = mapped_column("ACCOUNT_NO", CHAR(ACCOUNT_NO_LENGTH))
    portfolio_id: Mapped[str] = mapped_column("PORTFOLIO_ID", CHAR(PORTFOLIO_ID_LENGTH))
    trans_date: Mapped[date] = mapped_column("TRANS_DATE", Date)
    trans_time: Mapped[time] = mapped_column("TRANS_TIME", Time)
    trans_type: Mapped[str] = mapped_column("TRANS_TYPE", CHAR(2))
    security_id: Mapped[str] = mapped_column("SECURITY_ID", CHAR(12))
    quantity: Mapped[Decimal] = mapped_column("QUANTITY", Numeric(15, 3))
    price: Mapped[Decimal] = mapped_column("PRICE", Numeric(15, 3))
    amount: Mapped[Decimal] = mapped_column("AMOUNT", Numeric(15, 2))
    fees: Mapped[Decimal] = mapped_column(
        "FEES", Numeric(15, 2), default=Decimal("0"), server_default=text("0")
    )
    total_amount: Mapped[Decimal] = mapped_column("TOTAL_AMOUNT", Numeric(15, 2))
    cost_basis: Mapped[Decimal] = mapped_column("COST_BASIS", Numeric(15, 2))
    gain_loss: Mapped[Decimal] = mapped_column("GAIN_LOSS", Numeric(15, 2))
    process_date: Mapped[date] = mapped_column("PROCESS_DATE", Date)
    process_time: Mapped[time] = mapped_column("PROCESS_TIME", Time)
    program_id: Mapped[str] = mapped_column("PROGRAM_ID", CHAR(8))
    user_id: Mapped[str] = mapped_column("USER_ID", CHAR(8))
    audit_timestamp: Mapped[datetime] = mapped_column(
        "AUDIT_TIMESTAMP", TIMESTAMP, server_default=func.current_timestamp()
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "ACCOUNT_NO", "PORTFOLIO_ID", "TRANS_DATE", "TRANS_TIME", name="POSHIST_PK"
        ),
        Index("POSHIST_IX1", "SECURITY_ID", "TRANS_DATE"),
        Index("POSHIST_IX2", "PROCESS_DATE", "PROGRAM_ID"),
        # DB2 range-partitions the tablespace by TRANS_DATE into fixed quarterly
        # partitions. Postgres native range partitioning would require ongoing
        # partition DDL maintenance (Epic 4) and cannot be exercised without a
        # live server, so the table stays plain and the date-range access path
        # that the partitioning served is covered by this btree index. Neither
        # POSHIST_PK (leading ACCOUNT_NO) nor POSHIST_IX1 (leading SECURITY_ID)
        # supports a TRANS_DATE-only scan.
        Index("IX_POSHIST_TRANS_DATE", "TRANS_DATE"),
        CheckConstraint(
            "TRANS_TYPE IN ('BU', 'SL', 'TR', 'FE')",
            name="POSHIST_TRANS_TYPE_CK",
        ),
    )

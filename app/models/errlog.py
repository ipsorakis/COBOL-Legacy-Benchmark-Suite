"""ERRLOG - application error log table.

Legacy sources:
* ``src/database/db2/ERRLOG.sql`` (DB2 DDL, table + indexes + cleanup procedure)
* ``src/copybook/db2/DBTBLS.cpy`` lines 34-49 (``ERRLOG-RECORD`` host variable)
* ``src/programs/common/DB2ERR.cbl`` (``INSERT INTO ERRLOG``, severity mapping)
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.models.base import Base


class ErrorType(enum.StrEnum):
    """ERRLOG.ERROR_TYPE domain (DDL comment; ``EL-TYPE-*`` 88-levels)."""

    SYSTEM = "S"
    APPLICATION = "A"
    DATA = "D"


class ErrorSeverity(enum.IntEnum):
    """ERRLOG.ERROR_SEVERITY domain (DDL comment; ``EL-SEV-*`` 88-levels)."""

    INFO = 1
    WARNING = 2
    ERROR = 3
    SEVERE = 4


class ErrorLog(Base):
    """One logged error, written by DB2ERR and read back for retry decisions."""

    __tablename__ = "ERRLOG"

    error_timestamp: Mapped[datetime] = mapped_column("ERROR_TIMESTAMP", TIMESTAMP)
    program_id: Mapped[str] = mapped_column("PROGRAM_ID", CHAR(8))
    error_type: Mapped[str] = mapped_column("ERROR_TYPE", CHAR(1))
    error_severity: Mapped[int] = mapped_column("ERROR_SEVERITY", Integer)
    error_code: Mapped[str] = mapped_column("ERROR_CODE", CHAR(8))
    error_message: Mapped[str] = mapped_column("ERROR_MESSAGE", String(200))
    process_date: Mapped[date] = mapped_column("PROCESS_DATE", Date)
    process_time: Mapped[time] = mapped_column("PROCESS_TIME", Time)
    user_id: Mapped[str] = mapped_column("USER_ID", CHAR(8))
    additional_info: Mapped[str | None] = mapped_column(
        "ADDITIONAL_INFO", String(500), nullable=True
    )

    __table_args__ = (
        PrimaryKeyConstraint("ERROR_TIMESTAMP", "PROGRAM_ID", name="ERRLOG_PK"),
        Index("ERRLOG_IX1", "PROCESS_DATE", text("ERROR_SEVERITY DESC")),
        CheckConstraint("ERROR_TYPE IN ('S', 'A', 'D')", name="ERRLOG_ERROR_TYPE_CK"),
        CheckConstraint("ERROR_SEVERITY BETWEEN 1 AND 4", name="ERRLOG_ERROR_SEVERITY_CK"),
    )

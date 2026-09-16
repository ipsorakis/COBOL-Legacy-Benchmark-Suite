"""AUDIT_LOG - audit trail table.

There is no DB2 DDL for the audit trail: legacy AUDPROC writes a fixed-length
sequential file (``AUDFILE``). The table is therefore derived from the record
layout in ``src/copybook/common/AUDITLOG.cpy`` and from its writers:
``src/programs/common/AUDPROC.cbl`` (the writer subroutine) and
``src/programs/portfolio/PORTTRAN.cbl`` paragraph 2300 (a caller that fills
every field).

Two things are worth knowing when reading this model:

* ``AUD-TIMESTAMP`` is ``PIC X(26)``, the DB2 character form of a timestamp
  (``yyyy-mm-dd-hh.mm.ss.ffffff``), populated from ``ACCEPT ... FROM TIME
  STAMP``. It is mapped to a real ``TIMESTAMP`` column.
* The copybook has no unique key. The timestamp alone is not one (two audit
  records can share a microsecond and AUDPROC does not check), and the key info
  fields are optional for ``SYST`` events, so the table gets a surrogate
  identity primary key.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.models.base import Base


class AuditType(enum.StrEnum):
    """``AUD-TYPE`` domain (``AUD-TRANSACTION`` / ``AUD-USER-ACTION`` / ``AUD-SYSTEM-EVENT``)."""

    TRANSACTION = "TRAN"
    USER_ACTION = "USER"
    SYSTEM_EVENT = "SYST"


class AuditAction(enum.StrEnum):
    """``AUD-ACTION`` domain; the copybook values are blank-padded to 8 characters."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    INQUIRE = "INQUIRE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    STARTUP = "STARTUP"
    SHUTDOWN = "SHUTDOWN"


class AuditStatus(enum.StrEnum):
    """``AUD-STATUS`` domain (``SUCC`` / ``FAIL`` / ``WARN``)."""

    SUCCESS = "SUCC"
    FAILURE = "FAIL"
    WARNING = "WARN"


class AuditLog(Base):
    """One audit trail record as written by AUDPROC."""

    __tablename__ = "AUDIT_LOG"

    audit_id: Mapped[int] = mapped_column(
        "AUDIT_ID", BigInteger, primary_key=True, autoincrement=True
    )
    audit_timestamp: Mapped[datetime] = mapped_column("AUD_TIMESTAMP", TIMESTAMP)
    system_id: Mapped[str] = mapped_column("AUD_SYSTEM_ID", CHAR(8))
    user_id: Mapped[str] = mapped_column("AUD_USER_ID", CHAR(8))
    program: Mapped[str] = mapped_column("AUD_PROGRAM", CHAR(8))
    terminal: Mapped[str] = mapped_column("AUD_TERMINAL", CHAR(8))
    audit_type: Mapped[str] = mapped_column("AUD_TYPE", CHAR(4))
    audit_action: Mapped[str] = mapped_column("AUD_ACTION", CHAR(8))
    audit_status: Mapped[str] = mapped_column("AUD_STATUS", CHAR(4))
    portfolio_id: Mapped[str | None] = mapped_column("AUD_PORTFOLIO_ID", CHAR(8), nullable=True)
    account_no: Mapped[str | None] = mapped_column("AUD_ACCOUNT_NO", CHAR(10), nullable=True)
    before_image: Mapped[str | None] = mapped_column("AUD_BEFORE_IMAGE", String(100), nullable=True)
    after_image: Mapped[str | None] = mapped_column("AUD_AFTER_IMAGE", String(100), nullable=True)
    message: Mapped[str | None] = mapped_column("AUD_MESSAGE", String(100), nullable=True)

    __table_args__ = (
        Index("AUDIT_LOG_IX1", "AUD_TIMESTAMP"),
        Index("AUDIT_LOG_IX2", "AUD_PORTFOLIO_ID", "AUD_TIMESTAMP"),
        CheckConstraint("AUD_TYPE IN ('TRAN', 'USER', 'SYST')", name="AUDIT_LOG_TYPE_CK"),
        CheckConstraint(
            "AUD_STATUS IN ('SUCC', 'FAIL', 'WARN')",
            name="AUDIT_LOG_STATUS_CK",
        ),
        CheckConstraint(
            "AUD_ACTION IN ('CREATE', 'UPDATE', 'DELETE', 'INQUIRE', "
            "'LOGIN', 'LOGOUT', 'STARTUP', 'SHUTDOWN')",
            name="AUDIT_LOG_ACTION_CK",
        ),
    )

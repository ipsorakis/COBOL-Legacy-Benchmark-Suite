from datetime import datetime

from sqlalchemy import CHAR, TIMESTAMP, BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """AUDIT_LOG: relational form of the AUDITLOG copybook audit record.

    The copybook has no DDL and no key, so rows are identified by a surrogate id.
    AUD_TYPE: TRAN=transaction, USER=user action, SYST=system event.
    AUD_ACTION: CREATE, UPDATE, DELETE, INQUIRE, LOGIN, LOGOUT, STARTUP, SHUTDOWN.
    AUD_STATUS: SUCC=success, FAIL=failure, WARN=warning.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("audit_log_ix1", "aud_timestamp", "aud_type"),
        Index("audit_log_ix2", "aud_portfolio_id", "aud_timestamp"),
        Index("audit_log_ix3", "aud_user_id", "aud_timestamp"),
    )

    audit_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    aud_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    aud_system_id: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    aud_user_id: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    aud_program: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    aud_terminal: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    aud_type: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    aud_action: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    aud_status: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    aud_portfolio_id: Mapped[str | None] = mapped_column(CHAR(8))
    aud_account_no: Mapped[str | None] = mapped_column(CHAR(10))
    aud_before_image: Mapped[str | None] = mapped_column(String(100))
    aud_after_image: Mapped[str | None] = mapped_column(String(100))
    aud_message: Mapped[str | None] = mapped_column(String(100))

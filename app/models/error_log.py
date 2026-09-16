from datetime import date, datetime, time

from sqlalchemy import CHAR, TIMESTAMP, Date, Index, Integer, String, Time, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ErrorLog(Base):
    """ERRLOG: application error and warning journal.

    ERROR_TYPE: S=System, A=Application, D=Data.
    ERROR_SEVERITY: 1=Info, 2=Warning, 3=Error, 4=Severe.
    """

    __tablename__ = "errlog"
    __table_args__ = (Index("errlog_ix1", "process_date", text("error_severity DESC")),)

    error_timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, primary_key=True)
    program_id: Mapped[str] = mapped_column(CHAR(8), primary_key=True)
    error_type: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    error_severity: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    error_message: Mapped[str] = mapped_column(String(200), nullable=False)
    process_date: Mapped[date] = mapped_column(Date, nullable=False)
    process_time: Mapped[time] = mapped_column(Time, nullable=False)
    user_id: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    additional_info: Mapped[str | None] = mapped_column(String(500))

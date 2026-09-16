from datetime import datetime

from sqlalchemy import TIMESTAMP, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "%(table_name)s_ix_%(column_0_N_name)s",
    "uq": "%(table_name)s_uq_%(column_0_N_name)s",
    "ck": "%(table_name)s_ck_%(constraint_name)s",
    "fk": "%(table_name)s_fk_%(column_0_N_name)s",
    "pk": "%(table_name)s_pk",
}


class Base(DeclarativeBase):
    """Declarative base for every table ported from the DB2 and VSAM definitions."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class LastMaintenanceMixin:
    """DB2 audit columns LAST_MAINT_DATE / LAST_MAINT_USER."""

    last_maint_date: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    last_maint_user: Mapped[str] = mapped_column(String(8), nullable=False)

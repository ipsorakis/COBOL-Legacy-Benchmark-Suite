"""SQLAlchemy ORM models for the legacy IPMS schema."""

from app.models.base import Base
from app.models.transaction_history import TransactionHistory

__all__ = ["Base", "TransactionHistory"]

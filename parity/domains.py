"""Legacy code domains and their canonical equivalents.

The 88-levels in the copybooks are the authoritative domains for the ported
services; the documentation repeats some of them with different values, and the
divergences are recorded here rather than silently resolved.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class PositionStatus(StrEnum):
    """POS-STATUS 88-levels in copybook/common/POSREC.cpy."""

    ACTIVE = "A"
    CLOSED = "C"
    PENDING = "P"


class PortfolioStatus(StrEnum):
    """PORT-STATUS 88-levels in copybook/common/PORTFLIO.cpy."""

    ACTIVE = "A"
    CLOSED = "C"
    SUSPENDED = "S"


class ClientType(StrEnum):
    """PORT-CLIENT-TYPE 88-levels in copybook/common/PORTFLIO.cpy."""

    INDIVIDUAL = "I"
    CORPORATE = "C"
    TRUST = "T"


class TransactionType(StrEnum):
    """TRN-TYPE 88-levels in copybook/common/TRNREC.cpy."""

    BUY = "BU"
    SELL = "SL"
    TRANSFER = "TR"
    FEE = "FE"


class TransactionStatus(StrEnum):
    """TRN-STATUS 88-levels in copybook/common/TRNREC.cpy."""

    PENDING = "P"
    DONE = "D"
    FAILED = "F"
    REVERSED = "R"


class HistoryRecordType(StrEnum):
    """HIST-RECORD-TYPE 88-levels in copybook/common/HISTREC.cpy."""

    PORTFOLIO = "PT"
    POSITION = "PS"
    TRANSACTION = "TR"


class HistoryActionCode(StrEnum):
    """HIST-ACTION-CODE 88-levels in copybook/common/HISTREC.cpy."""

    ADD = "A"
    CHANGE = "C"
    DELETE = "D"


@dataclass(frozen=True)
class DomainDivergence:
    """A domain the legacy sources define twice, with different values."""

    field: str
    copybook_values: tuple[str, ...]
    documented_values: tuple[str, ...]
    sources: tuple[str, ...]
    note: str


DOMAIN_DIVERGENCES: tuple[DomainDivergence, ...] = (
    DomainDivergence(
        field="PORT-STATUS",
        copybook_values=("A", "C", "S"),
        documented_values=("A", "I", "C"),
        sources=(
            "src/copybook/common/PORTFLIO.cpy",
            "documentation/operations/test-data-specs.md section 3.3",
        ),
        note=(
            "The copybook has SUSPENDED='S'; the test-data specification has "
            "INACTIVE='I'. A portfolio extract carrying 'I' or 'S' therefore has no "
            "single canonical target until KAN-38 signs the domain off."
        ),
    ),
    DomainDivergence(
        field="TRN-TYPE",
        copybook_values=("BU", "SL", "TR", "FE"),
        documented_values=("B", "S"),
        sources=(
            "src/copybook/common/TRNREC.cpy",
            "documentation/operations/test-data-specs.md section 3.4",
        ),
        note=(
            "The specification's single-character B/S transaction record is a "
            "different layout from TRNREC; parity fixtures use the copybook domain."
        ),
    ),
    DomainDivergence(
        field="PORT-ID",
        copybook_values=("X(8)",),
        documented_values=("X(10): PORT + 5 digits",),
        sources=(
            "src/copybook/common/PORTFLIO.cpy",
            "documentation/operations/test-data-specs.md section 3.1",
        ),
        note="Width and format differ; the canonical model (KAN-40) uses CHAR(8).",
    ),
)

DOMAINS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "POS-STATUS": tuple(member.value for member in PositionStatus),
        "PORT-STATUS": tuple(member.value for member in PortfolioStatus),
        "PORT-CLIENT-TYPE": tuple(member.value for member in ClientType),
        "TRN-TYPE": tuple(member.value for member in TransactionType),
        "TRN-STATUS": tuple(member.value for member in TransactionStatus),
        "HIST-RECORD-TYPE": tuple(member.value for member in HistoryRecordType),
        "HIST-ACTION-CODE": tuple(member.value for member in HistoryActionCode),
    }
)


def in_domain(domain: str, value: str) -> bool:
    """Whether ``value`` is a member of the named legacy domain."""
    try:
        allowed = DOMAINS[domain]
    except KeyError as exc:  # pragma: no cover - guards typos in case definitions
        raise KeyError(f"unknown code domain {domain!r}") from exc
    return value.strip() in allowed

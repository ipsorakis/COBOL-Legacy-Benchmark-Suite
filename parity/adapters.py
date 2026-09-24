"""The seam between the harness and the ported services.

The harness owns the legacy side (baseline extracts) and the comparison; the
FastAPI side is supplied through the protocols below. None of the services the
parity cases need exist yet, so a run against the default :class:`PortedSystem`
reports its cases as blocked, naming the ticket that has to land first, instead
of passing vacuously or failing as if the port were wrong.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

POSITION_TICKET = "KAN-24"
HISTORY_TICKET = "KAN-25"
PORTFOLIO_INQUIRY_TICKET = "KAN-20"
HISTORY_INQUIRY_TICKET = "KAN-21"


class AdapterUnavailable(RuntimeError):
    """The ported service a parity case needs has not been implemented yet."""

    def __init__(self, capability: str, ticket: str, summary: str) -> None:
        super().__init__(f"{capability} is not available yet ({ticket}: {summary})")
        self.capability = capability
        self.ticket = ticket
        self.summary = summary


Record = Mapping[str, object]


@runtime_checkable
class BatchPositions(Protocol):
    """Positions and cost basis after a batch run (POSUPD00 / POSUPDT port)."""

    def positions_after_batch(self, data_set: str) -> Sequence[Record]: ...


@runtime_checkable
class BatchHistory(Protocol):
    """Transaction history rows after the history load (HISTLD00 port)."""

    def history_after_load(self, data_set: str) -> Sequence[Record]: ...


@runtime_checkable
class PortfolioInquiry(Protocol):
    """Portfolio position inquiry response (INQPORT port)."""

    def portfolio_inquiry(self, account_no: str) -> Record: ...


@runtime_checkable
class HistoryInquiry(Protocol):
    """Transaction history inquiry response (INQHIST port)."""

    def history_inquiry(
        self, portfolio_id: str, start: date, end: date, *, page: int = 1
    ) -> Record: ...


@dataclass(frozen=True)
class PortedSystem:
    """The ported implementations available to a parity run.

    Each capability is optional; ``require_*`` raises
    :class:`AdapterUnavailable` naming the ticket, which the runner turns into a
    blocked case.
    """

    batch_positions: BatchPositions | None = None
    batch_history: BatchHistory | None = None
    portfolio_inquiry: PortfolioInquiry | None = None
    history_inquiry: HistoryInquiry | None = None

    def require_batch_positions(self) -> BatchPositions:
        if self.batch_positions is None:
            raise AdapterUnavailable(
                "position and cost-basis output of the batch run",
                POSITION_TICKET,
                "Position update service (port POSUPD00 / POSUPDT)",
            )
        return self.batch_positions

    def require_batch_history(self) -> BatchHistory:
        if self.batch_history is None:
            raise AdapterUnavailable(
                "transaction history written by the history load",
                HISTORY_TICKET,
                "History load service (port HISTLD00)",
            )
        return self.batch_history

    def require_portfolio_inquiry(self) -> PortfolioInquiry:
        if self.portfolio_inquiry is None:
            raise AdapterUnavailable(
                "portfolio position inquiry response",
                PORTFOLIO_INQUIRY_TICKET,
                "Portfolio position inquiry endpoint (port INQPORT)",
            )
        return self.portfolio_inquiry

    def require_history_inquiry(self) -> HistoryInquiry:
        if self.history_inquiry is None:
            raise AdapterUnavailable(
                "transaction history inquiry response",
                HISTORY_INQUIRY_TICKET,
                "Transaction history inquiry endpoint (port INQHIST)",
            )
        return self.history_inquiry

    def pending_tickets(self) -> list[str]:
        """Tickets whose services are still missing, in ticket order."""
        pending = {
            POSITION_TICKET: self.batch_positions,
            HISTORY_TICKET: self.batch_history,
            PORTFOLIO_INQUIRY_TICKET: self.portfolio_inquiry,
            HISTORY_INQUIRY_TICKET: self.history_inquiry,
        }
        return sorted(ticket for ticket, service in pending.items() if service is None)

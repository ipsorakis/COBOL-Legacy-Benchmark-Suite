"""Stand-in ported services, used until the real ones exist.

A faithful fake replays the baseline, so a suite run over it is green and proves
the harness reports parity when the two sides agree. Tests that need a
difference mutate one field of the replay.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from parity.adapters import PortedSystem, Record
from parity.fixtures import baseline

Mutation = Callable[[dict[str, Any]], dict[str, Any]]


def _identity(record: dict[str, Any]) -> dict[str, Any]:
    return record


@dataclass
class FakeBatch:
    """Replays positions_after_batch and the history load input."""

    mutate: Mutation = _identity

    def positions_after_batch(self, data_set: str) -> Sequence[Record]:
        records = baseline("positions_after_batch").records_normalised()
        return [self.mutate(dict(record)) for record in records]

    def history_after_load(self, data_set: str) -> Sequence[Record]:
        records = baseline("transactions_input").records_normalised()
        return [self.mutate(dict(record) | {"status": "D"}) for record in records]


@dataclass
class FakeInquiry:
    """Replays the recorded INQPORT and INQHIST responses."""

    mutate: Mutation = _identity
    _accounts: dict[str, Mapping[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._accounts = {
            str(entry["request"]["account_no"]): entry["response"]
            for entry in baseline("inqport_responses").json()
        }

    def portfolio_inquiry(self, account_no: str) -> Record:
        return self.mutate(dict(self._accounts[account_no]))

    def history_inquiry(
        self, portfolio_id: str, start: date, end: date, *, page: int = 1
    ) -> Record:
        entry = baseline("inqhist_responses").json()[0]
        response = dict(entry["response"])
        response["rows"] = [dict(row) for row in response["rows"]]
        return self.mutate(response)


def faithful_system(mutate: Mutation = _identity) -> PortedSystem:
    """A fully wired system whose answers come from the baselines."""
    batch = FakeBatch(mutate)
    inquiry = FakeInquiry(mutate)
    return PortedSystem(
        batch_positions=batch,
        batch_history=batch,
        portfolio_inquiry=inquiry,
        history_inquiry=inquiry,
    )

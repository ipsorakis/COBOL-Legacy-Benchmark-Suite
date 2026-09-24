"""The TSTVAL00 test driver, ported.

TSTVAL00 reads TEST-CASE-RECORDs, dispatches on TEST-TYPE (2100-EXECUTE-TEST),
validates the actual result against the expected one (2600-VALIDATE-RESULTS),
keeps pass/fail metrics and elapsed time (2700 / 1300 / 2900) and writes a
report. The port keeps that structure with three deliberate changes:

* validation produces a :class:`~parity.diff.DiffReport` rather than the
  single WS-TEST-PASSED flag, because the ticket asks for a structured diff;
* a case whose ported service does not exist yet is *blocked*, not failed;
* the success rate is guarded, where 2900-WRITE-SUMMARY divides by
  WS-TOTAL-TESTS unconditionally and abends on an empty test-case file.

The 2200-2800 paragraphs TSTVAL00 performs are not defined in the COBOL source,
so the execution semantics of each test type are defined here from the test-case
specification in documentation/operations/test-data-specs.md section 2.
"""

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any

from parity.adapters import AdapterUnavailable, PortedSystem
from parity.diff import Difference, DiffKind, DiffReport
from parity.records import TEST_CASE_RECORD, decode_file


class CaseType(StrEnum):
    """WS-TEST-TYPES values TSTVAL00 dispatches on."""

    FUNCTIONAL = "FUNCTIONAL"
    INTEGRATION = "INTEGRATE"
    PERFORMANCE = "PERFORM"
    ERROR = "ERROR"


class Outcome(StrEnum):
    """Result of one case.

    ``BLOCKED`` and ``ERRORED`` have no COBOL equivalent: TSTVAL00 only knows
    WS-TEST-PASSED, and routes anything unexpected to 9999-ERROR-HANDLER, which
    sets RETURN-CODE 12 and abandons the run.
    """

    PASSED = "PASS"
    FAILED = "FAIL"
    BLOCKED = "BLCK"
    ERRORED = "ERR "


Comparison = Callable[[PortedSystem], DiffReport]


@dataclass(frozen=True)
class ParityCase:
    """One TEST-CASE-RECORD plus the comparison it runs."""

    test_id: str
    test_type: CaseType
    description: str
    compare: Comparison
    parameters: str = ""
    budget: timedelta | None = None

    def __post_init__(self) -> None:
        if len(self.test_id) > 10:
            raise ValueError("TEST-ID is PIC X(10)")
        if len(self.description) > 50:
            raise ValueError("TEST-DESCRIPTION is PIC X(50)")
        if len(self.parameters) > 100:
            raise ValueError("TEST-PARAMETERS is PIC X(100)")
        if self.budget is not None and self.test_type is not CaseType.PERFORMANCE:
            raise ValueError("only PERFORM cases carry an elapsed-time budget")


@dataclass(frozen=True)
class CaseResult:
    """Outcome of one case, with the diff that produced it."""

    case: ParityCase
    outcome: Outcome
    report: DiffReport
    elapsed: timedelta
    blocked_by: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.case.test_id,
            "test_type": self.case.test_type.value,
            "description": self.case.description,
            "parameters": self.case.parameters,
            "outcome": self.outcome.value.strip(),
            "elapsed_seconds": round(self.elapsed.total_seconds(), 6),
            "blocked_by": self.blocked_by,
            "error": self.error,
            "diff": self.report.to_dict(),
        }


@dataclass
class SuiteResult:
    """WS-TEST-METRICS for a whole run."""

    results: list[CaseResult] = field(default_factory=list)
    elapsed: timedelta = timedelta()

    @property
    def total(self) -> int:
        return len(self.results)

    def _count(self, outcome: Outcome) -> int:
        return sum(1 for result in self.results if result.outcome is outcome)

    @property
    def passed(self) -> int:
        return self._count(Outcome.PASSED)

    @property
    def failed(self) -> int:
        return self._count(Outcome.FAILED)

    @property
    def blocked(self) -> int:
        return self._count(Outcome.BLOCKED)

    @property
    def errored(self) -> int:
        return self._count(Outcome.ERRORED)

    @property
    def executed(self) -> int:
        """Cases that actually compared something."""
        return self.passed + self.failed

    @property
    def success_rate(self) -> float:
        """Passed as a percentage of all cases; 0.0 for an empty run."""
        if not self.total:
            return 0.0
        return self.passed / self.total * 100

    @property
    def blocking_differences(self) -> list[Difference]:
        return [difference for result in self.results for difference in result.report.blocking]

    @property
    def pending_tickets(self) -> list[str]:
        return sorted({result.blocked_by for result in self.results if result.blocked_by})

    def to_dict(self) -> dict[str, Any]:
        return {
            "totals": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "blocked": self.blocked,
                "errored": self.errored,
                "success_rate": round(self.success_rate, 2),
            },
            "elapsed_seconds": round(self.elapsed.total_seconds(), 6),
            "pending_tickets": self.pending_tickets,
            "cases": [result.to_dict() for result in self.results],
        }


def run_case(case: ParityCase, system: PortedSystem) -> CaseResult:
    """Run one case: 2100-EXECUTE-TEST through 2700-UPDATE-METRICS."""
    started = time.perf_counter()
    try:
        report = case.compare(system)
    except AdapterUnavailable as unavailable:
        return CaseResult(
            case=case,
            outcome=Outcome.BLOCKED,
            report=DiffReport(),
            elapsed=_since(started),
            blocked_by=unavailable.ticket,
            error=str(unavailable),
        )
    except Exception as failure:  # noqa: BLE001 - one bad case must not end the run
        return CaseResult(
            case=case,
            outcome=Outcome.ERRORED,
            report=DiffReport(),
            elapsed=_since(started),
            error=f"{type(failure).__name__}: {failure}",
        )
    elapsed = _since(started)
    if case.budget is not None and elapsed > case.budget:
        report.differences.append(
            Difference(
                DiffKind.VALUE,
                case.test_id,
                "elapsed_seconds",
                expected=f"<= {case.budget.total_seconds()}",
                actual=round(elapsed.total_seconds(), 6),
                note="performance budget exceeded",
            )
        )
    outcome = Outcome.PASSED if report.matched else Outcome.FAILED
    return CaseResult(case=case, outcome=outcome, report=report, elapsed=elapsed)


def run_suite(cases: Iterable[ParityCase], system: PortedSystem) -> SuiteResult:
    """Run every case: 2000-PROCESS with the 1300 / 2900 timing around it."""
    started = time.perf_counter()
    results = [run_case(case, system) for case in cases]
    return SuiteResult(results=results, elapsed=_since(started))


def _since(started: float) -> timedelta:
    return timedelta(seconds=time.perf_counter() - started)


def case_type(value: str) -> CaseType:
    """Map a TEST-TYPE field onto :class:`CaseType`.

    TSTVAL00 routes an unrecognised type to 9999-ERROR-HANDLER; here it is a
    ``ValueError`` at load time so a malformed test-case file is rejected before
    anything runs.
    """
    try:
        return CaseType(value.strip().upper())
    except ValueError as exc:
        raise ValueError(f"invalid TEST-TYPE {value.strip()!r}") from exc


@dataclass(frozen=True)
class CaseRecord:
    """A TEST-CASE-RECORD read off a legacy test-case file."""

    test_id: str
    test_type: CaseType
    description: str
    parameters: str


def load_case_records(path: str, *, encoding: str = "ascii") -> list[CaseRecord]:
    """Read a legacy TESTCASE file (TSTVAL00 2000-PROCESS input)."""
    records = decode_file(TEST_CASE_RECORD, path, encoding=encoding)
    return [
        CaseRecord(
            test_id=str(record["TEST-ID"]),
            test_type=case_type(str(record["TEST-TYPE"])),
            description=str(record["TEST-DESCRIPTION"]),
            parameters=str(record["TEST-PARAMETERS"]),
        )
        for record in records
    ]


def cases_by_type(cases: Sequence[ParityCase], wanted: CaseType) -> list[ParityCase]:
    return [case for case in cases if case.test_type is wanted]

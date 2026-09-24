"""Test reports: the TSTVAL00 132-column listing plus a structured diff report.

The fixed-width listing reproduces WS-HEADER1/WS-HEADER2, WS-TEST-DETAIL and
WS-SUMMARY-LINE so the ported run can be read side by side with an archived
legacy report. Everything a reviewer needs to act on - which field of which
record differs - lives in the JSON report, since the legacy listing has no room
for it.
"""

import json
from pathlib import Path

from parity.cases import Outcome, SuiteResult

LINE_WIDTH = 132
"""REPORT-RECORD PIC X(132)."""


def _edited(value: int) -> str:
    """PIC ZZ,ZZ9: zero-suppressed with an inserted comma."""
    return f"{value:,}".rjust(6)


def _rate(value: float) -> str:
    """PIC ZZ9.99."""
    return f"{value:.2f}".rjust(6)


def _line(text: str) -> str:
    return text.ljust(LINE_WIDTH)[:LINE_WIDTH]


def legacy_report_lines(result: SuiteResult) -> list[str]:
    """The report TSTVAL00 writes, one 132-character line per record.

    The blocked/errored line has no COBOL counterpart; it is written only when a
    run had cases whose ported service does not exist yet, so a clean run still
    produces exactly the legacy listing.
    """
    lines = [
        _line("*" * LINE_WIDTH),
        _line(" " * 30 + "TEST VALIDATION REPORT".ljust(72) + " " * 30),
    ]
    for case_result in result.results:
        case = case_result.case
        lines.append(
            _line(
                f"{case.test_id:<10}  {case.test_type.value:<10}  "
                f"{case.description:<50}  {case_result.outcome.value:<4}"
            )
        )
    lines.append(
        _line(
            f"{'TOTAL TESTS:':<15}{_edited(result.total)}"
            f"{'  PASSED:':<15}{_edited(result.passed)}"
            f"{'  FAILED:':<15}{_edited(result.failed)}"
            f"{'  SUCCESS:':<15}{_rate(result.success_rate)}%"
        )
    )
    if result.blocked or result.errored:
        pending = ", ".join(result.pending_tickets) or "none"
        lines.append(
            _line(
                f"{'BLOCKED:':<15}{_edited(result.blocked)}"
                f"{'  ERRORED:':<15}{_edited(result.errored)}"
                f"{'  PENDING:':<15}{pending}"
            )
        )
    return lines


def legacy_report(result: SuiteResult) -> str:
    return "\n".join(legacy_report_lines(result)) + "\n"


def diff_report(result: SuiteResult) -> dict[str, object]:
    """The structured report: totals, pending tickets and every difference."""
    return result.to_dict()


def diff_text(result: SuiteResult) -> str:
    """Human-readable rendering of the differences, for a CI log."""
    blocks: list[str] = []
    for case_result in result.results:
        if case_result.outcome is Outcome.PASSED:
            continue
        header = (
            f"{case_result.case.test_id} [{case_result.outcome.value.strip()}] "
            f"{case_result.case.description}"
        )
        body = case_result.error or case_result.report.to_text()
        blocks.append(f"{header}\n  " + body.replace("\n", "\n  "))
    if not blocks:
        return "all cases passed"
    return "\n".join(blocks)


def write_reports(result: SuiteResult, directory: Path) -> dict[str, Path]:
    """Write the listing, the JSON diff report and the text diff to ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    listing = directory / "test-validation-report.txt"
    structured = directory / "parity-diff.json"
    text = directory / "parity-diff.txt"
    listing.write_text(legacy_report(result), encoding="utf-8")
    structured.write_text(
        json.dumps(diff_report(result), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    text.write_text(diff_text(result) + "\n", encoding="utf-8")
    return {"listing": listing, "json": structured, "text": text}

"""Test reports: the 132-column TSTVAL00 listing and the structured diff."""

import json
from pathlib import Path

from parity.adapters import PortedSystem
from parity.cases import run_suite
from parity.report import LINE_WIDTH, diff_text, legacy_report_lines, write_reports
from parity.suite import CASES
from tests.parity.fakes import faithful_system


def test_every_report_line_is_a_132_byte_record() -> None:
    lines = legacy_report_lines(run_suite(CASES, faithful_system()))
    assert {len(line) for line in lines} == {LINE_WIDTH}


def test_listing_carries_a_header_a_detail_line_per_case_and_a_summary() -> None:
    suite = run_suite(CASES, faithful_system())
    lines = legacy_report_lines(suite)
    assert lines[0].strip("*") == ""
    assert "TEST VALIDATION REPORT" in lines[1]
    assert len(lines) == 2 + suite.total + 1
    summary = lines[-1]
    assert "TOTAL TESTS:" in summary
    assert "SUCCESS:" in summary
    assert "100.00%" in summary


def test_detail_line_shows_the_outcome_of_each_case() -> None:
    lines = legacy_report_lines(run_suite(CASES, faithful_system()))
    detail = next(line for line in lines if line.startswith("PAR-POS-01"))
    assert "FUNCTIONAL" in detail
    assert detail.split()[-1] == "PASS"


def test_a_blocked_run_adds_a_line_naming_the_pending_tickets() -> None:
    lines = legacy_report_lines(run_suite(CASES, PortedSystem()))
    pending = lines[-1]
    assert pending.startswith("BLOCKED:")
    assert "KAN-20, KAN-21, KAN-24, KAN-25" in pending
    assert "BLCK" in lines[2]


def test_a_clean_run_writes_only_the_legacy_lines() -> None:
    lines = legacy_report_lines(run_suite(CASES, faithful_system()))
    assert not any(line.startswith("BLOCKED:") for line in lines)


def test_diff_text_explains_a_blocked_case_instead_of_listing_differences() -> None:
    text = diff_text(run_suite(CASES, PortedSystem()))
    assert "PAR-POS-01 [BLCK]" in text
    assert "KAN-24" in text


def test_diff_text_says_so_when_nothing_differs() -> None:
    assert diff_text(run_suite(CASES, faithful_system())) == "all cases passed"


def test_write_reports_produces_the_listing_and_the_structured_diff(tmp_path: Path) -> None:
    suite = run_suite(CASES, PortedSystem())
    written = write_reports(suite, tmp_path / "reports")
    assert set(written) == {"listing", "json", "text"}
    document = json.loads(written["json"].read_text())
    assert document["totals"]["blocked"] == len(CASES)
    assert document["pending_tickets"] == ["KAN-20", "KAN-21", "KAN-24", "KAN-25"]
    assert document["cases"][0]["test_id"] == "PAR-POS-01"
    assert written["listing"].read_text().splitlines()[1].strip() == "TEST VALIDATION REPORT"

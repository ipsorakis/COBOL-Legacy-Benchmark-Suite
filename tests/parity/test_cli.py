"""The ``python -m parity`` entry point."""

import json
from pathlib import Path

import pytest

from parity.__main__ import main
from parity.suite import CASES


def test_a_blocked_run_succeeds_so_the_suite_can_sit_in_ci(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "TEST VALIDATION REPORT" in output
    assert "KAN-24" in output


def test_blocked_cases_fail_the_run_on_request() -> None:
    assert main(["--fail-on-blocked"]) == 1


def test_reports_are_written_where_asked(tmp_path: Path) -> None:
    assert main(["--out", str(tmp_path)]) == 0
    document = json.loads((tmp_path / "parity-diff.json").read_text())
    assert document["totals"]["total"] == len(CASES)
    assert (tmp_path / "test-validation-report.txt").exists()
    assert (tmp_path / "parity-diff.txt").exists()


def test_a_single_test_type_can_be_run(tmp_path: Path) -> None:
    assert main(["--type", "PERFORM", "--out", str(tmp_path)]) == 0
    document = json.loads((tmp_path / "parity-diff.json").read_text())
    assert [case["test_id"] for case in document["cases"]] == ["PAR-PRF-01"]

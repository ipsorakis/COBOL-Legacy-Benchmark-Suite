"""The ported TSTVAL00 driver: dispatch, metrics, blocked cases and timing."""

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from parity.adapters import AdapterUnavailable, PortedSystem
from parity.cases import (
    CaseType,
    Outcome,
    ParityCase,
    case_type,
    cases_by_type,
    load_case_records,
    run_case,
    run_suite,
)
from parity.diff import Difference, DiffKind, DiffReport
from parity.records import TEST_CASE_RECORD, encode_records


def _passing(_: PortedSystem) -> DiffReport:
    return DiffReport()


def _failing(_: PortedSystem) -> DiffReport:
    return DiffReport([Difference(DiffKind.VALUE, "PORT0001", "cost_basis", "1.00", "2.00")])


def _blocked(system: PortedSystem) -> DiffReport:
    system.require_portfolio_inquiry()
    return DiffReport()


def _broken(_: PortedSystem) -> DiffReport:
    raise ZeroDivisionError("division by zero")


def _case(
    test_id: str,
    compare: Callable[[PortedSystem], DiffReport],
    *,
    test_type: CaseType = CaseType.FUNCTIONAL,
    description: str = "case",
    budget: timedelta | None = None,
) -> ParityCase:
    return ParityCase(
        test_id=test_id,
        test_type=test_type,
        description=description,
        compare=compare,
        budget=budget,
    )


def test_a_case_with_no_differences_passes() -> None:
    result = run_case(_case("PAR-01", _passing), PortedSystem())
    assert result.outcome is Outcome.PASSED
    assert result.report.matched


def test_a_case_with_a_difference_fails_and_keeps_the_diff() -> None:
    result = run_case(_case("PAR-02", _failing), PortedSystem())
    assert result.outcome is Outcome.FAILED
    assert result.report.differences[0].field == "cost_basis"


def test_a_missing_ported_service_blocks_rather_than_fails() -> None:
    result = run_case(_case("PAR-03", _blocked), PortedSystem())
    assert result.outcome is Outcome.BLOCKED
    assert result.blocked_by == "KAN-20"
    assert result.report.differences == []


def test_an_unexpected_exception_is_contained_in_the_case() -> None:
    suite = run_suite(
        [_case("PAR-04", _broken), _case("PAR-05", _passing)],
        PortedSystem(),
    )
    assert [result.outcome for result in suite.results] == [Outcome.ERRORED, Outcome.PASSED]
    assert suite.results[0].error is not None
    assert "ZeroDivisionError" in suite.results[0].error


def test_metrics_count_every_outcome_separately() -> None:
    suite = run_suite(
        [
            _case("PAR-06", _passing),
            _case("PAR-07", _failing),
            _case("PAR-08", _blocked),
            _case("PAR-09", _broken),
        ],
        PortedSystem(),
    )
    assert (suite.total, suite.passed, suite.failed, suite.blocked, suite.errored) == (
        4,
        1,
        1,
        1,
        1,
    )
    assert suite.executed == 2
    assert suite.success_rate == 25.0
    assert suite.pending_tickets == ["KAN-20"]


def test_an_empty_run_does_not_divide_by_zero() -> None:
    # 2900-WRITE-SUMMARY divides by WS-TOTAL-TESTS unconditionally.
    assert run_suite([], PortedSystem()).success_rate == 0.0


def test_a_performance_case_over_budget_reports_the_elapsed_time() -> None:
    case = _case(
        "PAR-10",
        _passing,
        test_type=CaseType.PERFORMANCE,
        budget=timedelta(0),
    )
    result = run_case(case, PortedSystem())
    assert result.outcome is Outcome.FAILED
    assert result.report.differences[0].field == "elapsed_seconds"
    assert result.report.differences[0].note == "performance budget exceeded"


def test_only_performance_cases_carry_a_budget() -> None:
    with pytest.raises(ValueError, match="elapsed-time budget"):
        _case("PAR-11", _passing, budget=timedelta(seconds=1))


def test_case_fields_respect_the_test_case_record_pictures() -> None:
    with pytest.raises(ValueError, match="TEST-ID is PIC X"):
        _case("PAR-THIS-IS-TOO-LONG", _passing)
    with pytest.raises(ValueError, match="TEST-DESCRIPTION is PIC X"):
        _case("PAR-12", _passing, description="d" * 51)


def test_unknown_test_type_is_rejected_at_load_time() -> None:
    assert case_type(" functional ") is CaseType.FUNCTIONAL
    with pytest.raises(ValueError, match="invalid TEST-TYPE"):
        case_type("REGRESSION")


def test_legacy_test_case_file_is_read(tmp_path: Path) -> None:
    records: list[dict[str, str | Decimal]] = [
        {
            "TEST-ID": "PAR-POS-01",
            "TEST-TYPE": "FUNCTIONAL",
            "TEST-DESCRIPTION": "Batch positions",
            "TEST-PARAMETERS": "baseline=positions_after_batch",
        },
        {
            "TEST-ID": "PAR-PRF-01",
            "TEST-TYPE": "PERFORM",
            "TEST-DESCRIPTION": "Batch throughput",
            "TEST-PARAMETERS": "budget=30s",
        },
    ]
    path = tmp_path / "testcase.dat"
    path.write_bytes(encode_records(TEST_CASE_RECORD, records))
    loaded = load_case_records(str(path))
    assert [item.test_type for item in loaded] == [CaseType.FUNCTIONAL, CaseType.PERFORMANCE]
    assert loaded[0].test_id == "PAR-POS-01"


def test_cases_can_be_selected_by_test_type() -> None:
    cases = [
        _case("PAR-13", _passing),
        _case("PAR-14", _passing, test_type=CaseType.ERROR),
    ]
    assert [case.test_id for case in cases_by_type(cases, CaseType.ERROR)] == ["PAR-14"]


def test_blocked_case_result_serialises_with_its_ticket() -> None:
    document = run_case(_case("PAR-15", _blocked), PortedSystem()).to_dict()
    assert document["outcome"] == "BLCK"
    assert document["blocked_by"] == "KAN-20"
    assert document["diff"]["differences"] == []


def test_adapter_unavailable_names_the_capability_and_ticket() -> None:
    with pytest.raises(AdapterUnavailable) as raised:
        PortedSystem().require_batch_positions()
    assert raised.value.ticket == "KAN-24"
    assert "POSUPD00" in raised.value.summary


def test_pending_tickets_lists_every_missing_service() -> None:
    assert PortedSystem().pending_tickets() == ["KAN-20", "KAN-21", "KAN-24", "KAN-25"]


def test_suite_result_serialises_totals_and_cases() -> None:
    suite = run_suite([_case("PAR-16", _failing)], PortedSystem())
    document = suite.to_dict()
    assert document["totals"]["failed"] == 1
    assert document["cases"][0]["diff"]["differences"][0]["field"] == "cost_basis"
    assert Decimal(str(document["elapsed_seconds"])) >= 0

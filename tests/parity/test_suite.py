"""The KAN-31 parity cases, run against a faithful and a divergent fake port."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from parity.adapters import PortedSystem
from parity.cases import Outcome, run_suite
from parity.diff import DiffKind
from parity.suite import CASES
from tests.parity.fakes import faithful_system


def test_every_case_is_blocked_while_no_service_exists() -> None:
    suite = run_suite(CASES, PortedSystem())
    assert suite.total == len(CASES)
    assert suite.blocked == len(CASES)
    assert (suite.passed, suite.failed, suite.errored) == (0, 0, 0)
    assert suite.pending_tickets == ["KAN-20", "KAN-21", "KAN-24", "KAN-25"]


def test_the_ticket_a_case_waits_on_is_the_one_that_owns_its_service() -> None:
    blocked = {
        result.case.test_id: result.blocked_by
        for result in run_suite(CASES, PortedSystem()).results
    }
    assert blocked["PAR-POS-01"] == "KAN-24"
    assert blocked["PAR-HST-01"] == "KAN-25"
    assert blocked["PAR-INP-01"] == "KAN-20"
    assert blocked["PAR-INH-01"] == "KAN-21"


def test_coverage_spans_everything_the_ticket_asks_for() -> None:
    descriptions = " ".join(case.description for case in CASES).lower()
    assert "cost basis" in descriptions
    assert "inqport" in descriptions
    assert "inqhist" in descriptions
    assert "scale" in descriptions
    assert "code" in descriptions


def test_a_faithful_port_passes_every_case() -> None:
    suite = run_suite(CASES, faithful_system())
    assert suite.failed == 0, suite.to_dict()
    assert suite.errored == 0, suite.to_dict()
    assert suite.passed == len(CASES)
    assert suite.success_rate == 100.0


def test_a_wrong_cost_basis_is_reported_field_by_field() -> None:
    def overstate(record: dict[str, Any]) -> dict[str, Any]:
        if "cost_basis" in record:
            record["cost_basis"] = Decimal(str(record["cost_basis"])) + Decimal("0.01")
        return record

    suite = run_suite(CASES, faithful_system(overstate))
    positions = next(result for result in suite.results if result.case.test_id == "PAR-POS-01")
    assert positions.outcome is Outcome.FAILED
    fields = {difference.field for difference in positions.report.differences}
    assert fields == {"cost_basis"}
    difference = positions.report.differences[0]
    assert difference.kind is DiffKind.VALUE
    assert difference.expected == Decimal("15250.00")
    assert difference.actual == Decimal("15250.01")
    assert difference.record.startswith("PORT0001|2024-03-20|")


def test_extra_decimal_places_are_reported_as_a_precision_difference() -> None:
    def over_precise(record: dict[str, Any]) -> dict[str, Any]:
        if "cost_basis" in record:
            record["cost_basis"] = Decimal(str(record["cost_basis"])) + Decimal("0.005")
        return record

    suite = run_suite(CASES, faithful_system(over_precise))
    precision = next(result for result in suite.results if result.case.test_id == "PAR-POS-02")
    assert precision.outcome is Outcome.FAILED
    kinds = {difference.kind for difference in precision.report.differences}
    assert kinds == {DiffKind.PRECISION}
    assert "legacy picture allows 2" in precision.report.differences[0].note


def test_an_out_of_domain_status_is_reported_as_a_domain_violation() -> None:
    def bad_status(record: dict[str, Any]) -> dict[str, Any]:
        if "status" in record and "investment_id" in record:
            record["status"] = "X"
        return record

    suite = run_suite(CASES, faithful_system(bad_status))
    domains = next(result for result in suite.results if result.case.test_id == "PAR-POS-03")
    assert domains.outcome is Outcome.FAILED
    assert {difference.kind for difference in domains.report.differences} == {DiffKind.DOMAIN}
    assert domains.report.differences[0].field == "status"


def test_a_missing_position_is_reported_as_a_missing_record() -> None:
    class Short:
        def positions_after_batch(self, data_set: str) -> list[Mapping[str, object]]:
            complete = faithful_system().require_batch_positions().positions_after_batch(data_set)
            return [record for record in complete if record["investment_id"] != "SEC0000002"]

    system = PortedSystem(batch_positions=Short())
    suite = run_suite([CASES[0]], system)
    (difference,) = suite.results[0].report.differences
    assert difference.kind is DiffKind.MISSING_RECORD
    assert difference.record == "PORT0001|2024-03-20|SEC0000002"


def test_a_wrong_inquiry_message_is_reported_with_both_strings() -> None:
    def rewrite(record: dict[str, Any]) -> dict[str, Any]:
        if record.get("error_message") == "Position not found for account":
            record["error_message"] = "Not found"
        return record

    suite = run_suite(CASES, faithful_system(rewrite))
    not_found = next(result for result in suite.results if result.case.test_id == "PAR-INP-02")
    assert not_found.outcome is Outcome.FAILED
    (difference,) = not_found.report.differences
    assert difference.expected == "Position not found for account"
    assert difference.actual == "Not found"


def test_a_reordered_history_page_is_reported_row_by_row() -> None:
    def reorder(record: dict[str, Any]) -> dict[str, Any]:
        if "rows" in record:
            record["rows"] = list(reversed(record["rows"]))
        return record

    suite = run_suite(CASES, faithful_system(reorder))
    history = next(result for result in suite.results if result.case.test_id == "PAR-INH-01")
    assert history.outcome is Outcome.FAILED
    rows = {difference.record for difference in history.report.differences}
    assert rows == {"1", "2", "3", "4"}

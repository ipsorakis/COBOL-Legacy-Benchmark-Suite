"""The structured diff: what it reports, and that it never collapses to a flag."""

import json
from decimal import Decimal

import pytest

from parity.diff import (
    DiffKind,
    DiffReport,
    Tolerance,
    compare_record_sets,
    compare_records,
    domain_differences,
    precision_differences,
    record_key,
)

POSITION = {
    "portfolio_id": "PORT0001",
    "position_date": "20240320",
    "investment_id": "SEC0000001",
    "quantity": Decimal("120.0000"),
    "cost_basis": Decimal("15250.00"),
    "status": "A",
}


def test_identical_records_produce_no_differences() -> None:
    assert compare_records(POSITION, dict(POSITION)) == []


def test_a_value_mismatch_names_the_field_and_both_values() -> None:
    actual = POSITION | {"cost_basis": Decimal("15250.01")}
    (difference,) = compare_records(POSITION, actual, record="PORT0001")
    assert difference.kind is DiffKind.VALUE
    assert difference.field == "cost_basis"
    assert difference.expected == Decimal("15250.00")
    assert difference.actual == Decimal("15250.01")


def test_missing_and_extra_fields_are_distinguished() -> None:
    actual = {key: value for key, value in POSITION.items() if key != "status"}
    actual["market_value"] = Decimal("15852.00")
    kinds = {
        (difference.field, difference.kind) for difference in compare_records(POSITION, actual)
    }
    assert ("status", DiffKind.MISSING_FIELD) in kinds
    assert ("market_value", DiffKind.EXTRA_FIELD) in kinds


def test_a_response_code_of_the_wrong_type_is_a_type_mismatch() -> None:
    expected = POSITION | {"response_code": 0}
    (difference,) = compare_records(expected, POSITION | {"response_code": "0"})
    assert difference.kind is DiffKind.TYPE
    assert difference.note == "int vs str"


def test_out_of_domain_status_is_reported_even_when_both_sides_agree() -> None:
    both = POSITION | {"status": "X"}
    (difference,) = compare_records(both, dict(both), domains={"status": "POS-STATUS"})
    assert difference.kind is DiffKind.DOMAIN
    assert "POS-STATUS" in difference.note


def test_a_justified_tolerance_is_recorded_rather_than_hidden() -> None:
    tolerance = Tolerance(
        field="market_value",
        absolute=Decimal("0.01"),
        justification="legacy values at the close price of the previous day",
    )
    expected = POSITION | {"market_value": Decimal("15852.00")}
    actual = POSITION | {"market_value": Decimal("15852.01")}
    report = DiffReport(compare_records(expected, actual, tolerances=[tolerance]))
    assert report.matched
    assert report.differences[0].kind is DiffKind.WITHIN_TOLERANCE
    assert report.differences[0].note == tolerance.justification


def test_a_tolerance_needs_a_justification() -> None:
    with pytest.raises(ValueError, match="needs a justification"):
        Tolerance(field="cost_basis", absolute=Decimal("0.01"), justification="  ")


def test_a_difference_beyond_the_tolerance_still_fails() -> None:
    tolerance = Tolerance(
        field="market_value", absolute=Decimal("0.01"), justification="price source"
    )
    expected = POSITION | {"market_value": Decimal("15852.00")}
    actual = POSITION | {"market_value": Decimal("15852.50")}
    report = DiffReport(compare_records(expected, actual, tolerances=[tolerance]))
    assert not report.matched


def test_ignored_fields_are_not_compared() -> None:
    actual = POSITION | {"last_maint_user": "API00001"}
    expected = POSITION | {"last_maint_user": "POSUPD00"}
    assert compare_records(expected, actual, ignore=["last_maint_user"]) == []


def test_record_sets_are_paired_on_their_key() -> None:
    other = POSITION | {"investment_id": "SEC0000002", "cost_basis": Decimal("9150.00")}
    report = compare_record_sets(
        [POSITION, other],
        [other, POSITION],
        key_fields=["portfolio_id", "position_date", "investment_id"],
    )
    assert report.matched


def test_missing_and_extra_records_are_reported_with_their_key() -> None:
    other = POSITION | {"investment_id": "SEC0000002"}
    report = compare_record_sets(
        [POSITION],
        [other],
        key_fields=["portfolio_id", "position_date", "investment_id"],
    )
    kinds = {difference.kind for difference in report.differences}
    assert kinds == {DiffKind.MISSING_RECORD, DiffKind.EXTRA_RECORD}
    assert report.differences[0].record == "PORT0001|2024-03-20|SEC0000001"


def test_record_key_requires_its_fields() -> None:
    with pytest.raises(KeyError, match="key field"):
        record_key(POSITION, ["portfolio_id", "settlement_date"])


def test_precision_beyond_the_legacy_picture_is_its_own_kind() -> None:
    (difference,) = precision_differences(
        [POSITION | {"cost_basis": Decimal("15250.005")}],
        scales={"cost_basis": 2},
        key_fields=["portfolio_id"],
    )
    assert difference.kind is DiffKind.PRECISION
    assert difference.actual == "15250.005"
    assert difference.record == "PORT0001"


def test_precision_check_accepts_a_value_at_the_legacy_scale() -> None:
    assert precision_differences([POSITION], scales={"cost_basis": 2, "quantity": 4}) == []


def test_domain_check_runs_without_a_legacy_counterpart() -> None:
    differences = domain_differences(
        [POSITION, POSITION | {"status": "Z"}],
        domains={"status": "POS-STATUS"},
        key_fields=["investment_id"],
    )
    assert [difference.kind for difference in differences] == [DiffKind.DOMAIN]


def test_report_serialises_to_json_keeping_the_decimal_scale() -> None:
    actual = POSITION | {"cost_basis": Decimal("15250.10")}
    report = DiffReport(compare_records(POSITION, actual, record="PORT0001"))
    document = json.loads(report.to_json())
    assert document["matched"] is False
    assert document["counts"] == {"value_mismatch": 1}
    assert document["differences"][0]["expected"] == "15250.00"
    assert document["differences"][0]["actual"] == "15250.10"


def test_report_text_lists_every_difference() -> None:
    actual = POSITION | {"cost_basis": Decimal("1.00"), "quantity": Decimal("1.0000")}
    report = DiffReport(compare_records(POSITION, actual, record="PORT0001"))
    assert len(report.to_text().splitlines()) == 2
    assert "PORT0001.cost_basis" in report.to_text()

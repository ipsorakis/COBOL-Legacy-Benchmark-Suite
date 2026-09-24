"""Baselines and their provenance (KAN-103)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from parity.fixtures import BaselineError, CaptureMethod, baseline, load_manifest


def test_every_baseline_declares_where_it_came_from() -> None:
    for item in load_manifest().values():
        assert item.provenance.source_program
        assert item.provenance.inputs
        assert item.provenance.captured_by


def test_no_baseline_is_signed_off_as_an_executed_extract_yet() -> None:
    # Nothing here came off a mainframe run; a green parity run proves the port
    # matches the specification as read, which is what the report has to say.
    for item in load_manifest().values():
        assert item.provenance.capture_method is CaptureMethod.DERIVED_FROM_SOURCE
        assert not item.provenance.is_executed


def test_a_baseline_needing_sign_off_names_its_ticket() -> None:
    for item in load_manifest().values():
        if item.provenance.requires_sign_off:
            assert item.provenance.sign_off_ticket


def test_checksums_match_the_files_on_disk() -> None:
    for item in load_manifest().values():
        item.read_bytes()


def test_record_counts_match_the_manifest() -> None:
    for item in load_manifest().values():
        if item.layout is not None:
            assert len(item.raw_records()) == item.records


def test_positions_baseline_decodes_to_the_expected_cost_basis() -> None:
    records = {
        (record["portfolio_id"], record["investment_id"]): record
        for record in baseline("positions_after_batch").records_normalised()
    }
    held = records[("PORT0001", "SEC0000001")]
    assert held["quantity"] == Decimal("120.0000")
    assert held["cost_basis"] == Decimal("15250.00")
    assert held["market_value"] == Decimal("15852.00")


def test_truncated_transaction_amount_is_preserved_byte_for_byte() -> None:
    records = baseline("transactions_input").records_normalised()
    truncated = next(record for record in records if record["sequence_no"] == "000004")
    # 10 x 1234.5678 is 12345.678, truncated to the S9(13)V9(2) picture.
    assert truncated["price"] == Decimal("1234.5678")
    assert truncated["amount"] == Decimal("12345.67")


def test_inquiry_baselines_are_json_not_fixed_width() -> None:
    responses = baseline("inqport_responses").json()
    assert {entry["request"]["account_no"] for entry in responses} == {
        "1000000001",
        "9999999999",
    }
    with pytest.raises(BaselineError, match="not a fixed-width baseline"):
        baseline("inqport_responses").records_normalised()


def test_inqhist_baseline_is_ordered_by_date_descending() -> None:
    rows = baseline("inqhist_responses").json()[0]["response"]["rows"]
    assert len(rows) == 4
    assert [row["transaction_type"] for row in rows][0] == "SL"


def test_a_tampered_baseline_is_rejected(tmp_path: Path) -> None:
    source = load_manifest()
    entry = source["positions_after_batch"]
    manifest = json.loads((entry.path.parent / "manifest.json").read_text())
    for item in manifest["baselines"]:
        target = tmp_path / str(item["file"])
        target.write_bytes((entry.path.parent / str(item["file"])).read_bytes())
    tampered = tmp_path / "positions_after_batch.dat"
    tampered.write_bytes(tampered.read_bytes().replace(b"PORT0001", b"PORT9999", 1))
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BaselineError, match="checksum mismatch"):
        baseline("positions_after_batch", tmp_path / "manifest.json").read_bytes()


def test_a_manifest_entry_without_provenance_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "data.dat").write_bytes(b"")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "baselines": [
                    {
                        "name": "nameless",
                        "file": "data.dat",
                        "sha256": "",
                        "capture_method": "derived-from-source-spec",
                        "captured_at": "2026-09-24",
                        "captured_by": "",
                        "inputs": "",
                        "notes": "",
                        "source_program": "",
                    }
                ]
            }
        )
    )
    with pytest.raises(BaselineError, match="missing source_program"):
        load_manifest(manifest)


def test_unknown_baseline_name_is_rejected() -> None:
    with pytest.raises(BaselineError, match="unknown baseline"):
        baseline("nosuch")

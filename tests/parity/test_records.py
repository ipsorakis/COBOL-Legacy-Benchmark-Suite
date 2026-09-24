"""Record layout decoding: the harness is only as good as its reader."""

from decimal import Decimal

import pytest

from parity.records import (
    EBCDIC,
    POSITION_EXTRACT,
    POSITION_RECORD,
    TRANSACTION_RECORD,
    DecodeError,
    Layout,
    alpha,
    display,
    layout_by_name,
    packed,
)


def test_position_record_length_matches_copybook() -> None:
    # POSREC: 8 + 8 + 10 + 8 + 8 + 8 + 3 + 1 + 26 + 8 + 50 packed/alpha bytes
    assert POSITION_RECORD.length == 138
    assert POSITION_EXTRACT.length == 162


def test_packed_decimal_round_trip_keeps_scale() -> None:
    layout = Layout("T", (packed("AMOUNT", 15, 2),), source="test")
    encoded = layout.encode({"AMOUNT": Decimal("12345.67")})
    assert len(encoded) == 8
    assert layout.decode(encoded)["AMOUNT"] == Decimal("12345.67")


def test_packed_decimal_carries_the_sign_nibble() -> None:
    layout = Layout("T", (packed("AMOUNT", 15, 2),), source="test")
    negative = layout.encode({"AMOUNT": Decimal("-0.05")})
    assert negative.hex()[-1] == "d"
    assert layout.decode(negative)["AMOUNT"] == Decimal("-0.05")


def test_signed_display_field_round_trip() -> None:
    layout = Layout("T", (display("QTY", 7, 4, signed=True),), source="test")
    encoded = layout.encode({"QTY": Decimal("-12.5")})
    assert encoded == b"-0125000"
    assert layout.decode(encoded)["QTY"] == Decimal("-12.5000")


def test_value_too_large_for_its_picture_is_rejected() -> None:
    layout = Layout("T", (packed("AMOUNT", 5, 2),), source="test")
    with pytest.raises(DecodeError, match="does not fit"):
        layout.encode({"AMOUNT": Decimal("12345.67")})


def test_short_record_is_rejected() -> None:
    with pytest.raises(DecodeError, match="expected 138 bytes"):
        POSITION_RECORD.decode(b"too short")


def test_file_that_is_not_a_multiple_of_the_record_is_rejected() -> None:
    with pytest.raises(DecodeError, match="not a multiple"):
        POSITION_RECORD.decode_all(b"\x00" * (POSITION_RECORD.length + 1))


def test_ebcdic_extract_decodes() -> None:
    layout = Layout("T", (alpha("ID", 4),), source="test")
    assert layout.decode("PT01".encode(EBCDIC), encoding=EBCDIC)["ID"] == "PT01"


def test_alphanumeric_field_is_right_padded_and_trimmed() -> None:
    layout = Layout("T", (alpha("ID", 8),), source="test")
    assert layout.encode({"ID": "PORT1"}) == b"PORT1   "
    assert layout.decode(b"PORT1   ")["ID"] == "PORT1"


def test_transaction_layout_keeps_four_decimal_price() -> None:
    field = {item.name: item for item in TRANSACTION_RECORD.fields}["TRN-PRICE"]
    assert field.scale == 4
    assert field.picture == "S9(11)V9(4) COMP-3"


def test_layout_lookup_rejects_an_unknown_name() -> None:
    assert layout_by_name("POSITION-RECORD") is POSITION_RECORD
    with pytest.raises(KeyError, match="unknown record layout"):
        layout_by_name("NOSUCH")

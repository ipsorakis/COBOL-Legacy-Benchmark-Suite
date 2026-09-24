"""Normalisation and the decimal rules the parity comparison depends on."""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from parity.normalize import (
    NormalisationError,
    canonical_field,
    normalise,
    round_half_up,
    to_date,
    to_decimal,
    to_time,
    to_timestamp,
    truncate,
)


def test_truncate_matches_an_unrounded_compute() -> None:
    assert truncate(Decimal("12345.678"), 2) == Decimal("12345.67")
    assert truncate(Decimal("-12345.678"), 2) == Decimal("-12345.67")


def test_round_half_up_matches_compute_rounded() -> None:
    assert round_half_up(Decimal("12345.675"), 2) == Decimal("12345.68")
    assert round_half_up(Decimal("-12345.675"), 2) == Decimal("-12345.68")


def test_truncation_and_rounding_disagree_on_a_half_cent() -> None:
    value = Decimal("0.125")
    assert truncate(value, 2) != round_half_up(value, 2)


def test_to_decimal_pads_to_the_legacy_scale() -> None:
    assert to_decimal("120", 4) == Decimal("120.0000")
    assert str(to_decimal(Decimal("15250.5"), 2)) == "15250.50"


def test_extra_precision_is_an_error_not_something_to_round_away() -> None:
    with pytest.raises(NormalisationError, match="more than 2 decimal places"):
        to_decimal(Decimal("15250.505"), 2)


def test_non_numeric_value_is_rejected() -> None:
    with pytest.raises(NormalisationError, match="not numeric"):
        to_decimal("fifteen", 2)
    with pytest.raises(NormalisationError, match="cannot read"):
        to_decimal(None, 2)


def test_legacy_and_iso_dates_normalise_to_the_same_value() -> None:
    assert to_date("20240320") == date(2024, 3, 20)
    assert to_date("2024-03-20") == date(2024, 3, 20)
    assert to_date(datetime(2024, 3, 20, 18, 0)) == date(2024, 3, 20)


def test_bad_date_is_rejected() -> None:
    with pytest.raises(NormalisationError, match="not a YYYYMMDD date"):
        to_date("03/20/2024")


def test_legacy_time_and_timestamp() -> None:
    assert to_time("153045") == time(15, 30, 45)
    assert to_timestamp("2024-03-20-15.30.45.123456") == datetime(2024, 3, 20, 15, 30, 45, 123456)


def test_legacy_field_names_map_onto_canonical_ones() -> None:
    assert canonical_field("POS-COST-BASIS") == "cost_basis"
    assert canonical_field("TRN-TYPE") == "transaction_type"
    assert canonical_field("cost_basis") == "cost_basis"


def test_normalise_puts_both_sides_in_the_same_shape() -> None:
    legacy = normalise(
        {
            "POS-PORTFOLIO-ID": "PORT0001",
            "POS-DATE": "20240320",
            "POS-COST-BASIS": Decimal("15250.00"),
            "POS-STATUS": "A ",
        }
    )
    ported = normalise(
        {
            "portfolio_id": "PORT0001",
            "position_date": date(2024, 3, 20),
            "cost_basis": Decimal("15250"),
            "status": "A",
        }
    )
    assert legacy == ported

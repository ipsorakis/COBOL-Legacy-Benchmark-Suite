"""Normalisation of both sides of a comparison onto canonical values.

A COBOL extract carries space-padded text, YYYYMMDD dates and fixed-scale packed
decimals; the FastAPI services return trimmed strings, ``date``/``datetime`` and
``Decimal`` of the column scale. Comparing them only means something once both
sides are put through the same normalisation, which is what this module does.
"""

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

from parity.records import Layout

QUANTITY_SCALE = 4
"""POS-QUANTITY / TRN-QUANTITY PIC S9(11)V9(4)."""

AMOUNT_SCALE = 2
"""POS-COST-BASIS, POS-MARKET-VALUE, TRN-AMOUNT PIC S9(13)V9(2)."""

LEGACY_DATE = "%Y%m%d"
LEGACY_TIME = "%H%M%S"
LEGACY_TIMESTAMP = "%Y-%m-%d-%H.%M.%S.%f"
"""TXN-TIMESTAMP / *-PROCESS-DATE PIC X(26), documented in test-data-specs 3.6."""


class NormalisationError(ValueError):
    """A legacy value could not be put into canonical form."""


def truncate(value: Decimal, scale: int) -> Decimal:
    """Quantise the way an unROUNDED COBOL COMPUTE does: truncate toward zero."""
    return value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_DOWN)


def round_half_up(value: Decimal, scale: int) -> Decimal:
    """Quantise the way COMPUTE ... ROUNDED does: half away from zero."""
    return value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)


def to_decimal(value: object, scale: int) -> Decimal:
    """Coerce ``value`` to a Decimal of exactly ``scale`` places.

    Values that carry more precision than the legacy picture are an error rather
    than something to round away: a cost basis with three decimals means the
    ported service is computing at a different scale, which is exactly the kind
    of difference the harness exists to surface.
    """
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, str):
        try:
            number = Decimal(value.strip())
        except ArithmeticError as exc:
            raise NormalisationError(f"{value!r} is not numeric") from exc
    else:
        raise NormalisationError(f"cannot read {type(value).__name__} as a decimal")
    if -number.as_tuple().exponent > scale:  # type: ignore[operator]
        raise NormalisationError(f"{number} carries more than {scale} decimal places")
    return number.quantize(Decimal(1).scaleb(-scale))


def to_text(value: object) -> str:
    """Trim the trailing spaces a PIC X field pads with."""
    if value is None:
        return ""
    return str(value).rstrip()


def to_date(value: object) -> date:
    """Read a ``PIC X(8)`` YYYYMMDD date (or an already canonical date)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = to_text(value)
    for pattern in (LEGACY_DATE, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise NormalisationError(f"{text!r} is not a YYYYMMDD date")


def to_time(value: object) -> time:
    """Read a ``PIC X(6)`` HHMMSS time."""
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    text = to_text(value)
    try:
        return datetime.strptime(text, LEGACY_TIME).time()
    except ValueError as exc:
        raise NormalisationError(f"{text!r} is not an HHMMSS time") from exc


def to_timestamp(value: object) -> datetime:
    """Read a ``PIC X(26)`` YYYY-MM-DD-HH.MM.SS.MICSEC audit timestamp."""
    if isinstance(value, datetime):
        return value
    text = to_text(value)
    for pattern in (LEGACY_TIMESTAMP, "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise NormalisationError(f"{text!r} is not a legacy timestamp")


_POSITION_FIELDS: dict[str, str] = {
    "POS-PORTFOLIO-ID": "portfolio_id",
    "POS-DATE": "position_date",
    "POS-INVESTMENT-ID": "investment_id",
    "POS-QUANTITY": "quantity",
    "POS-COST-BASIS": "cost_basis",
    "POS-MARKET-VALUE": "market_value",
    "POS-CURRENCY": "currency_code",
    "POS-STATUS": "status",
    "POS-LAST-MAINT-DATE": "last_maint_date",
    "POS-LAST-MAINT-USER": "last_maint_user",
}

_TRANSACTION_FIELDS: dict[str, str] = {
    "TRN-DATE": "transaction_date",
    "TRN-TIME": "transaction_time",
    "TRN-PORTFOLIO-ID": "portfolio_id",
    "TRN-SEQUENCE-NO": "sequence_no",
    "TRN-INVESTMENT-ID": "investment_id",
    "TRN-TYPE": "transaction_type",
    "TRN-QUANTITY": "quantity",
    "TRN-PRICE": "price",
    "TRN-AMOUNT": "amount",
    "TRN-CURRENCY": "currency_code",
    "TRN-STATUS": "status",
    "TRN-PROCESS-DATE": "process_date",
    "TRN-PROCESS-USER": "process_user",
}

_PORTFOLIO_FIELDS: dict[str, str] = {
    "PORT-ID": "portfolio_id",
    "PORT-ACCOUNT-NO": "account_no",
    "PORT-CLIENT-NAME": "client_name",
    "PORT-CLIENT-TYPE": "client_type",
    "PORT-CREATE-DATE": "open_date",
    "PORT-LAST-MAINT": "last_maint",
    "PORT-STATUS": "status",
    "PORT-TOTAL-VALUE": "total_value",
    "PORT-CASH-BALANCE": "cash_balance",
    "PORT-LAST-USER": "last_maint_user",
}

_CONVERTERS: dict[str, Any] = {
    "portfolio_id": to_text,
    "investment_id": to_text,
    "currency_code": to_text,
    "status": to_text,
    "client_name": to_text,
    "client_type": to_text,
    "account_no": to_text,
    "sequence_no": to_text,
    "transaction_type": to_text,
    "last_maint_user": to_text,
    "process_user": to_text,
    "position_date": to_date,
    "transaction_date": to_date,
    "open_date": to_date,
    "transaction_time": to_time,
    "last_maint_date": to_timestamp,
    "process_date": to_timestamp,
    "quantity": lambda value: to_decimal(value, QUANTITY_SCALE),
    "units": lambda value: to_decimal(value, QUANTITY_SCALE),
    "price": lambda value: to_decimal(value, QUANTITY_SCALE),
    "cost_basis": lambda value: to_decimal(value, AMOUNT_SCALE),
    "market_value": lambda value: to_decimal(value, AMOUNT_SCALE),
    "amount": lambda value: to_decimal(value, AMOUNT_SCALE),
    "total_value": lambda value: to_decimal(value, AMOUNT_SCALE),
    "cash_balance": lambda value: to_decimal(value, AMOUNT_SCALE),
}

_NUMERIC_DATE_FIELDS = frozenset({"open_date", "last_maint"})


def canonical_field(name: str) -> str:
    """Canonical name of a legacy field, or the name itself when already canonical."""
    for mapping in (_POSITION_FIELDS, _TRANSACTION_FIELDS, _PORTFOLIO_FIELDS):
        if name in mapping:
            return mapping[name]
    return name


def normalise(values: Mapping[str, object]) -> dict[str, object]:
    """Normalise a record whose keys are canonical or legacy field names."""
    normalised: dict[str, object] = {}
    for name, value in values.items():
        canonical = canonical_field(name)
        converter = _CONVERTERS.get(canonical)
        if converter is None:
            normalised[canonical] = to_text(value) if isinstance(value, str) else value
            continue
        if canonical in _NUMERIC_DATE_FIELDS and isinstance(value, Decimal):
            value = format(int(value), "08d")
        normalised[canonical] = converter(value)
    return normalised


def normalise_extract(
    layout: Layout, records: list[dict[str, str | Decimal]]
) -> list[dict[str, object]]:
    """Normalise decoded legacy records, dropping FILLER items."""
    kept = {field.name for field in layout.fields if "FILLER" not in field.name}
    return [normalise({k: v for k, v in record.items() if k in kept}) for record in records]

"""Fixed-width COBOL record layouts and their decoders.

The parity baseline is a byte-for-byte legacy extract, so the harness needs to
read the record layouts the legacy programs write: the copybook layouts for VSAM
and sequential files (packed-decimal amounts) and the unloaded DISPLAY variant an
extract job produces for the checked-in fixtures.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

EBCDIC = "cp037"
"""Encoding of an extract taken straight off the mainframe."""

ASCII = "ascii"
"""Encoding of the fixtures checked into this repository."""


class Usage(StrEnum):
    """COBOL USAGE clauses the layouts below need."""

    DISPLAY = "DISPLAY"
    COMP_3 = "COMP-3"


class DecodeError(ValueError):
    """A record could not be decoded against its layout."""


@dataclass(frozen=True)
class Field:
    """One elementary item of a record layout.

    ``digits``/``scale`` mirror the PICTURE clause: ``PIC S9(13)V9(2)`` is
    ``digits=15, scale=2, signed=True``.
    """

    name: str
    picture: str
    size: int = 0
    digits: int = 0
    scale: int = 0
    signed: bool = False
    usage: Usage = Usage.DISPLAY
    numeric: bool = False

    def __post_init__(self) -> None:
        if self.numeric and self.digits <= 0:
            raise ValueError(f"{self.name}: numeric field needs a digit count")
        if not self.numeric and self.size <= 0:
            raise ValueError(f"{self.name}: alphanumeric field needs a size")

    @property
    def width(self) -> int:
        """Bytes this field occupies in the record."""
        if not self.numeric:
            return self.size
        if self.usage is Usage.COMP_3:
            return (self.digits + 2) // 2
        return self.digits + (1 if self.signed else 0)


def alpha(name: str, size: int) -> Field:
    """``PIC X(size)``."""
    return Field(name=name, picture=f"X({size})", size=size)


def display(name: str, digits: int, scale: int = 0, *, signed: bool = False) -> Field:
    """``PIC 9(digits)V9(scale)`` held as zoned decimal (one byte per digit)."""
    return Field(
        name=name,
        picture=_picture(digits, scale, signed),
        digits=digits,
        scale=scale,
        signed=signed,
        usage=Usage.DISPLAY,
        numeric=True,
    )


def packed(name: str, digits: int, scale: int = 0, *, signed: bool = True) -> Field:
    """``PIC S9(digits)V9(scale) COMP-3``."""
    return Field(
        name=name,
        picture=f"{_picture(digits, scale, signed)} COMP-3",
        digits=digits,
        scale=scale,
        signed=signed,
        usage=Usage.COMP_3,
        numeric=True,
    )


def _picture(digits: int, scale: int, signed: bool) -> str:
    integer = digits - scale
    picture = "S" if signed else ""
    picture += f"9({integer})" if integer else ""
    if scale:
        picture += f"V9({scale})"
    return picture


@dataclass(frozen=True)
class Layout:
    """An ordered list of fields making up one fixed-length record."""

    name: str
    fields: tuple[Field, ...]
    source: str

    @property
    def length(self) -> int:
        return sum(field.width for field in self.fields)

    def decode(self, record: bytes, *, encoding: str = ASCII) -> dict[str, str | Decimal]:
        """Decode one record into ``{field name: value}``."""
        if len(record) != self.length:
            raise DecodeError(
                f"{self.name}: expected {self.length} bytes, got {len(record)}",
            )
        values: dict[str, str | Decimal] = {}
        offset = 0
        for field in self.fields:
            chunk = record[offset : offset + field.width]
            offset += field.width
            values[field.name] = _decode_field(field, chunk, encoding)
        return values

    def decode_all(self, data: bytes, *, encoding: str = ASCII) -> list[dict[str, str | Decimal]]:
        """Decode a whole unblocked fixed-length file."""
        if len(data) % self.length:
            raise DecodeError(
                f"{self.name}: {len(data)} bytes is not a multiple of {self.length}",
            )
        return [self.decode(record, encoding=encoding) for record in _chunks(data, self.length)]

    def encode(self, values: Mapping[str, str | Decimal], *, encoding: str = ASCII) -> bytes:
        """Build a record from ``values``; used to produce fixtures and test input."""
        parts: list[bytes] = []
        for field in self.fields:
            parts.append(_encode_field(field, values.get(field.name, ""), encoding))
        return b"".join(parts)


def _chunks(data: bytes, size: int) -> Iterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start : start + size]


def _decode_field(field: Field, chunk: bytes, encoding: str) -> str | Decimal:
    if not field.numeric:
        return chunk.decode(encoding).rstrip()
    if field.usage is Usage.COMP_3:
        return _decode_packed(field, chunk)
    return _decode_display(field, chunk, encoding)


def _decode_display(field: Field, chunk: bytes, encoding: str) -> Decimal:
    text = chunk.decode(encoding)
    sign = 1
    if field.signed:
        marker, text = text[0], text[1:]
        if marker not in "+-":
            raise DecodeError(f"{field.name}: missing sign, got {marker!r}")
        sign = -1 if marker == "-" else 1
    if not text.isdigit():
        raise DecodeError(f"{field.name}: {text!r} is not numeric")
    return _scaled(sign * int(text), field.scale)


def _decode_packed(field: Field, chunk: bytes) -> Decimal:
    nibbles = chunk.hex()
    digits, sign_nibble = nibbles[:-1], nibbles[-1]
    if not digits.isdigit():
        raise DecodeError(f"{field.name}: {nibbles!r} is not packed decimal")
    if sign_nibble.lower() not in "abcdef":
        raise DecodeError(f"{field.name}: {sign_nibble!r} is not a sign nibble")
    sign = -1 if sign_nibble.lower() in "bd" else 1
    return _scaled(sign * int(digits), field.scale)


def _scaled(value: int, scale: int) -> Decimal:
    return Decimal(value).scaleb(-scale) if scale else Decimal(value)


def _encode_field(field: Field, value: str | Decimal, encoding: str) -> bytes:
    if not field.numeric:
        return str(value).ljust(field.size)[: field.size].encode(encoding)
    number = Decimal(value or 0).scaleb(field.scale).to_integral_value()
    magnitude = abs(int(number))
    digits = str(magnitude).rjust(field.digits, "0")
    if len(digits) > field.digits:
        raise DecodeError(f"{field.name}: {value} does not fit in {field.picture}")
    if field.usage is Usage.COMP_3:
        sign_nibble = "d" if number < 0 else "c"
        nibbles = digits.rjust(field.width * 2 - 1, "0") + sign_nibble
        return bytes.fromhex(nibbles)
    sign = ("-" if number < 0 else "+") if field.signed else ""
    return f"{sign}{digits}".encode(encoding)


POSITION_RECORD = Layout(
    name="POSITION-RECORD",
    source="src/copybook/common/POSREC.cpy",
    fields=(
        alpha("POS-PORTFOLIO-ID", 8),
        alpha("POS-DATE", 8),
        alpha("POS-INVESTMENT-ID", 10),
        packed("POS-QUANTITY", 15, 4),
        packed("POS-COST-BASIS", 15, 2),
        packed("POS-MARKET-VALUE", 15, 2),
        alpha("POS-CURRENCY", 3),
        alpha("POS-STATUS", 1),
        alpha("POS-LAST-MAINT-DATE", 26),
        alpha("POS-LAST-MAINT-USER", 8),
        alpha("POS-FILLER", 50),
    ),
)

PORTFOLIO_RECORD = Layout(
    name="PORT-RECORD",
    source="src/copybook/common/PORTFLIO.cpy",
    fields=(
        alpha("PORT-ID", 8),
        alpha("PORT-ACCOUNT-NO", 10),
        alpha("PORT-CLIENT-NAME", 30),
        alpha("PORT-CLIENT-TYPE", 1),
        display("PORT-CREATE-DATE", 8),
        display("PORT-LAST-MAINT", 8),
        alpha("PORT-STATUS", 1),
        packed("PORT-TOTAL-VALUE", 15, 2),
        packed("PORT-CASH-BALANCE", 15, 2),
        alpha("PORT-LAST-USER", 8),
        display("PORT-LAST-TRANS", 8),
        alpha("PORT-FILLER", 50),
    ),
)

TRANSACTION_RECORD = Layout(
    name="TRANSACTION-RECORD",
    source="src/copybook/common/TRNREC.cpy",
    fields=(
        alpha("TRN-DATE", 8),
        alpha("TRN-TIME", 6),
        alpha("TRN-PORTFOLIO-ID", 8),
        alpha("TRN-SEQUENCE-NO", 6),
        alpha("TRN-INVESTMENT-ID", 10),
        alpha("TRN-TYPE", 2),
        packed("TRN-QUANTITY", 15, 4),
        packed("TRN-PRICE", 15, 4),
        packed("TRN-AMOUNT", 15, 2),
        alpha("TRN-CURRENCY", 3),
        alpha("TRN-STATUS", 1),
        alpha("TRN-PROCESS-DATE", 26),
        alpha("TRN-PROCESS-USER", 8),
        alpha("TRN-FILLER", 50),
    ),
)

HISTORY_RECORD = Layout(
    name="HISTORY-RECORD",
    source="src/copybook/common/HISTREC.cpy",
    fields=(
        alpha("HIST-PORTFOLIO-ID", 8),
        alpha("HIST-DATE", 8),
        alpha("HIST-TIME", 6),
        alpha("HIST-SEQ-NO", 4),
        alpha("HIST-RECORD-TYPE", 2),
        alpha("HIST-ACTION-CODE", 1),
        alpha("HIST-BEFORE-IMAGE", 400),
        alpha("HIST-AFTER-IMAGE", 400),
        alpha("HIST-REASON-CODE", 4),
        alpha("HIST-PROCESS-DATE", 26),
        alpha("HIST-PROCESS-USER", 8),
        alpha("HIST-FILLER", 50),
    ),
)

TEST_CASE_RECORD = Layout(
    name="TEST-CASE-RECORD",
    source="src/programs/test/TSTVAL00.cbl",
    fields=(
        alpha("TEST-ID", 10),
        alpha("TEST-TYPE", 10),
        alpha("TEST-DESCRIPTION", 50),
        alpha("TEST-PARAMETERS", 100),
    ),
)


def _unpacked(layout: Layout, name: str) -> Layout:
    """The same layout with COMP-3 items unloaded to DISPLAY."""
    fields = tuple(
        display(field.name, field.digits, field.scale, signed=field.signed)
        if field.usage is Usage.COMP_3
        else field
        for field in layout.fields
    )
    return Layout(name=name, fields=fields, source=layout.source)


POSITION_EXTRACT = _unpacked(POSITION_RECORD, "POSITION-EXTRACT")
"""DISPLAY unload of POSITION-RECORD: the format of the checked-in baselines."""

PORTFOLIO_EXTRACT = _unpacked(PORTFOLIO_RECORD, "PORTFOLIO-EXTRACT")

TRANSACTION_EXTRACT = _unpacked(TRANSACTION_RECORD, "TRANSACTION-EXTRACT")

LAYOUTS: Mapping[str, Layout] = {
    layout.name: layout
    for layout in (
        POSITION_RECORD,
        PORTFOLIO_RECORD,
        TRANSACTION_RECORD,
        HISTORY_RECORD,
        TEST_CASE_RECORD,
        POSITION_EXTRACT,
        PORTFOLIO_EXTRACT,
        TRANSACTION_EXTRACT,
    )
}


def layout_by_name(name: str) -> Layout:
    try:
        return LAYOUTS[name]
    except KeyError as exc:
        raise KeyError(f"unknown record layout {name!r}") from exc


def decode_file(
    layout: Layout, path: str, *, encoding: str = ASCII
) -> list[dict[str, str | Decimal]]:
    """Decode every record of a fixed-length file."""
    with open(path, "rb") as handle:
        return layout.decode_all(handle.read(), encoding=encoding)


def encode_records(
    layout: Layout, records: Sequence[Mapping[str, str | Decimal]], *, encoding: str = ASCII
) -> bytes:
    return b"".join(layout.encode(record, encoding=encoding) for record in records)

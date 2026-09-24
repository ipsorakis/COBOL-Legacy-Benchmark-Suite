"""Field-level structured diffing of legacy and ported results.

A parity run reports *what* differs, never a bare pass/fail: every difference
carries the record key, the field, both values and why it was flagged, so the
report can be read without re-running anything.
"""

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Any

from parity.domains import in_domain
from parity.normalize import normalise


class DiffKind(StrEnum):
    """Why a field or record was flagged."""

    VALUE = "value_mismatch"
    TYPE = "type_mismatch"
    MISSING_FIELD = "missing_field"
    EXTRA_FIELD = "extra_field"
    MISSING_RECORD = "missing_record"
    EXTRA_RECORD = "extra_record"
    DOMAIN = "domain_violation"
    PRECISION = "precision_mismatch"
    WITHIN_TOLERANCE = "within_tolerance"


@dataclass(frozen=True)
class Tolerance:
    """An accepted difference on one field.

    A tolerance has to say why it exists; an unjustified one is rejected so that
    "make the diff go away" is never the cheapest way to get a green run.
    """

    field: str
    absolute: Decimal
    justification: str

    def __post_init__(self) -> None:
        if self.absolute < 0:
            raise ValueError(f"{self.field}: tolerance cannot be negative")
        if not self.justification.strip():
            raise ValueError(f"{self.field}: tolerance needs a justification")

    def accepts(self, expected: object, actual: object) -> bool:
        if not isinstance(expected, Decimal) or not isinstance(actual, Decimal):
            return False
        return abs(expected - actual) <= self.absolute


@dataclass(frozen=True)
class Difference:
    """One difference between the legacy and the ported result."""

    kind: DiffKind
    record: str
    field: str
    expected: object = None
    actual: object = None
    note: str = ""

    @property
    def accepted(self) -> bool:
        """Whether this difference was explained by a justified tolerance."""
        return self.kind is DiffKind.WITHIN_TOLERANCE

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "record": self.record,
            "field": self.field,
            "expected": _plain(self.expected),
            "actual": _plain(self.actual),
            "note": self.note,
        }

    def __str__(self) -> str:
        location = f"{self.record}.{self.field}" if self.field else self.record
        detail = f"expected {_plain(self.expected)!r}, got {_plain(self.actual)!r}"
        return f"[{self.kind.value}] {location}: {detail}" + (
            f" ({self.note})" if self.note else ""
        )


@dataclass
class DiffReport:
    """Every difference found by one comparison."""

    differences: list[Difference] = field(default_factory=list)

    @property
    def blocking(self) -> list[Difference]:
        """Differences that were not explained by a tolerance."""
        return [difference for difference in self.differences if not difference.accepted]

    @property
    def matched(self) -> bool:
        return not self.blocking

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for difference in self.differences:
            counts[difference.kind.value] = counts.get(difference.kind.value, 0) + 1
        return counts

    def extend(self, differences: Iterable[Difference]) -> None:
        self.differences.extend(differences)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "counts": self.counts(),
            "differences": [difference.to_dict() for difference in self.differences],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_text(self) -> str:
        if not self.differences:
            return "no differences"
        return "\n".join(str(difference) for difference in self.differences)


def _plain(value: object) -> Any:
    """JSON-safe rendering that keeps the exact decimal scale."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def _tolerance_for(field_name: str, tolerances: Sequence[Tolerance]) -> Tolerance | None:
    for tolerance in tolerances:
        if tolerance.field == field_name:
            return tolerance
    return None


def compare_records(
    expected: Mapping[str, object],
    actual: Mapping[str, object],
    *,
    record: str = "",
    tolerances: Sequence[Tolerance] = (),
    ignore: Iterable[str] = (),
    domains: Mapping[str, str] | None = None,
) -> list[Difference]:
    """Compare two records field by field after normalising both sides.

    ``domains`` maps a canonical field onto a legacy code domain (for instance
    ``{"status": "POS-STATUS"}``); the actual value is then also checked for
    membership, so a plausible-looking but out-of-domain code is reported even
    when both sides happen to agree.
    """
    skip = set(ignore)
    left = normalise(expected)
    right = normalise(actual)
    differences: list[Difference] = []

    for name in sorted(set(left) | set(right)):
        if name in skip:
            continue
        if name not in right:
            differences.append(
                Difference(DiffKind.MISSING_FIELD, record, name, expected=left[name])
            )
            continue
        if name not in left:
            differences.append(Difference(DiffKind.EXTRA_FIELD, record, name, actual=right[name]))
            continue
        differences.extend(
            _compare_value(record, name, left[name], right[name], tolerances, domains)
        )
    return differences


def _compare_value(
    record: str,
    name: str,
    expected: object,
    actual: object,
    tolerances: Sequence[Tolerance],
    domains: Mapping[str, str] | None,
) -> list[Difference]:
    differences: list[Difference] = []
    if domains and name in domains and isinstance(actual, str):
        domain = domains[name]
        if not in_domain(domain, actual):
            differences.append(
                Difference(
                    DiffKind.DOMAIN,
                    record,
                    name,
                    expected=expected,
                    actual=actual,
                    note=f"{actual!r} is not a member of {domain}",
                )
            )
    if expected == actual:
        return differences
    if type(expected) is not type(actual):
        differences.append(
            Difference(
                DiffKind.TYPE,
                record,
                name,
                expected=expected,
                actual=actual,
                note=f"{type(expected).__name__} vs {type(actual).__name__}",
            )
        )
        return differences
    tolerance = _tolerance_for(name, tolerances)
    if tolerance is not None and tolerance.accepts(expected, actual):
        differences.append(
            Difference(
                DiffKind.WITHIN_TOLERANCE,
                record,
                name,
                expected=expected,
                actual=actual,
                note=tolerance.justification,
            )
        )
        return differences
    differences.append(Difference(DiffKind.VALUE, record, name, expected=expected, actual=actual))
    return differences


def record_key(values: Mapping[str, object], key_fields: Sequence[str]) -> str:
    """Stable identity of a record, used to pair the two sides up."""
    normalised = normalise(values)
    parts: list[str] = []
    for name in key_fields:
        if name not in normalised:
            raise KeyError(f"key field {name!r} missing from record")
        parts.append(str(_plain(normalised[name])))
    return "|".join(parts)


def precision_differences(
    records: Sequence[Mapping[str, object]],
    *,
    scales: Mapping[str, int],
    key_fields: Sequence[str] = (),
) -> list[Difference]:
    """Report values carrying more decimal places than the legacy picture allows.

    Checked before normalisation, which rejects over-precise values outright: a
    cost basis the ported service computes at three decimals has to appear in
    the report as a precision difference rather than as a harness error.
    """
    differences: list[Difference] = []
    for index, record in enumerate(records, start=1):
        identity = "|".join(str(record.get(name, "")).strip() for name in key_fields)
        ident = identity or f"row {index}"
        for name, scale in scales.items():
            if name not in record:
                continue
            value = record[name]
            if isinstance(value, Decimal):
                number = value
            elif isinstance(value, str | int):
                try:
                    number = Decimal(str(value).strip())
                except ArithmeticError:
                    differences.append(
                        Difference(
                            DiffKind.TYPE,
                            ident,
                            name,
                            expected=f"decimal with at most {scale} places",
                            actual=value,
                        )
                    )
                    continue
            else:
                differences.append(
                    Difference(
                        DiffKind.TYPE,
                        ident,
                        name,
                        expected=f"decimal with at most {scale} places",
                        actual=value,
                        note=f"{type(value).__name__} is not a decimal",
                    )
                )
                continue
            places = -int(number.as_tuple().exponent)
            if places > scale:
                differences.append(
                    Difference(
                        DiffKind.PRECISION,
                        ident,
                        name,
                        expected=f"at most {scale} decimal places",
                        actual=format(number, "f"),
                        note=f"{places} decimal places, legacy picture allows {scale}",
                    )
                )
    return differences


def domain_differences(
    records: Sequence[Mapping[str, object]],
    *,
    domains: Mapping[str, str],
    key_fields: Sequence[str] = (),
) -> list[Difference]:
    """Report values outside their legacy code domain, without pairing records.

    This checks the ported side on its own, so an out-of-domain status is
    reported even for a record the legacy baseline does not contain.
    """
    differences: list[Difference] = []
    for index, record in enumerate(records, start=1):
        normalised = normalise(record)
        identity = "|".join(str(_plain(normalised.get(name, ""))) for name in key_fields)
        ident = identity or f"row {index}"
        for name, domain in domains.items():
            if name not in normalised:
                differences.append(Difference(DiffKind.MISSING_FIELD, ident, name))
                continue
            value = normalised[name]
            if not isinstance(value, str):
                differences.append(
                    Difference(
                        DiffKind.TYPE,
                        ident,
                        name,
                        expected=f"member of {domain}",
                        actual=value,
                        note=f"{type(value).__name__} is not a code value",
                    )
                )
                continue
            if not in_domain(domain, value):
                differences.append(
                    Difference(
                        DiffKind.DOMAIN,
                        ident,
                        name,
                        expected=f"member of {domain}",
                        actual=value,
                        note=f"{value!r} is not a member of {domain}",
                    )
                )
    return differences


def compare_record_sets(
    expected: Sequence[Mapping[str, object]],
    actual: Sequence[Mapping[str, object]],
    *,
    key_fields: Sequence[str],
    tolerances: Sequence[Tolerance] = (),
    ignore: Iterable[str] = (),
    domains: Mapping[str, str] | None = None,
) -> DiffReport:
    """Diff two sets of records, pairing them on ``key_fields``."""
    left = {record_key(record, key_fields): record for record in expected}
    right = {record_key(record, key_fields): record for record in actual}
    report = DiffReport()

    for key in sorted(set(left) - set(right)):
        report.differences.append(
            Difference(DiffKind.MISSING_RECORD, key, "", expected=_plain(normalise(left[key])))
        )
    for key in sorted(set(right) - set(left)):
        report.differences.append(
            Difference(DiffKind.EXTRA_RECORD, key, "", actual=_plain(normalise(right[key])))
        )
    for key in sorted(set(left) & set(right)):
        report.extend(
            compare_records(
                left[key],
                right[key],
                record=key,
                tolerances=tolerances,
                ignore=ignore,
                domains=domains,
            )
        )
    return report

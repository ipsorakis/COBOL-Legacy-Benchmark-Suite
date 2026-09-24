"""Loading of the legacy baseline fixtures and their provenance (KAN-103).

Every baseline in ``parity/baselines`` is described in ``manifest.json``: the
layout it is written in, a checksum, where the data came from and how it was
obtained. Provenance is mandatory because it decides how much a green parity run
is worth - a run against baselines derived from the COBOL source proves the port
matches the *specification*, not the production system, and only a baseline
captured from a real execution can be signed off as a benchmark.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from parity.normalize import normalise_extract
from parity.records import Layout, layout_by_name

BASELINE_DIR = Path(__file__).parent / "baselines"
MANIFEST = BASELINE_DIR / "manifest.json"


class CaptureMethod(StrEnum):
    """How a baseline was obtained."""

    MAINFRAME_EXTRACT = "mainframe-extract"
    """Unloaded from a real run of the legacy program. Can be signed off."""

    DERIVED_FROM_SOURCE = "derived-from-source-spec"
    """Written from the copybooks, program source and specification by hand."""


class BaselineError(ValueError):
    """A baseline is missing, corrupt or lacks provenance."""


@dataclass(frozen=True)
class Provenance:
    """Where a baseline came from."""

    source_program: str
    capture_method: CaptureMethod
    captured_at: str
    captured_by: str
    inputs: str
    notes: str
    requires_sign_off: bool = False
    sign_off_ticket: str | None = None

    @property
    def is_executed(self) -> bool:
        """Whether the baseline came out of a real legacy run."""
        return self.capture_method is CaptureMethod.MAINFRAME_EXTRACT


@dataclass(frozen=True)
class Baseline:
    """One baseline file plus its provenance."""

    name: str
    path: Path
    layout: Layout | None
    encoding: str
    sha256: str
    records: int
    provenance: Provenance

    def read_bytes(self) -> bytes:
        data = self.path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != self.sha256:
            raise BaselineError(
                f"{self.name}: checksum mismatch, manifest has {self.sha256}, file is {digest}"
            )
        return data

    def raw_records(self) -> list[dict[str, str | Decimal]]:
        """Decode the fixture against its layout, without normalising."""
        if self.layout is None:
            raise BaselineError(f"{self.name}: not a fixed-width baseline")
        return self.layout.decode_all(self.read_bytes(), encoding=self.encoding)

    def records_normalised(self) -> list[dict[str, object]]:
        """Decoded and normalised records, ready to diff."""
        if self.layout is None:
            raise BaselineError(f"{self.name}: not a fixed-width baseline")
        return normalise_extract(self.layout, self.raw_records())

    def json(self) -> Any:
        """Contents of a JSON baseline (inquiry responses, price tables)."""
        if self.layout is not None:
            raise BaselineError(f"{self.name}: fixed-width baseline, use records_normalised()")
        return json.loads(self.read_bytes().decode(self.encoding))


def _provenance(entry: Mapping[str, Any], name: str) -> Provenance:
    required = ("source_program", "capture_method", "captured_at", "captured_by", "inputs", "notes")
    missing = [key for key in required if not str(entry.get(key, "")).strip()]
    if missing:
        raise BaselineError(f"{name}: manifest entry is missing {', '.join(missing)}")
    try:
        method = CaptureMethod(entry["capture_method"])
    except ValueError as exc:
        raise BaselineError(f"{name}: unknown capture_method {entry['capture_method']!r}") from exc
    requires_sign_off = bool(entry.get("requires_sign_off", False))
    ticket = entry.get("sign_off_ticket")
    if requires_sign_off and not ticket:
        raise BaselineError(f"{name}: requires_sign_off without a sign_off_ticket")
    return Provenance(
        source_program=str(entry["source_program"]),
        capture_method=method,
        captured_at=str(entry["captured_at"]),
        captured_by=str(entry["captured_by"]),
        inputs=str(entry["inputs"]),
        notes=str(entry["notes"]),
        requires_sign_off=requires_sign_off,
        sign_off_ticket=str(ticket) if ticket else None,
    )


def load_manifest(manifest: Path = MANIFEST) -> dict[str, Baseline]:
    """Read the manifest and validate every entry it declares."""
    document = json.loads(manifest.read_text(encoding="utf-8"))
    baselines: dict[str, Baseline] = {}
    for entry in document["baselines"]:
        name = str(entry["name"])
        path = manifest.parent / str(entry["file"])
        if not path.is_file():
            raise BaselineError(f"{name}: {path} does not exist")
        layout_name = entry.get("layout")
        baselines[name] = Baseline(
            name=name,
            path=path,
            layout=layout_by_name(str(layout_name)) if layout_name else None,
            encoding=str(entry.get("encoding", "ascii")),
            sha256=str(entry["sha256"]),
            records=int(entry.get("records", 0)),
            provenance=_provenance(entry, name),
        )
    return baselines


def baseline(name: str, manifest: Path = MANIFEST) -> Baseline:
    """One baseline by name."""
    baselines = load_manifest(manifest)
    try:
        return baselines[name]
    except KeyError as exc:
        raise BaselineError(f"unknown baseline {name!r}") from exc


def baseline_names(manifest: Path = MANIFEST) -> Sequence[str]:
    return sorted(load_manifest(manifest))


def unsigned_baselines(manifest: Path = MANIFEST) -> list[Baseline]:
    """Baselines that were not captured from a legacy execution."""
    return [item for item in load_manifest(manifest).values() if not item.provenance.is_executed]

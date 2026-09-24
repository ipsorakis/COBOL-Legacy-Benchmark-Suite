# COBOL-vs-FastAPI parity harness

The harness is the port of `src/programs/test/TSTVAL00.cbl`. It runs the same inputs through
recorded legacy COBOL output and the FastAPI implementation and reports every field-level
difference. TSTVAL00 wrote one pass/fail flag per case; this port keeps the case table, the
type dispatch, the metrics and the 132-column listing, and replaces the flag with a
structured diff.

```
make parity                 # writes parity-report/
uv run python -m parity --out parity-report [--type FUNCTIONAL] [--fail-on-blocked]
```

Three artifacts are produced:

| file | contents |
| --- | --- |
| `test-validation-report.txt` | the TSTVAL00 listing: one detail line per case plus the summary |
| `parity-diff.json` | the structured diff, per case and per field |
| `parity-diff.txt` | the same diff, readable in a CI log |

## What is compared

| case | covers |
| --- | --- |
| `PAR-POS-01` | position quantity, cost basis and market value after batch processing |
| `PAR-POS-02` | decimal scale of batch output: `S9(11)V9(4)` quantities, `S9(13)V9(2)` amounts |
| `PAR-POS-03` | `POS-STATUS` code domain |
| `PAR-HST-01` | every transaction value preserved by the history load |
| `PAR-INP-01` / `PAR-INP-02` | `INQPORT` success response and the not-found path |
| `PAR-INH-01` / `PAR-INH-02` | `INQHIST` first page, row order, and the `S9(9)V99` screen scale |
| `PAR-PRF-01` | the performance budget TSTVAL00 measured with elapsed time |

A difference names its kind (`value_mismatch`, `type_mismatch`, `precision_mismatch`,
`domain_violation`, `missing_record`, `extra_record`, `missing_field`, `extra_field`,
`within_tolerance`), the record key, the field, both values and a note. Numeric tolerances
must carry a written justification, so an accepted rounding difference is still visible in
the report rather than silently equal.

## Blocked cases

A case whose ported service does not exist yet is reported as `BLCK` against the ticket that
owns it — KAN-20 (`INQPORT`), KAN-21 (`INQHIST`), KAN-24 (position update), KAN-25 (history
load) — never as a pass. `PortedSystem` is a set of optional adapters; as each service lands,
pass it in and its cases start comparing:

```python
PortedSystem(portfolio_inquiry=InquiryAdapter(session))
```

The CI job runs the suite on every pull request and uploads the report as an artifact. It
does not fail on blocked cases, so the pending list stays visible while the ports land; add
`--fail-on-blocked` once all four services exist.

## Baselines and their provenance

`parity/baselines/` holds the legacy side: fixed-width records decoded through the copybook
layouts in `parity/records.py`, and JSON for the two inquiry screens. Every file is listed in
`manifest.json` with a SHA-256 checksum, which is verified on read, and with provenance:
source program, capture method, timestamp, inputs and notes.

The checked-in files have capture method `derived-from-source-spec`: they were built from the
copybooks and the COBOL source, not extracted from a mainframe run. They demonstrate
conformance to the interpreted specification and are marked `requires_sign_off`, with the
arithmetic assumptions (purchase cost basis from truncated transaction amounts, average-cost
sales, market value as quantity times closing price) recorded in the manifest notes.
Replacing them with a real extract (KAN-103) is what turns the suite into an authoritative
benchmark; `unsigned_baselines()` lists what still needs that sign-off.

Where the copybooks and the documentation disagree — `PORT-STATUS` (`A/C/S` vs `A/I/C`),
`TRN-TYPE` (`BU/SL/TR/FE` vs `B/S`), `PORT-ID` length — `parity/domains.py` treats the
copybook as canonical and records the divergence in `DOMAIN_DIVERGENCES` rather than
resolving it silently.

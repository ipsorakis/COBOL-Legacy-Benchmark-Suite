"""The parity cases KAN-31 asks for, bound to the legacy baselines.

Each case pairs a baseline from ``parity/baselines`` with one capability of the
ported system and returns a structured diff. Every case is runnable today: with
no ported services wired in, the run reports them as blocked against the ticket
that owns the missing service.
"""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from parity.adapters import PortedSystem, Record
from parity.cases import CaseType, ParityCase
from parity.diff import (
    Difference,
    DiffKind,
    DiffReport,
    compare_record_sets,
    compare_records,
    domain_differences,
    precision_differences,
)
from parity.fixtures import baseline
from parity.normalize import AMOUNT_SCALE, QUANTITY_SCALE

BATCH_DATA_SET = "transactions_input"
"""Name of the input baseline a batch case asks the ported service to process."""

BUSINESS_DATE = date(2024, 3, 20)
ACCOUNT_NO = "1000000001"
PORTFOLIO_ID = "PORT0001"

AUDIT_FIELDS = ("last_maint_date", "last_maint_user", "process_date", "process_user")
"""Fields that record who wrote the row and when.

They are excluded from value comparison because they differ by construction -
the legacy extract carries the mainframe job's stamp - not because differences
there are acceptable. The ported services are expected to populate them, which
the presence checks below still enforce.
"""

POSITION_KEYS = ("portfolio_id", "position_date", "investment_id")
TRANSACTION_KEYS = ("portfolio_id", "sequence_no")

POSITION_SCALES: Mapping[str, int] = {
    "quantity": QUANTITY_SCALE,
    "cost_basis": AMOUNT_SCALE,
    "market_value": AMOUNT_SCALE,
}

TRANSACTION_SCALES: Mapping[str, int] = {
    "quantity": QUANTITY_SCALE,
    "price": QUANTITY_SCALE,
    "amount": AMOUNT_SCALE,
}

POSITION_DOMAINS: Mapping[str, str] = {"status": "POS-STATUS"}
TRANSACTION_DOMAINS: Mapping[str, str] = {
    "transaction_type": "TRN-TYPE",
    "status": "TRN-STATUS",
}


def _missing_audit_fields(records: Sequence[Record], keys: Sequence[str]) -> list[Difference]:
    """Audit fields are exempt from value comparison but not from existing."""
    differences: list[Difference] = []
    for index, record in enumerate(records, start=1):
        identity = "|".join(str(record.get(name, "")).strip() for name in keys) or f"row {index}"
        for name in AUDIT_FIELDS:
            if name in record and not str(record[name]).strip():
                differences.append(
                    Difference(
                        DiffKind.MISSING_FIELD,
                        identity,
                        name,
                        note="audit field is not populated",
                    )
                )
    return differences


def _positions_after_batch(system: PortedSystem) -> tuple[list[dict[str, object]], list[Record]]:
    expected = baseline("positions_after_batch").records_normalised()
    actual = list(system.require_batch_positions().positions_after_batch(BATCH_DATA_SET))
    return expected, actual


def batch_positions(system: PortedSystem) -> DiffReport:
    """Positions and cost basis after the batch run, field by field."""
    expected, actual = _positions_after_batch(system)
    report = compare_record_sets(
        expected,
        actual,
        key_fields=POSITION_KEYS,
        ignore=AUDIT_FIELDS,
        domains=POSITION_DOMAINS,
    )
    report.extend(_missing_audit_fields(actual, POSITION_KEYS))
    return report


def batch_position_precision(system: PortedSystem) -> DiffReport:
    """Decimal scale of the batch output, checked before any normalisation.

    POS-QUANTITY is PIC S9(11)V9(4) and the amounts are PIC S9(13)V9(2); a value
    with more places than that means the ported arithmetic rounds somewhere the
    legacy program does not, even when the two sides agree once rounded.
    """
    _, actual = _positions_after_batch(system)
    report = DiffReport()
    report.extend(precision_differences(actual, scales=POSITION_SCALES, key_fields=POSITION_KEYS))
    return report


def batch_position_domains(system: PortedSystem) -> DiffReport:
    """POS-STATUS of every row the batch produced is a legacy code."""
    _, actual = _positions_after_batch(system)
    report = DiffReport()
    report.extend(domain_differences(actual, domains=POSITION_DOMAINS, key_fields=POSITION_KEYS))
    return report


def history_load(system: PortedSystem) -> DiffReport:
    """History rows the load wrote against the transactions it was given.

    The legacy history file has no checked-in extract, so the baseline is the
    input batch: this proves the load carried every transaction across without
    altering its values, not that the HISTREC before/after images match.
    """
    expected = baseline("transactions_input").records_normalised()
    actual = list(system.require_batch_history().history_after_load(BATCH_DATA_SET))
    report = compare_record_sets(
        expected,
        actual,
        key_fields=TRANSACTION_KEYS,
        ignore=(*AUDIT_FIELDS, "status"),
        domains=TRANSACTION_DOMAINS,
    )
    report.extend(
        precision_differences(actual, scales=TRANSACTION_SCALES, key_fields=TRANSACTION_KEYS)
    )
    return report


def _inqport_baseline(account_no: str) -> Mapping[str, object]:
    for entry in baseline("inqport_responses").json():
        if entry["request"]["account_no"] == account_no:
            response: Mapping[str, object] = entry["response"]
            return response
    raise KeyError(f"no INQPORT baseline for account {account_no!r}")


def inqport_position(system: PortedSystem) -> DiffReport:
    """INQPORT response for an account that holds a position."""
    expected = _inqport_baseline(ACCOUNT_NO)
    actual = system.require_portfolio_inquiry().portfolio_inquiry(ACCOUNT_NO)
    report = DiffReport()
    report.extend(
        compare_records(
            expected,
            actual,
            record=f"INQPORT|{ACCOUNT_NO}",
            ignore=AUDIT_FIELDS,
            domains=POSITION_DOMAINS,
        )
    )
    report.extend(
        precision_differences([actual], scales=POSITION_SCALES, key_fields=("investment_id",))
    )
    return report


def inqport_not_found(system: PortedSystem) -> DiffReport:
    """INQPORT response for an account with no position (P900-NOT-FOUND)."""
    missing = "9999999999"
    expected = _inqport_baseline(missing)
    actual = system.require_portfolio_inquiry().portfolio_inquiry(missing)
    report = DiffReport()
    report.extend(compare_records(expected, actual, record=f"INQPORT|{missing}"))
    return report


def _numbered(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Give ordered rows a key, so the diff pairs them by position."""
    return [{"row_number": index, **dict(row)} for index, row in enumerate(rows, start=1)]


def _rows(response: Mapping[str, object]) -> list[Mapping[str, object]]:
    """The display rows of an inquiry response, rejecting any other shape."""
    rows = response.get("rows", [])
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes):
        raise TypeError(f"inquiry response 'rows' is {type(rows).__name__}, not a sequence")
    typed: list[Mapping[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError(f"inquiry row is {type(row).__name__}, not a mapping")
        typed.append(row)
    return typed


def inqhist_page(system: PortedSystem) -> DiffReport:
    """INQHIST first page: the rows, their order and the envelope around them."""
    entry = baseline("inqhist_responses").json()[0]
    expected = entry["response"]
    actual = system.require_history_inquiry().history_inquiry(
        PORTFOLIO_ID, BUSINESS_DATE, BUSINESS_DATE, page=1
    )
    report = compare_record_sets(
        _numbered(expected["rows"]),
        _numbered(_rows(actual)),
        key_fields=("row_number",),
        domains={"transaction_type": "TRN-TYPE"},
    )
    envelope = {key: value for key, value in expected.items() if key != "rows"}
    report.extend(
        compare_records(
            envelope,
            {key: value for key, value in actual.items() if key != "rows"},
            record=f"INQHIST|{PORTFOLIO_ID}",
        )
    )
    return report


def inqhist_precision(system: PortedSystem) -> DiffReport:
    """Units and price of an INQHIST row.

    WS-HISTORY-ENTRY holds units and price as PIC S9(9)V99 while TRNREC holds
    four decimals, so the legacy screen truncates a fractional quantity. The
    comparison keeps the transaction-level scale and lets the difference surface
    rather than quantising it away.
    """
    actual = system.require_history_inquiry().history_inquiry(
        PORTFOLIO_ID, BUSINESS_DATE, BUSINESS_DATE, page=1
    )
    rows = _numbered(_rows(actual))
    report = DiffReport()
    report.extend(
        precision_differences(
            rows,
            scales={"units": 2, "price": 2, "amount": AMOUNT_SCALE},
            key_fields=("row_number",),
        )
    )
    return report


def batch_throughput(system: PortedSystem) -> DiffReport:
    """PERFORM case: the batch comparison has to finish inside its budget."""
    return batch_positions(system)


CASES: tuple[ParityCase, ...] = (
    ParityCase(
        test_id="PAR-POS-01",
        test_type=CaseType.FUNCTIONAL,
        description="Batch positions and cost basis vs POSUPD extract",
        parameters=f"baseline=positions_after_batch;input={BATCH_DATA_SET}",
        compare=batch_positions,
    ),
    ParityCase(
        test_id="PAR-POS-02",
        test_type=CaseType.FUNCTIONAL,
        description="Batch amount scale: S9(11)V9(4) and S9(13)V9(2)",
        parameters="scales=quantity:4,cost_basis:2,market_value:2",
        compare=batch_position_precision,
    ),
    ParityCase(
        test_id="PAR-POS-03",
        test_type=CaseType.FUNCTIONAL,
        description="POS-STATUS of batch output is a legacy code",
        parameters="domain=POS-STATUS",
        compare=batch_position_domains,
    ),
    ParityCase(
        test_id="PAR-HST-01",
        test_type=CaseType.INTEGRATION,
        description="History load preserves every transaction value",
        parameters=f"baseline=transactions_input;input={BATCH_DATA_SET}",
        compare=history_load,
    ),
    ParityCase(
        test_id="PAR-INP-01",
        test_type=CaseType.FUNCTIONAL,
        description="INQPORT response for an account with a position",
        parameters=f"account_no={ACCOUNT_NO}",
        compare=inqport_position,
    ),
    ParityCase(
        test_id="PAR-INP-02",
        test_type=CaseType.ERROR,
        description="INQPORT not-found message and response code",
        parameters="account_no=9999999999",
        compare=inqport_not_found,
    ),
    ParityCase(
        test_id="PAR-INH-01",
        test_type=CaseType.FUNCTIONAL,
        description="INQHIST first page rows, order and row count",
        parameters=f"portfolio_id={PORTFOLIO_ID};range=20240320-20240320;page=1",
        compare=inqhist_page,
    ),
    ParityCase(
        test_id="PAR-INH-02",
        test_type=CaseType.FUNCTIONAL,
        description="INQHIST units and price scale: S9(9)V99",
        parameters="scales=units:2,price:2,amount:2",
        compare=inqhist_precision,
    ),
    ParityCase(
        test_id="PAR-PRF-01",
        test_type=CaseType.PERFORMANCE,
        description="Batch position parity run inside its budget",
        parameters="budget=30s",
        compare=batch_throughput,
        budget=timedelta(seconds=30),
    ),
)


def expected_positions() -> list[dict[str, object]]:
    """The baseline positions, for a caller that wants the expected side."""
    return baseline("positions_after_batch").records_normalised()

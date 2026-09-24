"""Error-condition test data (TSTGEN00 2400-GEN-ERROR-DATA).

2410-GEN-DATA-ERRORS produces records that break the validation rules in
documentation/operations/test-data-specs.md section 3, and 2420-GEN-PROCESS-ERRORS
produces the file-handling conditions from section 2.2. Each scenario carries the
PORTVAL return code the legacy validator raises, so the parity harness can assert
that the ported service rejects the row for the same reason.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, Any

from app.models import Base, PortfolioMaster, TransactionHistory

if TYPE_CHECKING:
    from tests.factories.data import DataFactory


class ValidationCode(IntEnum):
    """VAL-RETURN-CODES from the PORTVAL copybook."""

    SUCCESS = 0
    INVALID_ID = 1
    INVALID_ACCOUNT = 2
    INVALID_TYPE = 3
    INVALID_AMOUNT = 4


class ErrorKind(StrEnum):
    """ERRLOG ERROR_TYPE: data validation vs. file/process handling."""

    DATA = "D"
    PROCESS = "S"

    @property
    def error_type(self) -> str:
        return self.value


@dataclass(frozen=True)
class ErrorScenario:
    """A row (or pair of rows) that must be rejected, and why.

    ``overrides`` are applied on top of a valid row from the factory, so a scenario
    only states the field it corrupts. ``duplicate`` marks the process errors that need
    a second, already-persisted row to collide with, and ``missing_row`` the ones that
    reference a row that was never written.
    """

    name: str
    description: str
    kind: ErrorKind
    model: type[Base]
    overrides: dict[str, Any]
    validation_code: ValidationCode
    error_code: str
    message: str
    severity: int = 3
    duplicate: bool = False
    missing_row: bool = False
    field_name: str | None = None

    def build(
        self,
        factory: "DataFactory",
        portfolio: PortfolioMaster | None = None,
        **extra: Any,
    ) -> Base:
        """Build the invalid row from ``factory``, applying the scenario overrides."""
        values: dict[str, Any] = {**self.overrides, **extra}
        if self.model is PortfolioMaster:
            return factory.portfolio(**values)
        if self.model is TransactionHistory:
            return factory.transaction(portfolio, **values)
        raise ValueError(f"no builder for {self.model.__name__}")


def data_error_scenarios() -> list[ErrorScenario]:
    """2410-GEN-DATA-ERRORS: rows violating the section 3 validation criteria."""
    return [
        ErrorScenario(
            name="portfolio_id_wrong_prefix",
            description="Portfolio ID must be PORT followed by digits",
            kind=ErrorKind.DATA,
            model=PortfolioMaster,
            overrides={"portfolio_id": "XXXX0001"},
            validation_code=ValidationCode.INVALID_ID,
            error_code="VAL00001",
            message="Invalid Portfolio ID format",
            field_name="portfolio_id",
        ),
        ErrorScenario(
            name="portfolio_id_not_numeric",
            description="Portfolio ID digits must be numeric",
            kind=ErrorKind.DATA,
            model=PortfolioMaster,
            overrides={"portfolio_id": "PORTABCD"},
            validation_code=ValidationCode.INVALID_ID,
            error_code="VAL00001",
            message="Invalid Portfolio ID format",
            field_name="portfolio_id",
        ),
        ErrorScenario(
            name="portfolio_name_all_spaces",
            description="Portfolio name is required and must not be all spaces",
            kind=ErrorKind.DATA,
            model=PortfolioMaster,
            overrides={"portfolio_name": "   "},
            validation_code=ValidationCode.INVALID_ID,
            error_code="VAL00005",
            message="Portfolio name is required",
            field_name="portfolio_name",
        ),
        ErrorScenario(
            name="portfolio_status_unknown",
            description="Status must be A, C or S",
            kind=ErrorKind.DATA,
            model=PortfolioMaster,
            overrides={"status": "X"},
            validation_code=ValidationCode.INVALID_TYPE,
            error_code="VAL00003",
            message="Invalid Investment Type",
            field_name="status",
        ),
        ErrorScenario(
            name="portfolio_missing_client_id",
            description="CLIENT_ID is NOT NULL in PORTFOLIO_MASTER",
            kind=ErrorKind.DATA,
            model=PortfolioMaster,
            overrides={"client_id": None},
            validation_code=ValidationCode.INVALID_ACCOUNT,
            error_code="VAL00002",
            message="Invalid Account Number format",
            field_name="client_id",
        ),
        ErrorScenario(
            name="portfolio_open_date_in_future",
            description="Creation date cannot be a future date",
            kind=ErrorKind.DATA,
            model=PortfolioMaster,
            overrides={"open_date": date(2999, 12, 31)},
            validation_code=ValidationCode.INVALID_ID,
            error_code="VAL00006",
            message="Open date cannot be in the future",
            field_name="open_date",
        ),
        ErrorScenario(
            name="transaction_type_unknown",
            description="Transaction type must be BU, SL, TR or FE",
            kind=ErrorKind.DATA,
            model=TransactionHistory,
            overrides={"transaction_type": "ZZ"},
            validation_code=ValidationCode.INVALID_TYPE,
            error_code="VAL00003",
            message="Invalid Investment Type",
            field_name="transaction_type",
        ),
        ErrorScenario(
            name="transaction_amount_below_minimum",
            description="Transaction amount must be at least 0.01",
            kind=ErrorKind.DATA,
            model=TransactionHistory,
            overrides={"amount": Decimal("0.00")},
            validation_code=ValidationCode.INVALID_AMOUNT,
            error_code="VAL00004",
            message="Amount outside valid range",
            field_name="amount",
        ),
        ErrorScenario(
            name="transaction_amount_above_maximum",
            description="Transaction amount must not exceed 99,999,999,999.99",
            kind=ErrorKind.DATA,
            model=TransactionHistory,
            overrides={"amount": Decimal("100000000000.00")},
            validation_code=ValidationCode.INVALID_AMOUNT,
            error_code="VAL00004",
            message="Amount outside valid range",
            field_name="amount",
        ),
        ErrorScenario(
            name="transaction_missing_amount",
            description="AMOUNT is NOT NULL in TRANSACTION_HISTORY",
            kind=ErrorKind.DATA,
            model=TransactionHistory,
            overrides={"amount": None},
            validation_code=ValidationCode.INVALID_AMOUNT,
            error_code="VAL00004",
            message="Amount is required",
            field_name="amount",
        ),
    ]


def process_error_scenarios() -> list[ErrorScenario]:
    """2420-GEN-PROCESS-ERRORS: the file-handling conditions of section 2.2."""
    return [
        ErrorScenario(
            name="duplicate_portfolio_key",
            description="Writing a portfolio whose key already exists (VSAM status 22)",
            kind=ErrorKind.PROCESS,
            model=PortfolioMaster,
            overrides={},
            validation_code=ValidationCode.INVALID_ID,
            error_code="FIL00022",
            message="Duplicate key violation",
            severity=4,
            duplicate=True,
        ),
        ErrorScenario(
            name="duplicate_transaction_key",
            description="Re-posting a transaction id that is already stored",
            kind=ErrorKind.PROCESS,
            model=TransactionHistory,
            overrides={},
            validation_code=ValidationCode.INVALID_ID,
            error_code="FIL00022",
            message="Duplicate key violation",
            severity=4,
            duplicate=True,
        ),
        ErrorScenario(
            name="transaction_orphan_portfolio",
            description="Transaction for a portfolio that does not exist (VSAM status 23)",
            kind=ErrorKind.PROCESS,
            model=TransactionHistory,
            overrides={"portfolio_id": "PORT9999"},
            validation_code=ValidationCode.INVALID_ID,
            error_code="FIL00023",
            message="Record not found",
            severity=4,
            missing_row=True,
        ),
    ]


def error_scenarios() -> list[ErrorScenario]:
    """Every scenario TSTGEN00 generates under CFG-TEST-TYPE 'ERROR'."""
    return data_error_scenarios() + process_error_scenarios()

"""Seeded factories building canonical-model rows (TSTGEN00 2200-2500)."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from random import Random
from typing import Any

from app.models import (
    AuditLog,
    Base,
    ErrorLog,
    InvestmentPosition,
    PortfolioMaster,
    PositionHistory,
    TransactionHistory,
)
from tests.factories.scenarios import error_scenarios

DEFAULT_SEED = 20240409
"""TSTGEN00 reads its seed from the RANDSEED file; the port defaults to its write date."""

DEFAULT_AS_OF = date(2024, 3, 20)
"""Business date of the sample records in documentation/operations/test-data-specs.md."""

PORTFOLIO_ID_PREFIX = "PORT"
GENERATOR_PROGRAM = "TSTGEN00"
GENERATOR_USER = "TESTGEN"

ACCOUNT_TYPES = ("IN", "CO", "TR")
BRANCH_IDS = ("01", "02", "03", "04")
CURRENCY_CODES = ("USD", "EUR", "GBP")
RISK_LEVELS = ("1", "2", "3", "4", "5")
PORTFOLIO_STATUSES = ("A", "C", "S")
TRANSACTION_TYPES = ("BU", "SL", "TR", "FE")
TRANSACTION_STATUSES = ("P", "F", "R")
POSITION_HISTORY_TYPES = ("BU", "SL", "TR")

MAX_PORTFOLIO_VALUE = Decimal("9999999999999.99")
MIN_TRANSACTION_AMOUNT = Decimal("0.01")
MAX_TRANSACTION_AMOUNT = Decimal("99999999999.99")

_PORTFOLIO_NAMES = ("GROWTH", "INCOME", "BALANCED", "RESERVE", "PENSION")


class DataSetType(StrEnum):
    """CFG-TEST-TYPE values accepted by TSTGEN00 2100-GENERATE-TEST-DATA."""

    PORTFOLIO = "PORTFOLIO"
    TRANSACTION = "TRANSACTN"
    ERROR = "ERROR"
    VOLUME = "VOLUME"


@dataclass(frozen=True)
class GenerationConfig:
    """CONFIG-RECORD: which data set to generate and how much of it."""

    data_set: DataSetType
    volume: int = 1
    positions_per_portfolio: int = 2
    transactions_per_portfolio: int = 3

    def __post_init__(self) -> None:
        if self.volume < 1:
            raise ValueError("volume must be at least 1")
        if self.positions_per_portfolio < 0 or self.transactions_per_portfolio < 0:
            raise ValueError("per-portfolio counts cannot be negative")


@dataclass
class DataSet:
    """Generated rows, grouped by canonical model."""

    portfolios: list[PortfolioMaster] = field(default_factory=list)
    positions: list[InvestmentPosition] = field(default_factory=list)
    transactions: list[TransactionHistory] = field(default_factory=list)
    position_history: list[PositionHistory] = field(default_factory=list)
    error_logs: list[ErrorLog] = field(default_factory=list)
    audit_logs: list[AuditLog] = field(default_factory=list)

    def rows(self) -> list[Base]:
        """Every row in foreign-key safe insert order."""
        ordered: list[Base] = []
        ordered.extend(self.portfolios)
        ordered.extend(self.positions)
        ordered.extend(self.transactions)
        ordered.extend(self.position_history)
        ordered.extend(self.error_logs)
        ordered.extend(self.audit_logs)
        return ordered

    def __len__(self) -> int:
        return len(self.rows())


def build_transaction_id(moment: datetime, sequence: int) -> str:
    """TRANSACTION_ID: YYYYMMDDHHMMSS followed by a 6-digit sequence."""
    if not 0 <= sequence <= 999999:
        raise ValueError("transaction sequence must fit in six digits")
    return f"{moment:%Y%m%d%H%M%S}{sequence:06d}"


class DataFactory:
    """Builds canonical-model rows from a seeded generator.

    Two factories created with the same seed and business date emit identical rows,
    which is what the parity harness needs to compare COBOL and Python output.
    """

    def __init__(self, seed: int = DEFAULT_SEED, as_of: date = DEFAULT_AS_OF) -> None:
        self.seed = seed
        self.as_of = as_of
        self._random = Random(seed)
        self._portfolio_sequence = 0
        self._investment_sequence = 0
        self._transaction_sequence = 0
        self._audit_sequence = 0
        self._error_offset = 0

    def reset(self) -> None:
        """Restart the sequences and the generator, as 1200-INIT-RANDOM does."""
        self._random = Random(self.seed)
        self._portfolio_sequence = 0
        self._investment_sequence = 0
        self._transaction_sequence = 0
        self._audit_sequence = 0
        self._error_offset = 0

    # ------------------------------------------------------------------ ids

    def next_portfolio_id(self) -> str:
        self._portfolio_sequence += 1
        return f"{PORTFOLIO_ID_PREFIX}{self._portfolio_sequence:04d}"

    def next_investment_id(self) -> str:
        self._investment_sequence += 1
        return f"SEC{self._investment_sequence:07d}"

    def next_transaction_id(self, moment: datetime) -> str:
        self._transaction_sequence += 1
        return build_transaction_id(moment, self._transaction_sequence)

    # -------------------------------------------------------------- factories

    def portfolio(self, **overrides: Any) -> PortfolioMaster:
        """PORTFOLIO_MASTER row (2210-GEN-PORT-DATA)."""
        portfolio_id = str(overrides.pop("portfolio_id", self.next_portfolio_id()))
        status = str(overrides.pop("status", self._choice(PORTFOLIO_STATUSES)))
        open_date = overrides.pop("open_date", self.as_of - timedelta(days=self._int(30, 900)))
        values: dict[str, Any] = {
            "portfolio_id": portfolio_id,
            "account_type": self._choice(ACCOUNT_TYPES),
            "branch_id": self._choice(BRANCH_IDS),
            "client_id": f"CLI{portfolio_id[-4:]}000",
            "portfolio_name": f"{self._choice(_PORTFOLIO_NAMES)} PORTFOLIO {portfolio_id}",
            "currency_code": self._choice(CURRENCY_CODES),
            "risk_level": self._choice(RISK_LEVELS),
            "status": status,
            "open_date": open_date,
            "close_date": self.as_of if status == "C" else None,
            "last_maint_date": self._timestamp(),
            "last_maint_user": GENERATOR_USER,
        }
        values.update(overrides)
        return PortfolioMaster(**values)

    def position(
        self, portfolio: PortfolioMaster | None = None, **overrides: Any
    ) -> InvestmentPosition:
        """INVESTMENT_POSITIONS row for ``portfolio``."""
        owner = portfolio if portfolio is not None else self.portfolio()
        quantity = self._decimal(1, 10_000, places=4)
        price = self._decimal(1, 5_000, places=4)
        cost_basis = (quantity * price).quantize(Decimal("0.01"))
        values: dict[str, Any] = {
            "portfolio_id": owner.portfolio_id,
            "investment_id": self.next_investment_id(),
            "position_date": self.as_of,
            "quantity": quantity,
            "cost_basis": cost_basis,
            "market_value": (cost_basis * self._factor()).quantize(Decimal("0.01")),
            "currency_code": owner.currency_code,
            "last_maint_date": self._timestamp(),
            "last_maint_user": GENERATOR_USER,
        }
        values.update(overrides)
        return InvestmentPosition(**values)

    def transaction(
        self, portfolio: PortfolioMaster | None = None, **overrides: Any
    ) -> TransactionHistory:
        """TRANSACTION_HISTORY row (2310-GEN-TRAN-DATA)."""
        owner = portfolio if portfolio is not None else self.portfolio()
        moment = self._timestamp()
        quantity = self._decimal(1, 5_000, places=4)
        price = self._decimal(1, 2_000, places=4)
        amount = (quantity * price).quantize(Decimal("0.01"))
        values: dict[str, Any] = {
            "transaction_id": self.next_transaction_id(moment),
            "portfolio_id": owner.portfolio_id,
            "transaction_date": moment.date(),
            "transaction_time": moment.time(),
            "investment_id": self.next_investment_id(),
            "transaction_type": self._choice(TRANSACTION_TYPES),
            "quantity": quantity,
            "price": price,
            "amount": min(max(amount, MIN_TRANSACTION_AMOUNT), MAX_TRANSACTION_AMOUNT),
            "currency_code": owner.currency_code,
            "status": self._choice(TRANSACTION_STATUSES),
            "process_date": moment,
            "process_user": GENERATOR_USER,
        }
        values.update(overrides)
        return TransactionHistory(**values)

    def position_history(
        self, portfolio: PortfolioMaster | None = None, **overrides: Any
    ) -> PositionHistory:
        """POSHIST row mirroring a position-affecting transaction."""
        owner = portfolio if portfolio is not None else self.portfolio()
        moment = self._timestamp()
        quantity = self._decimal(1, 5_000, places=3)
        price = self._decimal(1, 2_000, places=3)
        amount = (quantity * price).quantize(Decimal("0.01"))
        fees = (amount * Decimal("0.001")).quantize(Decimal("0.01"))
        cost_basis = (amount * self._factor()).quantize(Decimal("0.01"))
        values: dict[str, Any] = {
            "account_no": f"ACC{owner.portfolio_id[-5:]}",
            "portfolio_id": owner.portfolio_id,
            "trans_date": moment.date(),
            "trans_time": moment.time(),
            "trans_type": self._choice(POSITION_HISTORY_TYPES),
            "security_id": self.next_investment_id(),
            "quantity": quantity,
            "price": price,
            "amount": amount,
            "fees": fees,
            "total_amount": amount + fees,
            "cost_basis": cost_basis,
            "gain_loss": amount - cost_basis,
            "process_date": self.as_of,
            "process_time": moment.time(),
            "program_id": GENERATOR_PROGRAM,
            "user_id": GENERATOR_USER,
            "audit_timestamp": moment,
        }
        values.update(overrides)
        return PositionHistory(**values)

    def error_log(self, **overrides: Any) -> ErrorLog:
        """ERRLOG row (2410-GEN-DATA-ERRORS / 2420-GEN-PROCESS-ERRORS)."""
        moment = self._timestamp()
        values: dict[str, Any] = {
            "error_timestamp": moment,
            "program_id": GENERATOR_PROGRAM,
            "error_type": "D",
            "error_severity": 3,
            "error_code": "VAL00001",
            "error_message": "Invalid Portfolio ID format",
            "process_date": self.as_of,
            "process_time": moment.time(),
            "user_id": GENERATOR_USER,
            "additional_info": None,
        }
        values.update(overrides)
        return ErrorLog(**values)

    def audit_log(self, **overrides: Any) -> AuditLog:
        """AUDIT_LOG row for a generated action."""
        self._audit_sequence += 1
        moment = self._timestamp()
        values: dict[str, Any] = {
            "aud_timestamp": moment,
            "aud_system_id": "IPMS",
            "aud_user_id": GENERATOR_USER,
            "aud_program": GENERATOR_PROGRAM,
            "aud_terminal": f"TRM{self._audit_sequence:05d}",
            "aud_type": "SYST",
            "aud_action": "CREATE",
            "aud_status": "SUCC",
            "aud_portfolio_id": None,
            "aud_account_no": None,
            "aud_before_image": None,
            "aud_after_image": None,
            "aud_message": "Test data generated",
        }
        values.update(overrides)
        return AuditLog(**values)

    # -------------------------------------------------------------- data sets

    def generate(self, config: GenerationConfig) -> DataSet:
        """2100-GENERATE-TEST-DATA: dispatch on the configured data set type."""
        if config.data_set is DataSetType.PORTFOLIO:
            return self._generate_portfolios(config)
        if config.data_set is DataSetType.TRANSACTION:
            return self._generate_transactions(config)
        if config.data_set is DataSetType.ERROR:
            return self._generate_error_data(config)
        return self._generate_volume(config)

    def portfolios(self, count: int, **overrides: Any) -> list[PortfolioMaster]:
        return [self.portfolio(**overrides) for _ in range(count)]

    def transactions(
        self, count: int, portfolio: PortfolioMaster | None = None, **overrides: Any
    ) -> list[TransactionHistory]:
        owner = portfolio if portfolio is not None else self.portfolio()
        return [self.transaction(owner, **overrides) for _ in range(count)]

    def _generate_portfolios(self, config: GenerationConfig) -> DataSet:
        data_set = DataSet()
        for _ in range(config.volume):
            portfolio = self.portfolio()
            data_set.portfolios.append(portfolio)
            for _ in range(config.positions_per_portfolio):
                data_set.positions.append(self.position(portfolio))
        return data_set

    def _generate_transactions(self, config: GenerationConfig) -> DataSet:
        portfolio = self.portfolio(status="A")
        data_set = DataSet(portfolios=[portfolio])
        for _ in range(config.volume):
            data_set.transactions.append(self.transaction(portfolio))
        return data_set

    def _generate_error_data(self, config: GenerationConfig) -> DataSet:
        data_set = DataSet()
        scenarios = error_scenarios()
        for index in range(config.volume):
            scenario = scenarios[(self._error_offset + index) % len(scenarios)]
            data_set.error_logs.append(
                self.error_log(
                    error_type=scenario.kind.error_type,
                    error_severity=scenario.severity,
                    error_code=scenario.error_code,
                    error_message=scenario.message,
                    additional_info=scenario.description,
                )
            )
            data_set.audit_logs.append(self.audit_log(aud_status="FAIL", aud_message=scenario.name))
        self._error_offset += config.volume
        return data_set

    def _generate_volume(self, config: GenerationConfig) -> DataSet:
        data_set = self._generate_portfolios(config)
        for portfolio in data_set.portfolios:
            for _ in range(config.transactions_per_portfolio):
                data_set.transactions.append(self.transaction(portfolio))
                data_set.position_history.append(self.position_history(portfolio))
        return data_set

    # ---------------------------------------------------------------- helpers

    def _choice(self, values: Sequence[str]) -> str:
        return values[self._random.randrange(len(values))]

    def _int(self, low: int, high: int) -> int:
        return self._random.randint(low, high)

    def _decimal(self, low: int, high: int, places: int) -> Decimal:
        scale = 10**places
        raw = self._random.randrange(low * scale, high * scale)
        value: Decimal = Decimal(raw) / Decimal(scale)
        quantum: Decimal = Decimal(1).scaleb(-places)
        return value.quantize(quantum)

    def _factor(self) -> Decimal:
        """Market movement between 0.80 and 1.20 applied to a cost basis."""
        return Decimal(self._random.randrange(80, 121)) / Decimal(100)

    def _timestamp(self) -> datetime:
        moment = time(
            hour=self._int(9, 16),
            minute=self._int(0, 59),
            second=self._int(0, 59),
            microsecond=self._int(0, 999999),
        )
        return datetime.combine(self.as_of, moment)

    def __iter__(self) -> Iterator[PortfolioMaster]:
        """Endless stream of portfolios, for volume tests that consume lazily."""
        while True:
            yield self.portfolio()

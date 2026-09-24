"""Canonical-model test data generation, ported from TSTGEN00.

TSTGEN00 reads a configuration file of (test type, volume, parameters) records and
writes generated portfolio, transaction, error and volume data to sequential files
using a seeded pseudo-random generator. The port keeps that shape: a seeded
:class:`~tests.factories.data.DataFactory` builds ORM rows, a
:class:`~tests.factories.data.GenerationConfig` selects a data set, and error
scenarios are declarative rows plus the legacy validation code they trigger.
"""

from tests.factories.data import (
    ACCOUNT_TYPES,
    CURRENCY_CODES,
    DEFAULT_SEED,
    MAX_PORTFOLIO_VALUE,
    MAX_TRANSACTION_AMOUNT,
    MIN_TRANSACTION_AMOUNT,
    PORTFOLIO_ID_PREFIX,
    PORTFOLIO_STATUSES,
    RISK_LEVELS,
    TRANSACTION_STATUSES,
    TRANSACTION_TYPES,
    DataFactory,
    DataSet,
    DataSetType,
    GenerationConfig,
    build_transaction_id,
)
from tests.factories.scenarios import (
    ErrorKind,
    ErrorScenario,
    ValidationCode,
    data_error_scenarios,
    error_scenarios,
    process_error_scenarios,
)

__all__ = [
    "ACCOUNT_TYPES",
    "CURRENCY_CODES",
    "DEFAULT_SEED",
    "MAX_PORTFOLIO_VALUE",
    "MAX_TRANSACTION_AMOUNT",
    "MIN_TRANSACTION_AMOUNT",
    "PORTFOLIO_ID_PREFIX",
    "PORTFOLIO_STATUSES",
    "RISK_LEVELS",
    "TRANSACTION_STATUSES",
    "TRANSACTION_TYPES",
    "DataFactory",
    "DataSet",
    "DataSetType",
    "ErrorKind",
    "ErrorScenario",
    "GenerationConfig",
    "ValidationCode",
    "build_transaction_id",
    "data_error_scenarios",
    "error_scenarios",
    "process_error_scenarios",
]

import re
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PortfolioMaster, TransactionHistory
from tests.conftest import Persist
from tests.factories import (
    ACCOUNT_TYPES,
    CURRENCY_CODES,
    MAX_TRANSACTION_AMOUNT,
    MIN_TRANSACTION_AMOUNT,
    PORTFOLIO_STATUSES,
    RISK_LEVELS,
    TRANSACTION_STATUSES,
    TRANSACTION_TYPES,
    DataFactory,
    DataSetType,
    ErrorKind,
    ErrorScenario,
    GenerationConfig,
    build_transaction_id,
    data_error_scenarios,
    process_error_scenarios,
)

PORTFOLIO_ID = re.compile(r"^PORT\d{4}$")
TRANSACTION_ID = re.compile(r"^\d{14}\d{6}$")


def columns(row: object, names: tuple[str, ...]) -> tuple[object, ...]:
    return tuple(getattr(row, name) for name in names)


def test_generated_portfolios_match_the_validation_criteria(data_factory: DataFactory) -> None:
    for portfolio in data_factory.portfolios(20):
        assert PORTFOLIO_ID.match(portfolio.portfolio_id)
        assert portfolio.status in PORTFOLIO_STATUSES
        assert portfolio.account_type in ACCOUNT_TYPES
        assert portfolio.currency_code in CURRENCY_CODES
        assert portfolio.risk_level in RISK_LEVELS
        assert 1 <= len(portfolio.portfolio_name.strip()) <= 50
        assert portfolio.open_date <= data_factory.as_of
        assert (portfolio.close_date is not None) == (portfolio.status == "C")


def test_generated_transactions_match_the_validation_criteria(
    data_factory: DataFactory, portfolio: PortfolioMaster
) -> None:
    for transaction in data_factory.transactions(20, portfolio):
        assert TRANSACTION_ID.match(transaction.transaction_id)
        assert len(transaction.transaction_id) == 20
        assert transaction.portfolio_id == portfolio.portfolio_id
        assert transaction.transaction_type in TRANSACTION_TYPES
        assert transaction.status in TRANSACTION_STATUSES
        assert MIN_TRANSACTION_AMOUNT <= transaction.amount <= MAX_TRANSACTION_AMOUNT
        assert transaction.amount.as_tuple().exponent == -2
        assert transaction.transaction_date <= data_factory.as_of


def test_transaction_id_encodes_the_timestamp_and_sequence() -> None:
    assert build_transaction_id(datetime(2024, 3, 20, 15, 30, 45), 1) == "20240320153045000001"
    with pytest.raises(ValueError):
        build_transaction_id(datetime(2024, 3, 20, 15, 30, 45), 1_000_000)


def test_identifiers_are_unique_within_a_factory(data_factory: DataFactory) -> None:
    data_set = data_factory.generate(
        GenerationConfig(DataSetType.VOLUME, volume=25, transactions_per_portfolio=4)
    )
    assert len({row.portfolio_id for row in data_set.portfolios}) == 25
    assert len({row.transaction_id for row in data_set.transactions}) == 100
    assert len(
        {
            columns(row, ("portfolio_id", "investment_id", "position_date"))
            for row in data_set.positions
        }
    ) == len(data_set.positions)


def test_the_same_seed_reproduces_the_same_rows() -> None:
    config = GenerationConfig(DataSetType.VOLUME, volume=5)

    def snapshot(factory: DataFactory) -> list[tuple[object, ...]]:
        data_set = factory.generate(config)
        return [
            tuple(getattr(row, column.name) for column in row.__table__.c)
            for row in data_set.rows()
        ]

    assert snapshot(DataFactory(seed=7)) == snapshot(DataFactory(seed=7))
    assert snapshot(DataFactory(seed=7)) != snapshot(DataFactory(seed=8))


def test_reset_restarts_the_sequences(data_factory: DataFactory) -> None:
    first = data_factory.portfolio()
    data_factory.reset()
    assert columns(data_factory.portfolio(), ("portfolio_id", "client_id", "status")) == columns(
        first, ("portfolio_id", "client_id", "status")
    )


def test_portfolio_data_set_generates_positions_per_portfolio(data_factory: DataFactory) -> None:
    data_set = data_factory.generate(
        GenerationConfig(DataSetType.PORTFOLIO, volume=3, positions_per_portfolio=4)
    )
    assert len(data_set.portfolios) == 3
    assert len(data_set.positions) == 12
    assert data_set.transactions == []
    owners = {portfolio.portfolio_id for portfolio in data_set.portfolios}
    assert {position.portfolio_id for position in data_set.positions} == owners


def test_transaction_data_set_hangs_off_one_active_portfolio(data_factory: DataFactory) -> None:
    data_set = data_factory.generate(GenerationConfig(DataSetType.TRANSACTION, volume=10))
    (owner,) = data_set.portfolios
    assert owner.status == "A"
    assert len(data_set.transactions) == 10
    assert {row.portfolio_id for row in data_set.transactions} == {owner.portfolio_id}


def test_error_data_set_logs_every_scenario(data_factory: DataFactory) -> None:
    data_set = data_factory.generate(GenerationConfig(DataSetType.ERROR, volume=13))
    assert len(data_set.error_logs) == 13
    assert {row.error_type for row in data_set.error_logs} == {
        ErrorKind.DATA.value,
        ErrorKind.PROCESS.value,
    }
    assert {row.aud_status for row in data_set.audit_logs} == {"FAIL"}


def test_volume_data_set_scales_portfolios_transactions_and_history(
    data_factory: DataFactory,
) -> None:
    data_set = data_factory.generate(
        GenerationConfig(
            DataSetType.VOLUME,
            volume=50,
            positions_per_portfolio=1,
            transactions_per_portfolio=2,
        )
    )
    assert (len(data_set.portfolios), len(data_set.positions)) == (50, 50)
    assert (len(data_set.transactions), len(data_set.position_history)) == (100, 100)
    assert len(data_set) == 300


def test_generation_config_rejects_impossible_volumes() -> None:
    with pytest.raises(ValueError):
        GenerationConfig(DataSetType.PORTFOLIO, volume=0)
    with pytest.raises(ValueError):
        GenerationConfig(DataSetType.VOLUME, transactions_per_portfolio=-1)


def test_generated_rows_persist_against_the_canonical_schema(
    data_factory: DataFactory, db_session: Session, persist: Persist
) -> None:
    data_set = persist(data_factory.generate(GenerationConfig(DataSetType.VOLUME, volume=10)))

    for model, expected in (
        (PortfolioMaster, len(data_set.portfolios)),
        (TransactionHistory, len(data_set.transactions)),
    ):
        stored = db_session.scalar(select(func.count()).select_from(model))
        assert stored == expected

    total = db_session.scalar(select(func.sum(TransactionHistory.amount)))
    assert isinstance(total, Decimal)


def test_data_error_scenarios_are_rejected_by_the_database(
    data_factory: DataFactory, db_session: Session
) -> None:
    owner = data_factory.portfolio(status="A")
    db_session.add(owner)
    db_session.commit()

    rejected = []
    for scenario in data_error_scenarios():
        row = scenario.build(data_factory, portfolio=owner)
        db_session.add(row)
        try:
            db_session.commit()
        except IntegrityError:
            rejected.append(scenario.name)
        db_session.rollback()

    assert {
        "portfolio_missing_client_id",
        "transaction_missing_amount",
    } <= set(rejected)


def test_process_error_scenarios_collide_with_stored_rows(
    data_factory: DataFactory, db_engine: Engine
) -> None:
    owner = data_factory.portfolio(status="A")
    portfolio_id = owner.portfolio_id
    by_name = {scenario.name: scenario for scenario in process_error_scenarios()}
    colliding = [
        by_name["duplicate_portfolio_key"].build(data_factory, portfolio_id=portfolio_id),
        by_name["transaction_orphan_portfolio"].build(data_factory, portfolio=owner),
    ]

    with Session(db_engine) as session:
        session.add_all([owner, data_factory.transaction(owner)])
        session.commit()

    for row in colliding:
        with Session(db_engine) as session:
            session.add(row)
            with pytest.raises(IntegrityError):
                session.commit()


def test_every_scenario_carries_a_legacy_validation_code(scenarios: list[ErrorScenario]) -> None:
    assert len(scenarios) == len({scenario.name for scenario in scenarios})
    for scenario in scenarios:
        assert scenario.validation_code.value > 0
        assert scenario.error_code.strip() != ""
        assert 1 <= scenario.severity <= 4

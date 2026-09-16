from datetime import date, time
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import CHAR, Date, Numeric, Table, Time, create_engine, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.schema import ColumnDefault
from sqlalchemy.types import TIMESTAMP

from app.models.poshist import PositionHistory, TransactionType

TABLE = cast(Table, PositionHistory.__table__)


def test_table_name() -> None:
    assert TABLE.name == "POSHIST"


def test_primary_key_is_named_and_ordered() -> None:
    assert TABLE.primary_key.name == "POSHIST_PK"
    assert [column.name for column in TABLE.primary_key.columns] == [
        "ACCOUNT_NO",
        "PORTFOLIO_ID",
        "TRANS_DATE",
        "TRANS_TIME",
    ]


def test_identifier_widths_follow_the_canonical_model() -> None:
    """POSHIST.sql has these two swapped; the canonical widths win (see module docstring)."""
    account_no = TABLE.c["ACCOUNT_NO"].type
    portfolio_id = TABLE.c["PORTFOLIO_ID"].type
    assert isinstance(account_no, CHAR)
    assert isinstance(portfolio_id, CHAR)
    assert account_no.length == 10
    assert portfolio_id.length == 8


@pytest.mark.parametrize(
    ("name", "precision", "scale"),
    [
        ("QUANTITY", 15, 3),
        ("PRICE", 15, 3),
        ("AMOUNT", 15, 2),
        ("FEES", 15, 2),
        ("TOTAL_AMOUNT", 15, 2),
        ("COST_BASIS", 15, 2),
        ("GAIN_LOSS", 15, 2),
    ],
)
def test_numeric_columns(name: str, precision: int, scale: int) -> None:
    column = TABLE.c[name]
    assert isinstance(column.type, Numeric)
    assert (column.type.precision, column.type.scale) == (precision, scale)
    assert column.type.asdecimal is True
    assert column.nullable is False


def test_date_time_and_timestamp_columns() -> None:
    assert isinstance(TABLE.c["TRANS_DATE"].type, Date)
    assert isinstance(TABLE.c["TRANS_TIME"].type, Time)
    assert isinstance(TABLE.c["PROCESS_DATE"].type, Date)
    assert isinstance(TABLE.c["PROCESS_TIME"].type, Time)
    assert isinstance(TABLE.c["AUDIT_TIMESTAMP"].type, TIMESTAMP)


def test_every_column_is_not_null() -> None:
    assert [column.name for column in TABLE.columns if column.nullable] == []


def test_defaults() -> None:
    fees = TABLE.c["FEES"]
    assert isinstance(fees.default, ColumnDefault)
    assert fees.default.arg == Decimal("0")
    assert fees.server_default is not None
    assert TABLE.c["AUDIT_TIMESTAMP"].server_default is not None


def test_indexes_keep_the_legacy_names_and_columns() -> None:
    indexes = {
        str(index.name): [column.name for column in index.columns] for index in TABLE.indexes
    }
    assert indexes["POSHIST_IX1"] == ["SECURITY_ID", "TRANS_DATE"]
    assert indexes["POSHIST_IX2"] == ["PROCESS_DATE", "PROGRAM_ID"]
    # Replaces the DB2 range partitioning by TRANS_DATE.
    assert indexes["IX_POSHIST_TRANS_DATE"] == ["TRANS_DATE"]


def test_transaction_type_domain_and_check_constraint() -> None:
    assert [member.value for member in TransactionType] == ["BU", "SL", "TR", "FE"]
    constraints = {
        str(constraint.name)
        for constraint in TABLE.constraints
        if str(constraint.name).endswith("_CK")
    }
    assert constraints == {"POSHIST_TRANS_TYPE_CK"}


@pytest.fixture
def sqlite_engine() -> Engine:
    engine = create_engine("sqlite://")
    TABLE.create(engine)
    return engine


def test_model_round_trips_without_postgres(sqlite_engine: Engine) -> None:
    row = {
        "ACCOUNT_NO": "1234567890",
        "PORTFOLIO_ID": "PORT0001",
        "TRANS_DATE": date(2024, 4, 1),
        "TRANS_TIME": time(10, 15, 30),
        "TRANS_TYPE": TransactionType.BUY.value,
        "SECURITY_ID": "US0378331005",
        "QUANTITY": Decimal("100.000"),
        "PRICE": Decimal("12.345"),
        "AMOUNT": Decimal("1234.50"),
        "TOTAL_AMOUNT": Decimal("1240.50"),
        "COST_BASIS": Decimal("1240.50"),
        "GAIN_LOSS": Decimal("0.00"),
        "PROCESS_DATE": date(2024, 4, 1),
        "PROCESS_TIME": time(23, 0, 0),
        "PROGRAM_ID": "HISTLD00",
        "USER_ID": "BATCH   ",
    }
    with sqlite_engine.begin() as connection:
        connection.execute(insert(TABLE).values(**row))
        fees, total_amount = connection.execute(
            select(TABLE.c["FEES"], TABLE.c["TOTAL_AMOUNT"])
        ).one()

    assert fees == Decimal("0")
    assert isinstance(total_amount, Decimal)

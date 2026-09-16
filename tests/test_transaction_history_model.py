import datetime as dt
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    MetaData,
    Numeric,
    String,
    Table,
    Time,
    create_engine,
    insert,
    select,
)
from sqlalchemy.orm import Session

from app.models.transaction_history import (
    InvalidTransactionIdError,
    TransactionHistory,
    TransactionStatus,
    TransactionType,
    format_transaction_id,
    is_valid_transaction_id,
    parse_transaction_id,
)

TABLE: Table = cast(Table, TransactionHistory.__table__)


def test_table_name() -> None:
    assert TABLE.name == "TRANSACTION_HISTORY"


def test_column_names_match_ddl() -> None:
    assert list(TABLE.columns.keys()) == [
        "TRANSACTION_ID",
        "PORTFOLIO_ID",
        "TRANSACTION_DATE",
        "TRANSACTION_TIME",
        "INVESTMENT_ID",
        "TRANSACTION_TYPE",
        "QUANTITY",
        "PRICE",
        "AMOUNT",
        "CURRENCY_CODE",
        "STATUS",
        "PROCESS_DATE",
        "PROCESS_USER",
    ]


def test_primary_key_is_transaction_id() -> None:
    assert [column.name for column in TABLE.primary_key.columns] == ["TRANSACTION_ID"]


def test_all_columns_are_not_null() -> None:
    assert [column.name for column in TABLE.columns if column.nullable] == []


@pytest.mark.parametrize(
    ("column_name", "length"),
    [
        ("TRANSACTION_ID", 20),
        ("PORTFOLIO_ID", 8),
        ("INVESTMENT_ID", 10),
        ("TRANSACTION_TYPE", 2),
        ("CURRENCY_CODE", 3),
        ("STATUS", 1),
    ],
)
def test_fixed_width_char_columns(column_name: str, length: int) -> None:
    column_type = TABLE.columns[column_name].type
    assert isinstance(column_type, CHAR)
    assert column_type.length == length


def test_process_user_is_varchar_8() -> None:
    column_type = TABLE.columns["PROCESS_USER"].type
    assert isinstance(column_type, String)
    assert not isinstance(column_type, CHAR)
    assert column_type.length == 8


@pytest.mark.parametrize(
    ("column_name", "precision", "scale"),
    [("QUANTITY", 18, 4), ("PRICE", 18, 4), ("AMOUNT", 18, 2)],
)
def test_numeric_precision_and_scale(column_name: str, precision: int, scale: int) -> None:
    column_type = TABLE.columns[column_name].type
    assert isinstance(column_type, Numeric)
    assert (column_type.precision, column_type.scale) == (precision, scale)


def test_temporal_column_types() -> None:
    assert isinstance(TABLE.columns["TRANSACTION_DATE"].type, Date)
    assert isinstance(TABLE.columns["TRANSACTION_TIME"].type, Time)
    assert isinstance(TABLE.columns["PROCESS_DATE"].type, DateTime)


def test_portfolio_foreign_key() -> None:
    foreign_keys = list(TABLE.columns["PORTFOLIO_ID"].foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0]._get_colspec() == "PORTFOLIO_MASTER.PORTFOLIO_ID"


def test_indexes_use_legacy_names_and_column_order() -> None:
    indexes = {index.name: [column.name for column in index.columns] for index in TABLE.indexes}
    assert indexes == {
        "IDX_TRANS_HIST_PORT": ["PORTFOLIO_ID", "TRANSACTION_DATE"],
        "IDX_TRANS_HIST_DATE": ["TRANSACTION_DATE", "PORTFOLIO_ID"],
    }


def test_transaction_type_check_constraint() -> None:
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in TABLE.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "CK_TRANS_HIST_TYPE" in constraints
    for code in TransactionType:
        assert f"'{code.value}'" in constraints["CK_TRANS_HIST_TYPE"]


def test_legacy_code_domains() -> None:
    assert [code.value for code in TransactionType] == ["BU", "SL", "TR", "FE"]
    assert [code.value for code in TransactionStatus] == ["P", "D", "F", "R"]


def test_format_transaction_id() -> None:
    moment = dt.datetime(2024, 3, 15, 9, 8, 7)
    assert format_transaction_id(moment, 42) == "20240315090807000042"
    assert len(format_transaction_id(moment, 42)) == 20


def test_format_transaction_id_rejects_out_of_range_sequence() -> None:
    moment = dt.datetime(2024, 3, 15, 9, 8, 7)
    with pytest.raises(InvalidTransactionIdError):
        format_transaction_id(moment, 1_000_000)
    with pytest.raises(InvalidTransactionIdError):
        format_transaction_id(moment, -1)


def test_parse_transaction_id_round_trip() -> None:
    moment = dt.datetime(2024, 12, 31, 23, 59, 59)
    transaction_id = format_transaction_id(moment, 999_999)
    assert parse_transaction_id(transaction_id) == (moment, 999_999)


@pytest.mark.parametrize(
    "transaction_id",
    [
        "",
        "2024031509080700004",
        "202403150908070000421",
        "2024033109080700042X",
        "20241332000000000001",
    ],
)
def test_invalid_transaction_ids(transaction_id: str) -> None:
    assert not is_valid_transaction_id(transaction_id)
    with pytest.raises(InvalidTransactionIdError):
        parse_transaction_id(transaction_id)


def test_parse_transaction_id_tolerates_char_padding() -> None:
    assert is_valid_transaction_id(" 20240315090807000042 ")


def _table_without_foreign_keys() -> Table:
    """Copy of the table for DDL, so tests do not need PORTFOLIO_MASTER to exist."""
    return Table(
        TABLE.name,
        MetaData(),
        *[
            Column(column.name, column.type, primary_key=column.primary_key, nullable=False)
            for column in TABLE.columns
        ],
    )


def test_round_trip_on_sqlite_without_portfolio_master() -> None:
    engine = create_engine("sqlite://")
    standalone = _table_without_foreign_keys()
    with engine.begin() as connection:
        standalone.create(connection)
        connection.execute(
            insert(standalone).values(
                {
                    "TRANSACTION_ID": format_transaction_id(dt.datetime(2024, 3, 15, 9, 8, 7), 1),
                    "PORTFOLIO_ID": "PORT0001",
                    "TRANSACTION_DATE": dt.date(2024, 3, 15),
                    "TRANSACTION_TIME": dt.time(9, 8, 7),
                    "INVESTMENT_ID": "FUND000001",
                    "TRANSACTION_TYPE": TransactionType.BUY.value,
                    "QUANTITY": Decimal("100.5000"),
                    "PRICE": Decimal("12.3456"),
                    "AMOUNT": Decimal("1240.73"),
                    "CURRENCY_CODE": "GBP",
                    "STATUS": TransactionStatus.DONE.value,
                    "PROCESS_DATE": dt.datetime(2024, 3, 15, 22, 0, 0),
                    "PROCESS_USER": "BATCHUSR",
                }
            )
        )

    with Session(engine) as session:
        transaction = session.scalars(select(TransactionHistory)).one()

    assert transaction.portfolio_id == "PORT0001"
    assert transaction.quantity == Decimal("100.5000")
    assert transaction.amount == Decimal("1240.73")
    assert parse_transaction_id(transaction.transaction_id) == (
        dt.datetime(2024, 3, 15, 9, 8, 7),
        1,
    )

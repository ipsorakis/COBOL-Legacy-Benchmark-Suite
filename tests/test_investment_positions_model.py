from typing import cast

from sqlalchemy import CHAR, TIMESTAMP, Date, Numeric, String, Table

from app.models.investment_positions import InvestmentPosition


def test_investment_positions_table_metadata() -> None:
    table = cast(Table, InvestmentPosition.__table__)

    assert table.name == "INVESTMENT_POSITIONS"
    assert set(table.c.keys()) == {
        "PORTFOLIO_ID",
        "INVESTMENT_ID",
        "POSITION_DATE",
        "QUANTITY",
        "COST_BASIS",
        "MARKET_VALUE",
        "CURRENCY_CODE",
        "LAST_MAINT_DATE",
        "LAST_MAINT_USER",
    }


def test_investment_positions_column_types_and_nullability() -> None:
    table = cast(Table, InvestmentPosition.__table__)

    assert isinstance(table.c.PORTFOLIO_ID.type, CHAR)
    assert table.c.PORTFOLIO_ID.type.length == 8
    assert isinstance(table.c.INVESTMENT_ID.type, CHAR)
    assert table.c.INVESTMENT_ID.type.length == 10
    assert isinstance(table.c.POSITION_DATE.type, Date)
    for name, precision, scale in (
        ("QUANTITY", 18, 4),
        ("COST_BASIS", 18, 2),
        ("MARKET_VALUE", 18, 2),
    ):
        column_type = table.c[name].type
        assert isinstance(column_type, Numeric)
        assert column_type.precision == precision
        assert column_type.scale == scale
    assert isinstance(table.c.CURRENCY_CODE.type, CHAR)
    assert table.c.CURRENCY_CODE.type.length == 3
    assert isinstance(table.c.LAST_MAINT_DATE.type, TIMESTAMP)
    assert isinstance(table.c.LAST_MAINT_USER.type, String)
    assert table.c.LAST_MAINT_USER.type.length == 8
    assert all(column.nullable is False for column in table.c)


def test_investment_positions_primary_key_and_foreign_key() -> None:
    table = cast(Table, InvestmentPosition.__table__)

    assert [column.name for column in table.primary_key.columns] == [
        "PORTFOLIO_ID",
        "INVESTMENT_ID",
        "POSITION_DATE",
    ]
    foreign_keys = list(table.c.PORTFOLIO_ID.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "PORTFOLIO_MASTER.PORTFOLIO_ID"


def test_investment_positions_index() -> None:
    table = cast(Table, InvestmentPosition.__table__)

    index = next(index for index in table.indexes if index.name == "IDX_POSITIONS_DATE")
    assert tuple(column.name for column in index.columns) == (
        "POSITION_DATE",
        "PORTFOLIO_ID",
    )


def test_investment_positions_python_attributes_map_to_legacy_columns() -> None:
    attributes = {
        "portfolio_id": "PORTFOLIO_ID",
        "investment_id": "INVESTMENT_ID",
        "position_date": "POSITION_DATE",
        "quantity": "QUANTITY",
        "cost_basis": "COST_BASIS",
        "market_value": "MARKET_VALUE",
        "currency_code": "CURRENCY_CODE",
        "last_maint_date": "LAST_MAINT_DATE",
        "last_maint_user": "LAST_MAINT_USER",
    }

    for attribute_name, column_name in attributes.items():
        attribute = getattr(InvestmentPosition, attribute_name)
        assert attribute.key == attribute_name
        assert attribute.expression.name == column_name

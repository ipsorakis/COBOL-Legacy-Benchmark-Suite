from datetime import date, datetime
from typing import cast

from sqlalchemy import CHAR, Date, DateTime, String, Table, create_engine, inspect
from sqlalchemy.orm import Session

from app.models import PortfolioMaster
from app.models.base import Base
from app.models.portfolio_master import PortfolioStatus


def test_portfolio_master_table_metadata() -> None:
    table = cast(Table, PortfolioMaster.__table__)
    columns = {column.key: column for column in table.columns}

    assert PortfolioMaster.__tablename__ == "PORTFOLIO_MASTER"
    assert set(columns) == {
        "PORTFOLIO_ID",
        "ACCOUNT_TYPE",
        "BRANCH_ID",
        "CLIENT_ID",
        "PORTFOLIO_NAME",
        "CURRENCY_CODE",
        "RISK_LEVEL",
        "STATUS",
        "OPEN_DATE",
        "CLOSE_DATE",
        "LAST_MAINT_DATE",
        "LAST_MAINT_USER",
    }
    for name, length in {
        "PORTFOLIO_ID": 8,
        "ACCOUNT_TYPE": 2,
        "BRANCH_ID": 2,
        "CLIENT_ID": 10,
        "CURRENCY_CODE": 3,
        "RISK_LEVEL": 1,
        "STATUS": 1,
    }.items():
        assert type(columns[name].type) is CHAR
        assert cast(CHAR, columns[name].type).length == length
    for name, length in {"PORTFOLIO_NAME": 50, "LAST_MAINT_USER": 8}.items():
        assert type(columns[name].type) is String
        assert cast(String, columns[name].type).length == length
    assert type(columns["OPEN_DATE"].type) is Date
    assert type(columns["CLOSE_DATE"].type) is Date
    assert type(columns["LAST_MAINT_DATE"].type) is DateTime

    assert {name for name, column in columns.items() if column.nullable} == {"CLOSE_DATE"}
    assert tuple(column.name for column in table.primary_key.columns) == ("PORTFOLIO_ID",)
    assert all(not column.foreign_keys for column in table.columns)

    assert len(table.indexes) == 1
    index = next(iter(table.indexes))
    assert index.name == "IDX_PORT_MASTER_CLIENT"
    assert tuple(column.name for column in index.columns) == ("CLIENT_ID", "STATUS")

    assert PortfolioMaster.portfolio_id.expression.name == "PORTFOLIO_ID"
    assert PortfolioMaster.last_maint_date.expression.name == "LAST_MAINT_DATE"
    assert [status.value for status in PortfolioStatus] == ["A", "C", "S"]


def test_portfolio_master_round_trips_with_sqlite() -> None:
    engine = create_engine("sqlite://")
    table = cast(Table, PortfolioMaster.__table__)
    Base.metadata.create_all(engine, tables=[table])

    assert inspect(engine).get_table_names() == ["PORTFOLIO_MASTER"]
    opened = date(2024, 1, 2)
    maintained = datetime(2024, 1, 2, 3, 4, 5)
    with Session(engine) as session:
        session.add(
            PortfolioMaster(
                portfolio_id="PORT1234",
                account_type="IN",
                branch_id="01",
                client_id="CLIENT0001",
                portfolio_name="Legacy Portfolio",
                currency_code="USD",
                risk_level="2",
                status=PortfolioStatus.ACTIVE.value,
                open_date=opened,
                close_date=None,
                last_maint_date=maintained,
                last_maint_user="OPERATOR",
            )
        )
        session.commit()

        portfolio = session.get(PortfolioMaster, "PORT1234")

    assert portfolio is not None
    assert portfolio.open_date == opened
    assert portfolio.close_date is None
    assert portfolio.last_maint_date == maintained

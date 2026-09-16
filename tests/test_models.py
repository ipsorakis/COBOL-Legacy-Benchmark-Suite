from decimal import Decimal

from sqlalchemy import CHAR, Numeric, String, Table

from app.models import (
    AuditLog,
    Base,
    ErrorLog,
    InvestmentPosition,
    PortfolioMaster,
    PositionHistory,
    TransactionHistory,
)


def table(name: str) -> Table:
    return Base.metadata.tables[name]


def test_every_legacy_table_is_mapped() -> None:
    assert set(Base.metadata.tables) == {
        "portfolio_master",
        "investment_positions",
        "transaction_history",
        "poshist",
        "errlog",
        "audit_log",
    }


def test_primary_keys_match_the_legacy_definitions() -> None:
    def pk(model: type[Base]) -> list[str]:
        return [column.name for column in model.__table__.primary_key]

    assert pk(PortfolioMaster) == ["portfolio_id"]
    assert pk(InvestmentPosition) == ["portfolio_id", "investment_id", "position_date"]
    assert pk(TransactionHistory) == ["transaction_id"]
    assert pk(PositionHistory) == ["account_no", "portfolio_id", "trans_date", "trans_time"]
    assert pk(ErrorLog) == ["error_timestamp", "program_id"]
    assert pk(AuditLog) == ["audit_id"]


def test_transaction_id_keeps_the_char20_key() -> None:
    transaction_id = TransactionHistory.__table__.c.transaction_id.type
    assert isinstance(transaction_id, CHAR)
    assert transaction_id.length == 20


def test_portfolio_foreign_keys() -> None:
    for model in (InvestmentPosition, TransactionHistory):
        foreign_keys = list(model.__table__.c.portfolio_id.foreign_keys)
        assert [fk.target_fullname for fk in foreign_keys] == ["portfolio_master.portfolio_id"]


def test_money_and_quantity_columns_use_decimal_not_float() -> None:
    expected = {
        (InvestmentPosition, "quantity"): (18, 4),
        (InvestmentPosition, "cost_basis"): (18, 2),
        (InvestmentPosition, "market_value"): (18, 2),
        (TransactionHistory, "quantity"): (18, 4),
        (TransactionHistory, "price"): (18, 4),
        (TransactionHistory, "amount"): (18, 2),
        (PositionHistory, "quantity"): (15, 3),
        (PositionHistory, "price"): (15, 3),
        (PositionHistory, "amount"): (15, 2),
        (PositionHistory, "fees"): (15, 2),
        (PositionHistory, "total_amount"): (15, 2),
        (PositionHistory, "cost_basis"): (15, 2),
        (PositionHistory, "gain_loss"): (15, 2),
    }
    for (model, column_name), (precision, scale) in expected.items():
        column_type = model.__table__.c[column_name].type
        assert isinstance(column_type, Numeric)
        assert (column_type.precision, column_type.scale) == (precision, scale)
        assert column_type.asdecimal is True
        assert column_type.python_type is Decimal


def test_audit_columns_present_on_the_db2_master_tables() -> None:
    for name in ("portfolio_master", "investment_positions"):
        columns = table(name).c
        assert "last_maint_date" in columns
        assert "last_maint_user" in columns
        last_maint_user = columns.last_maint_user.type
        assert isinstance(last_maint_user, String)
        assert last_maint_user.length == 8


def test_indexes_match_db2_definitions() -> None:
    def indexes(name: str) -> dict[str | None, list[str]]:
        return {
            index.name: [str(expression) for expression in index.expressions]
            for index in table(name).indexes
        }

    assert indexes("portfolio_master") == {
        "idx_port_master_client": ["portfolio_master.client_id", "portfolio_master.status"]
    }
    assert indexes("investment_positions") == {
        "idx_positions_date": [
            "investment_positions.position_date",
            "investment_positions.portfolio_id",
        ]
    }
    assert indexes("transaction_history") == {
        "idx_trans_hist_port": [
            "transaction_history.portfolio_id",
            "transaction_history.transaction_date",
        ],
        "idx_trans_hist_date": [
            "transaction_history.transaction_date",
            "transaction_history.portfolio_id",
        ],
    }
    assert indexes("poshist") == {
        "poshist_ix1": ["poshist.security_id", "poshist.trans_date"],
        "poshist_ix2": ["poshist.process_date", "poshist.program_id"],
    }
    assert indexes("errlog") == {"errlog_ix1": ["errlog.process_date", "error_severity DESC"]}


def test_audit_log_columns_derive_from_the_copybook() -> None:
    assert set(AuditLog.__table__.c.keys()) == {
        "audit_id",
        "aud_timestamp",
        "aud_system_id",
        "aud_user_id",
        "aud_program",
        "aud_terminal",
        "aud_type",
        "aud_action",
        "aud_status",
        "aud_portfolio_id",
        "aud_account_no",
        "aud_before_image",
        "aud_after_image",
        "aud_message",
    }
    expected_lengths = {
        "aud_type": 4,
        "aud_status": 4,
        "aud_before_image": 100,
        "aud_after_image": 100,
        "aud_message": 100,
    }
    for column_name, length in expected_lengths.items():
        column_type = table("audit_log").c[column_name].type
        assert isinstance(column_type, String)
        assert column_type.length == length

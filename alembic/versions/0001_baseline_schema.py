"""Baseline schema ported from the DB2 definitions and the AUDITLOG copybook

Revision ID: 0001
Revises:
Create Date: 2026-09-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_master",
        sa.Column("portfolio_id", sa.CHAR(length=8), nullable=False),
        sa.Column("account_type", sa.CHAR(length=2), nullable=False),
        sa.Column("branch_id", sa.CHAR(length=2), nullable=False),
        sa.Column("client_id", sa.CHAR(length=10), nullable=False),
        sa.Column("portfolio_name", sa.String(length=50), nullable=False),
        sa.Column("currency_code", sa.CHAR(length=3), nullable=False),
        sa.Column("risk_level", sa.CHAR(length=1), nullable=False),
        sa.Column("status", sa.CHAR(length=1), nullable=False),
        sa.Column("open_date", sa.Date(), nullable=False),
        sa.Column("close_date", sa.Date(), nullable=True),
        sa.Column("last_maint_date", sa.TIMESTAMP(), nullable=False),
        sa.Column("last_maint_user", sa.String(length=8), nullable=False),
        sa.PrimaryKeyConstraint("portfolio_id", name=op.f("portfolio_master_pk")),
    )
    op.create_index("idx_port_master_client", "portfolio_master", ["client_id", "status"])

    op.create_table(
        "investment_positions",
        sa.Column("portfolio_id", sa.CHAR(length=8), nullable=False),
        sa.Column("investment_id", sa.CHAR(length=10), nullable=False),
        sa.Column("position_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("cost_basis", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("market_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency_code", sa.CHAR(length=3), nullable=False),
        sa.Column("last_maint_date", sa.TIMESTAMP(), nullable=False),
        sa.Column("last_maint_user", sa.String(length=8), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolio_master.portfolio_id"],
            name=op.f("investment_positions_fk_portfolio_id"),
        ),
        sa.PrimaryKeyConstraint(
            "portfolio_id",
            "investment_id",
            "position_date",
            name=op.f("investment_positions_pk"),
        ),
    )
    op.create_index("idx_positions_date", "investment_positions", ["position_date", "portfolio_id"])

    op.create_table(
        "transaction_history",
        sa.Column("transaction_id", sa.CHAR(length=20), nullable=False),
        sa.Column("portfolio_id", sa.CHAR(length=8), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_time", sa.Time(), nullable=False),
        sa.Column("investment_id", sa.CHAR(length=10), nullable=False),
        sa.Column("transaction_type", sa.CHAR(length=2), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency_code", sa.CHAR(length=3), nullable=False),
        sa.Column("status", sa.CHAR(length=1), nullable=False),
        sa.Column("process_date", sa.TIMESTAMP(), nullable=False),
        sa.Column("process_user", sa.String(length=8), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolio_master.portfolio_id"],
            name=op.f("transaction_history_fk_portfolio_id"),
        ),
        sa.PrimaryKeyConstraint("transaction_id", name=op.f("transaction_history_pk")),
    )
    op.create_index(
        "idx_trans_hist_port", "transaction_history", ["portfolio_id", "transaction_date"]
    )
    op.create_index(
        "idx_trans_hist_date", "transaction_history", ["transaction_date", "portfolio_id"]
    )

    op.create_table(
        "poshist",
        sa.Column("account_no", sa.CHAR(length=8), nullable=False),
        sa.Column("portfolio_id", sa.CHAR(length=10), nullable=False),
        sa.Column("trans_date", sa.Date(), nullable=False),
        sa.Column("trans_time", sa.Time(), nullable=False),
        sa.Column("trans_type", sa.CHAR(length=2), nullable=False),
        sa.Column("security_id", sa.CHAR(length=12), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=15, scale=3), nullable=False),
        sa.Column("price", sa.Numeric(precision=15, scale=3), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column(
            "fees",
            sa.Numeric(precision=15, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("total_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("cost_basis", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("gain_loss", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("process_date", sa.Date(), nullable=False),
        sa.Column("process_time", sa.Time(), nullable=False),
        sa.Column("program_id", sa.CHAR(length=8), nullable=False),
        sa.Column("user_id", sa.CHAR(length=8), nullable=False),
        sa.Column(
            "audit_timestamp",
            sa.TIMESTAMP(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "account_no", "portfolio_id", "trans_date", "trans_time", name=op.f("poshist_pk")
        ),
    )
    op.create_index("poshist_ix1", "poshist", ["security_id", "trans_date"])
    op.create_index("poshist_ix2", "poshist", ["process_date", "program_id"])

    op.create_table(
        "errlog",
        sa.Column("error_timestamp", sa.TIMESTAMP(), nullable=False),
        sa.Column("program_id", sa.CHAR(length=8), nullable=False),
        sa.Column("error_type", sa.CHAR(length=1), nullable=False),
        sa.Column("error_severity", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.CHAR(length=8), nullable=False),
        sa.Column("error_message", sa.String(length=200), nullable=False),
        sa.Column("process_date", sa.Date(), nullable=False),
        sa.Column("process_time", sa.Time(), nullable=False),
        sa.Column("user_id", sa.CHAR(length=8), nullable=False),
        sa.Column("additional_info", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("error_timestamp", "program_id", name=op.f("errlog_pk")),
    )
    op.create_index("errlog_ix1", "errlog", ["process_date", sa.text("error_severity DESC")])

    op.create_table(
        "audit_log",
        sa.Column(
            "audit_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("aud_timestamp", sa.TIMESTAMP(), nullable=False),
        sa.Column("aud_system_id", sa.CHAR(length=8), nullable=False),
        sa.Column("aud_user_id", sa.CHAR(length=8), nullable=False),
        sa.Column("aud_program", sa.CHAR(length=8), nullable=False),
        sa.Column("aud_terminal", sa.CHAR(length=8), nullable=False),
        sa.Column("aud_type", sa.CHAR(length=4), nullable=False),
        sa.Column("aud_action", sa.CHAR(length=8), nullable=False),
        sa.Column("aud_status", sa.CHAR(length=4), nullable=False),
        sa.Column("aud_portfolio_id", sa.CHAR(length=8), nullable=True),
        sa.Column("aud_account_no", sa.CHAR(length=10), nullable=True),
        sa.Column("aud_before_image", sa.String(length=100), nullable=True),
        sa.Column("aud_after_image", sa.String(length=100), nullable=True),
        sa.Column("aud_message", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("audit_id", name=op.f("audit_log_pk")),
    )
    op.create_index("audit_log_ix1", "audit_log", ["aud_timestamp", "aud_type"])
    op.create_index("audit_log_ix2", "audit_log", ["aud_portfolio_id", "aud_timestamp"])
    op.create_index("audit_log_ix3", "audit_log", ["aud_user_id", "aud_timestamp"])


def downgrade() -> None:
    op.drop_index("audit_log_ix3", table_name="audit_log")
    op.drop_index("audit_log_ix2", table_name="audit_log")
    op.drop_index("audit_log_ix1", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("errlog_ix1", table_name="errlog")
    op.drop_table("errlog")
    op.drop_index("poshist_ix2", table_name="poshist")
    op.drop_index("poshist_ix1", table_name="poshist")
    op.drop_table("poshist")
    op.drop_index("idx_trans_hist_date", table_name="transaction_history")
    op.drop_index("idx_trans_hist_port", table_name="transaction_history")
    op.drop_table("transaction_history")
    op.drop_index("idx_positions_date", table_name="investment_positions")
    op.drop_table("investment_positions")
    op.drop_index("idx_port_master_client", table_name="portfolio_master")
    op.drop_table("portfolio_master")

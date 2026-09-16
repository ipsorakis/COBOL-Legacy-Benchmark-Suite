from typing import cast

import pytest
from sqlalchemy import CHAR, BigInteger, String, Table
from sqlalchemy.types import TIMESTAMP

from app.models.audit_log import AuditAction, AuditLog, AuditStatus, AuditType

TABLE = cast(Table, AuditLog.__table__)


def test_table_and_column_names_follow_the_copybook() -> None:
    assert TABLE.name == "AUDIT_LOG"
    assert [column.name for column in TABLE.columns] == [
        "AUDIT_ID",
        "AUD_TIMESTAMP",
        "AUD_SYSTEM_ID",
        "AUD_USER_ID",
        "AUD_PROGRAM",
        "AUD_TERMINAL",
        "AUD_TYPE",
        "AUD_ACTION",
        "AUD_STATUS",
        "AUD_PORTFOLIO_ID",
        "AUD_ACCOUNT_NO",
        "AUD_BEFORE_IMAGE",
        "AUD_AFTER_IMAGE",
        "AUD_MESSAGE",
    ]


def test_surrogate_primary_key() -> None:
    assert [column.name for column in TABLE.primary_key.columns] == ["AUDIT_ID"]
    assert isinstance(TABLE.c["AUDIT_ID"].type, BigInteger)
    assert TABLE.c["AUDIT_ID"].autoincrement is True


def test_timestamp_is_a_real_timestamp_not_the_copybook_x26() -> None:
    assert isinstance(TABLE.c["AUD_TIMESTAMP"].type, TIMESTAMP)


@pytest.mark.parametrize(
    ("column", "length"),
    [
        ("AUD_SYSTEM_ID", 8),
        ("AUD_USER_ID", 8),
        ("AUD_PROGRAM", 8),
        ("AUD_TERMINAL", 8),
        ("AUD_TYPE", 4),
        ("AUD_ACTION", 8),
        ("AUD_STATUS", 4),
        ("AUD_PORTFOLIO_ID", 8),
        ("AUD_ACCOUNT_NO", 10),
    ],
)
def test_fixed_width_columns(column: str, length: int) -> None:
    column_type = TABLE.c[column].type
    assert isinstance(column_type, CHAR)
    assert column_type.length == length


@pytest.mark.parametrize("name", ["AUD_BEFORE_IMAGE", "AUD_AFTER_IMAGE", "AUD_MESSAGE"])
def test_free_text_columns(name: str) -> None:
    column = TABLE.c[name]
    assert isinstance(column.type, String)
    assert column.type.length == 100
    assert column.nullable is True


def test_header_and_classification_columns_are_not_null() -> None:
    assert [column.name for column in TABLE.columns if column.nullable] == [
        "AUD_PORTFOLIO_ID",
        "AUD_ACCOUNT_NO",
        "AUD_BEFORE_IMAGE",
        "AUD_AFTER_IMAGE",
        "AUD_MESSAGE",
    ]


def test_indexes() -> None:
    indexes = {
        str(index.name): [column.name for column in index.columns] for index in TABLE.indexes
    }
    assert indexes["AUDIT_LOG_IX1"] == ["AUD_TIMESTAMP"]
    assert indexes["AUDIT_LOG_IX2"] == ["AUD_PORTFOLIO_ID", "AUD_TIMESTAMP"]


def test_code_domains() -> None:
    assert [member.value for member in AuditType] == ["TRAN", "USER", "SYST"]
    assert [member.value for member in AuditStatus] == ["SUCC", "FAIL", "WARN"]
    assert [member.value for member in AuditAction] == [
        "CREATE",
        "UPDATE",
        "DELETE",
        "INQUIRE",
        "LOGIN",
        "LOGOUT",
        "STARTUP",
        "SHUTDOWN",
    ]
    assert {
        str(constraint.name)
        for constraint in TABLE.constraints
        if str(constraint.name).endswith("_CK")
    } == {"AUDIT_LOG_TYPE_CK", "AUDIT_LOG_STATUS_CK", "AUDIT_LOG_ACTION_CK"}

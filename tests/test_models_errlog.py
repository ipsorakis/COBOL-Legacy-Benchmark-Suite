from typing import cast

from sqlalchemy import CHAR, Date, Integer, String, Table, Time
from sqlalchemy.types import TIMESTAMP

from app.models.errlog import ErrorLog, ErrorSeverity, ErrorType

TABLE = cast(Table, ErrorLog.__table__)


def test_table_and_column_names() -> None:
    assert TABLE.name == "ERRLOG"
    assert [column.name for column in TABLE.columns] == [
        "ERROR_TIMESTAMP",
        "PROGRAM_ID",
        "ERROR_TYPE",
        "ERROR_SEVERITY",
        "ERROR_CODE",
        "ERROR_MESSAGE",
        "PROCESS_DATE",
        "PROCESS_TIME",
        "USER_ID",
        "ADDITIONAL_INFO",
    ]


def test_primary_key() -> None:
    assert TABLE.primary_key.name == "ERRLOG_PK"
    assert [column.name for column in TABLE.primary_key.columns] == [
        "ERROR_TIMESTAMP",
        "PROGRAM_ID",
    ]


def test_column_types() -> None:
    assert isinstance(TABLE.c["ERROR_TIMESTAMP"].type, TIMESTAMP)
    assert isinstance(TABLE.c["PROGRAM_ID"].type, CHAR)
    assert TABLE.c["PROGRAM_ID"].type.length == 8
    assert isinstance(TABLE.c["ERROR_TYPE"].type, CHAR)
    assert TABLE.c["ERROR_TYPE"].type.length == 1
    assert isinstance(TABLE.c["ERROR_SEVERITY"].type, Integer)
    assert isinstance(TABLE.c["ERROR_CODE"].type, CHAR)
    assert TABLE.c["ERROR_CODE"].type.length == 8
    assert isinstance(TABLE.c["ERROR_MESSAGE"].type, String)
    assert TABLE.c["ERROR_MESSAGE"].type.length == 200
    assert isinstance(TABLE.c["PROCESS_DATE"].type, Date)
    assert isinstance(TABLE.c["PROCESS_TIME"].type, Time)
    assert isinstance(TABLE.c["ADDITIONAL_INFO"].type, String)
    assert TABLE.c["ADDITIONAL_INFO"].type.length == 500


def test_only_additional_info_is_nullable() -> None:
    assert [column.name for column in TABLE.columns if column.nullable] == ["ADDITIONAL_INFO"]


def test_secondary_index_orders_severity_descending() -> None:
    index = next(index for index in TABLE.indexes if index.name == "ERRLOG_IX1")
    rendered = str(index.expressions[0]), str(index.expressions[1])
    assert rendered == ("ERRLOG.PROCESS_DATE", "ERROR_SEVERITY DESC")


def test_code_domains() -> None:
    assert [member.value for member in ErrorType] == ["S", "A", "D"]
    assert [member.value for member in ErrorSeverity] == [1, 2, 3, 4]
    assert {
        str(constraint.name)
        for constraint in TABLE.constraints
        if str(constraint.name).endswith("_CK")
    } == {"ERRLOG_ERROR_TYPE_CK", "ERRLOG_ERROR_SEVERITY_CK"}

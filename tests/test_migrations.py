from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.models import Base

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_baseline_migration_creates_the_mapped_schema(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'ipms.db'}"
    config = _config(database_url)

    upgrade(config, "head")

    inspector = inspect(create_engine(database_url))
    migrated = set(inspector.get_table_names()) - {"alembic_version"}
    assert migrated == set(Base.metadata.tables)

    for name, table in Base.metadata.tables.items():
        columns = inspector.get_columns(name)
        assert {column["name"] for column in columns} == set(table.c.keys())
        assert set(inspector.get_pk_constraint(name)["constrained_columns"]) == {
            column.name for column in table.primary_key
        }
        assert {index["name"] for index in inspector.get_indexes(name)} == {
            index.name for index in table.indexes
        }


def test_baseline_migration_is_reversible(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'ipms.db'}"
    config = _config(database_url)

    upgrade(config, "head")
    downgrade(config, "base")

    inspector = inspect(create_engine(database_url))
    assert set(inspector.get_table_names()) - {"alembic_version"} == set()

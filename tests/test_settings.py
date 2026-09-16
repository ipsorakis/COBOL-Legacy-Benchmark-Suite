import pytest

from app.core.settings import Settings


def test_settings_are_environment_driven(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPMS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("IPMS_DATABASE_POOL_SIZE", "17")
    monkeypatch.setenv("IPMS_BATCH_COMMIT_INTERVAL", "250")

    settings = Settings()

    assert settings.log_level == "DEBUG"
    assert settings.database_pool_size == 17
    assert settings.batch_commit_interval == 250


def test_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPMS_LOG_LEVEL", "CHATTY")

    with pytest.raises(ValueError):
        Settings()

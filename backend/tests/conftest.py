import pytest

from siteline import approvals, db, priority, storage


@pytest.fixture(autouse=True)
def no_database(monkeypatch, tmp_path):
    """Keep the suite off any real database or bucket, even when DATABASE_URL and S3_* are
    set in .env. test_precedent_pg.py opts back in with a throwaway local database."""
    monkeypatch.setattr(db, "enabled", lambda: False)
    monkeypatch.setattr(storage, "enabled", lambda: False)
    monkeypatch.setattr(storage, "LOCAL_DIR", tmp_path / "documents")


@pytest.fixture(autouse=True)
def no_real_texts_or_saved_config(monkeypatch, tmp_path):
    """Triage in tests never texts a real approver, and priority settings saved by a test
    land in a temp dir instead of var/."""
    monkeypatch.setattr(approvals, "_real_phone", lambda owner: None)
    monkeypatch.setattr(priority, "SAVED_PATH", tmp_path / "priority_config.json")
    monkeypatch.setattr(priority, "LOG_PATH", tmp_path / "priority_config_log.json")

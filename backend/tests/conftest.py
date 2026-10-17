import pytest

from siteline import db, storage


@pytest.fixture(autouse=True)
def no_database(monkeypatch, tmp_path):
    """Keep the suite off any real database or bucket, even when DATABASE_URL and S3_* are
    set in .env. test_precedent_pg.py opts back in with a throwaway local database."""
    monkeypatch.setattr(db, "enabled", lambda: False)
    monkeypatch.setattr(storage, "enabled", lambda: False)
    monkeypatch.setattr(storage, "LOCAL_DIR", tmp_path / "documents")

"""Pytest fixtures for telecalbot tests."""

import os
import tempfile
from pathlib import Path

import pytest

# Set test environment variables before importing app modules
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("CALCOM_API_KEY", "test_api_key")
os.environ.setdefault("ADMIN_TELEGRAM_ID", "123456789")


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)
    # Also cleanup WAL and SHM files
    Path(f"{db_path}-wal").unlink(missing_ok=True)
    Path(f"{db_path}-shm").unlink(missing_ok=True)

"""Tests for durable log output on the Fly volume.

Fly only keeps a short live tail, so a rotating file on the mounted volume is
the bot's own record of what happened. It shares that volume with the SQLite
database, which is why the total size is capped rather than left to grow.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from app.config import settings
from app.main import setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    root = logging.getLogger()
    previous_handlers = root.handlers[:]
    previous_level = root.level
    yield
    for handler in root.handlers[:]:
        if handler not in previous_handlers:
            handler.close()
    root.handlers = previous_handlers
    root.setLevel(previous_level)


def _file_handlers() -> list[RotatingFileHandler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    ]


def test_logs_only_to_stdout_when_no_file_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "log_file_path", None, raising=False)

    setup_logging()

    assert _file_handlers() == []


def test_writes_to_the_configured_file(monkeypatch, tmp_path):
    log_file = tmp_path / "telecalbot.log"
    monkeypatch.setattr(settings, "log_file_path", str(log_file), raising=False)

    setup_logging()
    logging.getLogger(__name__).info("hello from the volume")

    handlers = _file_handlers()
    assert len(handlers) == 1
    handlers[0].flush()
    assert "hello from the volume" in log_file.read_text()


def test_total_log_size_is_capped(monkeypatch, tmp_path):
    """The database lives on the same volume, so logs cannot grow unbounded."""
    monkeypatch.setattr(
        settings, "log_file_path", str(tmp_path / "telecalbot.log"), raising=False
    )
    monkeypatch.setattr(settings, "log_file_max_bytes", 2048, raising=False)
    monkeypatch.setattr(settings, "log_file_backup_count", 3, raising=False)

    setup_logging()

    handler = _file_handlers()[0]
    assert handler.maxBytes == 2048
    assert handler.backupCount == 3

    logger = logging.getLogger(__name__)
    for index in range(500):
        logger.info("a noisy line that will force rotation %s", index)
    handler.flush()

    written = sum(path.stat().st_size for path in tmp_path.iterdir())
    assert written <= 2048 * (3 + 1) * 1.5, f"log files grew to {written} bytes"


def test_unwritable_log_path_does_not_stop_the_bot(monkeypatch, tmp_path):
    """A missing or read-only volume must not keep the bot from starting."""
    unwritable = tmp_path / "not-a-directory" / "nested" / "telecalbot.log"
    monkeypatch.setattr(settings, "log_file_path", str(unwritable), raising=False)
    monkeypatch.setattr(Path, "mkdir", _raise_permission_error)

    setup_logging()

    assert _file_handlers() == []
    assert logging.getLogger().handlers, "stdout logging was lost too"


def _raise_permission_error(*args, **kwargs):
    raise PermissionError("read-only file system")

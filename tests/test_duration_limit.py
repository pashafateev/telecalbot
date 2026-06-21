"""Tests for DurationLimitService and duration limit admin commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import Database
from app.database.migrations import initialize_schema, run_migrations
from app.handlers.duration_limit import (
    limits_command,
    removelimit_command,
    setlimit_command,
)
from app.services.duration_limit import DurationLimitService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def duration_limit_service(temp_db_path):
    """Create a DurationLimitService with a test database."""
    db = Database(temp_db_path)
    initialize_schema(db)
    return DurationLimitService(db)


@pytest.fixture
def mock_update():
    """Create a mock Update object (admin user)."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789  # Admin ID from conftest
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_to_message = None
    return update


@pytest.fixture
def mock_context(duration_limit_service):
    """Create a mock Context with duration_limit_service."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.args = []
    context.bot_data = {"duration_limit_service": duration_limit_service}
    return context


# ===========================================================================
# DurationLimitService tests
# ===========================================================================


class TestGetLimit:
    def test_returns_none_for_unknown_user(self, duration_limit_service):
        assert duration_limit_service.get_limit(999) is None

    def test_returns_limit_after_set(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1)
        assert duration_limit_service.get_limit(111) == 30

    def test_returns_updated_limit(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1)
        duration_limit_service.set_limit(111, 60, set_by=1)
        assert duration_limit_service.get_limit(111) == 60


class TestSetLimit:
    def test_sets_new_limit(self, duration_limit_service):
        duration_limit_service.set_limit(222, 60, set_by=1)
        assert duration_limit_service.get_limit(222) == 60

    def test_upserts_existing_limit(self, duration_limit_service):
        duration_limit_service.set_limit(222, 60, set_by=1)
        duration_limit_service.set_limit(222, 30, set_by=2)
        assert duration_limit_service.get_limit(222) == 30


class TestRemoveLimit:
    def test_removes_existing_limit(self, duration_limit_service):
        duration_limit_service.set_limit(333, 30, set_by=1)
        assert duration_limit_service.remove_limit(333) is True
        assert duration_limit_service.get_limit(333) is None

    def test_returns_false_for_nonexistent(self, duration_limit_service):
        assert duration_limit_service.remove_limit(999) is False


class TestGetAllLimits:
    def test_returns_empty_list(self, duration_limit_service):
        assert duration_limit_service.get_all_limits() == []

    def test_returns_all_limits(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1)
        duration_limit_service.set_limit(222, 60, set_by=1)
        limits = duration_limit_service.get_all_limits()
        assert len(limits) == 2
        ids = {limit["telegram_id"] for limit in limits}
        assert ids == {111, 222}


# ===========================================================================
# Admin command handler tests
# ===========================================================================


class TestSetlimitCommand:
    @pytest.mark.asyncio
    async def test_sets_limit_by_id(self, mock_update, mock_context, duration_limit_service):
        mock_context.args = ["555", "30"]
        await setlimit_command(mock_update, mock_context)

        assert duration_limit_service.get_limit(555) == 30
        reply = mock_update.message.reply_text.call_args[0][0]
        assert "555" in reply
        assert "30" in reply

    @pytest.mark.asyncio
    async def test_sets_limit_by_reply(self, mock_update, mock_context, duration_limit_service):
        mock_update.message.reply_to_message = MagicMock()
        mock_update.message.reply_to_message.from_user = MagicMock()
        mock_update.message.reply_to_message.from_user.id = 777
        mock_context.args = ["60"]
        await setlimit_command(mock_update, mock_context)

        assert duration_limit_service.get_limit(777) == 60

    @pytest.mark.asyncio
    async def test_rejects_invalid_duration(self, mock_update, mock_context):
        mock_context.args = ["555", "45"]
        await setlimit_command(mock_update, mock_context)

        reply = mock_update.message.reply_text.call_args[0][0]
        assert "30" in reply and "60" in reply

    @pytest.mark.asyncio
    async def test_shows_usage_when_no_args(self, mock_update, mock_context):
        mock_context.args = []
        await setlimit_command(mock_update, mock_context)

        reply = mock_update.message.reply_text.call_args[0][0]
        assert "/setlimit" in reply.lower() or "использование" in reply.lower()

    @pytest.mark.asyncio
    async def test_rejects_non_admin(self, mock_update, mock_context):
        mock_update.effective_user.id = 999  # Not admin
        mock_context.args = ["555", "30"]
        await setlimit_command(mock_update, mock_context)

        # Should not have set the limit
        reply = mock_update.message.reply_text.call_args[0][0]
        assert "555" not in reply or "администратор" in reply.lower()


class TestRemovelimitCommand:
    @pytest.mark.asyncio
    async def test_removes_existing_limit(self, mock_update, mock_context, duration_limit_service):
        duration_limit_service.set_limit(555, 30, set_by=1)
        mock_context.args = ["555"]
        await removelimit_command(mock_update, mock_context)

        assert duration_limit_service.get_limit(555) is None
        reply = mock_update.message.reply_text.call_args[0][0]
        assert "удалён" in reply.lower()

    @pytest.mark.asyncio
    async def test_reports_not_found(self, mock_update, mock_context):
        mock_context.args = ["999"]
        await removelimit_command(mock_update, mock_context)

        reply = mock_update.message.reply_text.call_args[0][0]
        assert "не найден" in reply.lower()

    @pytest.mark.asyncio
    async def test_removes_by_reply(self, mock_update, mock_context, duration_limit_service):
        duration_limit_service.set_limit(777, 60, set_by=1)
        mock_update.message.reply_to_message = MagicMock()
        mock_update.message.reply_to_message.from_user = MagicMock()
        mock_update.message.reply_to_message.from_user.id = 777
        mock_context.args = []
        await removelimit_command(mock_update, mock_context)

        assert duration_limit_service.get_limit(777) is None


class TestLimitsCommand:
    @pytest.mark.asyncio
    async def test_shows_empty_message(self, mock_update, mock_context):
        await limits_command(mock_update, mock_context)

        reply = mock_update.message.reply_text.call_args[0][0]
        assert "нет" in reply.lower()

    @pytest.mark.asyncio
    async def test_lists_all_limits(self, mock_update, mock_context, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1)
        duration_limit_service.set_limit(222, 60, set_by=1)
        await limits_command(mock_update, mock_context)

        reply = mock_update.message.reply_text.call_args[0][0]
        assert "111" in reply
        assert "222" in reply
        assert "30" in reply
        assert "60" in reply


# ===========================================================================
# One-time scope: service
# ===========================================================================


class TestOneTimeScope:
    def test_set_limit_defaults_to_one_time(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1)
        assert duration_limit_service.get_all_limits()[0]["one_time"] is True

    def test_set_limit_can_be_ongoing(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1, one_time=False)
        assert duration_limit_service.get_all_limits()[0]["one_time"] is False

    def test_consume_clears_one_time_limit(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1, one_time=True)
        assert duration_limit_service.consume_one_time_limit(111) is True
        assert duration_limit_service.get_limit(111) is None

    def test_consume_leaves_ongoing_limit(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1, one_time=False)
        assert duration_limit_service.consume_one_time_limit(111) is False
        assert duration_limit_service.get_limit(111) == 30

    def test_consume_returns_false_for_unknown_user(self, duration_limit_service):
        assert duration_limit_service.consume_one_time_limit(999) is False

    def test_reset_changes_scope(self, duration_limit_service):
        duration_limit_service.set_limit(111, 30, set_by=1, one_time=False)
        duration_limit_service.set_limit(111, 30, set_by=1, one_time=True)
        assert duration_limit_service.get_all_limits()[0]["one_time"] is True


# ===========================================================================
# One-time scope: migration of pre-existing databases
# ===========================================================================


class TestOneTimeScopeMigration:
    def test_adds_one_time_column_to_legacy_table(self, temp_db_path):
        db = Database(temp_db_path)
        db.execute_write(
            "CREATE TABLE duration_limits ("
            "telegram_id INTEGER PRIMARY KEY, "
            "max_duration_minutes INTEGER NOT NULL, "
            "set_at TEXT NOT NULL, "
            "set_by INTEGER NOT NULL)"
        )
        db.execute_write(
            "INSERT INTO duration_limits "
            "(telegram_id, max_duration_minutes, set_at, set_by) "
            "VALUES (?, ?, ?, ?)",
            (111, 60, "2026-01-01T00:00:00+00:00", 1),
        )

        run_migrations(db)

        columns = {row["name"] for row in db.execute("PRAGMA table_info(duration_limits)")}
        assert "one_time" in columns
        # Limits that predate the column are treated as ongoing.
        assert DurationLimitService(db).get_all_limits()[0]["one_time"] is False

    def test_migration_is_idempotent(self, temp_db_path):
        db = Database(temp_db_path)
        run_migrations(db)
        run_migrations(db)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(duration_limits)")}
        assert "one_time" in columns


# ===========================================================================
# One-time scope: /setlimit command parsing
# ===========================================================================


class TestSetlimitScope:
    @pytest.mark.asyncio
    async def test_defaults_to_one_time(
        self, mock_update, mock_context, duration_limit_service
    ):
        mock_context.args = ["555", "30"]
        await setlimit_command(mock_update, mock_context)

        assert duration_limit_service.get_all_limits()[0]["one_time"] is True
        reply = mock_update.message.reply_text.call_args[0][0]
        assert "разов" in reply.lower()

    @pytest.mark.asyncio
    async def test_ongoing_with_keyword(
        self, mock_update, mock_context, duration_limit_service
    ):
        mock_context.args = ["555", "30", "постоянно"]
        await setlimit_command(mock_update, mock_context)

        assert duration_limit_service.get_limit(555) == 30
        assert duration_limit_service.get_all_limits()[0]["one_time"] is False
        reply = mock_update.message.reply_text.call_args[0][0]
        assert "постоянн" in reply.lower()

    @pytest.mark.asyncio
    async def test_ongoing_keyword_by_reply(
        self, mock_update, mock_context, duration_limit_service
    ):
        mock_update.message.reply_to_message = MagicMock()
        mock_update.message.reply_to_message.from_user = MagicMock()
        mock_update.message.reply_to_message.from_user.id = 777
        mock_context.args = ["60", "always"]
        await setlimit_command(mock_update, mock_context)

        assert duration_limit_service.get_limit(777) == 60
        assert duration_limit_service.get_all_limits()[0]["one_time"] is False

    @pytest.mark.asyncio
    async def test_limits_command_shows_scope(
        self, mock_update, mock_context, duration_limit_service
    ):
        duration_limit_service.set_limit(111, 30, set_by=1, one_time=True)
        duration_limit_service.set_limit(222, 60, set_by=1, one_time=False)
        await limits_command(mock_update, mock_context)

        reply = mock_update.message.reply_text.call_args[0][0]
        assert "разовый" in reply.lower()
        assert "постоянный" in reply.lower()

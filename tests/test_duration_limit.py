"""Tests for DurationLimitService and duration limit admin commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import Database
from app.database.migrations import initialize_schema
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
        ids = {l["telegram_id"] for l in limits}
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

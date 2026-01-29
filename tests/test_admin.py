"""Tests for admin command handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import Database
from app.database.migrations import initialize_schema
from app.handlers.admin import admin_only, approve_command, pending_command, reject_command
from app.services.whitelist import WhitelistService


@pytest.fixture
def whitelist_service(temp_db_path):
    """Create a WhitelistService with a test database."""
    db = Database(temp_db_path)
    initialize_schema(db)
    return WhitelistService(db)


@pytest.fixture
def mock_update():
    """Create a mock Update object."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789  # Admin ID from conftest
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context(whitelist_service):
    """Create a mock Context object with injected services."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.args = []
    context.bot_data = {"whitelist_service": whitelist_service}
    return context


class TestAdminOnlyDecorator:
    """Tests for admin_only decorator."""

    @pytest.mark.asyncio
    async def test_allows_admin_user(self, mock_update, mock_context):
        """Admin user can access the command."""

        @admin_only
        async def test_handler(update, context):
            await update.message.reply_text("success")

        await test_handler(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once_with("success")

    @pytest.mark.asyncio
    async def test_blocks_non_admin_user(self, mock_update, mock_context):
        """Non-admin user is blocked."""
        mock_update.effective_user.id = 999999  # Not admin

        @admin_only
        async def test_handler(update, context):
            await update.message.reply_text("success")

        await test_handler(mock_update, mock_context)

        # Should not call success, should send access denied
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) == 1
        assert "not authorized" in calls[0][0][0].lower()


class TestApproveCommand:
    """Tests for /approve command."""

    @pytest.mark.asyncio
    async def test_requires_telegram_id_argument(self, mock_update, mock_context):
        """Shows usage when no argument provided."""
        mock_context.args = []

        await approve_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "usage" in mock_update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_approves_pending_request(
        self, mock_update, mock_context, whitelist_service
    ):
        """Approves a pending access request."""
        whitelist_service.create_access_request(
            telegram_id=12345,
            display_name="Test User",
            username="testuser",
        )
        mock_context.args = ["12345"]

        await approve_command(mock_update, mock_context)

        # User should be whitelisted
        assert whitelist_service.is_whitelisted(12345) is True

        # Confirmation should be sent
        mock_update.message.reply_text.assert_called_once()
        assert "approved" in mock_update.message.reply_text.call_args[0][0].lower()

        # User should be notified
        mock_context.bot.send_message.assert_called_once()
        call_kwargs = mock_context.bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 12345

    @pytest.mark.asyncio
    async def test_handles_nonexistent_request(self, mock_update, mock_context):
        """Handles request that doesn't exist."""
        mock_context.args = ["99999"]

        await approve_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "no pending" in mock_update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_handles_invalid_telegram_id(self, mock_update, mock_context):
        """Handles invalid telegram ID argument."""
        mock_context.args = ["not_a_number"]

        await approve_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "invalid" in mock_update.message.reply_text.call_args[0][0].lower()


class TestRejectCommand:
    """Tests for /reject command."""

    @pytest.mark.asyncio
    async def test_requires_telegram_id_argument(self, mock_update, mock_context):
        """Shows usage when no argument provided."""
        mock_context.args = []

        await reject_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "usage" in mock_update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_rejects_pending_request(
        self, mock_update, mock_context, whitelist_service
    ):
        """Rejects a pending access request."""
        whitelist_service.create_access_request(
            telegram_id=12345,
            display_name="Test User",
            username="testuser",
        )
        mock_context.args = ["12345"]

        await reject_command(mock_update, mock_context)

        # User should NOT be whitelisted
        assert whitelist_service.is_whitelisted(12345) is False

        # Request should be marked rejected
        request = whitelist_service.get_access_request(12345)
        assert request.status == "rejected"

        # Confirmation should be sent
        mock_update.message.reply_text.assert_called_once()
        assert "rejected" in mock_update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_handles_nonexistent_request(self, mock_update, mock_context):
        """Handles request that doesn't exist."""
        mock_context.args = ["99999"]

        await reject_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "no pending" in mock_update.message.reply_text.call_args[0][0].lower()


class TestPendingCommand:
    """Tests for /pending command."""

    @pytest.mark.asyncio
    async def test_shows_no_pending_requests(self, mock_update, mock_context):
        """Shows message when no pending requests."""
        await pending_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "no pending" in mock_update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_lists_pending_requests(
        self, mock_update, mock_context, whitelist_service
    ):
        """Lists all pending access requests."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="User One",
            username="user1",
        )
        whitelist_service.create_access_request(
            telegram_id=456,
            display_name="User Two",
            username=None,
        )

        await pending_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        response = mock_update.message.reply_text.call_args[0][0]

        # Should include both users
        assert "123" in response
        assert "User One" in response
        assert "456" in response
        assert "User Two" in response

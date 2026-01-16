"""Tests for /start command handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import Database
from app.database.migrations import initialize_schema
from app.handlers.start import start_command
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
    update.effective_user.id = 12345
    update.effective_user.first_name = "Test"
    update.effective_user.username = "testuser"
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Context object."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    return context


class TestStartCommandAccessControl:
    """Tests for /start command access control."""

    @pytest.mark.asyncio
    async def test_whitelisted_user_sees_welcome(
        self, mock_update, mock_context, whitelist_service
    ):
        """Whitelisted user sees welcome message."""
        # Add user to whitelist
        whitelist_service.add_to_whitelist(
            telegram_id=12345,
            display_name="Test",
            username="testuser",
            approved_by=789,
        )

        with patch("app.handlers.start.whitelist_service", whitelist_service):
            await start_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        response = mock_update.message.reply_text.call_args[0][0]
        assert "welcome" in response.lower() or "book" in response.lower()

    @pytest.mark.asyncio
    async def test_non_whitelisted_user_sees_access_denied(
        self, mock_update, mock_context, whitelist_service
    ):
        """Non-whitelisted user sees access denied with chat ID."""
        with patch("app.handlers.start.whitelist_service", whitelist_service):
            await start_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        response = mock_update.message.reply_text.call_args[0][0]

        # Should mention access denied / approved users only
        assert "approved" in response.lower() or "access" in response.lower()
        # Should include chat ID
        assert "12345" in response

    @pytest.mark.asyncio
    async def test_creates_access_request_for_new_user(
        self, mock_update, mock_context, whitelist_service
    ):
        """New user's access request is created."""
        with patch("app.handlers.start.whitelist_service", whitelist_service):
            await start_command(mock_update, mock_context)

        # Check that access request was created
        request = whitelist_service.get_access_request(12345)
        assert request is not None
        assert request.display_name == "Test"
        assert request.username == "testuser"
        assert request.status == "pending"

    @pytest.mark.asyncio
    async def test_notifies_admin_for_new_request(
        self, mock_update, mock_context, whitelist_service
    ):
        """Admin is notified when new access request is created."""
        with (
            patch("app.handlers.start.whitelist_service", whitelist_service),
            patch("app.handlers.start.settings") as mock_settings,
        ):
            mock_settings.admin_telegram_id = 999

            await start_command(mock_update, mock_context)

        # Admin should be notified
        mock_context.bot.send_message.assert_called_once()
        call_kwargs = mock_context.bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 999

        # Notification should include user info
        message = call_kwargs["text"]
        assert "Test" in message
        assert "12345" in message

    @pytest.mark.asyncio
    async def test_does_not_notify_admin_for_existing_request(
        self, mock_update, mock_context, whitelist_service
    ):
        """Admin is NOT notified for existing pending request."""
        # Create existing request
        whitelist_service.create_access_request(
            telegram_id=12345,
            display_name="Test",
            username="testuser",
        )

        with (
            patch("app.handlers.start.whitelist_service", whitelist_service),
            patch("app.handlers.start.settings") as mock_settings,
        ):
            mock_settings.admin_telegram_id = 999

            await start_command(mock_update, mock_context)

        # Admin should NOT be notified
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_user_without_username(
        self, mock_update, mock_context, whitelist_service
    ):
        """User without Telegram username can still request access."""
        mock_update.effective_user.username = None

        with patch("app.handlers.start.whitelist_service", whitelist_service):
            await start_command(mock_update, mock_context)

        # Request should be created
        request = whitelist_service.get_access_request(12345)
        assert request is not None
        assert request.username is None

    @pytest.mark.asyncio
    async def test_admin_user_is_auto_whitelisted(
        self, mock_update, mock_context, whitelist_service
    ):
        """Admin user is automatically whitelisted on /start."""
        with (
            patch("app.handlers.start.whitelist_service", whitelist_service),
            patch("app.handlers.start.settings") as mock_settings,
        ):
            mock_settings.admin_telegram_id = 12345  # Same as user ID

            await start_command(mock_update, mock_context)

        # Admin should be whitelisted
        assert whitelist_service.is_whitelisted(12345) is True

        # Should see welcome, not access denied
        response = mock_update.message.reply_text.call_args[0][0]
        assert "approved" not in response.lower() or "welcome" in response.lower()

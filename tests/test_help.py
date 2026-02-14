"""Tests for /help command handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import Database
from app.database.migrations import initialize_schema
from app.handlers.help import help_command
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
def mock_context(whitelist_service):
    """Create a mock Context object with injected services."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot_data = {"whitelist_service": whitelist_service}
    return context


class TestHelpCommand:
    """Tests for /help command."""

    @pytest.mark.asyncio
    async def test_whitelisted_user_sees_available_commands(
        self, mock_update, mock_context, whitelist_service
    ):
        """Whitelisted user sees /book and /help commands."""
        whitelist_service.add_to_whitelist(
            telegram_id=12345,
            display_name="Test",
            username="testuser",
            approved_by=789,
        )

        await help_command(mock_update, mock_context)

        response = mock_update.message.reply_text.call_args[0][0]
        assert "/book" in response
        assert "/help" in response

    @pytest.mark.asyncio
    async def test_non_whitelisted_user_sees_minimal_message(
        self, mock_update, mock_context
    ):
        """Non-whitelisted user sees only /start."""
        await help_command(mock_update, mock_context)

        response = mock_update.message.reply_text.call_args[0][0]
        assert "/start" in response
        # Should NOT see /book
        assert "/book" not in response

    @pytest.mark.asyncio
    async def test_admin_sees_admin_commands(
        self, mock_update, mock_context, whitelist_service
    ):
        """Admin user sees admin commands in addition to regular ones."""
        whitelist_service.add_to_whitelist(
            telegram_id=12345,
            display_name="Test",
            username="testuser",
            approved_by=789,
        )

        with patch("app.handlers.help.settings") as mock_settings:
            mock_settings.admin_telegram_id = 12345

            await help_command(mock_update, mock_context)

        response = mock_update.message.reply_text.call_args[0][0]
        assert "/approve" in response
        assert "/reject" in response
        assert "/pending" in response

    @pytest.mark.asyncio
    async def test_non_admin_does_not_see_admin_commands(
        self, mock_update, mock_context, whitelist_service
    ):
        """Regular whitelisted user does NOT see admin commands."""
        whitelist_service.add_to_whitelist(
            telegram_id=12345,
            display_name="Test",
            username="testuser",
            approved_by=789,
        )

        with patch("app.handlers.help.settings") as mock_settings:
            mock_settings.admin_telegram_id = 99999

            await help_command(mock_update, mock_context)

        response = mock_update.message.reply_text.call_args[0][0]
        assert "/approve" not in response
        assert "/reject" not in response
        assert "/pending" not in response

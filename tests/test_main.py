"""Tests for application entrypoint and global error handling."""

from unittest.mock import MagicMock, patch

import pytest
from telegram.error import NetworkError

from app.main import error_handler, main


class TestErrorHandler:
    """Tests for global Telegram error handler."""

    @pytest.mark.asyncio
    async def test_logs_warning_for_network_error(self, caplog):
        caplog.set_level("WARNING")
        update = {"update_id": 1}
        context = MagicMock()
        context.error = NetworkError("temporary network issue")

        await error_handler(update, context)

        assert "Transient Telegram network error" in caplog.text
        assert "Unhandled exception while processing update" not in caplog.text

    @pytest.mark.asyncio
    async def test_logs_error_for_unhandled_exception(self, caplog):
        caplog.set_level("ERROR")
        update = {"update_id": 2}
        context = MagicMock()
        context.error = RuntimeError("boom")

        await error_handler(update, context)

        assert "Unhandled exception while processing update" in caplog.text


class TestMain:
    """Tests for main application wiring."""

    @patch("app.main.Application")
    @patch("app.main.run_migrations")
    @patch("app.main.setup_logging")
    def test_registers_error_handler_and_starts_polling(
        self, mock_setup_logging, mock_run_migrations, mock_application
    ):
        app_instance = MagicMock()
        mock_application.builder.return_value.token.return_value.build.return_value = app_instance

        main()

        mock_setup_logging.assert_called_once()
        mock_run_migrations.assert_called_once()
        app_instance.add_error_handler.assert_called_once_with(error_handler)
        app_instance.run_polling.assert_called_once()

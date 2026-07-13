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

    @patch("app.config.Settings.validate_event_type_configuration")
    @patch("app.main.run_migrations")
    @patch("app.main.setup_logging")
    def test_invalid_event_type_config_fails_before_migrations(
        self,
        mock_setup_logging,
        mock_run_migrations,
        mock_validate_event_types,
    ):
        mock_validate_event_types.side_effect = ValueError(
            "No event type ID configured for 120-minute duration"
        )

        with pytest.raises(ValueError, match="120-minute"):
            main()

        mock_setup_logging.assert_called_once_with()
        mock_run_migrations.assert_not_called()

    @patch("app.config.Settings.validate_event_type_configuration")
    @patch("app.main.Application")
    @patch("app.main.run_migrations")
    @patch("app.main.setup_logging")
    def test_registers_error_handler_and_starts_polling(
        self,
        mock_setup_logging,
        mock_run_migrations,
        mock_application,
        mock_validate_event_types,
    ):
        app_instance = MagicMock()
        mock_application.builder.return_value.token.return_value.build.return_value = app_instance

        main()

        mock_setup_logging.assert_called_once()
        mock_validate_event_types.assert_called_once_with()
        mock_run_migrations.assert_called_once()
        app_instance.add_error_handler.assert_called_once_with(error_handler)
        app_instance.run_polling.assert_called_once()

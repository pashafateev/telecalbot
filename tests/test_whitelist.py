"""Tests for WhitelistService."""

import pytest

from app.database import Database
from app.database.migrations import initialize_schema
from app.services.whitelist import WhitelistService


@pytest.fixture
def whitelist_service(temp_db_path):
    """Create a WhitelistService with a test database."""
    db = Database(temp_db_path)
    initialize_schema(db)
    return WhitelistService(db)


class TestIsWhitelisted:
    """Tests for is_whitelisted method."""

    def test_returns_false_for_unknown_user(self, whitelist_service):
        """Non-whitelisted user returns False."""
        assert whitelist_service.is_whitelisted(999999) is False

    def test_returns_true_for_whitelisted_user(self, whitelist_service):
        """Whitelisted user returns True."""
        whitelist_service.add_to_whitelist(
            telegram_id=123456,
            display_name="Test User",
            username="testuser",
            approved_by=789,
        )
        assert whitelist_service.is_whitelisted(123456) is True


class TestAddToWhitelist:
    """Tests for add_to_whitelist method."""

    def test_adds_user_to_whitelist(self, whitelist_service):
        """User is added to whitelist."""
        whitelist_service.add_to_whitelist(
            telegram_id=123456,
            display_name="Test User",
            username="testuser",
            approved_by=789,
        )

        assert whitelist_service.is_whitelisted(123456) is True

    def test_handles_none_username(self, whitelist_service):
        """User without username can be added."""
        whitelist_service.add_to_whitelist(
            telegram_id=123456,
            display_name="Test User",
            username=None,
            approved_by=789,
        )

        assert whitelist_service.is_whitelisted(123456) is True

    def test_updates_existing_user(self, whitelist_service):
        """Adding existing user updates their info."""
        whitelist_service.add_to_whitelist(
            telegram_id=123456,
            display_name="Old Name",
            username="olduser",
            approved_by=789,
        )
        whitelist_service.add_to_whitelist(
            telegram_id=123456,
            display_name="New Name",
            username="newuser",
            approved_by=999,
        )

        entry = whitelist_service.get_whitelist_entry(123456)
        assert entry is not None
        assert entry.display_name == "New Name"
        assert entry.username == "newuser"


class TestCreateAccessRequest:
    """Tests for create_access_request method."""

    def test_creates_new_request(self, whitelist_service):
        """New access request is created and returns True."""
        is_new = whitelist_service.create_access_request(
            telegram_id=123456,
            display_name="Test User",
            username="testuser",
        )

        assert is_new is True

    def test_returns_false_for_existing_pending(self, whitelist_service):
        """Existing pending request returns False."""
        whitelist_service.create_access_request(
            telegram_id=123456,
            display_name="Test User",
            username="testuser",
        )

        is_new = whitelist_service.create_access_request(
            telegram_id=123456,
            display_name="Test User",
            username="testuser",
        )

        assert is_new is False

    def test_handles_none_username(self, whitelist_service):
        """User without username can request access."""
        is_new = whitelist_service.create_access_request(
            telegram_id=123456,
            display_name="Test User",
            username=None,
        )

        assert is_new is True


class TestGetPendingRequests:
    """Tests for get_pending_requests method."""

    def test_returns_empty_list_when_none(self, whitelist_service):
        """Returns empty list when no pending requests."""
        requests = whitelist_service.get_pending_requests()
        assert requests == []

    def test_returns_pending_requests(self, whitelist_service):
        """Returns all pending requests."""
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

        requests = whitelist_service.get_pending_requests()

        assert len(requests) == 2
        ids = {r.telegram_id for r in requests}
        assert ids == {123, 456}

    def test_excludes_approved_requests(self, whitelist_service):
        """Approved requests are not returned."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="User One",
            username="user1",
        )
        whitelist_service.approve_request(123, approved_by=789)

        requests = whitelist_service.get_pending_requests()

        assert len(requests) == 0

    def test_excludes_rejected_requests(self, whitelist_service):
        """Rejected requests are not returned."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="User One",
            username="user1",
        )
        whitelist_service.reject_request(123)

        requests = whitelist_service.get_pending_requests()

        assert len(requests) == 0


class TestApproveRequest:
    """Tests for approve_request method."""

    def test_approves_pending_request(self, whitelist_service):
        """Pending request is approved and user is whitelisted."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="Test User",
            username="testuser",
        )

        result = whitelist_service.approve_request(123, approved_by=789)

        assert result is True
        assert whitelist_service.is_whitelisted(123) is True

    def test_returns_false_for_nonexistent_request(self, whitelist_service):
        """Returns False when request doesn't exist."""
        result = whitelist_service.approve_request(999, approved_by=789)
        assert result is False

    def test_updates_request_status(self, whitelist_service):
        """Request status is updated to approved."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="Test User",
            username="testuser",
        )
        whitelist_service.approve_request(123, approved_by=789)

        request = whitelist_service.get_access_request(123)
        assert request is not None
        assert request.status == "approved"


class TestRejectRequest:
    """Tests for reject_request method."""

    def test_rejects_pending_request(self, whitelist_service):
        """Pending request is rejected."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="Test User",
            username="testuser",
        )

        result = whitelist_service.reject_request(123)

        assert result is True
        assert whitelist_service.is_whitelisted(123) is False

    def test_returns_false_for_nonexistent_request(self, whitelist_service):
        """Returns False when request doesn't exist."""
        result = whitelist_service.reject_request(999)
        assert result is False

    def test_updates_request_status(self, whitelist_service):
        """Request status is updated to rejected."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="Test User",
            username="testuser",
        )
        whitelist_service.reject_request(123)

        request = whitelist_service.get_access_request(123)
        assert request is not None
        assert request.status == "rejected"


class TestGetAccessRequest:
    """Tests for get_access_request method."""

    def test_returns_none_for_unknown(self, whitelist_service):
        """Returns None for unknown telegram_id."""
        assert whitelist_service.get_access_request(999) is None

    def test_returns_access_request(self, whitelist_service):
        """Returns AccessRequest model for existing request."""
        whitelist_service.create_access_request(
            telegram_id=123,
            display_name="Test User",
            username="testuser",
        )

        request = whitelist_service.get_access_request(123)

        assert request is not None
        assert request.telegram_id == 123
        assert request.display_name == "Test User"
        assert request.username == "testuser"
        assert request.status == "pending"


class TestRemoveFromWhitelist:
    """Tests for remove_from_whitelist method."""

    def test_removes_user_from_whitelist(self, whitelist_service):
        """User is removed from whitelist."""
        whitelist_service.add_to_whitelist(
            telegram_id=123456,
            display_name="Test User",
            username="testuser",
            approved_by=789,
        )
        assert whitelist_service.is_whitelisted(123456) is True

        whitelist_service.remove_from_whitelist(123456)

        assert whitelist_service.is_whitelisted(123456) is False

    def test_handles_nonexistent_user(self, whitelist_service):
        """No error when removing nonexistent user."""
        whitelist_service.remove_from_whitelist(999999)  # Should not raise

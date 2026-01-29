"""Whitelist service for access control."""

from datetime import datetime, timezone

from app.database import Database
from app.database.models import AccessRequest, WhitelistEntry


class WhitelistService:
    """Service for managing whitelisted users and access requests."""

    def __init__(self, db: Database):
        self.db = db

    def is_whitelisted(self, telegram_id: int) -> bool:
        """Check if a user is whitelisted."""
        result = self.db.execute_one(
            "SELECT 1 FROM whitelist WHERE telegram_id = ?",
            (telegram_id,),
        )
        return result is not None

    def add_to_whitelist(
        self,
        telegram_id: int,
        display_name: str,
        username: str | None,
        approved_by: int,
    ) -> None:
        """Add or update a user in the whitelist."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute_write(
            """
            INSERT INTO whitelist (telegram_id, display_name, username, approved_at, approved_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                display_name = excluded.display_name,
                username = excluded.username,
                approved_at = excluded.approved_at,
                approved_by = excluded.approved_by
            """,
            (telegram_id, display_name, username, now, approved_by),
        )

    def remove_from_whitelist(self, telegram_id: int) -> None:
        """Remove a user from the whitelist."""
        self.db.execute_write(
            "DELETE FROM whitelist WHERE telegram_id = ?",
            (telegram_id,),
        )

    def get_whitelist_entry(self, telegram_id: int) -> WhitelistEntry | None:
        """Get a whitelist entry by telegram_id."""
        row = self.db.execute_one(
            "SELECT * FROM whitelist WHERE telegram_id = ?",
            (telegram_id,),
        )
        if row is None:
            return None
        return WhitelistEntry(
        telegram_id=row["telegram_id"],
            display_name=row["display_name"],
            username=row["username"],
            approved_at=datetime.fromisoformat(row["approved_at"]),
            approved_by=row["approved_by"],
        )

    def create_access_request(
        self,
        telegram_id: int,
        display_name: str,
        username: str | None,
    ) -> bool:
        """
        Create an access request.

        Returns True if a new request was created, False if one already exists.
        """
        now = datetime.now(timezone.utc).isoformat()
        rowcount = self.db.execute_write(
            """
            INSERT OR IGNORE INTO access_requests
                (telegram_id, display_name, username, requested_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (telegram_id, display_name, username, now),
        )
        return rowcount > 0

    def get_access_request(self, telegram_id: int) -> AccessRequest | None:
        """Get an access request by telegram_id."""
        row = self.db.execute_one(
            "SELECT * FROM access_requests WHERE telegram_id = ?",
            (telegram_id,),
        )
        if row is None:
            return None
        return AccessRequest(
            telegram_id=row["telegram_id"],
            display_name=row["display_name"],
            username=row["username"],
            requested_at=datetime.fromisoformat(row["requested_at"]),
            status=row["status"],
        )

    def get_pending_requests(self) -> list[AccessRequest]:
        """Get all pending access requests."""
        rows = self.db.execute(
            "SELECT * FROM access_requests WHERE status = 'pending' ORDER BY requested_at",
        )
        return [
            AccessRequest(
                telegram_id=row["telegram_id"],
                display_name=row["display_name"],
                username=row["username"],
                requested_at=datetime.fromisoformat(row["requested_at"]),
                status=row["status"],
            )
            for row in rows
        ]

    def approve_request(self, telegram_id: int, approved_by: int) -> bool:
        """
        Approve an access request.

        Returns True if request was found and approved, False otherwise.
        """
        request = self.get_access_request(telegram_id)
        if request is None or request.status != "pending":
            return False

        # Add to whitelist
        self.add_to_whitelist(
            telegram_id=request.telegram_id,
            display_name=request.display_name,
            username=request.username,
            approved_by=approved_by,
        )

        # Update request status
        self.db.execute_write(
            "UPDATE access_requests SET status = 'approved' WHERE telegram_id = ?",
            (telegram_id,),
        )

        return True

    def reject_request(self, telegram_id: int) -> bool:
        """
        Reject an access request.

        Returns True if request was found and rejected, False otherwise.
        """
        request = self.get_access_request(telegram_id)
        if request is None or request.status != "pending":
            return False

        self.db.execute_write(
            "UPDATE access_requests SET status = 'rejected' WHERE telegram_id = ?",
            (telegram_id,),
        )

        return True

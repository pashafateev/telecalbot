"""Pydantic models for database entities."""

from datetime import datetime

from pydantic import BaseModel


class WhitelistEntry(BaseModel):
    """A whitelisted user who can access the bot."""

    telegram_id: int
    display_name: str
    username: str | None = None
    approved_at: datetime
    approved_by: int


class AccessRequest(BaseModel):
    """A pending access request from a user."""

    telegram_id: int
    display_name: str
    username: str | None = None
    requested_at: datetime
    status: str = "pending"  # pending, approved, rejected


class UserPreference(BaseModel):
    """User preferences (timezone, etc.)."""

    telegram_id: int
    timezone: str
    updated_at: datetime

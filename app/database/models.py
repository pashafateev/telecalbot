"""Pydantic models for database entities."""

from datetime import datetime
from typing import Literal

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


class UserProfile(BaseModel):
    """Explicitly consented booking profile fields."""

    telegram_id: int
    preferred_name: str | None = None
    timezone: str | None = None
    email_mode: Literal["ask", "private", "saved"] = "ask"
    email: str | None = None
    updated_at: datetime


# Compatibility for code/tests written against the original timezone-only model.
UserPreference = UserProfile


class StoredBooking(BaseModel):
    """Booking record persisted for cancellation lookup."""

    id: int
    internal_ref: str | None = None
    telegram_id: int
    calcom_booking_id: int
    calcom_booking_uid: str
    title: str
    start: datetime
    end: datetime
    status: str
    created_at: datetime
    cancelled_at: datetime | None = None

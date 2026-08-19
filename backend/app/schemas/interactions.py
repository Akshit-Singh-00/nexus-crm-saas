"""Schemas for cross-channel customer interactions: emails, calls, meetings, files."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, EmailStr

InteractionKind = Literal["email", "call", "meeting", "file"]


class EmailLogIn(BaseModel):
    customer_id: Optional[str] = None
    deal_id: Optional[str] = None
    direction: Literal["outbound", "inbound"] = "outbound"
    to_email: Optional[EmailStr] = None
    from_email: Optional[EmailStr] = None
    subject: str
    body: str = ""


class CallLogIn(BaseModel):
    customer_id: Optional[str] = None
    deal_id: Optional[str] = None
    outcome: Literal["connected", "voicemail", "no_answer", "busy"] = "connected"
    duration_seconds: int = Field(default=0, ge=0)
    summary: str = ""


class MeetingIn(BaseModel):
    customer_id: Optional[str] = None
    deal_id: Optional[str] = None
    title: str
    scheduled_at: str  # ISO datetime
    duration_minutes: int = Field(default=30, ge=5, le=600)
    location: Optional[str] = ""
    description: str = ""
    reminder_minutes: int = Field(default=15, ge=0, le=1440)


class MeetingStatusIn(BaseModel):
    status: Literal["scheduled", "completed", "cancelled"]


class FileMetaIn(BaseModel):
    """A file record. Content is stored as a data URL (base64) in Mongo for portability."""
    customer_id: Optional[str] = None
    deal_id: Optional[str] = None
    filename: str
    mime_type: str = "application/octet-stream"
    size_bytes: int = Field(default=0, ge=0)
    data_url: str = ""  # capped server-side


class IntegrationConnectIn(BaseModel):
    provider: Literal["gmail", "outlook", "google_calendar"]
    account_email: Optional[EmailStr] = None

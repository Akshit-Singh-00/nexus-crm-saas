"""Pydantic request schemas for auth + membership."""
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class InviteIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "manager", "member", "support", "viewer"] = "member"
    send_email: bool = False


class InviteAcceptIn(BaseModel):
    password: str = Field(min_length=6)
    name: Optional[str] = None


class MemberRoleIn(BaseModel):
    role: Literal["admin", "manager", "member", "support", "viewer"]

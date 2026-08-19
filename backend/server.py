"""Entry point for supervisor (`server:app`).

The application has been refactored into `app/` (see app/main.py).
This shim keeps the supervisor start command working without change.
"""
from app.main import app  # noqa: F401

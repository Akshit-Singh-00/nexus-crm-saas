"""Shared slowapi limiter instance."""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import RATE_LIMIT_ENABLED

limiter = Limiter(key_func=get_remote_address, headers_enabled=False, enabled=RATE_LIMIT_ENABLED)

"""Pagination helpers."""


def clamp_limit(limit: int, default: int = 25, maximum: int = 100) -> int:
    if not isinstance(limit, int) or limit <= 0:
        return default
    return min(limit, maximum)


def clamp_skip(page: int, limit: int) -> int:
    page = max(1, int(page or 1))
    return (page - 1) * limit

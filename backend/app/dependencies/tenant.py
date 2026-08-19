"""Workspace membership dependency."""
from typing import Optional

from fastapi import Depends, HTTPException, Header

from app.core.database import db
from app.dependencies.auth import current_user


async def get_membership(user_id: str, workspace_id: str) -> Optional[dict]:
    return await db.memberships.find_one(
        {"user_id": user_id, "workspace_id": workspace_id}, {"_id": 0}
    )


async def require_workspace(
    x_workspace_id: str = Header(...),
    user: dict = Depends(current_user),
) -> dict:
    m = await get_membership(user["id"], x_workspace_id)
    if not m:
        raise HTTPException(403, "Not a member of this workspace")
    return {"user": user, "workspace_id": x_workspace_id, "role": m["role"]}

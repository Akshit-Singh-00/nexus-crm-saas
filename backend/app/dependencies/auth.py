"""FastAPI auth dependencies."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.database import db
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


async def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    uid = decode_token(cred.credentials)
    if not uid:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": uid}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user

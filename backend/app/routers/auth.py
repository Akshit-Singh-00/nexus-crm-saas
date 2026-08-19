"""Auth + invite endpoints."""
import logging
from datetime import datetime, timezone, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import APP_URL, EMERGENT_EMAIL_KEY, JWT_ALG, JWT_SECRET
from app.core.database import db
from app.core.rate_limit import limiter
from app.core.security import hash_pw, make_token, verify_pw
from app.dependencies.auth import current_user
from app.dependencies.permissions import require_perm
from app.dependencies.tenant import get_membership
from app.schemas.auth import InviteAcceptIn, InviteIn, LoginIn, SignupIn
from app.services.audit_service import audit_auth_event, log_activity
from app.services.email_service import render_invite_email, send_email
from app.utils.ids import new_id, now_iso

router = APIRouter()


@router.post("/auth/signup")
@limiter.limit("60/hour")
async def signup(request: Request, body: SignupIn):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    uid = new_id()
    user = {
        "id": uid,
        "email": body.email.lower(),
        "name": body.name,
        "password": hash_pw(body.password),
        "avatar_url": None,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    token = make_token(uid)
    user.pop("password")
    user.pop("_id", None)
    return {"token": token, "user": user}


@router.post("/auth/login")
@limiter.limit("30/minute")
async def login(request: Request, body: LoginIn):
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_pw(body.password, user["password"]):
        await audit_auth_event(None, body.email.lower(), "login_failed", body.email.lower())
        raise HTTPException(401, "Invalid credentials")
    token = make_token(user["id"])
    await audit_auth_event(user["id"], user.get("email"), "login_success", user["id"])
    user.pop("password", None)
    user.pop("_id", None)
    return {"token": token, "user": user}


@router.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    memberships = await db.memberships.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    ws_ids = [m["workspace_id"] for m in memberships]
    workspaces = await db.workspaces.find({"id": {"$in": ws_ids}}, {"_id": 0}).to_list(100)
    ws_map = {w["id"]: w for w in workspaces}
    result_ws = [
        {**ws_map[m["workspace_id"]], "role": m["role"]}
        for m in memberships if m["workspace_id"] in ws_map
    ]
    return {"user": user, "workspaces": result_ws}


@router.post("/workspaces/invite")
@limiter.limit("60/hour")
async def invite_member(request: Request, body: InviteIn,
                        ctx: dict = Depends(require_perm("member", "invite"))):
    workspace = await db.workspaces.find_one({"id": ctx["workspace_id"]}, {"_id": 0})
    token_payload = {
        "workspace_id": ctx["workspace_id"],
        "email": body.email.lower(),
        "role": body.role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALG)
    invite_link = f"{APP_URL}/invite/{token}" if APP_URL else f"/invite/{token}"

    await db.invites.insert_one({
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "email": body.email.lower(),
        "role": body.role,
        "invited_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "accepted": False,
    })
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "invited", "user", body.email, {"role": body.role})

    email_sent = False
    if body.send_email and EMERGENT_EMAIL_KEY:
        try:
            html = render_invite_email(
                inviter=ctx["user"]["name"], workspace_name=workspace["name"],
                link=invite_link, role=body.role,
            )
            await send_email(to=body.email, subject=f"You're invited to {workspace['name']} on NexusCRM", html=html)
            email_sent = True
        except Exception:
            logging.exception("Invite email failed")

    return {"ok": True, "invite_link": invite_link, "email_sent": email_sent}


@router.get("/invites/{token}")
async def get_invite(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(400, "Invalid or expired invite")
    workspace = await db.workspaces.find_one({"id": payload["workspace_id"]}, {"_id": 0})
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    existing_user = await db.users.find_one({"email": payload["email"].lower()}, {"_id": 0, "password": 0})
    return {
        "email": payload["email"],
        "role": payload["role"],
        "workspace": {"id": workspace["id"], "name": workspace["name"]},
        "user_exists": bool(existing_user and not existing_user.get("invited")),
    }


@router.post("/invites/{token}/accept")
async def accept_invite(token: str, body: InviteAcceptIn):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(400, "Invalid or expired invite")
    email = payload["email"].lower()
    workspace_id = payload["workspace_id"]

    already = await db.invites.find_one(
        {"workspace_id": workspace_id, "email": email, "accepted": True}, {"_id": 1}
    )
    if already:
        raise HTTPException(400, "This invitation has already been used")

    user = await db.users.find_one({"email": email})
    if user:
        if user.get("invited"):
            await db.users.update_one({"id": user["id"]}, {"$set": {
                "password": hash_pw(body.password),
                "name": body.name or user.get("name") or email.split("@")[0],
                "invited": False,
            }})
    else:
        user = {
            "id": new_id(),
            "email": email,
            "name": body.name or email.split("@")[0],
            "password": hash_pw(body.password),
            "avatar_url": None,
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)

    existing = await get_membership(user["id"], workspace_id)
    if not existing:
        await db.memberships.insert_one({
            "id": new_id(),
            "user_id": user["id"],
            "workspace_id": workspace_id,
            "role": payload["role"],
            "created_at": now_iso(),
        })
    await db.invites.update_many(
        {"workspace_id": workspace_id, "email": email},
        {"$set": {"accepted": True, "accepted_at": now_iso()}},
    )
    tok = make_token(user["id"])
    return {"token": tok, "workspace_id": workspace_id}

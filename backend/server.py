"""NexusCRM - Multi-tenant SaaS CRM Backend."""
import os
import uuid
import logging
import re
import ipaddress
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Literal
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import jwt
import bcrypt
import httpx
import stripe
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Env
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ['JWT_SECRET']
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')
EMERGENT_EMAIL_KEY = os.environ.get('EMERGENT_EMAIL_KEY', '')
EMAIL_FROM_NAME = os.environ.get('EMAIL_FROM_NAME', 'NexusCRM')
APP_URL = os.environ.get('APP_URL', '')
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
JWT_ALG = "HS256"
JWT_EXP_HOURS = 24 * 7

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="NexusCRM API")
api = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)

# ----------- Helpers -----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def new_id() -> str:
    return uuid.uuid4().hex

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload.get("sub")
    except Exception:
        return None

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

def require_role(*roles: str):
    async def _dep(ctx: dict = Depends(require_workspace)):
        if ctx["role"] not in roles:
            raise HTTPException(403, f"Requires role: {', '.join(roles)}")
        return ctx
    return _dep

# ----------- Models -----------
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class WorkspaceIn(BaseModel):
    name: str
    industry: Optional[str] = None

class InviteIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "member", "viewer"] = "member"
    send_email: bool = False

class InviteAcceptIn(BaseModel):
    password: str = Field(min_length=6)
    name: Optional[str] = None

class CustomerIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Literal["active", "churned", "prospect"] = "active"
    tags: List[str] = []

class LeadIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = "manual"
    status: Literal["new", "contacted", "qualified", "unqualified"] = "new"
    value: float = 0

class DealIn(BaseModel):
    title: str
    customer_id: Optional[str] = None
    value: float = 0
    stage: Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"] = "lead"
    assignee_id: Optional[str] = None
    close_date: Optional[str] = None

class DealStageUpdate(BaseModel):
    stage: Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]

class TaskIn(BaseModel):
    title: str
    description: Optional[str] = ""
    due_date: Optional[str] = None
    priority: Literal["low", "medium", "high"] = "medium"
    status: Literal["todo", "in_progress", "done"] = "todo"
    assignee_id: Optional[str] = None
    related_type: Optional[str] = None  # customer/lead/deal
    related_id: Optional[str] = None

class NoteIn(BaseModel):
    content: str
    related_type: str  # customer/lead/deal
    related_id: str

# ----------- Activity -----------
async def log_activity(workspace_id: str, actor_id: str, action: str,
                       entity_type: str, entity_id: str, meta: Optional[dict] = None):
    await db.activities.insert_one({
        "id": new_id(),
        "workspace_id": workspace_id,
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "meta": meta or {},
        "created_at": now_iso(),
    })

# ----------- Auth -----------
@api.post("/auth/signup")
async def signup(body: SignupIn):
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

@api.post("/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_pw(body.password, user["password"]):
        raise HTTPException(401, "Invalid credentials")
    token = make_token(user["id"])
    user.pop("password", None)
    user.pop("_id", None)
    return {"token": token, "user": user}

@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    # attach workspaces
    memberships = await db.memberships.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).to_list(100)
    ws_ids = [m["workspace_id"] for m in memberships]
    workspaces = await db.workspaces.find(
        {"id": {"$in": ws_ids}}, {"_id": 0}
    ).to_list(100)
    ws_map = {w["id"]: w for w in workspaces}
    result_ws = [
        {**ws_map[m["workspace_id"]], "role": m["role"]}
        for m in memberships if m["workspace_id"] in ws_map
    ]
    return {"user": user, "workspaces": result_ws}

# ----------- Workspaces -----------
@api.post("/workspaces")
async def create_workspace(body: WorkspaceIn, user: dict = Depends(current_user)):
    wid = new_id()
    workspace = {
        "id": wid,
        "name": body.name,
        "industry": body.industry,
        "owner_id": user["id"],
        "plan": "starter",
        "created_at": now_iso(),
    }
    await db.workspaces.insert_one(workspace)
    await db.memberships.insert_one({
        "id": new_id(),
        "user_id": user["id"],
        "workspace_id": wid,
        "role": "owner",
        "created_at": now_iso(),
    })
    workspace.pop("_id", None)
    return {**workspace, "role": "owner"}

@api.get("/workspaces/members")
async def list_members(ctx: dict = Depends(require_workspace)):
    memberships = await db.memberships.find(
        {"workspace_id": ctx["workspace_id"]}, {"_id": 0}
    ).to_list(500)
    uids = [m["user_id"] for m in memberships]
    users = await db.users.find(
        {"id": {"$in": uids}}, {"_id": 0, "password": 0}
    ).to_list(500)
    umap = {u["id"]: u for u in users}
    return [
        {**umap.get(m["user_id"], {"id": m["user_id"]}), "role": m["role"], "membership_id": m["id"]}
        for m in memberships
    ]

@api.post("/workspaces/invite")
async def invite_member(body: InviteIn, ctx: dict = Depends(require_role("owner", "admin"))):
    # Create signed invite token (7 days)
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

    # Store invite record for audit
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
            html = _render_invite_email(inviter=ctx["user"]["name"], workspace_name=workspace["name"], link=invite_link, role=body.role)
            await send_email(to=body.email, subject=f"You're invited to {workspace['name']} on NexusCRM", html=html)
            email_sent = True
        except Exception as e:
            logging.exception("Invite email failed")

    return {"ok": True, "invite_link": invite_link, "email_sent": email_sent}


@api.get("/invites/{token}")
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


@api.post("/invites/{token}/accept")
async def accept_invite(token: str, body: InviteAcceptIn):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(400, "Invalid or expired invite")
    email = payload["email"].lower()
    workspace_id = payload["workspace_id"]

    # Find or create user
    user = await db.users.find_one({"email": email})
    if user:
        # If stub/invited user, set the real password now
        if user.get("invited"):
            await db.users.update_one({"id": user["id"]}, {"$set": {
                "password": hash_pw(body.password),
                "name": body.name or user.get("name") or email.split("@")[0],
                "invited": False,
            }})
        # else: existing real user — attach membership without changing password
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

    # Add membership if not exists
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

# ----------- Generic CRUD builders -----------
def workspace_query(ctx: dict, extra: dict = None) -> dict:
    q = {"workspace_id": ctx["workspace_id"]}
    if extra:
        q.update(extra)
    return q

# ----------- Customers -----------
@api.get("/customers")
async def list_customers(search: str = "", ctx: dict = Depends(require_workspace)):
    q = workspace_query(ctx)
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
        ]
    docs = await db.customers.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs

@api.post("/customers")
async def create_customer(body: CustomerIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.customers.insert_one(doc)
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "created", "customer", doc["id"], {"name": body.name})
    doc.pop("_id", None)
    return doc

@api.get("/customers/{cid}")
async def get_customer(cid: str, ctx: dict = Depends(require_workspace)):
    doc = await db.customers.find_one(workspace_query(ctx, {"id": cid}), {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc

@api.put("/customers/{cid}")
async def update_customer(cid: str, body: CustomerIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    r = await db.customers.update_one(
        workspace_query(ctx, {"id": cid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "updated", "customer", cid)
    return {"ok": True}

@api.delete("/customers/{cid}")
async def delete_customer(cid: str, ctx: dict = Depends(require_role("owner", "admin"))):
    r = await db.customers.delete_one(workspace_query(ctx, {"id": cid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "deleted", "customer", cid)
    return {"ok": True}

# ----------- Leads -----------
@api.get("/leads")
async def list_leads(search: str = "", ctx: dict = Depends(require_workspace)):
    q = workspace_query(ctx)
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
        ]
    return await db.leads.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/leads")
async def create_lead(body: LeadIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "score": None,
        "score_reason": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.leads.insert_one(doc)
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "created", "lead", doc["id"], {"name": body.name})
    doc.pop("_id", None)
    return doc

@api.put("/leads/{lid}")
async def update_lead(lid: str, body: LeadIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    r = await db.leads.update_one(
        workspace_query(ctx, {"id": lid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.delete("/leads/{lid}")
async def delete_lead(lid: str, ctx: dict = Depends(require_role("owner", "admin"))):
    r = await db.leads.delete_one(workspace_query(ctx, {"id": lid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

# ----------- Deals -----------
@api.get("/deals")
async def list_deals(ctx: dict = Depends(require_workspace)):
    return await db.deals.find(workspace_query(ctx), {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/deals")
async def create_deal(body: DealIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.deals.insert_one(doc)
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "created", "deal", doc["id"], {"title": body.title})
    doc.pop("_id", None)
    return doc

@api.put("/deals/{did}")
async def update_deal(did: str, body: DealIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    r = await db.deals.update_one(
        workspace_query(ctx, {"id": did}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.patch("/deals/{did}/stage")
async def update_deal_stage(did: str, body: DealStageUpdate, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    r = await db.deals.update_one(
        workspace_query(ctx, {"id": did}),
        {"$set": {"stage": body.stage, "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "stage_changed", "deal", did, {"stage": body.stage})
    await notify_workspace(
        ctx["workspace_id"],
        exclude_user=ctx["user"]["id"],
        title=f"Deal moved to {body.stage}",
        body=f"{ctx['user']['name']} moved a deal to {body.stage}.",
        kind="deal_stage",
        entity_type="deal",
        entity_id=did,
    )
    return {"ok": True}

@api.delete("/deals/{did}")
async def delete_deal(did: str, ctx: dict = Depends(require_role("owner", "admin"))):
    r = await db.deals.delete_one(workspace_query(ctx, {"id": did}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

# ----------- Tasks -----------
@api.get("/tasks")
async def list_tasks(status_filter: Optional[str] = None, ctx: dict = Depends(require_workspace)):
    q = workspace_query(ctx)
    if status_filter:
        q["status"] = status_filter
    return await db.tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/tasks")
async def create_task(body: TaskIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.tasks.insert_one(doc)
    doc.pop("_id", None)
    # Notify assignee if different from creator
    if body.assignee_id and body.assignee_id != ctx["user"]["id"]:
        await create_notification(
            workspace_id=ctx["workspace_id"],
            user_id=body.assignee_id,
            title="New task assigned",
            body=f"{ctx['user']['name']} assigned you: {body.title}",
            kind="task_assigned",
            entity_type="task",
            entity_id=doc["id"],
        )
    return doc

@api.put("/tasks/{tid}")
async def update_task(tid: str, body: TaskIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    r = await db.tasks.update_one(
        workspace_query(ctx, {"id": tid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.delete("/tasks/{tid}")
async def delete_task(tid: str, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    r = await db.tasks.delete_one(workspace_query(ctx, {"id": tid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

# ----------- Notes -----------
@api.get("/notes")
async def list_notes(related_type: str, related_id: str, ctx: dict = Depends(require_workspace)):
    q = workspace_query(ctx, {"related_type": related_type, "related_id": related_id})
    docs = await db.notes.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    # attach author names
    uids = list({d["author_id"] for d in docs})
    users = await db.users.find({"id": {"$in": uids}}, {"_id": 0, "password": 0}).to_list(500)
    umap = {u["id"]: u for u in users}
    for d in docs:
        d["author"] = umap.get(d["author_id"], {"name": "Unknown"})
    return docs

@api.post("/notes")
async def create_note(body: NoteIn, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "author_id": ctx["user"]["id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.notes.insert_one(doc)
    doc.pop("_id", None)
    return doc

# ----------- Activities -----------
@api.get("/activities")
async def list_activities(limit: int = 50, ctx: dict = Depends(require_workspace)):
    docs = await db.activities.find(
        workspace_query(ctx), {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    uids = list({d["actor_id"] for d in docs})
    users = await db.users.find({"id": {"$in": uids}}, {"_id": 0, "password": 0}).to_list(500)
    umap = {u["id"]: u for u in users}
    for d in docs:
        d["actor"] = umap.get(d["actor_id"], {"name": "System"})
    return docs

# ----------- Dashboard analytics -----------
@api.get("/analytics/overview")
async def analytics_overview(ctx: dict = Depends(require_workspace)):
    wid = ctx["workspace_id"]
    total_customers = await db.customers.count_documents({"workspace_id": wid})
    total_leads = await db.leads.count_documents({"workspace_id": wid})
    total_deals = await db.deals.count_documents({"workspace_id": wid})
    open_tasks = await db.tasks.count_documents({"workspace_id": wid, "status": {"$ne": "done"}})

    # pipeline value by stage
    pipeline = await db.deals.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$stage", "value": {"$sum": "$value"}, "count": {"$sum": 1}}},
    ]).to_list(20)
    stages = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
    stage_map = {p["_id"]: p for p in pipeline}
    by_stage = [
        {"stage": s, "value": stage_map.get(s, {}).get("value", 0), "count": stage_map.get(s, {}).get("count", 0)}
        for s in stages
    ]

    # leads by status
    leads_agg = await db.leads.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]).to_list(20)
    leads_by_status = [{"status": p["_id"], "count": p["count"]} for p in leads_agg]

    won_value = stage_map.get("won", {}).get("value", 0)
    total_pipeline = sum(p["value"] for p in pipeline if p["_id"] not in ("lost",))

    return {
        "totals": {
            "customers": total_customers,
            "leads": total_leads,
            "deals": total_deals,
            "open_tasks": open_tasks,
            "won_value": won_value,
            "pipeline_value": total_pipeline,
        },
        "pipeline_by_stage": by_stage,
        "leads_by_status": leads_by_status,
    }

# ----------- AI -----------
async def call_claude(system: str, user_msg: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=new_id(),
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")
    resp = await chat.send_message(UserMessage(text=user_msg))
    return str(resp)

@api.post("/ai/score-lead/{lid}")
async def ai_score_lead(lid: str, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    lead = await db.leads.find_one(workspace_query(ctx, {"id": lid}), {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    system = ("You are a B2B sales analyst. Score the lead 0-100 for likelihood to convert. "
              "Return STRICT JSON: {\"score\": <int>, \"reason\": \"<1-2 sentence rationale>\"}. No other text.")
    profile = (
        f"Name: {lead.get('name')}\n"
        f"Email: {lead.get('email')}\n"
        f"Company: {lead.get('company')}\n"
        f"Source: {lead.get('source')}\n"
        f"Status: {lead.get('status')}\n"
        f"Estimated Value: ${lead.get('value', 0)}\n"
    )
    try:
        raw = await call_claude(system, profile)
    except Exception as e:
        logging.exception("AI scoring failed")
        raise HTTPException(500, f"AI error: {e}")
    import json, re
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise HTTPException(500, "AI did not return JSON")
    data = json.loads(m.group(0))
    score = int(data.get("score", 0))
    reason = data.get("reason", "")
    await db.leads.update_one(
        workspace_query(ctx, {"id": lid}),
        {"$set": {"score": score, "score_reason": reason, "updated_at": now_iso()}},
    )
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "ai_scored", "lead", lid, {"score": score})
    return {"score": score, "reason": reason}

@api.post("/ai/summarize-customer/{cid}")
async def ai_summarize_customer(cid: str, ctx: dict = Depends(require_role("owner", "admin", "member"))):
    customer = await db.customers.find_one(workspace_query(ctx, {"id": cid}), {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer not found")
    notes = await db.notes.find(
        workspace_query(ctx, {"related_type": "customer", "related_id": cid}),
        {"_id": 0}
    ).to_list(100)
    deals = await db.deals.find(workspace_query(ctx, {"customer_id": cid}), {"_id": 0}).to_list(100)
    system = ("You are a CRM insight engine. Given customer info, notes, and deals, produce a concise "
              "executive summary in 3 short paragraphs: 1) Relationship overview, 2) Opportunity & risks, "
              "3) Recommended next actions. Plain text, no markdown headers.")
    ctx_msg = (
        f"CUSTOMER: {customer.get('name')} | {customer.get('company')} | {customer.get('email')}\n"
        f"Status: {customer.get('status')} | Tags: {', '.join(customer.get('tags', []))}\n\n"
        f"NOTES ({len(notes)}):\n" + "\n".join(f"- {n['content']}" for n in notes[:20]) + "\n\n"
        f"DEALS ({len(deals)}):\n" + "\n".join(f"- {d['title']} | {d['stage']} | ${d['value']}" for d in deals) 
    )
    try:
        summary = await call_claude(system, ctx_msg)
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
    return {"summary": summary}

@api.get("/ai/sales-forecast")
async def ai_sales_forecast(ctx: dict = Depends(require_workspace)):
    wid = ctx["workspace_id"]
    pipeline = await db.deals.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$stage", "value": {"$sum": "$value"}, "count": {"$sum": 1}}},
    ]).to_list(20)
    stage_map = {p["_id"]: p for p in pipeline}
    context_str = "Pipeline snapshot:\n" + "\n".join(
        f"- {p['_id']}: {p['count']} deals, ${p['value']:,.0f}" for p in pipeline
    )
    system = ("You are a sales forecasting analyst. Given a pipeline snapshot with deal counts and values per stage, "
              "predict likely revenue for the next quarter and highlight two key risks. Keep it under 120 words, plain text.")
    try:
        forecast = await call_claude(system, context_str)
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
    return {"forecast": forecast, "pipeline": pipeline}

# ----------- Email (Resend via Emergent proxy) -----------
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> Optional[str]:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    async with httpx.AsyncClient(timeout=30) as client_http:
        resp = await client_http.post(
            f"{EMAIL_BASE_URL}/api/v1/email/send",
            headers={"X-Email-Key": EMERGENT_EMAIL_KEY},
            json=payload,
        )
    resp.raise_for_status()
    return resp.json().get("id")


def _render_invite_email(inviter: str, workspace_name: str, link: str, role: str) -> str:
    inv = escape(inviter); ws = escape(workspace_name); ro = escape(role); ln = escape(link)
    return (
        f'<table role="presentation" width="100%" style="max-width:560px;margin:0 auto;'
        f'font-family:Arial,sans-serif"><tr><td style="padding:32px 24px">'
        f'<h1 style="margin:0 0 12px;font-size:22px;color:#0A0A0A">You\'re invited to {ws}</h1>'
        f'<p style="color:#333;line-height:1.5">{inv} has invited you to join the '
        f'<strong>{ws}</strong> workspace on NexusCRM as a <strong>{ro}</strong>.</p>'
        f'<p style="margin:24px 0"><a href="{ln}" '
        f'style="background:#0047FF;color:#fff;padding:12px 20px;text-decoration:none;'
        f'border-radius:4px;font-weight:600">Accept invitation</a></p>'
        f'<p style="font-size:12px;color:#888">This link expires in 7 days. If you didn\'t expect '
        f'this, you can ignore this email — NexusCRM never asks for your password by email.</p>'
        f'</td></tr></table>'
    )


# ----------- Notifications -----------
async def create_notification(*, workspace_id: str, user_id: str, title: str, body: str,
                              kind: str, entity_type: Optional[str] = None,
                              entity_id: Optional[str] = None):
    await db.notifications.insert_one({
        "id": new_id(),
        "workspace_id": workspace_id,
        "user_id": user_id,
        "title": title,
        "body": body,
        "kind": kind,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "read": False,
        "created_at": now_iso(),
    })


async def notify_workspace(workspace_id: str, exclude_user: str, title: str, body: str,
                           kind: str, entity_type: Optional[str] = None,
                           entity_id: Optional[str] = None):
    members = await db.memberships.find(
        {"workspace_id": workspace_id, "user_id": {"$ne": exclude_user}}, {"_id": 0}
    ).to_list(500)
    for m in members:
        await create_notification(
            workspace_id=workspace_id, user_id=m["user_id"], title=title, body=body,
            kind=kind, entity_type=entity_type, entity_id=entity_id,
        )


@api.get("/notifications")
async def list_notifications(ctx: dict = Depends(require_workspace)):
    q = {"workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"]}
    docs = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({**q, "read": False})
    return {"items": docs, "unread": unread}


@api.post("/notifications/{nid}/read")
async def mark_notification_read(nid: str, ctx: dict = Depends(require_workspace)):
    await db.notifications.update_one(
        {"id": nid, "workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@api.post("/notifications/read-all")
async def mark_all_read(ctx: dict = Depends(require_workspace)):
    await db.notifications.update_many(
        {"workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"], "read": False},
        {"$set": {"read": True}},
    )
    return {"ok": True}


# ----------- Global Search -----------
@api.get("/search")
async def global_search(q: str, ctx: dict = Depends(require_workspace)):
    if not q or len(q) < 1:
        return {"customers": [], "leads": [], "deals": []}
    rx = {"$regex": q, "$options": "i"}
    wq = {"workspace_id": ctx["workspace_id"]}
    customers = await db.customers.find(
        {**wq, "$or": [{"name": rx}, {"email": rx}, {"company": rx}]}, {"_id": 0}
    ).limit(6).to_list(6)
    leads = await db.leads.find(
        {**wq, "$or": [{"name": rx}, {"email": rx}, {"company": rx}]}, {"_id": 0}
    ).limit(6).to_list(6)
    deals = await db.deals.find({**wq, "title": rx}, {"_id": 0}).limit(6).to_list(6)
    return {"customers": customers, "leads": leads, "deals": deals}


# ----------- Billing / Stripe -----------
stripe.api_key = STRIPE_API_KEY

PLANS = {
    "starter": {"name": "Starter", "price": 0.0, "features": ["Up to 100 customers", "Basic AI scoring", "1 workspace"]},
    "pro": {"name": "Pro", "price": 29.0, "features": ["Unlimited customers", "AI summaries & forecasts", "Priority support"]},
    "team": {"name": "Team", "price": 79.0, "features": ["Everything in Pro", "Advanced RBAC", "Custom AI training", "SLA"]},
}


class CheckoutRequestIn(BaseModel):
    plan_id: Literal["pro", "team"]
    origin_url: str


@api.get("/billing/plans")
async def get_plans():
    return {"plans": PLANS}


@api.get("/billing/subscription")
async def get_subscription(ctx: dict = Depends(require_workspace)):
    workspace = await db.workspaces.find_one({"id": ctx["workspace_id"]}, {"_id": 0})
    plan = workspace.get("plan", "starter")
    if plan == "free":
        plan = "starter"
    return {
        "plan": plan,
        "plan_details": PLANS.get(plan),
        "subscription_id": workspace.get("stripe_subscription_id"),
        "status": workspace.get("subscription_status", "active"),
    }


@api.post("/billing/checkout")
async def billing_checkout(body: CheckoutRequestIn, ctx: dict = Depends(require_role("owner", "admin"))):
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )
    plan = PLANS.get(body.plan_id)
    if not plan or plan["price"] <= 0:
        raise HTTPException(400, "Invalid plan")

    host = APP_URL or body.origin_url.rstrip("/")
    webhook_url = f"{host}/api/webhook/stripe"
    checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    req = CheckoutSessionRequest(
        amount=float(plan["price"]),
        currency="usd",
        success_url=f"{body.origin_url}/app/billing?status=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{body.origin_url}/app/billing?status=cancel",
        metadata={
            "workspace_id": ctx["workspace_id"],
            "plan_id": body.plan_id,
            "user_id": ctx["user"]["id"],
        },
    )
    session = await checkout.create_checkout_session(req)

    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "workspace_id": ctx["workspace_id"],
        "user_id": ctx["user"]["id"],
        "plan_id": body.plan_id,
        "amount": float(plan["price"]),
        "currency": "usd",
        "status": "initiated",
        "payment_status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.session_id}


@api.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Transaction not found")
    # Ask Stripe directly if still pending
    if record.get("payment_status") != "paid":
        try:
            from emergentintegrations.payments.stripe.checkout import StripeCheckout
            checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{APP_URL}/api/webhook/stripe")
            s = await checkout.get_checkout_status(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await _mark_paid(session_id, record.get("workspace_id"), record.get("plan_id"))
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except Exception:
            pass
    return {
        "session_id": record["session_id"],
        "status": record["status"],
        "payment_status": record["payment_status"],
        "plan_id": record.get("plan_id"),
    }


async def _mark_paid(session_id: str, workspace_id: Optional[str], plan_id: Optional[str]):
    r = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid", "updated_at": now_iso()}},
    )
    if r.modified_count and workspace_id and plan_id:
        await db.workspaces.update_one(
            {"id": workspace_id},
            {"$set": {"plan": plan_id, "subscription_status": "active", "updated_at": now_iso()}},
        )


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    host = APP_URL
    checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{host}/api/webhook/stripe")
    try:
        event = await checkout.handle_webhook(body, sig)
    except Exception as e:
        logging.exception("Webhook verification failed")
        raise HTTPException(400, str(e))

    if event.payment_status == "paid":
        meta = event.metadata or {}
        await _mark_paid(event.session_id, meta.get("workspace_id"), meta.get("plan_id"))
    return {"status": "ok"}


# ----------- Health -----------
@api.get("/")
async def root():
    return {"service": "NexusCRM", "status": "ok"}


# Mount
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexuscrm")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

"""NexusCRM - Multi-tenant SaaS CRM Backend."""
import os
import csv
import io
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


# ----------- Permission Matrix (RBAC 2.0) -----------
# Backwards-compatible: keeps existing role names, adds `manager` and `support`.
ROLES = ("owner", "admin", "manager", "member", "support", "viewer")
ROLE_LABELS = {
    "owner": "Super Admin",
    "admin": "Organization Admin",
    "manager": "Sales Manager",
    "member": "Sales Representative",
    "support": "Support Agent",
    "viewer": "Viewer",
}

# resource -> action -> set(role)
PERMISSIONS: dict = {
    "customer":     {"view": {"owner","admin","manager","member","support","viewer"}, "create": {"owner","admin","manager","member"}, "edit": {"owner","admin","manager","member"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager"}},
    "lead":         {"view": {"owner","admin","manager","member","viewer"},           "create": {"owner","admin","manager","member"}, "edit": {"owner","admin","manager","member"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager"}},
    "deal":         {"view": {"owner","admin","manager","member","viewer"},           "create": {"owner","admin","manager","member"}, "edit": {"owner","admin","manager","member"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager"}},
    "task":         {"view": {"owner","admin","manager","member","support","viewer"}, "create": {"owner","admin","manager","member","support"}, "edit": {"owner","admin","manager","member","support"}, "delete": {"owner","admin","manager","member","support"}},
    "note":         {"view": {"owner","admin","manager","member","support","viewer"}, "create": {"owner","admin","manager","member","support"}},
    "ticket":       {"view": {"owner","admin","manager","support","viewer"},           "create": {"owner","admin","manager","support","member"}, "edit": {"owner","admin","manager","support"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager","support"}},
    "settings":     {"view": {"owner","admin","manager"}, "manage": {"owner","admin"}},
    "audit_log":    {"view": {"owner","admin"}},
    "billing":      {"view": {"owner","admin"}, "manage": {"owner"}},
    "member":       {"view": {"owner","admin","manager","member","support","viewer"}, "invite": {"owner","admin"}, "manage": {"owner","admin"}},
    "ai":           {"use":  {"owner","admin","manager","member","support"}},
    "report":       {"view": {"owner","admin","manager","viewer"}, "export": {"owner","admin","manager"}},
}


def can(role: str, resource: str, action: str) -> bool:
    return role in PERMISSIONS.get(resource, {}).get(action, set())


def require_perm(resource: str, action: str):
    async def _dep(ctx: dict = Depends(require_workspace)):
        if not can(ctx["role"], resource, action):
            raise HTTPException(403, f"Missing permission: {resource}.{action}")
        return ctx
    return _dep


# ----------- Audit Log -----------
async def audit(ctx: dict, action: str, resource: str, resource_id: str,
                before: Optional[dict] = None, after: Optional[dict] = None):
    await db.audit_logs.insert_one({
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "user_id": ctx["user"]["id"],
        "user_email": ctx["user"].get("email"),
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "before": before,
        "after": after,
        "created_at": now_iso(),
    })

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
    role: Literal["admin", "manager", "member", "support", "viewer"] = "member"
    send_email: bool = False

class InviteAcceptIn(BaseModel):
    password: str = Field(min_length=6)
    name: Optional[str] = None

class MemberRoleIn(BaseModel):
    role: Literal["admin", "manager", "member", "support", "viewer"]

class WorkspaceSettingsIn(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    industry: Optional[str] = None
    pipeline_stages: Optional[List[dict]] = None  # [{id, label, color, probability}]

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
    stage: str = "lead"
    assignee_id: Optional[str] = None
    close_date: Optional[str] = None
    probability: int = Field(default=25, ge=0, le=100)
    priority: Literal["low", "medium", "high"] = "medium"
    tags: List[str] = []
    description: Optional[str] = ""

class DealStageUpdate(BaseModel):
    stage: str

class TicketIn(BaseModel):
    subject: str
    description: Optional[str] = ""
    customer_id: Optional[str] = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["open", "in_progress", "waiting", "resolved", "closed"] = "open"
    assignee_id: Optional[str] = None
    tags: List[str] = []

class CopilotIn(BaseModel):
    message: str
    context_type: Optional[str] = None  # customer/lead/deal
    context_id: Optional[str] = None


# ----------- CSV Import models -----------
class ImportPreviewIn(BaseModel):
    csv_text: str
    entity: Literal["customer", "lead"]

class ImportExecuteIn(BaseModel):
    csv_text: str
    entity: Literal["customer", "lead"]
    mapping: dict  # {csv_column_name: entity_field_name}


# ----------- Workflow models -----------
WORKFLOW_TRIGGERS = ("lead_created", "lead_scored", "customer_created", "deal_stage_changed", "deal_created")
WORKFLOW_ACTIONS = ("create_task", "assign_user", "notify_user", "add_tag")

class WorkflowConditionIn(BaseModel):
    field: str
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains", "in"]
    value: object = None

class WorkflowActionIn(BaseModel):
    type: Literal["create_task", "assign_user", "notify_user", "add_tag"]
    params: dict = {}

class WorkflowIn(BaseModel):
    name: str
    description: Optional[str] = ""
    trigger: Literal["lead_created", "lead_scored", "customer_created", "deal_stage_changed", "deal_created"]
    conditions: List[WorkflowConditionIn] = []
    actions: List[WorkflowActionIn] = Field(min_length=1)
    enabled: bool = True

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

DEFAULT_PIPELINE_STAGES = [
    {"id": "lead",        "label": "Lead",        "color": "#94a3b8", "probability": 10},
    {"id": "qualified",   "label": "Qualified",   "color": "#0047FF", "probability": 25},
    {"id": "demo",        "label": "Demo",        "color": "#7c3aed", "probability": 40},
    {"id": "proposal",    "label": "Proposal",    "color": "#0036CC", "probability": 60},
    {"id": "negotiation", "label": "Negotiation", "color": "#0A0A0A", "probability": 80},
    {"id": "won",         "label": "Won",         "color": "#10b981", "probability": 100},
    {"id": "lost",        "label": "Lost",        "color": "#FF3823", "probability": 0},
]


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
        "logo_url": None,
        "pipeline_stages": DEFAULT_PIPELINE_STAGES,
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
async def invite_member(body: InviteIn, ctx: dict = Depends(require_perm("member", "invite"))):
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
async def list_customers(search: str = "", ctx: dict = Depends(require_perm("customer", "view"))):
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
async def create_customer(body: CustomerIn, ctx: dict = Depends(require_perm("customer", "create"))):
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
    await fire_workflows("customer_created", ctx["workspace_id"], doc)
    doc.pop("_id", None)
    return doc

@api.get("/customers/{cid}")
async def get_customer(cid: str, ctx: dict = Depends(require_perm("customer", "view"))):
    doc = await db.customers.find_one(workspace_query(ctx, {"id": cid}), {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc

@api.put("/customers/{cid}")
async def update_customer(cid: str, body: CustomerIn, ctx: dict = Depends(require_perm("customer", "edit"))):
    r = await db.customers.update_one(
        workspace_query(ctx, {"id": cid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "updated", "customer", cid)
    return {"ok": True}

@api.delete("/customers/{cid}")
async def delete_customer(cid: str, ctx: dict = Depends(require_perm("customer", "delete"))):
    r = await db.customers.delete_one(workspace_query(ctx, {"id": cid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "deleted", "customer", cid)
    return {"ok": True}

# ----------- Leads -----------
@api.get("/leads")
async def list_leads(search: str = "", ctx: dict = Depends(require_perm("lead", "view"))):
    q = workspace_query(ctx)
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
        ]
    return await db.leads.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/leads")
async def create_lead(body: LeadIn, ctx: dict = Depends(require_perm("lead", "create"))):
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
    await fire_workflows("lead_created", ctx["workspace_id"], doc)
    doc.pop("_id", None)
    return doc

@api.put("/leads/{lid}")
async def update_lead(lid: str, body: LeadIn, ctx: dict = Depends(require_perm("lead", "edit"))):
    r = await db.leads.update_one(
        workspace_query(ctx, {"id": lid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.delete("/leads/{lid}")
async def delete_lead(lid: str, ctx: dict = Depends(require_perm("lead", "delete"))):
    r = await db.leads.delete_one(workspace_query(ctx, {"id": lid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

# ----------- Deal risk detection -----------
def _compute_deal_risk(deal: dict) -> dict:
    """Compute deal risk based on activity age, close date and stage."""
    if deal.get("stage") in ("won", "lost"):
        return {"level": "none", "reasons": []}
    reasons = []
    now = datetime.now(timezone.utc)
    try:
        updated = datetime.fromisoformat(deal.get("updated_at", "").replace("Z", "+00:00"))
        days_since = (now - updated).days
    except Exception:
        days_since = 0
    if days_since >= 7:
        reasons.append(f"No activity for {days_since} days")
    close_date = deal.get("close_date")
    if close_date:
        try:
            cd = datetime.fromisoformat(close_date)
            if cd.tzinfo is None:
                cd = cd.replace(tzinfo=timezone.utc)
            days_to_close = (cd - now).days
            if days_to_close < 0 and deal.get("stage") not in ("won", "lost"):
                reasons.append(f"Overdue by {-days_to_close} days")
            elif 0 <= days_to_close <= 5 and deal.get("stage") not in ("negotiation", "proposal"):
                reasons.append(f"Close date in {days_to_close} days but not in negotiation")
        except Exception:
            pass
    if deal.get("stage") == "proposal" and days_since >= 5:
        reasons.append("Proposal without follow-up")
    if deal.get("probability", 0) < 20 and days_since >= 3:
        reasons.append("Low probability with stale activity")
    if not reasons:
        return {"level": "none", "reasons": []}
    level = "high" if len(reasons) >= 2 or days_since >= 14 else "medium"
    return {"level": level, "reasons": reasons}


# ----------- Deals -----------
@api.get("/deals")
async def list_deals(ctx: dict = Depends(require_perm("deal", "view"))):
    deals = await db.deals.find(workspace_query(ctx), {"_id": 0}).sort("created_at", -1).to_list(500)
    for d in deals:
        d["risk"] = _compute_deal_risk(d)
    return deals

@api.post("/deals")
async def create_deal(body: DealIn, ctx: dict = Depends(require_perm("deal", "create"))):
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
    await fire_workflows("deal_created", ctx["workspace_id"], doc)
    doc.pop("_id", None)
    return doc

@api.put("/deals/{did}")
async def update_deal(did: str, body: DealIn, ctx: dict = Depends(require_perm("deal", "edit"))):
    r = await db.deals.update_one(
        workspace_query(ctx, {"id": did}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.patch("/deals/{did}/stage")
async def update_deal_stage(did: str, body: DealStageUpdate, ctx: dict = Depends(require_perm("deal", "edit"))):
    r = await db.deals.update_one(
        workspace_query(ctx, {"id": did}),
        {"$set": {"stage": body.stage, "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "stage_changed", "deal", did, {"stage": body.stage})
    updated = await db.deals.find_one(workspace_query(ctx, {"id": did}), {"_id": 0})
    if updated:
        await fire_workflows("deal_stage_changed", ctx["workspace_id"], updated)
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
async def delete_deal(did: str, ctx: dict = Depends(require_perm("deal", "delete"))):
    r = await db.deals.delete_one(workspace_query(ctx, {"id": did}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

# ----------- Tasks -----------
@api.get("/tasks")
async def list_tasks(status_filter: Optional[str] = None, ctx: dict = Depends(require_perm("task", "view"))):
    q = workspace_query(ctx)
    if status_filter:
        q["status"] = status_filter
    return await db.tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/tasks")
async def create_task(body: TaskIn, ctx: dict = Depends(require_perm("task", "create"))):
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
async def update_task(tid: str, body: TaskIn, ctx: dict = Depends(require_perm("task", "edit"))):
    r = await db.tasks.update_one(
        workspace_query(ctx, {"id": tid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.delete("/tasks/{tid}")
async def delete_task(tid: str, ctx: dict = Depends(require_perm("task", "delete"))):
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
async def create_note(body: NoteIn, ctx: dict = Depends(require_perm("note", "create"))):
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
    open_tickets = await db.tickets.count_documents({"workspace_id": wid, "status": {"$nin": ["resolved", "closed"]}})

    # Pipeline: use workspace stages
    workspace = await db.workspaces.find_one({"id": wid}, {"_id": 0})
    stages = workspace.get("pipeline_stages") or DEFAULT_PIPELINE_STAGES
    stage_ids = [s["id"] for s in stages]
    stage_prob = {s["id"]: s.get("probability", 50) for s in stages}

    pipeline = await db.deals.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$stage", "value": {"$sum": "$value"}, "count": {"$sum": 1}}},
    ]).to_list(50)
    stage_map = {p["_id"]: p for p in pipeline}
    by_stage = [
        {
            "stage": s["id"],
            "label": s["label"],
            "color": s.get("color", "#0047FF"),
            "value": stage_map.get(s["id"], {}).get("value", 0),
            "count": stage_map.get(s["id"], {}).get("count", 0),
        }
        for s in stages
    ]

    leads_agg = await db.leads.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]).to_list(20)
    leads_by_status = [{"status": p["_id"], "count": p["count"]} for p in leads_agg]

    won_value = stage_map.get("won", {}).get("value", 0)
    won_count = stage_map.get("won", {}).get("count", 0)
    lost_count = stage_map.get("lost", {}).get("count", 0)
    total_closed = won_count + lost_count
    win_rate = round((won_count / total_closed) * 100, 1) if total_closed else 0.0
    avg_deal_size = round(won_value / won_count, 2) if won_count else 0.0

    # Weighted pipeline: for each open deal, value * probability (stage or deal)
    open_deals = await db.deals.find(
        {"workspace_id": wid, "stage": {"$nin": ["won", "lost"]}},
        {"_id": 0}
    ).to_list(1000)
    weighted = 0.0
    committed = 0.0  # deals with probability >= 90
    best_case = 0.0  # deals with probability >= 60
    for d in open_deals:
        prob = d.get("probability") if d.get("probability") is not None else stage_prob.get(d.get("stage"), 50)
        v = float(d.get("value") or 0)
        weighted += v * (prob / 100.0)
        if prob >= 90:
            committed += v
        if prob >= 60:
            best_case += v
    total_pipeline = sum(d.get("value") or 0 for d in open_deals)
    forecast = weighted + won_value

    # Sales cycle: avg days from created_at to updated_at for won deals
    won_deals = await db.deals.find({"workspace_id": wid, "stage": "won"}, {"_id": 0}).to_list(500)
    cycle_days = 0.0
    if won_deals:
        total_days = 0
        n = 0
        for d in won_deals:
            try:
                c = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
                u = datetime.fromisoformat(d["updated_at"].replace("Z", "+00:00"))
                total_days += (u - c).days
                n += 1
            except Exception:
                pass
        cycle_days = round(total_days / n, 1) if n else 0.0

    # At-risk deals
    at_risk = []
    for d in open_deals:
        r = _compute_deal_risk(d)
        if r["level"] in ("medium", "high"):
            at_risk.append({**d, "risk": r})
    at_risk.sort(key=lambda x: (x["risk"]["level"] == "high", x.get("value") or 0), reverse=True)

    return {
        "totals": {
            "customers": total_customers,
            "leads": total_leads,
            "deals": total_deals,
            "open_tasks": open_tasks,
            "open_tickets": open_tickets,
            "won_value": won_value,
            "pipeline_value": total_pipeline,
        },
        "forecast": {
            "committed": round(committed, 2),
            "best_case": round(best_case, 2),
            "pipeline": round(total_pipeline, 2),
            "weighted": round(weighted, 2),
            "forecast": round(forecast, 2),
        },
        "kpis": {
            "win_rate": win_rate,
            "avg_deal_size": avg_deal_size,
            "sales_cycle_days": cycle_days,
            "won_count": won_count,
            "lost_count": lost_count,
        },
        "pipeline_by_stage": by_stage,
        "leads_by_status": leads_by_status,
        "at_risk_deals": at_risk[:10],
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
async def ai_score_lead(lid: str, ctx: dict = Depends(require_perm("ai", "use"))):
    lead = await db.leads.find_one(workspace_query(ctx, {"id": lid}), {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    system = ("You are a B2B sales analyst. Score the lead 0-100 for likelihood to convert. "
              "Return STRICT JSON: {\"score\": <int>, \"classification\": \"hot\"|\"warm\"|\"cold\", "
              "\"reasons\": [\"<3-5 short bullet reasons>\"]}. No other text.")
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
    import json
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise HTTPException(500, "AI did not return JSON")
    try:
        data = json.loads(m.group(0))
    except Exception:
        raise HTTPException(500, "AI returned malformed JSON")
    score = int(data.get("score", 0))
    reasons = data.get("reasons") or ([data["reason"]] if data.get("reason") else [])
    classification = data.get("classification") or ("hot" if score >= 75 else "warm" if score >= 50 else "cold")
    await db.leads.update_one(
        workspace_query(ctx, {"id": lid}),
        {"$set": {
            "score": score,
            "score_reason": " · ".join(reasons) if isinstance(reasons, list) else str(reasons),
            "score_reasons": reasons if isinstance(reasons, list) else [str(reasons)],
            "classification": classification,
            "scored_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "ai_scored", "lead", lid, {"score": score})
    updated_lead = await db.leads.find_one(workspace_query(ctx, {"id": lid}), {"_id": 0})
    if updated_lead:
        await fire_workflows("lead_scored", ctx["workspace_id"], updated_lead)
    return {"score": score, "classification": classification, "reasons": reasons}

@api.post("/ai/summarize-customer/{cid}")
async def ai_summarize_customer(cid: str, ctx: dict = Depends(require_perm("ai", "use"))):
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


# ----------- Workspace settings -----------
@api.get("/workspaces/settings")
async def get_workspace_settings(ctx: dict = Depends(require_perm("settings", "view"))):
    ws = await db.workspaces.find_one({"id": ctx["workspace_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(404, "Workspace not found")
    if not ws.get("pipeline_stages"):
        ws["pipeline_stages"] = DEFAULT_PIPELINE_STAGES
    return ws


@api.put("/workspaces/settings")
async def update_workspace_settings(body: WorkspaceSettingsIn,
                                    ctx: dict = Depends(require_perm("settings", "manage"))):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if "pipeline_stages" in update:
        seen_ids = set()
        for s in update["pipeline_stages"]:
            if not s.get("id") or not s.get("label"):
                raise HTTPException(400, "Each stage needs id and label")
            if s["id"] in seen_ids:
                raise HTTPException(400, f"Duplicate stage id: {s['id']}")
            seen_ids.add(s["id"])
    if not update:
        return {"ok": True}
    before = await db.workspaces.find_one({"id": ctx["workspace_id"]}, {"_id": 0, "password": 0})
    await db.workspaces.update_one({"id": ctx["workspace_id"]},
                                   {"$set": {**update, "updated_at": now_iso()}})
    await audit(ctx, "updated", "workspace", ctx["workspace_id"],
                before={k: before.get(k) for k in update.keys()},
                after=update)
    return {"ok": True}


@api.patch("/workspaces/members/{user_id}/role")
async def update_member_role(user_id: str, body: MemberRoleIn,
                             ctx: dict = Depends(require_perm("member", "manage"))):
    # Cannot change your own role or the owner role
    target = await db.memberships.find_one(
        {"workspace_id": ctx["workspace_id"], "user_id": user_id}, {"_id": 0}
    )
    if not target:
        raise HTTPException(404, "Member not found")
    if target["role"] == "owner":
        raise HTTPException(403, "Cannot change the owner's role")
    if user_id == ctx["user"]["id"]:
        raise HTTPException(403, "Cannot change your own role")
    await db.memberships.update_one(
        {"workspace_id": ctx["workspace_id"], "user_id": user_id},
        {"$set": {"role": body.role}},
    )
    await audit(ctx, "role_changed", "member", user_id,
                before={"role": target["role"]}, after={"role": body.role})
    return {"ok": True}


@api.delete("/workspaces/members/{user_id}")
async def remove_member(user_id: str, ctx: dict = Depends(require_perm("member", "manage"))):
    target = await db.memberships.find_one(
        {"workspace_id": ctx["workspace_id"], "user_id": user_id}, {"_id": 0}
    )
    if not target:
        raise HTTPException(404, "Member not found")
    if target["role"] == "owner":
        raise HTTPException(403, "Cannot remove the owner")
    if user_id == ctx["user"]["id"]:
        raise HTTPException(403, "Cannot remove yourself")
    await db.memberships.delete_one({"workspace_id": ctx["workspace_id"], "user_id": user_id})
    await audit(ctx, "removed", "member", user_id, before=target)
    return {"ok": True}


# ----------- Support Tickets -----------
def _next_ticket_number(seq: int) -> str:
    return f"TKT-{seq:05d}"


@api.get("/tickets")
async def list_tickets(status_filter: Optional[str] = None,
                       ctx: dict = Depends(require_perm("ticket", "view"))):
    q = workspace_query(ctx)
    if status_filter:
        q["status"] = status_filter
    return await db.tickets.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/tickets")
async def create_ticket(body: TicketIn, ctx: dict = Depends(require_perm("ticket", "create"))):
    count = await db.tickets.count_documents({"workspace_id": ctx["workspace_id"]})
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "number": _next_ticket_number(count + 1),
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.tickets.insert_one(doc)
    await audit(ctx, "created", "ticket", doc["id"], after={"subject": body.subject})
    if body.assignee_id and body.assignee_id != ctx["user"]["id"]:
        await create_notification(
            workspace_id=ctx["workspace_id"], user_id=body.assignee_id,
            title=f"Ticket {doc['number']} assigned",
            body=f"{ctx['user']['name']} assigned you a ticket: {body.subject}",
            kind="ticket_assigned", entity_type="ticket", entity_id=doc["id"],
        )
    doc.pop("_id", None)
    return doc


@api.get("/tickets/{tid}")
async def get_ticket(tid: str, ctx: dict = Depends(require_perm("ticket", "view"))):
    doc = await db.tickets.find_one(workspace_query(ctx, {"id": tid}), {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@api.put("/tickets/{tid}")
async def update_ticket(tid: str, body: TicketIn, ctx: dict = Depends(require_perm("ticket", "edit"))):
    before = await db.tickets.find_one(workspace_query(ctx, {"id": tid}), {"_id": 0})
    if not before:
        raise HTTPException(404, "Not found")
    await db.tickets.update_one(
        workspace_query(ctx, {"id": tid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    changed = {k: body.model_dump().get(k) for k in body.model_dump() if before.get(k) != body.model_dump().get(k)}
    await audit(ctx, "updated", "ticket", tid,
                before={k: before.get(k) for k in changed}, after=changed)
    return {"ok": True}


@api.delete("/tickets/{tid}")
async def delete_ticket(tid: str, ctx: dict = Depends(require_perm("ticket", "delete"))):
    before = await db.tickets.find_one(workspace_query(ctx, {"id": tid}), {"_id": 0})
    r = await db.tickets.delete_one(workspace_query(ctx, {"id": tid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await audit(ctx, "deleted", "ticket", tid, before=before)
    return {"ok": True}


@api.get("/tickets/stats/overview")
async def ticket_stats(ctx: dict = Depends(require_perm("ticket", "view"))):
    wid = ctx["workspace_id"]
    open_ = await db.tickets.count_documents({"workspace_id": wid, "status": {"$nin": ["resolved", "closed"]}})
    resolved = await db.tickets.count_documents({"workspace_id": wid, "status": "resolved"})
    high_pri = await db.tickets.count_documents({"workspace_id": wid, "priority": {"$in": ["high", "urgent"]}, "status": {"$nin": ["resolved", "closed"]}})
    total = await db.tickets.count_documents({"workspace_id": wid})
    return {"open": open_, "resolved": resolved, "high_priority": high_pri, "total": total}


# ----------- Audit log viewer -----------
@api.get("/audit-logs")
async def list_audit_logs(limit: int = 100, ctx: dict = Depends(require_perm("audit_log", "view"))):
    docs = await db.audit_logs.find(workspace_query(ctx), {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs


# ----------- AI Sales Copilot -----------
async def _gather_ai_context(workspace_id: str, focus_type: Optional[str] = None, focus_id: Optional[str] = None) -> str:
    """Aggregate a compact CRM snapshot for the AI copilot."""
    now = datetime.now(timezone.utc)
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    stages = ws.get("pipeline_stages") or DEFAULT_PIPELINE_STAGES
    stage_map = {s["id"]: s.get("probability", 50) for s in stages}

    # Deals summary
    deals = await db.deals.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    open_deals = [d for d in deals if d.get("stage") not in ("won", "lost")]
    won_deals = [d for d in deals if d.get("stage") == "won"]
    at_risk = []
    for d in open_deals:
        r = _compute_deal_risk(d)
        if r["level"] in ("medium", "high"):
            at_risk.append({**d, "risk": r})
    at_risk.sort(key=lambda x: (x["risk"]["level"] == "high", x.get("value") or 0), reverse=True)

    # Leads (top 10 by score if any, else recent)
    leads = await db.leads.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    scored = [l for l in leads if l.get("score") is not None]
    top_leads = sorted(scored, key=lambda l: l["score"] or 0, reverse=True)[:5] if scored else leads[:5]

    tasks = await db.tasks.find({"workspace_id": workspace_id, "status": {"$ne": "done"}}, {"_id": 0}).sort("due_date", 1).to_list(10)

    lines = [f"=== WORKSPACE: {ws.get('name')} (industry: {ws.get('industry') or 'n/a'}) ==="]
    lines.append(f"Pipeline stages: {', '.join(s['id'] for s in stages)}")
    lines.append(f"\n[DEALS] total={len(deals)} open={len(open_deals)} won={len(won_deals)}")
    for d in open_deals[:12]:
        prob = d.get("probability") or stage_map.get(d.get("stage"), 50)
        lines.append(f"  - {d.get('title')} | stage={d.get('stage')} | ${d.get('value',0):,.0f} | prob={prob}% | close={d.get('close_date') or '—'}")

    if at_risk:
        lines.append(f"\n[AT-RISK] ({len(at_risk)})")
        for d in at_risk[:6]:
            lines.append(f"  - {d.get('title')} | ${d.get('value',0):,.0f} | risk={d['risk']['level']} | reasons: {'; '.join(d['risk']['reasons'])}")

    lines.append(f"\n[TOP LEADS]")
    for l in top_leads:
        lines.append(f"  - {l.get('name')} ({l.get('company') or '—'}) score={l.get('score','?')} status={l.get('status')} value=${l.get('value',0):,.0f}")

    lines.append(f"\n[OPEN TASKS] ({len(tasks)})")
    for t in tasks[:6]:
        lines.append(f"  - {t.get('title')} | priority={t.get('priority')} | due={t.get('due_date') or '—'}")

    # Focused entity
    if focus_type and focus_id:
        coll = {"customer": db.customers, "lead": db.leads, "deal": db.deals}.get(focus_type)
        if coll is not None:
            entity = await coll.find_one({"workspace_id": workspace_id, "id": focus_id}, {"_id": 0})
            if entity:
                notes = await db.notes.find(
                    {"workspace_id": workspace_id, "related_type": focus_type, "related_id": focus_id},
                    {"_id": 0}
                ).sort("created_at", -1).to_list(20)
                lines.append(f"\n[FOCUSED {focus_type.upper()}] {entity}")
                if notes:
                    lines.append(f"[NOTES]")
                    for n in notes[:10]:
                        lines.append(f"  - {n['content']}")
    return "\n".join(lines)


@api.post("/ai/copilot")
async def ai_copilot(body: CopilotIn, ctx: dict = Depends(require_perm("ai", "use"))):
    ctx_snapshot = await _gather_ai_context(ctx["workspace_id"], body.context_type, body.context_id)
    system = (
        "You are NexusCRM Sales Copilot — an expert B2B sales analyst embedded in a live CRM. "
        "You are given a snapshot of the user's workspace: deals, leads, tasks, at-risk deals, notes. "
        "Respond concisely and specifically using ONLY the data provided. When suggesting actions, name the actual deal/lead by title. "
        "Format: short bullet points or 1-3 short paragraphs. No markdown headers. When drafting emails, keep them under 150 words and professional. "
        "If the user asks about data that isn't in the snapshot, say what's missing and suggest how to record it."
    )
    prompt = (
        f"USER QUESTION:\n{body.message}\n\n"
        f"CRM SNAPSHOT:\n{ctx_snapshot}\n"
    )
    try:
        answer = await call_claude(system, prompt)
    except Exception as e:
        raise HTTPException(500, f"Copilot error: {e}")
    return {"answer": answer}


# ----------- CSV Import -----------
CUSTOMER_FIELDS = ["name", "email", "phone", "company", "status"]
LEAD_FIELDS = ["name", "email", "phone", "company", "source", "status", "value"]


def _parse_csv(csv_text: str) -> tuple:
    if not csv_text.strip():
        raise HTTPException(400, "Empty CSV")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        raise HTTPException(400, "No rows in CSV")
    headers = [h.strip() for h in rows[0]]
    data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]
    return headers, data_rows


def _infer_mapping(headers: List[str], entity: str) -> dict:
    fields = CUSTOMER_FIELDS if entity == "customer" else LEAD_FIELDS
    result = {}
    for h in headers:
        low = h.lower().strip()
        for f in fields:
            if f == low or f in low or low in f:
                result[h] = f
                break
    return result


@api.post("/import/preview")
async def import_preview(body: ImportPreviewIn, ctx: dict = Depends(require_workspace)):
    if body.entity == "lead" and not can(ctx["role"], "lead", "create"):
        raise HTTPException(403, "Missing permission: lead.create")
    if body.entity == "customer" and not can(ctx["role"], "customer", "create"):
        raise HTTPException(403, "Missing permission: customer.create")
    headers, data_rows = _parse_csv(body.csv_text)
    fields = CUSTOMER_FIELDS if body.entity == "customer" else LEAD_FIELDS
    return {
        "headers": headers,
        "sample_rows": [dict(zip(headers, r + [""] * (len(headers) - len(r)))) for r in data_rows[:5]],
        "total_rows": len(data_rows),
        "target_fields": fields,
        "suggested_mapping": _infer_mapping(headers, body.entity),
    }


@api.post("/import/execute")
async def import_execute(body: ImportExecuteIn, ctx: dict = Depends(require_workspace)):
    if body.entity == "lead" and not can(ctx["role"], "lead", "create"):
        raise HTTPException(403, "Missing permission: lead.create")
    if body.entity == "customer" and not can(ctx["role"], "customer", "create"):
        raise HTTPException(403, "Missing permission: customer.create")
    headers, data_rows = _parse_csv(body.csv_text)
    if len(data_rows) > 5000:
        raise HTTPException(400, f"Too many rows ({len(data_rows)}). Maximum 5000 per import.")
    fields = CUSTOMER_FIELDS if body.entity == "customer" else LEAD_FIELDS
    coll = db.customers if body.entity == "customer" else db.leads
    inserted = 0
    errors = []
    for i, row in enumerate(data_rows):
        try:
            row_dict = dict(zip(headers, row + [""] * (len(headers) - len(row))))
            entity_data = {}
            for csv_col, field in body.mapping.items():
                if field not in fields:
                    continue
                val = row_dict.get(csv_col, "").strip()
                if not val:
                    continue
                if field == "value":
                    try:
                        entity_data[field] = float(val)
                    except Exception:
                        entity_data[field] = 0
                else:
                    entity_data[field] = val
            if not entity_data.get("name"):
                errors.append({"row": i + 2, "error": "Missing name"})
                continue
            # Defaults
            if body.entity == "customer":
                entity_data.setdefault("status", "active")
                entity_data.setdefault("tags", [])
            else:
                entity_data.setdefault("status", "new")
                entity_data.setdefault("source", "csv_import")
                entity_data.setdefault("value", 0)
                entity_data.setdefault("score", None)
                entity_data.setdefault("classification", None)
            doc = {
                "id": new_id(),
                "workspace_id": ctx["workspace_id"],
                "created_by": ctx["user"]["id"],
                "created_at": now_iso(),
                "updated_at": now_iso(),
                **entity_data,
            }
            await coll.insert_one(doc)
            inserted += 1
        except Exception as e:
            errors.append({"row": i + 2, "error": str(e)})
    await audit(ctx, "imported", body.entity, "batch", after={"count": inserted, "errors": len(errors)})
    return {"inserted": inserted, "errors": errors, "total": len(data_rows)}


# ----------- Workflow Automation -----------
def _eval_condition(record: dict, cond: dict) -> bool:
    val = record.get(cond["field"])
    target = cond.get("value")
    op = cond["op"]
    try:
        if op == "eq": return val == target
        if op == "neq": return val != target
        if op == "gt": return (val or 0) > float(target)
        if op == "gte": return (val or 0) >= float(target)
        if op == "lt": return (val or 0) < float(target)
        if op == "lte": return (val or 0) <= float(target)
        if op == "contains": return str(target).lower() in str(val or "").lower()
        if op == "in":
            items = target if isinstance(target, list) else [target]
            return val in items
    except Exception:
        return False
    return False


async def _execute_action(action: dict, record: dict, workflow: dict, workspace_id: str):
    a_type = action["type"]
    params = action.get("params", {})
    try:
        if a_type == "create_task":
            task = {
                "id": new_id(),
                "workspace_id": workspace_id,
                "created_by": workflow.get("id", "workflow"),
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "title": (params.get("title") or f"Follow up on {record.get('name') or record.get('title', 'record')}"),
                "description": params.get("description", f"Auto-created by workflow: {workflow['name']}"),
                "priority": params.get("priority", "medium"),
                "status": "todo",
                "assignee_id": params.get("assignee_id"),
                "due_date": params.get("due_date"),
                "related_type": workflow.get("_entity_type"),
                "related_id": record.get("id"),
            }
            await db.tasks.insert_one(task)
            if task["assignee_id"]:
                await create_notification(
                    workspace_id=workspace_id, user_id=task["assignee_id"],
                    title="Task auto-assigned by workflow",
                    body=task["title"], kind="workflow_task",
                    entity_type="task", entity_id=task["id"],
                )
        elif a_type == "assign_user":
            uid = params.get("user_id")
            entity_type = workflow.get("_entity_type")
            if uid and entity_type and record.get("id"):
                coll = {"lead": db.leads, "customer": db.customers, "deal": db.deals}.get(entity_type)
                if coll is not None:
                    await coll.update_one(
                        {"id": record["id"], "workspace_id": workspace_id},
                        {"$set": {"assignee_id": uid, "updated_at": now_iso()}}
                    )
                    await create_notification(
                        workspace_id=workspace_id, user_id=uid,
                        title=f"{entity_type.title()} auto-assigned by workflow",
                        body=(record.get("name") or record.get("title") or ""),
                        kind="workflow_assign", entity_type=entity_type, entity_id=record["id"],
                    )
        elif a_type == "notify_user":
            uid = params.get("user_id")
            if uid:
                await create_notification(
                    workspace_id=workspace_id, user_id=uid,
                    title=params.get("title", f"Workflow: {workflow['name']}"),
                    body=params.get("body", f"Triggered on {record.get('name') or record.get('title', 'a record')}"),
                    kind="workflow_notify",
                )
        elif a_type == "add_tag":
            tag = params.get("tag")
            entity_type = workflow.get("_entity_type")
            if tag and entity_type and record.get("id"):
                coll = {"lead": db.leads, "customer": db.customers, "deal": db.deals}.get(entity_type)
                if coll is not None:
                    await coll.update_one(
                        {"id": record["id"], "workspace_id": workspace_id},
                        {"$addToSet": {"tags": tag}, "$set": {"updated_at": now_iso()}}
                    )
    except Exception:
        logging.exception(f"Workflow action failed: {a_type}")


TRIGGER_ENTITY = {
    "lead_created": "lead",
    "lead_scored": "lead",
    "customer_created": "customer",
    "deal_created": "deal",
    "deal_stage_changed": "deal",
}


async def fire_workflows(trigger: str, workspace_id: str, record: dict):
    """Fire all enabled workflows matching this trigger for the given workspace."""
    try:
        workflows = await db.workflows.find(
            {"workspace_id": workspace_id, "trigger": trigger, "enabled": True}, {"_id": 0}
        ).to_list(50)
        for wf in workflows:
            wf["_entity_type"] = TRIGGER_ENTITY.get(trigger)
            conds = wf.get("conditions", []) or []
            if conds and not all(_eval_condition(record, c) for c in conds):
                continue
            for action in wf.get("actions", []) or []:
                await _execute_action(action, record, wf, workspace_id)
            await db.workflows.update_one(
                {"id": wf["id"]},
                {"$set": {"last_run_at": now_iso()}, "$inc": {"run_count": 1}},
            )
    except Exception:
        logging.exception(f"fire_workflows failed for {trigger}")


@api.get("/workflows")
async def list_workflows(ctx: dict = Depends(require_perm("settings", "manage"))):
    return await db.workflows.find(workspace_query(ctx), {"_id": 0}).sort("created_at", -1).to_list(100)


@api.post("/workflows")
async def create_workflow(body: WorkflowIn, ctx: dict = Depends(require_perm("settings", "manage"))):
    if body.trigger not in WORKFLOW_TRIGGERS:
        raise HTTPException(400, "Invalid trigger")
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "run_count": 0,
        "last_run_at": None,
        **body.model_dump(),
    }
    await db.workflows.insert_one(doc)
    await audit(ctx, "created", "workflow", doc["id"], after={"name": body.name, "trigger": body.trigger})
    doc.pop("_id", None)
    return doc


@api.put("/workflows/{wid}")
async def update_workflow(wid: str, body: WorkflowIn, ctx: dict = Depends(require_perm("settings", "manage"))):
    r = await db.workflows.update_one(
        workspace_query(ctx, {"id": wid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await audit(ctx, "updated", "workflow", wid, after={"name": body.name})
    return {"ok": True}


@api.delete("/workflows/{wid}")
async def delete_workflow(wid: str, ctx: dict = Depends(require_perm("settings", "manage"))):
    r = await db.workflows.delete_one(workspace_query(ctx, {"id": wid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await audit(ctx, "deleted", "workflow", wid)
    return {"ok": True}


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

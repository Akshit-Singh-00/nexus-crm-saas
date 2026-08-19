"""NexusCRM - Multi-tenant SaaS CRM Backend."""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Literal

import jwt
import bcrypt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Header
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
        "plan": "free",
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
    invited = await db.users.find_one({"email": body.email.lower()})
    if not invited:
        # Create a stub user with temp password (they'll reset via signup with same email)
        uid = new_id()
        temp_pw = new_id()[:12]
        await db.users.insert_one({
            "id": uid,
            "email": body.email.lower(),
            "name": body.email.split("@")[0],
            "password": hash_pw(temp_pw),
            "avatar_url": None,
            "created_at": now_iso(),
            "invited": True,
        })
        invited = {"id": uid, "email": body.email.lower()}
    exists = await get_membership(invited["id"], ctx["workspace_id"])
    if exists:
        raise HTTPException(400, "Already a member")
    await db.memberships.insert_one({
        "id": new_id(),
        "user_id": invited["id"],
        "workspace_id": ctx["workspace_id"],
        "role": body.role,
        "created_at": now_iso(),
    })
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "invited", "user", invited["id"], {"email": body.email})
    return {"ok": True, "user_id": invited["id"]}

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

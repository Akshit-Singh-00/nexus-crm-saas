"""FastAPI application factory — wires middleware, routers and lifecycle hooks."""
import logging

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

from app.core.config import APP_URL, CORS_ORIGINS_RAW
from app.core.database import client as mongo_client, ensure_indexes
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.routers import (
    activities,
    ai,
    analytics,
    audit,
    auth,
    billing,
    customer360,
    customers,
    deals,
    health,
    imports,
    integrations,
    interactions,
    leads,
    notes,
    notifications,
    search,
    tasks,
    tickets,
    workflows,
    workspaces,
)

app = FastAPI(title="NexusCRM API")
app.state.limiter = limiter


# ----------- Exception handlers -----------
@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down and try again shortly."},
    )


@app.exception_handler(Exception)
async def _generic_error_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logging.exception("Unhandled server error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ----------- Mount routers under /api -----------
api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(auth.router)
api.include_router(workspaces.router)
api.include_router(customers.router)
api.include_router(leads.router)
api.include_router(deals.router)
api.include_router(tasks.router)
api.include_router(notes.router)
api.include_router(activities.router)
api.include_router(analytics.router)
api.include_router(search.router)
api.include_router(notifications.router)
api.include_router(tickets.router)
api.include_router(audit.router)
api.include_router(workflows.router)
api.include_router(ai.router)
api.include_router(billing.router)
api.include_router(imports.router)
api.include_router(interactions.router)
api.include_router(integrations.router)
api.include_router(customer360.router)
app.include_router(api)


# ----------- CORS (restrictive, from env) -----------
_origins = [o.strip() for o in CORS_ORIGINS_RAW.split(',') if o.strip() and o.strip() != '*']
if not _origins:
    _origins = [u for u in [APP_URL, "http://localhost:3000"] if u]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Workspace-Id"],
)


# ----------- Lifecycle -----------
logger = setup_logging()


@app.on_event("startup")
async def _startup():
    await ensure_indexes()


@app.on_event("shutdown")
async def _shutdown():
    mongo_client.close()

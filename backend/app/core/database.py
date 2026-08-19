"""MongoDB connection + index bootstrap."""
import logging

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import MONGO_URL, DB_NAME

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


async def ensure_indexes() -> None:
    """Create indexes for common workspace-scoped queries. Safe to run repeatedly."""
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
        await db.memberships.create_index([("workspace_id", 1), ("user_id", 1)], unique=True)
        await db.memberships.create_index("user_id")
        await db.workspaces.create_index("id", unique=True)
        await db.customers.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.customers.create_index([("workspace_id", 1), ("id", 1)])
        await db.customers.create_index([("workspace_id", 1), ("email", 1)])
        await db.leads.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.leads.create_index([("workspace_id", 1), ("id", 1)])
        await db.leads.create_index([("workspace_id", 1), ("status", 1)])
        await db.deals.create_index([("workspace_id", 1), ("stage", 1)])
        await db.deals.create_index([("workspace_id", 1), ("id", 1)])
        await db.deals.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.tasks.create_index([("workspace_id", 1), ("status", 1)])
        await db.tasks.create_index([("workspace_id", 1), ("assignee_id", 1)])
        await db.tickets.create_index([("workspace_id", 1), ("status", 1)])
        await db.tickets.create_index([("workspace_id", 1), ("id", 1)])
        await db.notes.create_index([("workspace_id", 1), ("related_type", 1), ("related_id", 1)])
        await db.activities.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.notifications.create_index([("workspace_id", 1), ("user_id", 1), ("read", 1)])
        await db.audit_logs.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.workflows.create_index([("workspace_id", 1), ("trigger", 1), ("enabled", 1)])
        await db.payment_transactions.create_index([("workspace_id", 1), ("session_id", 1)])
        await db.payment_transactions.create_index("session_id", unique=True)
        await db.invites.create_index([("workspace_id", 1), ("email", 1)])
        await db.interactions.create_index([("workspace_id", 1), ("kind", 1), ("customer_id", 1)])
        await db.interactions.create_index([("workspace_id", 1), ("kind", 1), ("deal_id", 1)])
        await db.interactions.create_index([("workspace_id", 1), ("kind", 1), ("scheduled_at", 1)])
        await db.integrations.create_index([("workspace_id", 1), ("user_id", 1), ("provider", 1)], unique=True)
    except Exception:
        logging.exception("Index creation failed (continuing).")

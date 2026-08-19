"""Workflow trigger + condition + action engine."""
import logging
from typing import List

from fastapi import HTTPException

from app.core.database import db
from app.schemas.workflows import TRIGGER_ENTITY, WorkflowActionIn
from app.services.notification_service import create_notification
from app.utils.ids import new_id, now_iso


async def validate_workflow_action_targets(actions: List[WorkflowActionIn], workspace_id: str) -> None:
    """Ensure any user_id / assignee_id referenced by a workflow action belongs to this workspace."""
    for a in actions:
        params = a.params or {}
        uid = params.get("user_id") or params.get("assignee_id")
        if uid:
            m = await db.memberships.find_one(
                {"user_id": uid, "workspace_id": workspace_id}, {"_id": 1}
            )
            if not m:
                raise HTTPException(400, "Workflow action references a user outside this workspace")


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


async def _execute_action(action: dict, record: dict, workflow: dict, workspace_id: str) -> None:
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


async def fire_workflows(trigger: str, workspace_id: str, record: dict) -> None:
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

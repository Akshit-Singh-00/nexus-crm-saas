from typing import List, Optional, Literal
from pydantic import BaseModel, Field

WORKFLOW_TRIGGERS = ("lead_created", "lead_scored", "customer_created", "deal_stage_changed", "deal_created")
WORKFLOW_ACTIONS = ("create_task", "assign_user", "notify_user", "add_tag")
TRIGGER_ENTITY = {
    "lead_created": "lead",
    "lead_scored": "lead",
    "customer_created": "customer",
    "deal_created": "deal",
    "deal_stage_changed": "deal",
}


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

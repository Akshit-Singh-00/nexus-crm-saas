from typing import Optional, Literal
from pydantic import BaseModel


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

from typing import List, Optional, Literal
from pydantic import BaseModel


class TicketIn(BaseModel):
    subject: str
    description: Optional[str] = ""
    customer_id: Optional[str] = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["open", "in_progress", "waiting", "resolved", "closed"] = "open"
    assignee_id: Optional[str] = None
    tags: List[str] = []

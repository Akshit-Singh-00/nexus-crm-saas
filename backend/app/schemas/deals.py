from typing import List, Optional, Literal
from pydantic import BaseModel, Field


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

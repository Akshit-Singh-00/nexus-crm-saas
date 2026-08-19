from typing import Optional
from pydantic import BaseModel


class CopilotIn(BaseModel):
    message: str
    context_type: Optional[str] = None  # customer/lead/deal
    context_id: Optional[str] = None

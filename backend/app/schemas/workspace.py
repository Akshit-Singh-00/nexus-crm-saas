from typing import List, Optional
from pydantic import BaseModel


class WorkspaceIn(BaseModel):
    name: str
    industry: Optional[str] = None


class WorkspaceSettingsIn(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    industry: Optional[str] = None
    pipeline_stages: Optional[List[dict]] = None  # [{id, label, color, probability}]

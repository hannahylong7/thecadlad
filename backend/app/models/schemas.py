from datetime import datetime
from typing import Optional
from pydantic import BaseModel


#Request schemas

class MessageRequest(BaseModel):
    content: str


class ApproveRequest(BaseModel):
    approved: bool
    feedback: Optional[str] = None


#Response schemas

class SessionCreateResponse(BaseModel):
    id: str
    status: str
    created_at: datetime


class SessionSummaryResponse(BaseModel):
    id: str
    title: str
    status: str
    iteration: int
    has_render: bool
    has_model: bool
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    role: str
    content: str
    code: Optional[str] = None
    plan: Optional[str] = None
    timestamp: datetime


class ModelResponse(BaseModel):
    id: int
    session_id: str
    stl_path: str
    png_path: Optional[str] = None
    iteration: int
    approved: bool
    created_at: datetime


class SessionDetailResponse(BaseModel):
    id: str
    title: str
    status: str
    messages: list[MessageResponse]
    iteration: int
    has_render: bool
    has_model: bool
    version_count: int
    created_at: datetime
    updated_at: datetime


class AgentResponse(BaseModel):
    type: str
    content: Optional[str] = None
    plan: Optional[str] = None
    assumptions: Optional[list[str]] = None
    code: Optional[str] = None
    description: Optional[str] = None
    error_analysis: Optional[str] = None
    session_status: str
    png_path: Optional[str] = None
    stl_path: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    session_id: str
    status: str
    iteration: int
    duration_ms: Optional[int] = None
    stl_path: Optional[str] = None
    png_path: Optional[str] = None
    created_at: datetime
"""Data models for the application."""
from pydantic import BaseModel
from typing import Optional, Dict, Any


class TaskRequest(BaseModel):
    """HTTP request model for creating a task."""
    user_id: str
    content: str


class TaskMessage(BaseModel):
    """Message model for RocketMQ."""
    task_id: str
    user_id: str
    payload: str
    action: str = "generate_profile"


class TaskResult(BaseModel):
    """Task result model."""
    tags: list[str]
    score: int
    reason: str

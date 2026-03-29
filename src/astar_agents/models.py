"""Domain models for agents, messages, and tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Permission / authority tiers
# ---------------------------------------------------------------------------

class AuthorityLevel(IntEnum):
    """Higher number = higher authority."""
    CENTRE = 1       # National-centre directors
    INSTITUTE = 2    # Research-institute directors
    DIVISION = 3     # ACE / DCE level
    EXECUTIVE = 4    # CEO
    BOARD = 5        # Chairman & Board


class Division(StrEnum):
    BOARD = "board"
    CEO_OFFICE = "ceo-office"
    BMRC = "bmrc"
    SERC = "serc"
    IE = "innovation-enterprise"
    CORPORATE = "corporate"
    GRADUATE_ACADEMY = "graduate-academy"
    NATIONAL_CENTRES = "national-centres"
    NATIONAL_PROGRAMMES = "national-programmes"
    EXTERNAL = "external"


# ---------------------------------------------------------------------------
# Agent profile (static definition loaded at startup)
# ---------------------------------------------------------------------------

class AgentProfile(BaseModel):
    agent_id: str
    name: str
    title: str
    division: Division
    authority: AuthorityLevel
    reports_to: str | None = None  # agent_id of superior
    subordinates: list[str] = Field(default_factory=list)
    expertise: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    discord_channel: str = ""       # primary channel this agent posts in
    private_channel: str = ""       # private channel for user interaction


# ---------------------------------------------------------------------------
# Envelope — the inter-agent message wrapper
# ---------------------------------------------------------------------------

class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Envelope(BaseModel):
    envelope_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    from_agent: str
    to_agent: str
    subject: str = ""
    body: str = ""
    priority: Priority = Priority.NORMAL
    reply_to: str | None = None     # envelope_id this is a reply to
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Task — a formal unit of work flowing through the org
# ---------------------------------------------------------------------------

class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    REJECTED = "rejected"


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    title: str
    description: str
    created_by: str           # agent_id
    assigned_to: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.NORMAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: str = ""
    history: list[str] = Field(default_factory=list)  # audit trail

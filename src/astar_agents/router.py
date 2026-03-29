"""Message router — the 'envelope system' for inter-agent communication.

Every agent has a mailbox (async queue). The router delivers Envelope objects
between agents and optionally broadcasts to Discord channels for observability.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable

from .models import Envelope, Task, TaskStatus

log = logging.getLogger(__name__)


class Router:
    def __init__(self) -> None:
        self._mailboxes: dict[str, asyncio.Queue[Envelope]] = defaultdict(asyncio.Queue)
        self._tasks: dict[str, Task] = {}
        self._on_deliver: Callable[[Envelope], Awaitable[None]] | None = None

    # ------------------------------------------------------------------
    # Hooks — the Discord bot registers a callback so every envelope is
    # also posted to the appropriate channel for the user to observe.
    # ------------------------------------------------------------------

    def set_delivery_hook(self, hook: Callable[[Envelope], Awaitable[None]]) -> None:
        self._on_deliver = hook

    # ------------------------------------------------------------------
    # Envelope operations
    # ------------------------------------------------------------------

    async def send(self, envelope: Envelope) -> None:
        log.info(
            "MAIL  %s -> %s  [%s] %s",
            envelope.from_agent, envelope.to_agent, envelope.priority, envelope.subject,
        )
        self._mailboxes[envelope.to_agent].put_nowait(envelope)
        if self._on_deliver:
            try:
                await self._on_deliver(envelope)
            except Exception:
                log.exception("delivery hook error")

    async def receive(self, agent_id: str, timeout: float = 0.5) -> Envelope | None:
        try:
            return await asyncio.wait_for(self._mailboxes[agent_id].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def pending_count(self, agent_id: str) -> int:
        return self._mailboxes[agent_id].qsize()

    async def broadcast(self, from_agent: str, to_agents: list[str], subject: str, body: str) -> None:
        for agent_id in to_agents:
            env = Envelope(from_agent=from_agent, to_agent=agent_id, subject=subject, body=body)
            await self.send(env)

    # ------------------------------------------------------------------
    # Task registry
    # ------------------------------------------------------------------

    def register_task(self, task: Task) -> None:
        self._tasks[task.task_id] = task
        log.info("TASK registered: %s — %s", task.task_id, task.title)

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def update_task(self, task_id: str, **fields: object) -> Task | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        for k, v in fields.items():
            setattr(task, k, v)
        return task

    def list_tasks(self, *, assigned_to: str | None = None, status: TaskStatus | None = None) -> list[Task]:
        out: list[Task] = []
        for t in self._tasks.values():
            if assigned_to and t.assigned_to != assigned_to:
                continue
            if status and t.status != status:
                continue
            out.append(t)
        return out

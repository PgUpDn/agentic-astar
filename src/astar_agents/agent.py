"""Core Agent class — wraps an AgentProfile with LLM reasoning and mailbox processing."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from .config import settings
from .llm import chat
from .models import AgentProfile, Envelope, Priority, Task, TaskStatus
from .router import Router

log = logging.getLogger(__name__)


class Agent:
    """A live agent that can think, send/receive envelopes, and act."""

    def __init__(self, profile: AgentProfile, router: Router) -> None:
        self.profile = profile
        self.router = router
        self._memory: deque[dict[str, str]] = deque(maxlen=settings.max_memory)
        self._last_call: float = 0.0
        self._running = False

    @property
    def id(self) -> str:
        return self.profile.agent_id

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def _add_memory(self, role: str, content: str) -> None:
        self._memory.append({"role": role, "content": content})

    def _messages(self) -> list[dict[str, str]]:
        return list(self._memory)

    # ------------------------------------------------------------------
    # Thinking (LLM call)
    # ------------------------------------------------------------------

    async def think(self, prompt: str) -> str:
        """Send a prompt through the LLM with this agent's system persona."""
        now = time.monotonic()
        wait = settings.agent_cooldown - (now - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)

        self._add_memory("user", prompt)
        reply = await chat(self.profile.system_prompt, self._messages())
        self._add_memory("assistant", reply)
        self._last_call = time.monotonic()
        return reply

    # ------------------------------------------------------------------
    # Envelope handling
    # ------------------------------------------------------------------

    async def handle_envelope(self, env: Envelope) -> str | None:
        """Process an incoming envelope and optionally return a reply body."""
        prompt = (
            f"You received an internal message.\n"
            f"FROM: {env.from_agent}\n"
            f"SUBJECT: {env.subject}\n"
            f"PRIORITY: {env.priority}\n"
            f"---\n{env.body}\n---\n\n"
            f"Decide how to respond. If you need to delegate, state clearly "
            f"which agent_id you want to forward to and what they should do. "
            f"Format any delegation as: DELEGATE [agent_id]: <instruction>\n"
            f"If you are replying to the sender, just write your reply.\n"
            f"If you need to take action yourself, describe what you'd do."
        )
        return await self.think(prompt)

    async def process_mailbox(self) -> list[tuple[Envelope, str]]:
        """Drain the mailbox and handle each envelope. Returns (env, reply) pairs."""
        results: list[tuple[Envelope, str]] = []
        while True:
            env = await self.router.receive(self.id, timeout=0.1)
            if env is None:
                break
            log.info("[%s] processing envelope from %s: %s", self.id, env.from_agent, env.subject)
            reply_body = await self.handle_envelope(env)
            if reply_body:
                results.append((env, reply_body))
        return results

    # ------------------------------------------------------------------
    # Delegation parser — extracts DELEGATE directives from LLM output
    # ------------------------------------------------------------------

    @staticmethod
    def parse_delegations(text: str) -> list[tuple[str, str]]:
        """Return list of (agent_id, instruction) from DELEGATE directives."""
        delegations: list[tuple[str, str]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("DELEGATE ["):
                rest = stripped[len("DELEGATE ["):]
                bracket_end = rest.find("]")
                if bracket_end == -1:
                    continue
                target = rest[:bracket_end].strip()
                instruction = rest[bracket_end + 1:].lstrip(":").strip()
                delegations.append((target, instruction))
        return delegations

    # ------------------------------------------------------------------
    # Convenience: create & send envelope
    # ------------------------------------------------------------------

    async def send_mail(
        self,
        to: str,
        subject: str,
        body: str,
        priority: Priority = Priority.NORMAL,
        reply_to: str | None = None,
    ) -> Envelope:
        env = Envelope(
            from_agent=self.id,
            to_agent=to,
            subject=subject,
            body=body,
            priority=priority,
            reply_to=reply_to,
        )
        await self.router.send(env)
        return env

    async def create_task(self, title: str, description: str, priority: Priority = Priority.NORMAL) -> Task:
        task = Task(
            title=title,
            description=description,
            created_by=self.id,
            priority=priority,
        )
        self.router.register_task(task)
        return task

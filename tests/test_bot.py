from __future__ import annotations

import unittest

from astar_agents.agent import Agent
from astar_agents.bot import TaskCog, create_bot
from astar_agents.models import Envelope, Task, TaskStatus
from astar_agents.registry import AGENT_PROFILES


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_hook_registers_commands(self) -> None:
        bot = create_bot()
        await bot.setup_hook()

        self.assertTrue(
            {"agents", "org", "tasks", "mail", "roundtable", "autopilot", "status"}.issubset(
                {command.name for command in bot.commands}
            )
        )

        await bot.close()

    async def test_dispatch_delegations_forwards_mail_and_updates_task(self) -> None:
        bot = create_bot()
        sender = Agent(AGENT_PROFILES["ceo"], bot.router)
        receiver = Agent(AGENT_PROFILES["ace_bmrc"], bot.router)
        bot.agents = {
            sender.id: sender,
            receiver.id: receiver,
        }

        task = Task(
            task_id="task123",
            title="Diagnostic tool",
            description="Design a diagnostic tool.",
            created_by="user_liaison",
        )
        bot.router.register_task(task)

        original = Envelope(
            from_agent="user_liaison",
            to_agent=sender.id,
            subject="New Task: Diagnostic tool",
            body="Task ID: task123\n---\nDesign a diagnostic tool.\n---",
        )

        await bot._dispatch_delegations(
            sender,
            original,
            "DELEGATE [ace_bmrc]: Evaluate biomedical feasibility and propose next steps.",
        )

        delegated = await bot.router.receive(receiver.id, timeout=0.1)
        self.assertIsNotNone(delegated)
        assert delegated is not None
        self.assertEqual(delegated.from_agent, sender.id)
        self.assertEqual(delegated.to_agent, receiver.id)
        self.assertEqual(delegated.reply_to, original.envelope_id)
        self.assertIn("Task ID: task123", delegated.body)
        self.assertIn("biomedical feasibility", delegated.body)

        updated_task = bot.router.get_task("task123")
        self.assertIsNotNone(updated_task)
        assert updated_task is not None
        self.assertEqual(updated_task.assigned_to, receiver.id)
        self.assertEqual(updated_task.status, TaskStatus.ASSIGNED)
        self.assertTrue(updated_task.history)

        await bot.close()

    async def test_roundtable_uses_agents_assigned_to_current_channel(self) -> None:
        bot = create_bot()
        bot._spawn_agents()
        cog = TaskCog(bot)

        self.assertEqual(
            cog._agent_ids_for_channel("serc-council"),
            [
                "ace_serc",
                "dir_artc",
                "dir_ime",
                "dir_ihpc",
                "dir_imre",
                "dir_isce2",
                "dir_i2r",
                "dir_nmc",
            ],
        )

        await bot.close()

"""Discord bot — the observable runtime for the A*STAR multi-agent simulation.

Channel layout (auto-created on first run):
    Category: A*STAR HQ
        #board-room          — Chairman + CEO
        #executive-council   — CEO + all DCEs/ACEs
        #bmrc-council        — BMRC division
        #serc-council        — SERC division
        #ie-office           — Innovation & Enterprise
        #corporate-office    — Corporate group
        #research-collab     — Cross-institute collaboration
        #national-centres    — National centres
        #task-inbox          — User delivers tasks here
        #announcements       — Org-wide broadcasts

    Category: Private Channels
        One private text channel per agent for direct user interaction.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from .agent import Agent
from .config import settings
from .models import Envelope, Priority, TaskStatus
from .registry import AGENT_PROFILES
from .router import Router

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# Public channel names (order matters for creation)
PUBLIC_CHANNELS = [
    "board-room",
    "executive-council",
    "bmrc-council",
    "serc-council",
    "ie-office",
    "corporate-office",
    "research-collab",
    "national-centres",
    "task-inbox",
    "announcements",
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class AStarBot(commands.Bot):
    """The Discord bot that hosts the A*STAR agent simulation."""

    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.router = Router()
        self.agents: dict[str, Agent] = {}
        self._channels: dict[str, discord.TextChannel] = {}
        self._guild: discord.Guild | None = None
        self._ready_event = asyncio.Event()
        self.autopilot_enabled = False
        self._handled_msgs: set[int] = set()  # dedup message IDs

        self.router.set_delivery_hook(self._on_envelope_deliver)

    # ==================================================================
    # Bootstrap
    # ==================================================================

    async def setup_hook(self) -> None:
        await self.add_cog(TaskCog(self))

    async def on_ready(self) -> None:
        log.info("Bot logged in as %s (id=%s)", self.user, self.user.id)

        guild = self.get_guild(settings.discord_guild_id)
        if guild is None:
            guild = self.guilds[0] if self.guilds else None
        if guild is None:
            log.error("No guild found — set DISCORD_GUILD_ID in .env")
            return
        self._guild = guild
        log.info("Operating in guild: %s", guild.name)

        await self._ensure_channels(guild)

        # Only spawn agents once (on_ready can fire multiple times on reconnect)
        if not self.agents:
            self._spawn_agents()

        if not self.tick_loop.is_running():
            self.tick_loop.start()

        self._ready_event.set()
        log.info("A*STAR simulation is LIVE with %d agents", len(self.agents))

    # ------------------------------------------------------------------
    # Channel provisioning
    # ------------------------------------------------------------------

    async def _ensure_channels(self, guild: discord.Guild) -> None:
        existing = {ch.name: ch for ch in guild.text_channels}

        # Public category
        hq_cat = discord.utils.get(guild.categories, name="A*STAR HQ")
        if hq_cat is None:
            hq_cat = await guild.create_category("A*STAR HQ")

        for name in PUBLIC_CHANNELS:
            if name in existing:
                self._channels[name] = existing[name]
            else:
                ch = await guild.create_text_channel(name, category=hq_cat)
                self._channels[name] = ch
                log.info("Created channel #%s", name)

        # Private category
        priv_cat = discord.utils.get(guild.categories, name="Private Channels")
        if priv_cat is None:
            priv_cat = await guild.create_category("Private Channels")

        for profile in AGENT_PROFILES.values():
            pname = profile.private_channel
            if not pname:
                continue
            if pname in existing:
                self._channels[pname] = existing[pname]
            else:
                ch = await guild.create_text_channel(pname, category=priv_cat)
                self._channels[pname] = ch
                log.info("Created private channel #%s", pname)

    # ------------------------------------------------------------------
    # Agent spawning
    # ------------------------------------------------------------------

    def _spawn_agents(self) -> None:
        for profile in AGENT_PROFILES.values():
            agent = Agent(profile, self.router)
            self.agents[profile.agent_id] = agent

    # ==================================================================
    # Envelope → Discord (observability hook)
    # ==================================================================

    async def _on_envelope_deliver(self, env: Envelope) -> None:
        """Post every envelope into the sender's primary channel so users can watch."""
        sender = AGENT_PROFILES.get(env.from_agent)
        receiver = AGENT_PROFILES.get(env.to_agent)
        if not sender:
            return

        chan = self._channels.get(sender.discord_channel)
        if chan is None:
            return

        priority_emoji = {"low": "🟢", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(
            env.priority, "⚪"
        )

        embed = discord.Embed(
            title=f"{priority_emoji} {env.subject}",
            description=env.body[:4000],
            color=discord.Color.blurple(),
        )
        embed.set_author(name=f"{sender.name} ({sender.title})")
        to_label = f"{receiver.name}" if receiver else env.to_agent
        embed.add_field(name="To", value=to_label, inline=True)
        embed.add_field(name="Priority", value=env.priority.value, inline=True)
        embed.set_footer(text=f"envelope:{env.envelope_id}")

        await chan.send(embed=embed)

    # ==================================================================
    # Periodic tick — agents process mailbox & act
    # ==================================================================

    @tasks.loop(seconds=30)
    async def tick_loop(self) -> None:
        """Process pending envelopes, post replies, and forward delegations."""
        await self._ready_event.wait()
        self.tick_loop.change_interval(seconds=settings.tick_interval)

        for agent in self.agents.values():
            if self.router.pending_count(agent.id) == 0:
                continue
            try:
                results = await agent.process_mailbox()
                for env, reply in results:
                    await self._post_reply(agent, env, reply)
                    await self._dispatch_delegations(agent, env, reply)
            except Exception:
                log.exception("tick error for agent %s", agent.id)

    async def _post_reply(self, agent: Agent, original: Envelope, reply: str) -> None:
        """Post the agent's reply into its primary channel. No envelopes created."""
        chan = self._channels.get(agent.profile.discord_channel)
        if chan is None:
            return

        embed = discord.Embed(
            description=reply[:4000],
            color=discord.Color.green(),
        )
        embed.set_author(name=f"{agent.profile.name} replies")
        embed.set_footer(text=f"re: {original.subject}")
        await chan.send(embed=embed)

    async def _dispatch_delegations(self, agent: Agent, original: Envelope, reply: str) -> None:
        delegations = agent.parse_delegations(reply)
        if not delegations:
            return

        valid_targets = [target for target, _ in delegations if target in self.agents]
        task_id = self._extract_task_id(original.body)
        if task_id:
            task = self.router.get_task(task_id)
            if task is not None:
                history = list(task.history)
                history.append(
                    f"{agent.id} delegated to {', '.join(valid_targets) if valid_targets else 'unknown recipients'}"
                )
                fields: dict[str, object] = {
                    "updated_at": datetime.now(timezone.utc),
                    "history": history,
                }
                if valid_targets:
                    fields["status"] = TaskStatus.ASSIGNED
                if len(valid_targets) == 1:
                    fields["assigned_to"] = valid_targets[0]
                self.router.update_task(task_id, **fields)

        for target, instruction in delegations:
            if target not in self.agents:
                log.warning("[%s] delegation target does not exist: %s", agent.id, target)
                continue

            task_line = f"Task ID: {task_id}\n" if task_id else ""
            delegated_body = (
                f"Delegated by: {agent.profile.name} ({agent.id})\n"
                f"Original sender: {original.from_agent}\n"
                f"Original subject: {original.subject}\n"
                f"{task_line}"
                f"---\n{instruction}\n---"
            )
            await agent.send_mail(
                to=target,
                subject=f"Delegated: {original.subject}" if original.subject else "Delegated request",
                body=delegated_body,
                priority=original.priority,
                reply_to=original.envelope_id,
            )

    @staticmethod
    def _extract_task_id(body: str) -> str | None:
        match = re.search(r"Task ID:\s*([A-Za-z0-9_-]+)", body)
        if match:
            return match.group(1)
        return None

    # ==================================================================
    # Autopilot — continuous autonomous discussions
    # ==================================================================

    DISCUSSION_CHANNELS = [
        ("executive-council", ["ceo", "dce_research", "dce_ie", "dce_corporate", "ace_bmrc", "ace_serc"]),
        ("bmrc-council", ["ace_bmrc", "dir_bii", "dir_bti", "dir_gis", "dir_idl", "dir_ihdp", "dir_imcb", "dir_sign", "dir_sifbi", "dir_srl"]),
        ("serc-council", ["ace_serc", "dir_artc", "dir_ime", "dir_ihpc", "dir_imre", "dir_isce2", "dir_i2r", "dir_nmc"]),
        ("national-centres", ["dir_ai_coe", "dir_nscc", "dir_eddc", "dir_catos"]),
        ("research-collab", ["dce_research", "dir_i2r", "dir_ihpc", "dir_bii", "dir_ai_coe", "dir_nscc"]),
        ("ie-office", ["dce_ie", "ace_ie"]),
        ("board-room", ["chairman", "ceo"]),
    ]

    SEED_TOPICS = [
        "How should A*STAR position itself in the global AI race? What are our comparative advantages?",
        "Singapore's semiconductor strategy — what role should A*STAR play in building fab capabilities?",
        "Cross-institute collaboration: what joint projects between BMRC and SERC could yield breakthrough results?",
        "Pandemic preparedness 2.0 — lessons learned and how to strengthen our response capabilities.",
        "Sustainability and green tech — how do we accelerate our low-carbon research agenda?",
        "Talent pipeline: are we attracting and retaining enough top-tier researchers?",
        "Industry translation gap — how do we move more research from lab to market?",
        "Quantum computing roadmap — where should we invest for the next 5 years?",
        "Food security and the 30-by-30 goal — progress update and next steps.",
        "AI safety and online trust — how do we balance innovation with responsible AI?",
        "Digital twins for manufacturing — what's the adoption roadmap for Singapore's SMEs?",
        "Precision medicine for Asian populations — how do we leverage GIS and SIgN capabilities?",
        "HPC infrastructure scaling — do we need a new national supercomputer?",
        "Advanced packaging and chiplet architecture — IME's role in next-gen semiconductors.",
        "Bioprocessing innovation — can we become the global hub for cell therapy manufacturing?",
    ]

    @tasks.loop(seconds=60)
    async def autopilot_loop(self) -> None:
        await self._ready_event.wait()
        if not self.autopilot_enabled:
            return

        channel_name, member_ids = random.choice(self.DISCUSSION_CHANNELS)
        chan = self._channels.get(channel_name)
        if chan is None:
            return

        members = [self.agents[aid] for aid in member_ids if aid in self.agents]
        if len(members) < 2:
            return

        initiator = random.choice(members)
        respondents = [m for m in members if m.id != initiator.id]
        random.shuffle(respondents)
        respondents = respondents[:random.randint(1, max(1, min(4, len(respondents))))]

        topic = random.choice(self.SEED_TOPICS)

        log.info("AUTOPILOT: %s initiates in #%s — %s", initiator.id, channel_name, topic[:60])

        # Initiator raises the topic
        try:
            opening = await initiator.think(
                f"[COUNCIL DISCUSSION in #{channel_name}]\n"
                f"You are initiating a discussion with your colleagues.\n"
                f"Topic: {topic}\n\n"
                f"Present your opening thoughts (2-3 key points). "
                f"Address specific colleagues by name to invite their input."
            )
            await chan.send(
                embed=discord.Embed(
                    description=opening[:4000],
                    color=discord.Color.purple(),
                ).set_author(name=f"🎙️ {initiator.profile.name} ({initiator.profile.title})")
            )
        except Exception:
            log.exception("autopilot: initiator %s failed", initiator.id)
            return

        await asyncio.sleep(3)

        # Respondents reply in turn
        conversation_so_far = f"{initiator.profile.name}: {opening}\n\n"
        for resp in respondents:
            try:
                reply = await resp.think(
                    f"[COUNCIL DISCUSSION in #{channel_name}]\n"
                    f"Topic: {topic}\n\n"
                    f"Discussion so far:\n{conversation_so_far}\n"
                    f"Share your perspective. Respond to what's been said. "
                    f"Offer concrete proposals or raise concerns. Be concise."
                )
                await chan.send(
                    embed=discord.Embed(
                        description=reply[:4000],
                        color=discord.Color.purple(),
                    ).set_author(name=f"💬 {resp.profile.name} ({resp.profile.title})")
                )
                conversation_so_far += f"{resp.profile.name}: {reply}\n\n"
                await asyncio.sleep(2)
            except Exception:
                log.exception("autopilot: respondent %s failed", resp.id)

        # Initiator wraps up
        try:
            wrap_up = await initiator.think(
                f"[COUNCIL DISCUSSION in #{channel_name}]\n"
                f"Topic: {topic}\n\n"
                f"Full discussion:\n{conversation_so_far}\n"
                f"Summarise the key takeaways and propose next steps or action items."
            )
            await chan.send(
                embed=discord.Embed(
                    title="📋 Summary & Next Steps",
                    description=wrap_up[:4000],
                    color=discord.Color.dark_purple(),
                ).set_author(name=f"🎙️ {initiator.profile.name}")
            )
        except Exception:
            log.exception("autopilot: wrap-up failed for %s", initiator.id)

    # ==================================================================
    # Message handler — user talks in channels
    # ==================================================================

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # Dedup: skip if we already handled this message
        if message.id in self._handled_msgs:
            return
        self._handled_msgs.add(message.id)
        if len(self._handled_msgs) > 500:
            # Keep set from growing forever
            to_remove = list(self._handled_msgs)[:250]
            self._handled_msgs -= set(to_remove)

        # Process ! commands first; if it's a command, stop here
        ctx = await self.get_context(message)
        if ctx.valid:
            await self.invoke(ctx)
            return

        # If user posts in a private-* channel, route to that agent
        channel_name = message.channel.name
        for profile in AGENT_PROFILES.values():
            if profile.private_channel == channel_name:
                agent = self.agents.get(profile.agent_id)
                if agent:
                    reply = await agent.think(
                        f"[Direct message from user]\n{message.content}"
                    )
                    await message.channel.send(
                        embed=discord.Embed(
                            description=reply[:4000],
                            color=discord.Color.gold(),
                        ).set_author(name=profile.name)
                    )
                return

        # If user posts in #task-inbox, the liaison picks it up
        if channel_name == "task-inbox":
            liaison = self.agents.get("user_liaison")
            if liaison:
                reply = await liaison.think(
                    f"[New task from user]\n{message.content}\n\n"
                    f"Analyse this request and route it. Create a Task, then "
                    f"send an Envelope to the CEO or the most appropriate agent."
                )

                # Post liaison's analysis
                await message.channel.send(
                    embed=discord.Embed(
                        title="📋 Task received",
                        description=reply[:4000],
                        color=discord.Color.gold(),
                    ).set_author(name="Liaison Agent")
                )

                # Create the task object
                task = await liaison.create_task(
                    title=message.content[:100],
                    description=message.content,
                )

                # Send to CEO
                await liaison.send_mail(
                    to="ceo",
                    subject=f"New Task: {task.title}",
                    body=(
                        f"Task ID: {task.task_id}\n"
                        f"From: External user via Liaison\n"
                        f"---\n{message.content}\n---\n\n"
                        f"Liaison analysis:\n{reply}"
                    ),
                    priority=Priority.HIGH,
                )


# ======================================================================
# Cog with slash-like prefix commands for controlling the simulation
# ======================================================================

class TaskCog(commands.Cog):
    def __init__(self, bot: AStarBot) -> None:
        self.bot = bot

    @commands.command(name="agents")
    async def list_agents(self, ctx: commands.Context) -> None:
        """List all active agents."""
        lines = []
        for aid, agent in sorted(self.bot.agents.items()):
            p = agent.profile
            pending = self.bot.router.pending_count(aid)
            lines.append(f"**{p.name}** (`{aid}`) — {p.title}  [📬 {pending}]")
        embed = discord.Embed(
            title="A*STAR Agents",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="org")
    async def org_chart(self, ctx: commands.Context) -> None:
        """Show the org chart hierarchy."""
        lines = []
        # Board level
        lines.append("```")
        lines.append("A*STAR Organisation")
        lines.append("═══════════════════")
        for p in AGENT_PROFILES.values():
            indent = {5: "", 4: "  ", 3: "    ", 2: "      ", 1: "        "}.get(
                p.authority.value, "          "
            )
            lines.append(f"{indent}├─ {p.name} ({p.agent_id})")
        lines.append("```")
        await ctx.send("\n".join(lines))

    @commands.command(name="tasks")
    async def list_tasks(self, ctx: commands.Context) -> None:
        """List all tracked tasks."""
        all_tasks = self.bot.router.list_tasks()
        if not all_tasks:
            await ctx.send("No tasks registered yet.")
            return
        lines = []
        for t in all_tasks:
            lines.append(
                f"**{t.title[:60]}** (`{t.task_id}`) — "
                f"status: {t.status} | assigned: {t.assigned_to or 'unassigned'}"
            )
        embed = discord.Embed(
            title="Task Board",
            description="\n".join(lines[:20]),
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="mail")
    async def send_mail(self, ctx: commands.Context, to_agent: str, *, content: str) -> None:
        """Send an envelope to any agent: !mail <agent_id> <message>"""
        if to_agent not in self.bot.agents:
            await ctx.send(f"Unknown agent: `{to_agent}`")
            return
        liaison = self.bot.agents.get("user_liaison")
        if liaison:
            await liaison.send_mail(
                to=to_agent,
                subject=f"Direct from user: {content[:50]}",
                body=content,
                priority=Priority.NORMAL,
            )
            await ctx.send(f"📨 Envelope sent to `{to_agent}`.")

    @commands.command(name="roundtable")
    async def roundtable(self, ctx: commands.Context, *, args: str) -> None:
        """Roundtable discussion in the current channel."""
        # Parse --invite flag
        invite_ids: list[str] = []
        topic = args
        if "--invite" in args:
            parts = args.split("--invite")
            topic = parts[0].strip()
            invite_ids = parts[1].strip().split()

        channel_name = ctx.channel.name
        channel_agent_ids = self._agent_ids_for_channel(channel_name)
        if invite_ids:
            requested_ids = list(dict.fromkeys(invite_ids))
            participants = [aid for aid in requested_ids if aid in channel_agent_ids]
            ignored_ids = [aid for aid in requested_ids if aid not in channel_agent_ids]
        else:
            participants = channel_agent_ids
            ignored_ids = []

        if not participants:
            await ctx.send(
                f"No roundtable agents are assigned to `#{channel_name}`."
            )
            return

        names = []
        for aid in participants:
            p = AGENT_PROFILES.get(aid)
            names.append(f"`{aid}` ({p.name})" if p else f"`{aid}`")

        description = (
            f"Channel: `#{channel_name}`\n"
            f"Inviting {len(participants)} participant(s):\n"
            + ", ".join(names)
        )
        if ignored_ids:
            description += (
                "\n\nIgnored because they do not belong to this channel: "
                + ", ".join(f"`{aid}`" for aid in ignored_ids)
            )

        await ctx.send(
            embed=discord.Embed(
                title=f"🏛️ Roundtable: {topic}",
                description=description,
                color=discord.Color.purple(),
            )
        )

        conversation = ""
        chan = ctx.channel
        for aid in participants:
            agent = self.bot.agents.get(aid)
            if not agent:
                continue
            prompt = (
                f"[ROUNDTABLE DISCUSSION]\n"
                f"Topic: {topic}\n\n"
            )
            if conversation:
                prompt += f"Discussion so far:\n{conversation}\n\n"
            prompt += (
                f"Share your perspective on this topic. "
                f"Respond to what others have said. "
                f"Be concise (2-3 key points)."
            )
            reply = await agent.think(prompt)
            await chan.send(
                embed=discord.Embed(
                    description=reply[:4000],
                    color=discord.Color.purple(),
                ).set_author(name=f"🎙️ {agent.profile.name} ({agent.profile.title})")
            )
            conversation += f"{agent.profile.name}: {reply}\n\n"

    def _agent_ids_for_channel(self, channel_name: str) -> list[str]:
        agent_ids = [
            profile.agent_id
            for profile in AGENT_PROFILES.values()
            if profile.discord_channel == channel_name and profile.agent_id in self.bot.agents
        ]
        if agent_ids:
            return agent_ids

        return [
            profile.agent_id
            for profile in AGENT_PROFILES.values()
            if profile.private_channel == channel_name and profile.agent_id in self.bot.agents
        ]

    @commands.command(name="autopilot")
    async def autopilot(self, ctx: commands.Context, action: str = "on") -> None:
        """Start or stop autopilot mode: !autopilot on/off"""
        if action.lower() in ("on", "start", "1"):
            self.bot.autopilot_enabled = True
            if not self.bot.autopilot_loop.is_running():
                self.bot.autopilot_loop.start()
            await ctx.send(
                embed=discord.Embed(
                    title="🤖 Autopilot ON",
                    description=(
                        "Agents will now autonomously discuss topics across all council channels.\n"
                        "A new discussion starts roughly every 60 seconds.\n"
                        "Use `!autopilot off` to stop."
                    ),
                    color=discord.Color.green(),
                )
            )
        elif action.lower() in ("off", "stop", "0"):
            self.bot.autopilot_enabled = False
            await ctx.send(
                embed=discord.Embed(
                    title="⏸️ Autopilot OFF",
                    description="Autonomous discussions paused. Use `!autopilot on` to resume.",
                    color=discord.Color.greyple(),
                )
            )
        else:
            await ctx.send("Usage: `!autopilot on` or `!autopilot off`")

    @commands.command(name="status")
    async def simulation_status(self, ctx: commands.Context) -> None:
        """Show simulation status."""
        total_pending = sum(
            self.bot.router.pending_count(aid) for aid in self.bot.agents
        )
        embed = discord.Embed(
            title="Simulation Status",
            color=discord.Color.teal(),
        )
        embed.add_field(name="Agents", value=str(len(self.bot.agents)), inline=True)
        embed.add_field(name="Pending Mail", value=str(total_pending), inline=True)
        embed.add_field(
            name="Tasks",
            value=str(len(self.bot.router.list_tasks())),
            inline=True,
        )
        embed.add_field(
            name="Tick Interval",
            value=f"{settings.tick_interval}s",
            inline=True,
        )
        await ctx.send(embed=embed)

    def _get_channel(
        self, ctx: commands.Context, name: str
    ) -> discord.TextChannel | None:
        return self.bot._channels.get(name)


def create_bot() -> AStarBot:
    return AStarBot()

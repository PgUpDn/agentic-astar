# Agentic A*STAR — Multi-Agent Discord Simulation

A Discord-based multi-agent simulation of [A\*STAR](https://www.a-star.edu.sg/) (Agency for Science, Technology and Research, Singapore). Every key role in the org chart is an AI agent that can receive tasks, deliberate, delegate, and report — all observable in real-time through Discord channels.

## Architecture

```
You (user)
  │
  └──▶ #task-inbox  ──▶  Liaison Agent  ──▶  CEO
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                    DCE Research          DCE I&E           DCE Corporate
                         │                    │                    │
              ┌──────────┼──────────┐         │         ┌─────────┼─────────┐
              ▼          ▼          ▼         ...       ▼         ▼         ▼
          ACE BMRC   ACE SERC  Inst. Dirs            ACE CorpDev  ACE Infra
              │          │
         9 Institutes  8 Institutes + National Centres
```

**31 agents** mapped from the real A\*STAR org chart, plus roles aligned to the public org chart, with a **Liaison Agent** you control.

### Key concepts

| Concept | Implementation |
|---|---|
| Permission levels | `AuthorityLevel` enum (Board → Centre, 5 tiers) |
| Private channels | Each agent has a `#private-*` channel for direct user chat |
| Public channels | Division channels (`#bmrc-council`, `#serc-council`, …) for observable inter-agent discussion |
| Envelope system | `Envelope` model routed through `Router` — every message is logged to Discord |
| Task delivery | User posts in `#task-inbox` → Liaison analyses → CEO delegates down the hierarchy |
| Roundtable | `!roundtable <topic>` triggers a council discussion among executives |

## Quick start

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- An OpenAI-compatible API key

### 2. Setup

```bash
# Clone / cd into the project
cd Agentic_ASTAR

# Install dependencies (uv already initialised)
uv sync

# Copy env template and fill in your tokens
cp .env.example .env
# Edit .env with your DISCORD_TOKEN, DISCORD_GUILD_ID, OPENAI_API_KEY
```

### 3. Create a Discord bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new Application → Bot tab → copy the token
3. Enable **Message Content Intent** and **Server Members Intent** under Privileged Gateway Intents
4. Generate an invite URL with bot permissions: `Manage Channels`, `Send Messages`, `Embed Links`, `Read Message History`
5. Invite the bot to your server
6. Right-click your server → Copy Server ID → set as `DISCORD_GUILD_ID`

### 4. Run

```bash
uv run astar-sim
```

On first run the bot will auto-create all channels under two categories: **A\*STAR HQ** (public) and **Private Channels**.

## Commands

| Command | Description |
|---|---|
| `!agents` | List all agents and their pending mail count |
| `!org` | Show the org-chart hierarchy |
| `!tasks` | List all tracked tasks |
| `!mail <agent_id> <message>` | Send a direct envelope to any agent |
| `!roundtable <topic>` | Start an executive roundtable discussion |
| `!status` | Show simulation status |
| `!autopilot on` / `!autopilot off` | Continuous autonomous council discussions |

## GitHub

Clone, configure secrets locally, and run:

```bash
git clone https://github.com/<your-username>/agentic-astar.git
cd agentic-astar
cp .env.example .env   # then edit with your tokens — never commit .env
uv sync
uv run astar-sim
```

If this repository is public, rotate any API keys that were previously pasted into chat or committed by mistake.

## Verification

Run a quick local check before pushing changes:

```bash
uv run python -m compileall src
uv run python -m unittest discover -s tests -v
```

## Delivering a task

Just type your request in **#task-inbox**:

> Design an AI-powered diagnostic tool for tropical diseases using genomic data

The Liaison Agent will analyse it, create a task, and send it to the CEO, who will delegate it through the hierarchy. Watch the conversation unfold in `#executive-council`, `#bmrc-council`, `#serc-council`, etc.

## Configuration

All settings via `.env`:

| Variable | Default | Description |
|---|---|---|
| `DISCORD_TOKEN` | — | Bot token |
| `DISCORD_GUILD_ID` | 0 | Server ID |
| `OPENAI_API_KEY` | — | LLM API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API endpoint |
| `OPENAI_MODEL` | `gpt-xx` | Model name |
| `TICK_INTERVAL` | 30 | Seconds between mailbox checks |
| `MAX_MEMORY` | 50 | Messages per agent memory |
| `AGENT_COOLDOWN` | 5 | Min seconds between LLM calls |

## Agent list

### Board & Executive
- **chairman** — Board Chairman
- **ceo** — CEO

### Deputy / Assistant Chief Executives
- **dce_research** — DCE Research
- **dce_ie** — DCE Innovation & Enterprise
- **dce_corporate** — DCE Corporate & General Counsel
- **ace_bmrc** — ACE Biomedical Research Council
- **ace_serc** — ACE Science & Engineering Research Council
- **ace_ie** — ACE I&E / Graduate Academy
- **ace_corp_dev** — ACE Corporate Development
- **ace_infra** — ACE Infrastructure

### BMRC Research Institutes
- **dir_bii** — Bioinformatics Institute
- **dir_bti** — Bioprocessing Technology Institute
- **dir_gis** — Genome Institute of Singapore
- **dir_idl** — Infectious Diseases Labs
- **dir_ihdp** — Institute for Human Development & Potential
- **dir_imcb** — Institute of Molecular & Cell Biology
- **dir_sign** — Singapore Immunology Network
- **dir_sifbi** — Singapore Inst. of Food & Biotech Innovation
- **dir_srl** — Skin Research Labs

### SERC Research Institutes
- **dir_artc** — ARTC / SIMTech
- **dir_ime** — Institute of Microelectronics
- **dir_ihpc** — Institute of High Performance Computing
- **dir_imre** — Institute of Materials Research & Engineering
- **dir_isce2** — ISCE2 — Sustainability
- **dir_i2r** — Institute for Infocomm Research
- **dir_nmc** — National Metrology Centre

### National Centres
- **dir_ai_coe** — AI Centre of Excellence for Manufacturing
- **dir_nscc** — National Supercomputing Centre
- **dir_eddc** — Experimental Drug Development Centre
- **dir_catos** — Centre for Advanced Technologies in Online Safety

### External
- **user_liaison** — Your personal AI agent for delivering tasks to A*STAR

## Author

Dr. Xinyu Yang from A*STAR (yang_xinyu@a-star.edu.sg)

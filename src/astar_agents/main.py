"""Entry point for the A*STAR multi-agent Discord simulation."""

from __future__ import annotations

import asyncio
import logging
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    from .config import settings

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)-28s  %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger(__name__)

    if not settings.discord_token:
        log.error("DISCORD_TOKEN is not set. Copy .env.example to .env and fill in your tokens.")
        sys.exit(1)
    if not settings.openai_api_key:
        log.error("OPENAI_API_KEY is not set.")
        sys.exit(1)

    from .bot import create_bot

    bot = create_bot()

    log.info("Starting A*STAR Agentic Simulation …")
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()

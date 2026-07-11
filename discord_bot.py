"""Discord bot using the official ADK Connector.

Wraps the Research Paper Agent as a Discord chatbot with database-backed
session persistence.  Supports cross-device sync with `adk web` so you can
inspect conversations from a browser while chatting on mobile Discord.

Docs: https://adk.dev/integrations/adk-connector/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing the agent (needs DEEPSEEK_API_KEY etc.).
PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

from adk_connectors.discord import DiscordConnector  # noqa: E402
from .agent import root_agent  # noqa: E402 — must follow .env load


DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    print("FATAL: DISCORD_BOT_TOKEN is not set in .env")
    sys.exit(1)

# Optional: your Discord user ID for cross-device session sync.
# When set, your Discord chats appear in the `adk web` UI under "user".
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID", "").strip() or None


if __name__ == "__main__":
    connector = DiscordConnector(
        token=DISCORD_BOT_TOKEN,
        agent=root_agent,
        session_management_across_device=True,  # SQLite-backed sync
        dev_user_id=DISCORD_USER_ID,            # map your Discord user → web UI
    )
    print("✅ Research Paper Agent Discord bot starting...")
    connector.start()

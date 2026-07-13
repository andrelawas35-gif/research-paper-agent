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
from adk_connectors.discord.adapter import DiscordAdapter  # noqa: E402
from adk_connectors.discord.formatter import DiscordFormatter  # noqa: E402
from .agent import root_agent  # noqa: E402 — must follow .env load

# adk-connector's DiscordAdapter.send_message() passes the full response to
# channel.send() with no length check, so any reply over Discord's 2000-char
# message cap gets rejected with a 400 (Invalid Form Body). Patch it here to
# split long replies into multiple messages instead of forking the package.
_DISCORD_MSG_LIMIT = 2000


def _chunk_for_discord(text: str, limit: int = _DISCORD_MSG_LIMIT) -> list[str]:
    if not text:
        return [""]
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    chunks.append(text)
    return chunks


async def _send_message_chunked(self, chat_id, message):
    channel = await self._get_channel(chat_id)
    if not channel:
        raise ValueError(f"Channel or User not found for ID: {chat_id}")

    payload = DiscordFormatter.to_api_payload(message)
    view = payload.get("view")

    reference = None
    if message.reply_to_message_id:
        try:
            import discord

            reference = discord.MessageReference(
                message_id=int(message.reply_to_message_id),
                channel_id=channel.id,
            )
        except Exception:
            reference = None

    chunks = _chunk_for_discord(payload.get("content"))
    sent_msg = None
    for i, chunk in enumerate(chunks):
        sent_msg = await channel.send(
            content=chunk,
            view=view if i == len(chunks) - 1 else None,
            reference=reference if i == 0 else None,
        )
    return {"message_id": str(sent_msg.id)}


DiscordAdapter.send_message = _send_message_chunked


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

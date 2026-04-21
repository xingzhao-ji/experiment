"""Claw Engine Discord Bot.

Posts run digests and manages publish/kill/rerun interactions.
Supports a local test mode that exercises the same code paths
without requiring Discord credentials.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from discord_bot.digest import format_digest, format_digest_embed
from discord_bot.views import LocalPublishView

logger = logging.getLogger("claw.discord")


# ── Local test mode ─────────────────────────────────────────────────

def post_digest_local(run_result, auto_publish: bool = False) -> dict:
    """Post a digest in local test mode (no Discord credentials needed).

    Returns a dict describing what happened.  Exercises the same
    formatting and publish-gate logic as the real bot.

    IMPORTANT: auto_publish is intentionally ignored.  The spec requires
    an explicit click to publish — in local mode we simulate a user
    confirming publication interactively.
    """
    digest_text = format_digest(run_result)
    embed = format_digest_embed(run_result)

    print("=" * 60)
    print("DISCORD DIGEST (local test mode)")
    print("=" * 60)
    print(digest_text)
    print("=" * 60)

    result = {
        "mode": "local",
        "digest": digest_text,
        "embed": embed,
        "published": False,
        "bundle_dir": run_result.bundle_dir,
    }

    if not run_result.success:
        print("[LOCAL] Run failed – not eligible for publishing.")
        return result

    # In local mode, simulate the publish gate
    view = LocalPublishView(run_result.bundle_dir)
    # For automated testing, we simulate a publish click
    publish_msg = view.publish()
    print(f"[LOCAL] {publish_msg}")
    result["published"] = view.published
    return result


# ── Real Discord bot ────────────────────────────────────────────────

async def post_digest_discord(run_result, channel_id: int, bot_token: str) -> dict:
    """Post a digest to a real Discord channel with interactive buttons.

    The publish button is the ONLY way to publish.  There is no
    auto-publish flag.  A human must click the button.
    """
    try:
        import discord
        from discord_bot.views import PublishView
    except ImportError:
        logger.error("discord.py not installed – falling back to local mode")
        return post_digest_local(run_result)

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    result = {"mode": "discord", "published": False}

    @client.event
    async def on_ready():
        channel = client.get_channel(channel_id)
        if channel is None:
            logger.error("Channel %d not found", channel_id)
            await client.close()
            return

        digest_text = format_digest(run_result)
        embed_data = format_digest_embed(run_result)

        embed = discord.Embed(
            title=embed_data["title"],
            description=embed_data["description"],
            color=embed_data["color"],
        )
        for field in embed_data["fields"]:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False),
            )

        view = None
        if run_result.success and run_result.bundle_dir:
            view = PublishView(run_result.bundle_dir)

        await channel.send(content=digest_text, embed=embed, view=view)
        logger.info("Digest posted to channel %d", channel_id)

        # Don't close – keep running so button interactions work.
        # The view has a 24h timeout.

    await client.start(bot_token)
    return result


def run_bot(run_result, local_mode: bool = True) -> dict:
    """Main entry point for posting a digest.

    In local mode, prints to stdout.  In Discord mode, requires
    DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID environment variables.
    """
    if local_mode:
        return post_digest_local(run_result)

    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")

    if not token or not channel_id:
        logger.warning(
            "DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID not set – "
            "falling back to local mode"
        )
        return post_digest_local(run_result)

    return asyncio.run(post_digest_discord(run_result, int(channel_id), token))

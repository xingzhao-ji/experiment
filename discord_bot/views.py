"""Discord UI components – publish/kill/rerun buttons.

The publish button is the human gate: no auto-publish.
A user MUST click "Publish" to move the bundle to out/published/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

try:
    import discord
    from discord.ui import View, Button, button

    class PublishView(View):
        """Buttons attached to every digest message."""

        def __init__(self, bundle_dir: str, *, timeout: float = 86400):
            super().__init__(timeout=timeout)
            self.bundle_dir = Path(bundle_dir)
            self.published = False
            self.killed = False

        @button(label="Publish", style=discord.ButtonStyle.green, emoji="\u2705")
        async def publish_button(self, interaction: discord.Interaction, btn: Button):
            if self.published:
                await interaction.response.send_message("Already published.", ephemeral=True)
                return

            dest = Path("out/published") / self.bundle_dir.name
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.bundle_dir, dest, dirs_exist_ok=True)
            self.published = True

            await interaction.response.send_message(
                f"Published to `{dest}`", ephemeral=False
            )
            btn.disabled = True
            await interaction.message.edit(view=self)

        @button(label="Kill", style=discord.ButtonStyle.red, emoji="\u274C")
        async def kill_button(self, interaction: discord.Interaction, btn: Button):
            self.killed = True
            await interaction.response.send_message(
                "Run killed. Bundle will NOT be published.", ephemeral=False
            )
            self.stop()

        @button(label="Rerun", style=discord.ButtonStyle.blurple, emoji="\U0001F504")
        async def rerun_button(self, interaction: discord.Interaction, btn: Button):
            await interaction.response.send_message(
                "Rerun requested. The next nightly cycle will re-process this dataset.",
                ephemeral=False,
            )

except ImportError:
    # Fallback when discord.py is not installed
    pass


class LocalPublishView:
    """Local-mode replacement that exercises the same publish logic
    without requiring Discord credentials."""

    def __init__(self, bundle_dir: str):
        self.bundle_dir = Path(bundle_dir)
        self.published = False
        self.killed = False

    def publish(self) -> str:
        if self.published:
            return "Already published."
        dest = Path("out/published") / self.bundle_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.bundle_dir, dest, dirs_exist_ok=True)
        self.published = True
        return f"Published to {dest}"

    def kill(self) -> str:
        self.killed = True
        return "Run killed. Bundle will NOT be published."

    def rerun(self) -> str:
        return "Rerun requested."

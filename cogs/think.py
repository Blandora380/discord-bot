import discord
from discord import app_commands
from discord.ext import commands


class Think(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # channel_id -> list of pending Interaction yang lagi di-"defer"
        self.pending: dict[int, list[discord.Interaction]] = {}

    @app_commands.command(
        name="think",
        description="make the bot think",
    )
    async def think(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        self.pending.setdefault(interaction.channel_id, []).append(interaction)

    @app_commands.command(
        name="stopthink",
        description="stop think)",
    )
    async def stopthink(self, interaction: discord.Interaction):
        queue = self.pending.get(interaction.channel_id)

        if not queue:
            await interaction.response.send_message(
                "there's no thinks in this channel", ephemeral=True
            )
            return

        pending = queue.pop()
        if not queue:
            del self.pending[interaction.channel_id]

        try:
            await pending.followup.send("✅ done thinkings")
        except discord.HTTPException:
            pass  # kemungkinan udah expired (>15 menit)

        remaining = len(queue)
        await interaction.response.send_message(
            f"stopped. there's still {remaining} thinks ." if remaining
            else "Dihentikan.",
            ephemeral=True,
        )

    @app_commands.command(
        name="stopallthink",
        description="stop all thinks",
    )
    async def stopallthink(self, interaction: discord.Interaction):
        queue = self.pending.pop(interaction.channel_id, [])

        if not queue:
            await interaction.response.send_message(
                "there's no more thinking in this channel", ephemeral=True
            )
            return

        for pending in queue:
            try:
                await pending.followup.send("✅ done thinking")
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            f"stopped all thinkings ({len(queue)}).", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Think(bot))

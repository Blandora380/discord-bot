"""Per-guild admin switches (rule 3).

Server admins must be able to switch off or restrict every feature themselves,
without the bot owner's help and without editing the code. This cog stores the
switches in their own SQLite file and exposes slash commands that only members
with Administrator or Manage Server can use.

Switches provided:

  /the-prefix     on/off   prefix (text) commands
  /the-passive    on/off   auto-replies, keyword triggers, reactions, XP posts
  /the-ai         on/off   AI features (chat, summarize, roast, image tools)
  /the-aichannel  #channel where the AI may auto-reply; unset = never
  /the-voice      on/off   voice features
  /the-leavevoice          make the bot leave a voice channel (admin escape hatch)
  /the-settings           show the current state

Storage lives in its own module-level SQLite handle so cogs can read switches
without importing the bot object.
"""

from __future__ import annotations

import sqlite3
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("settings")

DB_PATH = Path("data/settings.db")
_LOCK = threading.Lock()

_FLAGS = ("prefix", "passive", "ai", "voice")


@dataclass(frozen=True)
class GuildSettings:
    guild_id: int
    prefix: bool = True
    passive: bool = True
    ai: bool = True
    voice: bool = True
    ai_channel_id: int | None = None


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS guild_settings (
               guild_id      INTEGER PRIMARY KEY,
               prefix        INTEGER NOT NULL DEFAULT 1,
               passive       INTEGER NOT NULL DEFAULT 1,
               ai            INTEGER NOT NULL DEFAULT 1,
               voice         INTEGER NOT NULL DEFAULT 1,
               ai_channel_id INTEGER
           )"""
    )
    conn.commit()
    return conn


def get(guild_id: int | None) -> GuildSettings:
    """Return settings for a guild, or safe defaults in DMs."""
    if guild_id is None:
        return GuildSettings(guild_id=0)

    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT prefix, passive, ai, voice, ai_channel_id "
            "FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()

    if row is None:
        return GuildSettings(guild_id=guild_id)

    return GuildSettings(
        guild_id=guild_id,
        prefix=bool(row[0]),
        passive=bool(row[1]),
        ai=bool(row[2]),
        voice=bool(row[3]),
        ai_channel_id=row[4],
    )


def set_flag(guild_id: int, flag: str, value: bool) -> None:
    if flag not in _FLAGS:
        raise ValueError(f"unknown flag: {flag}")
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO guild_settings (guild_id, {c}) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET {c} = excluded.{c}".format(c=flag),
            (guild_id, int(value)),
        )
        conn.commit()


def set_ai_channel(guild_id: int, channel_id: int | None) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO guild_settings (guild_id, ai_channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET ai_channel_id = excluded.ai_channel_id",
            (guild_id, channel_id),
        )
        conn.commit()


# --------------------------------------------------------------------------
# guards used by every other cog
# --------------------------------------------------------------------------

def prefix_allowed(guild: discord.Guild | None) -> bool:
    """May prefix/text commands run here? (rule 3)"""
    if guild is None:
        return True
    return get(guild.id).prefix


def passive_allowed(guild: discord.Guild | None) -> bool:
    """May auto-replies, reactions and automatic posts run here? (rule 3)"""
    if guild is None:
        return True
    return get(guild.id).passive


def ai_allowed(guild: discord.Guild | None) -> bool:
    """May AI features run here? (rule 3)"""
    if guild is None:
        return True
    return get(guild.id).ai


def voice_allowed(guild: discord.Guild | None) -> bool:
    """May voice features run here? (rule 3)"""
    if guild is None:
        return False
    return get(guild.id).voice


def ai_channel_id(guild: discord.Guild | None) -> int | None:
    """Channel an admin chose for AI auto-replies, or None for "never".

    There is deliberately no hardcoded fallback: rule 3 says the bot must never
    post automatically in a channel an admin didn't choose.
    """
    if guild is None:
        return None
    return get(guild.id).ai_channel_id


def ai_prefix_allowed(guild: discord.Guild | None) -> bool:
    """AI reached through a text command needs both switches on."""
    return prefix_allowed(guild) and ai_allowed(guild)


def is_admin(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return bool(perms.administrator or perms.manage_guild)


def admin_only():
    """Slash-command check: Administrator or Manage Server only (rule 3)."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("This command only works in a server.")
        if not is_admin(interaction.user):
            raise app_commands.CheckFailure(
                "You need the Administrator or Manage Server permission."
            )
        return True

    return app_commands.check(predicate)


# --------------------------------------------------------------------------
# the switch commands
# --------------------------------------------------------------------------

def _flag(value: bool) -> str:
    return "🟢 on" if value else "🔴 off"


class Settings(commands.Cog):
    # One group so the whole feature is namespaced under the bot's own prefix
    # (rule 4a: no name may match a Shigure Ui command).
    the_group = app_commands.Group(
        name="the-settings",
        description="Admin switches for this bot (Administrator or Manage Server only).",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _interaction_error(
        self, interaction: discord.Interaction, message: str
    ) -> None:
        try:
            await interaction.response.send_message(message, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(message, ephemeral=True)

    async def _set(self, interaction: discord.Interaction, flag: str, value: bool):
        assert interaction.guild is not None
        set_flag(interaction.guild.id, flag, value)
        await self._interaction_error(
            interaction, f"✅ `{flag}` is now {_flag(value)} for this server."
        )

    @the_group.command(name="show", description="Show this bot's admin switches.")
    @admin_only()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def show(self, interaction: discord.Interaction):
        s = get(interaction.guild.id)
        channel = (
            f"<#{s.ai_channel_id}>" if s.ai_channel_id else "_not set — AI never auto-replies_"
        )
        embed = discord.Embed(title="⚙️ Bot settings", color=0x5865F2)
        embed.add_field(name="Prefix commands", value=_flag(s.prefix), inline=True)
        embed.add_field(name="Passive features", value=_flag(s.passive), inline=True)
        embed.add_field(name="AI features", value=_flag(s.ai), inline=True)
        embed.add_field(name="Voice features", value=_flag(s.voice), inline=True)
        embed.add_field(name="AI auto-reply channel", value=channel, inline=False)
        embed.set_footer(text="Change these with /the-settings prefix, passive, ai, voice, aichannel")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @the_group.command(name="prefix", description="Turn the bot's text (prefix) commands on or off.")
    @app_commands.describe(enabled="On = members can use text commands")
    @admin_only()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def prefix(self, interaction: discord.Interaction, enabled: bool):
        await self._set(interaction, "prefix", enabled)

    @the_group.command(name="passive", description="Turn auto-replies, reactions and XP posts on or off.")
    @app_commands.describe(enabled="On = keyword replies, reactions and level-up posts are allowed")
    @admin_only()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def passive(self, interaction: discord.Interaction, enabled: bool):
        await self._set(interaction, "passive", enabled)

    @the_group.command(name="ai", description="Turn AI features on or off.")
    @app_commands.describe(enabled="On = AI chat, summarize and roast are allowed")
    @admin_only()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def ai(self, interaction: discord.Interaction, enabled: bool):
        await self._set(interaction, "ai", enabled)

    @the_group.command(name="voice", description="Turn voice features on or off.")
    @app_commands.describe(enabled="On = the bot may join voice when asked")
    @admin_only()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def voice(self, interaction: discord.Interaction, enabled: bool):
        await self._set(interaction, "voice", enabled)

    @the_group.command(name="aichannel", description="Choose where the AI may reply on its own, or clear it.")
    @app_commands.describe(
        channel="Channel for AI auto-replies. Leave empty to disable auto-replies entirely.",
    )
    @admin_only()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def aichannel(
        self, interaction: discord.Interaction, channel: discord.TextChannel | None = None
    ):
        assert interaction.guild is not None
        set_ai_channel(interaction.guild.id, channel.id if channel else None)
        if channel:
            msg = f"✅ AI may auto-reply in {channel.mention}."
        else:
            msg = "✅ AI auto-replies disabled. Members can still use AI commands."
        await self._interaction_error(interaction, msg)

    @the_group.command(name="leavevoice", description="Disconnect the bot from its voice channel.")
    @admin_only()
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def leavevoice(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            await self._interaction_error(interaction, "I'm not connected to a voice channel.")
            return
        try:
            await voice_client.disconnect()
        except Exception:
            log.exception("voice disconnect failed")
            await self._interaction_error(
                interaction, "⚠️ Couldn't disconnect right now. Please try again."
            )
            return
        await self._interaction_error(interaction, "✅ Left the voice channel.")

    @prefix.error
    @passive.error
    @ai.error
    @voice.error
    @aichannel.error
    @show.error
    @leavevoice.error
    async def settings_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        message = "⚠️ You don't have permission to change bot settings."
        if isinstance(error, app_commands.CheckFailure):
            message = "⛔ Only members with Administrator or Manage Server can change bot settings."
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = "⏳ Slow down a little."
        else:
            log.exception("settings command error")
            message = "⚠️ Something went wrong. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))

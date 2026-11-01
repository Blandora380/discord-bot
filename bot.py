import os
import socket
import time
import logging
import asyncio
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Rule 5: the prefix must be unique — not `ui!`, not a bare `!`, not `/`.
# Rule 6: @everyone/@here/role pings must be impossible even if a user's input
# or an AI reply contains them. Both live in helpers/prefix.py so listener-style
# commands that pattern-match raw message text can't drift from this.
from helpers.prefix import COMMAND_PREFIX, ALLOWED_MENTIONS

SYNC_DEBOUNCE = 300.0  # seconds; Discord rate-limits bulk command uploads

intents = discord.Intents.default()
# Rule 11: this is a privileged intent, so it is only requested because it is
# actually used — a large number of features read message text: the `the!`
# listeners in cogs/help.py, uptime.py, play.py, pigeon.py, join.py,
# playpigeon.py, ipgrabber.py, gacha.py, card.py and roast.py, plus XP in
# cogs/leveling.py and the AI auto-reply in cogs/ai.py.
# `intents.members` is deliberately NOT requested: cogs/leveling.py resolves
# display names from the database, the user cache, or REST `fetch_member`.
intents.message_content = True

_synced_once = False
_last_sync = 0.0
# Signature of the last command set we uploaded. Compared every watcher tick so
# renames and deleted cogs trigger a sync too — without this, only newly-added
# cog files would ever reach Discord (rule 11).
_last_signature: tuple | None = None


def _command_signature() -> tuple:
    slash = tuple(sorted(c.name for c in bot.tree.get_commands()))
    prefix = tuple(sorted(c.name for c in bot.commands))
    return slash, prefix

def discover_cogs():
    """Scan folder cogs/ otomatis, gak perlu tulis manual satu-satu di sini.
    Semua file .py di dalamnya (kecuali yang diawali _) otomatis kedetect."""
    cogs = []
    for filename in sorted(os.listdir("cogs")):
        if filename.endswith(".py") and not filename.startswith("_"):
            cogs.append(f"cogs.{filename[:-3]}")
    return cogs

async def on_ready():
    """Log in and push the command list to Discord exactly once per process.

    `on_ready` fires again on every reconnect, so an unguarded `tree.sync()`
    here would re-upload the global command list each time and burn Discord's
    daily application-command create quota (rule 11).
    """
    global _synced_once
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if _synced_once:
        return
    _synced_once = True
    await _sync_tree()


async def _sync_tree() -> None:
    global _last_sync, _last_signature
    _last_sync = time.monotonic()
    try:
        synced = await bot.tree.sync()
        _last_signature = _command_signature()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as sync_e:
        # Never let a sync failure reach users or kill the listener.
        print(f"Tree sync error: {sync_e}")

async def watch_cogs_for_changes(poll_interval: float = 2.0):
    """Auto-reload cogs pas file-nya berubah, dan auto-load cog baru pas ada
    file baru ditambahin ke folder cogs/ — gak perlu !restartbot manual buat
    dua-duanya."""
    await bot.wait_until_ready()

    def cog_path(cog: str) -> str:
        return os.path.join(*cog.split(".")) + ".py"

    loaded_cogs = set(bot.extensions.keys())
    last_mtimes = {cog: os.path.getmtime(cog_path(cog)) for cog in loaded_cogs}

    while not bot.is_closed():
        await asyncio.sleep(poll_interval)

        # cek cog baru yang belum pernah di-load
        for cog in discover_cogs():
            if cog not in loaded_cogs:
                try:
                    await bot.load_extension(cog)
                    loaded_cogs.add(cog)
                    last_mtimes[cog] = os.path.getmtime(cog_path(cog))
                    print(f"✨ Auto-loaded new cog: {cog}")
                except Exception as e:
                    print(f"⚠️ Failed to auto-load {cog}: {e}")

        # Upload the command list whenever it differs from what Discord has.
        # Keyed on the signature rather than "a file changed", so renamed and
        # deleted commands propagate too, while quota is only spent when the
        # list genuinely differs — a burst of edits still collapses into one
        # request per SYNC_DEBOUNCE seconds (rule 11).
        try:
            signature = _command_signature()
        except Exception:
            signature = None
        if signature is not None and signature != _last_signature:
            if time.monotonic() - _last_sync >= SYNC_DEBOUNCE:
                await _sync_tree()

        # cek perubahan (atau file yang ilang) di cog yang udah ke-load
        for cog in list(loaded_cogs):
            path = cog_path(cog)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                # file udah gak ada (dipindah/dihapus) — unload otomatis
                try:
                    await bot.unload_extension(cog)
                    print(f"🗑️ Auto-unloaded (file removed): {cog}")
                except Exception as e:
                    print(f"⚠️ Failed to auto-unload {cog}: {e}")
                loaded_cogs.discard(cog)
                last_mtimes.pop(cog, None)
                continue

            if mtime != last_mtimes.get(cog):
                last_mtimes[cog] = mtime
                try:
                    await bot.reload_extension(cog)
                    print(f"🔄 Auto-reloaded: {cog}")
                except Exception as e:
                    print(f"⚠️ Failed to auto-reload {cog}: {e}")

async def main():
    global bot

    # Paksa semua koneksi (REST + WebSocket gateway) pakai IPv4, biar ga
    # kena masalah IPv6 yang lambat/di-drop di beberapa jaringan WiFi.
    # Harus dibikin di sini (bukan di top-level module) karena butuh
    # event loop yang udah jalan.
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    bot = commands.Bot(
        command_prefix=COMMAND_PREFIX,
        intents=intents,
        connector=connector,
        allowed_mentions=ALLOWED_MENTIONS,
        # Rule 4a: discord.py auto-creates a prefix command named `help`, which
        # collides with Shigure Ui's `help`. This bot's help is the raw
        # `the!cmds` listener in cogs/help.py instead.
        help_command=None,
    )
    bot.add_listener(on_ready, "on_ready")

    from cogs.settings import prefix_allowed

    @bot.check
    async def prefix_switch_check(ctx: commands.Context) -> bool:
        """Rule 3: admins must be able to switch off prefix/text commands.

        Slash commands are deliberately exempt — admins already control them in
        Server Settings → Integrations, and exempting them means an admin can
        always turn text commands back on from the Integrations screen even if
        they were disabled.
        """
        if ctx.interaction is not None:
            return True
        if prefix_allowed(ctx.guild):
            return True
        raise commands.CheckFailure(
            "Text commands are switched off in this server. "
            "An admin can turn them back on with `/the-settings prefix`."
        )

    async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
        """Rule 11: members only ever see a short friendly message.

        Registering this listener also disables discord.py's default handler
        (it returns early when `extra_events['on_command_error']` is set), so
        the full traceback is re-logged here — to the log, never to the channel.
        """
        if isinstance(error, commands.CommandNotFound):
            # The bot's help lives in cogs/help.py; unknown text is normal noise.
            return

        if isinstance(error, commands.CheckFailure):
            message = str(error) or "You can't use that command here."
        elif isinstance(error, commands.CommandOnCooldown):
            message = f"⏳ Slow down — try again in {error.retry_after:.1f}s."
        elif isinstance(error, commands.MissingRequiredArgument):
            message = f"❌ Missing `{error.param.name}`. Try `the!cmds` for usage."
        else:
            # Never surface the original exception: it can contain paths or
            # upstream error bodies. Full detail still goes to the log.
            logging.getLogger("bot").error(
                "unhandled error in %s", ctx.command, exc_info=error
            )
            message = "⚠️ Something went wrong. Please try again."

        try:
            await ctx.send(message)
        except Exception:
            pass

    bot.add_listener(on_command_error, "on_command_error")

    async with bot:
        for cog in discover_cogs():
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")

        bot.loop.create_task(watch_cogs_for_changes())

        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
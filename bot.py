import os
import socket
import asyncio
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

def discover_cogs():
    """Scan folder cogs/ otomatis, gak perlu tulis manual satu-satu di sini.
    Semua file .py di dalamnya (kecuali yang diawali _) otomatis kedetect."""
    cogs = []
    for filename in sorted(os.listdir("cogs")):
        if filename.endswith(".py") and not filename.startswith("_"):
            cogs.append(f"cogs.{filename[:-3]}")
    return cogs

async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} slash command(s)")

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
        new_cogs_loaded = False
        for cog in discover_cogs():
            if cog not in loaded_cogs:
                try:
                    await bot.load_extension(cog)
                    loaded_cogs.add(cog)
                    last_mtimes[cog] = os.path.getmtime(cog_path(cog))
                    print(f"✨ Auto-loaded new cog: {cog}")
                    new_cogs_loaded = True
                except Exception as e:
                    print(f"⚠️ Failed to auto-load {cog}: {e}")

        if new_cogs_loaded:
            try:
                synced = await bot.tree.sync()
                print(f"Synced {len(synced)} slash command(s)")
            except Exception as sync_e:
                print(f"Tree sync error: {sync_e}")

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
    bot = commands.Bot(command_prefix="!", intents=intents, connector=connector)
    bot.add_listener(on_ready, "on_ready")

    async with bot:
        for cog in discover_cogs():
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")

        bot.loop.create_task(watch_cogs_for_changes())

        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
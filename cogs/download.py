import os
import time
import asyncio
import discord
from discord.ext import commands
import yt_dlp
import aiohttp

DOWNLOAD_DIR = "downloads"
DEFAULT_MAX_FILESIZE_MB = 10  # fallback kalau dipanggil di DM (nggak ada guild limit)
EMBED_COLOR = 0x5865F2  # blurple

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def make_progress_bar(percent: float, length: int = 20) -> str:
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}] {percent:.1f}%`"


def status_embed(title: str, description: str, color: int = EMBED_COLOR) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


async def get_video_duration(filepath: str) -> float:
    """Ambil durasi video (detik) pake ffprobe."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", filepath,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0


async def compress_video(input_path: str, output_path: str, target_size_mb: float, duration: float) -> bool:
    """Compress video pake ffmpeg biar muat di target_size_mb. Return True kalau sukses."""
    if duration <= 0:
        return False

    audio_bitrate_kbps = 96
    target_kbit = target_size_mb * 8192 * 0.92  # 8% margin buat container overhead
    video_bitrate_kbps = max(150, int((target_kbit / duration) - audio_bitrate_kbps))

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-b:v", f"{video_bitrate_kbps}k",
        "-preset", "fast",
        "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0 or not os.path.exists(output_path):
        print(f"[compress_video] ffmpeg error: {stderr.decode()[-1000:]}")
        return False
    return True


async def upload_to_catbox(filepath: str) -> str | None:
    """Upload file to catbox.moe, return URL-nya if success, None if failed."""
    url = "https://catbox.moe/user/api.php"
    filename = os.path.basename(filepath)

    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("reqtype", "fileupload")
            with open(filepath, "rb") as f:
                data.add_field("fileToUpload", f, filename=filename)
                async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    text = await resp.text()
                    if resp.status == 200 and text.startswith("https://"):
                        return text.strip()
                    print(f"[upload_to_catbox] unexpected response ({resp.status}): {text[:300]}")
                    return None
    except Exception as e:
        print(f"[upload_to_catbox] error: {e}")
        return None


class Download(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_max_filesize_mb(self, ctx) -> float:
        """Take the actual file size limit in effect (depending on guild level boost)."""
        if ctx.guild is not None:
            return ctx.guild.filesize_limit / (1024 * 1024)
        return DEFAULT_MAX_FILESIZE_MB

    @commands.command(name="downloadyt")
    async def download(self, ctx, url: str, fmt: str = "mp3"):
        fmt = fmt.lower()
        if fmt not in ("mp3", "mp4"):
            await ctx.send(embed=status_embed(
                "❌ Format is wrong", "Format: `mp3` or `mp4`.\nExample: `!download <link> mp3`",
                color=0xED4245
            ))
            return

        max_filesize_mb = self.get_max_filesize_mb(ctx)

        msg = await ctx.send(embed=status_embed(f"⏳ Preparing download ({fmt})...", url))

        loop = asyncio.get_event_loop()
        last_update = {"time": 0}

        def progress_hook(d):
            now = time.time()
            if now - last_update["time"] < 2 and d["status"] != "finished":
                return
            last_update["time"] = now

            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    percent = downloaded / total * 100
                    speed = d.get("speed")
                    speed_str = f"{speed/1024/1024:.2f} MB/s" if speed else "?"
                    eta = d.get("eta")
                    eta_str = f"{eta}s" if eta is not None else "?"
                    description = (
                        f"{make_progress_bar(percent)}\n"
                        f"**Speed:** {speed_str} | **ETA:** {eta_str}"
                    )
                else:
                    description = "Unknown file size..."

                embed = status_embed("⏳ Downloading...", description)
                asyncio.run_coroutine_threadsafe(self._safe_edit(msg, embed), loop)

            elif d["status"] == "finished":
                embed = status_embed("🔄 Processing/converting...", "Hampir selesai...")
                asyncio.run_coroutine_threadsafe(self._safe_edit(msg, embed), loop)

        filename_template = os.path.join(DOWNLOAD_DIR, f"{ctx.author.id}_%(title)s.%(ext)s")

        if fmt == "mp3":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": filename_template,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "quiet": True,
                "noplaylist": True,
                "progress_hooks": [progress_hook],
            }
        else:
            ydl_opts = {
                "format": f"best[ext=mp4][filesize<{int(max_filesize_mb)}M]/best[ext=mp4]/best",
                "outtmpl": filename_template,
                "quiet": True,
                "noplaylist": True,
                "progress_hooks": [progress_hook],
            }

        filepath = None
        title = None
        try:
            def run_download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return ydl.prepare_filename(info), info.get("title", "Unknown")

            filepath, title = await loop.run_in_executor(None, run_download)

            if fmt == "mp3":
                filepath = os.path.splitext(filepath)[0] + ".mp3"

            filesize_mb = os.path.getsize(filepath) / (1024 * 1024)

            if filesize_mb > max_filesize_mb:
                if fmt == "mp4":
                    await self._safe_edit(msg, status_embed(
                        "🔄 Compressing...",
                        f"File {filesize_mb:.1f}MB, compressing to {max_filesize_mb:.0f}MB..."
                    ))

                    duration = await get_video_duration(filepath)
                    compressed_path = os.path.splitext(filepath)[0] + "_compressed.mp4"
                    success = await compress_video(filepath, compressed_path, max_filesize_mb, duration)

                    if success:
                        compressed_size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
                        os.remove(filepath)
                        filepath = compressed_path
                        filesize_mb = compressed_size_mb
                    else:
                        await self._safe_edit(msg, status_embed(
                            "❌ Compress failed", "Checking if ffmpeg is installed in server.", color=0xED4245
                        ))
                        os.remove(filepath)
                        return

            # Kalau masih kegedean (walau udah dicompress, atau mp3 yang somehow gede) -> upload ke catbox
            if filesize_mb > max_filesize_mb:
                await self._safe_edit(msg, status_embed(
                    "🔄 Uploading to catbox.moe...",
                    f"File {filesize_mb:.1f}MB masih di atas limit Discord ({max_filesize_mb:.0f}MB)."
                ))

                link = await upload_to_catbox(filepath)
                os.remove(filepath)

                if link:
                    embed = status_embed("✅ Success!", f"**{title}**")
                    embed.set_footer(text=f"{filesize_mb:.1f}MB • di-hosting via catbox.moe (bukan Discord)")
                    await self._safe_edit(msg, embed)
                    # Kirim link mentah terpisah biar Discord auto-unfurl jadi video/audio player
                    await ctx.send(link)
                else:
                    await self._safe_edit(msg, status_embed(
                        "❌ Gagal upload",
                        "File too large for Discord dan catbox.moe.",
                        color=0xED4245
                    ))
                return

            # Muat di limit Discord -> attach langsung
            await self._safe_edit(msg, status_embed("✅ Success! Sending file...", title))
            embed = status_embed(f"🎬 {title}", f"Format: `{fmt}` • {filesize_mb:.1f}MB")
            await ctx.send(embed=embed, file=discord.File(filepath))
            os.remove(filepath)
            await msg.delete()

        except discord.HTTPException as e:
            if e.status == 413 or getattr(e, "code", None) == 40005:
                await self._safe_edit(msg, status_embed(
                    "❌ File rejected by Discord",
                    f"The file is too large for this server (limit ~{max_filesize_mb:.0f}MB).",
                    color=0xED4245
                ))
            else:
                await self._safe_edit(msg, status_embed("❌ Send failed", str(e), color=0xED4245))
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

        except Exception as e:
            await self._safe_edit(msg, status_embed("❌ Download failed", str(e), color=0xED4245))
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

    async def _safe_edit(self, msg, embed):
        try:
            await msg.edit(content=None, embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Download(bot))

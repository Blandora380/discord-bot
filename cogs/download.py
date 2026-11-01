import os
import time
import asyncio
import logging
import discord
from discord.ext import commands
import yt_dlp
import aiohttp

log = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
MIN_FILESIZE_LIMIT_MB = 20

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def make_progress_bar(percent: float, length: int = 20) -> str:
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}] {percent:.1f}%`"


def status(title: str, description: str = "") -> str:
    text = f"**{title}**"
    if description:
        text += f"\n{description}"
    return text[:2000]


async def get_video_duration(filepath: str) -> float:
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
    if duration <= 0:
        return False

    audio_bitrate_kbps = 96
    target_kbit = target_size_mb * 8192 * 0.92
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
        log.error("ffmpeg failed: %s", stderr.decode()[-1000:])
        return False
    return True


async def upload_to_catbox(filepath: str) -> str | None:
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
                    log.error("catbox unexpected response (%s): %s", resp.status, text[:300])
                    return None
    except Exception:
        log.exception("catbox upload failed")
        return None


class Download(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_max_filesize_mb(self, ctx) -> float:
        if ctx.guild is not None:
            return max(ctx.guild.filesize_limit / (1024 * 1024), MIN_FILESIZE_LIMIT_MB)
        return MIN_FILESIZE_LIMIT_MB

    @commands.command(name="downloadyt")
    async def download(self, ctx, url: str, fmt: str = "mp3"):
        fmt = fmt.lower()
        if fmt not in ("mp3", "mp4"):
            await ctx.send(status(
                "❌ Invalid format",
                "Format must be `mp3` or `mp4`.\nExample: `the!downloadyt <link> mp3`",
            ))
            return

        max_filesize_mb = self.get_max_filesize_mb(ctx)

        msg = await ctx.send(status(f"⏳ Preparing download ({fmt})...", f"<{url}>"))

        loop = asyncio.get_running_loop()
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

                asyncio.run_coroutine_threadsafe(
                    self._safe_edit(msg, status("⏳ Downloading...", description)), loop
                )

            elif d["status"] == "finished":
                asyncio.run_coroutine_threadsafe(
                    self._safe_edit(msg, status("🔄 Processing/converting...", "Almost done...")), loop
                )

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
                "js_runtimes": {"node": {}},
                "progress_hooks": [progress_hook],
            }
        else:
            ydl_opts = {
                "format": "bv*[ext=mp4][vcodec^=avc1][height<=720]+ba[ext=m4a]/bv*[ext=mp4][height<=720]+ba/b[ext=mp4]/b",
                "merge_output_format": "mp4",
                "extractor_args": {"youtube": {"player_client": ["mweb"]}},
                "outtmpl": filename_template,
                "quiet": True,
                "noplaylist": True,
                "js_runtimes": {"node": {}},
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

            if filesize_mb > max_filesize_mb and fmt == "mp4":
                await self._safe_edit(msg, status(
                    "🔄 Compressing...",
                    f"File is {filesize_mb:.1f}MB, compressing to fit {max_filesize_mb:.0f}MB..."
                ))

                duration = await get_video_duration(filepath)
                compressed_path = os.path.splitext(filepath)[0] + "_compressed.mp4"

                if await compress_video(filepath, compressed_path, max_filesize_mb, duration):
                    os.remove(filepath)
                    filepath = compressed_path
                    filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
                else:
                    await self._safe_edit(msg, status(
                        "❌ Compression failed",
                        "Check that ffmpeg is installed on the server."
                    ))
                    os.remove(filepath)
                    return

            if filesize_mb > max_filesize_mb:
                await self._safe_edit(msg, status(
                    "🔄 Uploading to catbox.moe...",
                    f"File is {filesize_mb:.1f}MB, still above the Discord limit ({max_filesize_mb:.0f}MB)."
                ))

                link = await upload_to_catbox(filepath)
                os.remove(filepath)

                if link:
                    await self._safe_edit(msg, status(
                        "✅ Success!",
                        f"{title}\n{filesize_mb:.1f}MB • hosted on catbox.moe (not Discord)"
                    ))
                    await ctx.send(link)
                else:
                    await self._safe_edit(msg, status(
                        "❌ Upload failed",
                        "The file is too large for both Discord and catbox.moe."
                    ))
                return

            await self._safe_edit(msg, status("✅ Success! Sending file...", title))
            await ctx.send(
                f"**🎬 {title}**\nFormat: `{fmt}` • {filesize_mb:.1f}MB",
                file=discord.File(filepath),
            )
            os.remove(filepath)
            await msg.delete()

        except discord.HTTPException as e:
            if e.status == 413 or getattr(e, "code", None) == 40005:
                await self._safe_edit(msg, status(
                    "❌ File rejected by Discord",
                    f"The file is too large for this server (limit ~{max_filesize_mb:.0f}MB)."
                ))
            else:
                log.exception("sending downloaded file failed")
                await self._safe_edit(msg, status(
                    "❌ Send failed",
                    "Couldn't send the file. Please try again."
                ))
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

        except Exception:
            log.exception("download failed")
            await self._safe_edit(msg, status(
                "❌ Download failed",
                "Couldn't download that. Please check the link and try again."
            ))
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

    async def _safe_edit(self, msg, text):
        try:
            await msg.edit(content=text)
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Download(bot))

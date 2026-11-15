"""Cache management utilities to control disk/memory usage."""

import asyncio
import logging
import time
from pathlib import Path

log = logging.getLogger("cache")


def cleanup_image_cache(cache_dir: Path, max_age_days: int = 7, max_size_mb: int = 50) -> int:
    """Remove old or excess cached images.

    Args:
        cache_dir: Directory containing cached images
        max_age_days: Delete files older than this many days
        max_size_mb: If total cache exceeds this, delete oldest files until under limit

    Returns:
        Number of files deleted
    """
    if not cache_dir.exists():
        return 0

    now = time.time()
    max_age_seconds = max_age_days * 86400
    max_size_bytes = max_size_mb * 1024 * 1024

    files = []
    total_size = 0

    for f in cache_dir.rglob("*"):
        if f.is_file():
            stat = f.stat()
            files.append((f, stat.st_mtime, stat.st_size))
            total_size += stat.st_size

    deleted = 0

    # Delete by age
    for f, mtime, size in files:
        if now - mtime > max_age_seconds:
            try:
                f.unlink()
                deleted += 1
                total_size -= size
            except Exception as e:
                log.warning(f"Failed to delete old cache file {f}: {e}")

    # Delete by size (oldest first)
    if total_size > max_size_bytes:
        files.sort(key=lambda x: x[1])  # Sort by mtime (oldest first)
        for f, mtime, size in files:
            if total_size <= max_size_bytes:
                break
            try:
                f.unlink()
                deleted += 1
                total_size -= size
            except Exception as e:
                log.warning(f"Failed to delete excess cache file {f}: {e}")

    if deleted:
        log.info(f"Cleaned up {deleted} cached images from {cache_dir}")

    return deleted


async def periodic_cache_cleanup(bot, interval_hours: int = 6):
    """Background task to periodically clean image caches."""
    from shared.cards import IMAGE_CACHE_DIR
    from cogs.gacha import IMAGE_CACHE_DIR as GACHA_CACHE_DIR

    while not bot.is_closed():
        try:
            cleanup_image_cache(IMAGE_CACHE_DIR, max_age_days=7, max_size_mb=50)
            cleanup_image_cache(GACHA_CACHE_DIR, max_age_days=7, max_size_mb=50)
        except Exception as e:
            log.warning(f"Cache cleanup failed: {e}")

        await asyncio.sleep(interval_hours * 3600)
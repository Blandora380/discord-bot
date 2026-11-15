"""Shared Project Sekai card data — loaded once, used by gacha & card cogs.

This avoids loading the same ~2MB JSON into memory twice (gacha.py + card.py).
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import aiohttp

from bot import get_shared_session

log = logging.getLogger("shared.cards")

CARDS_URL = "https://sekai-world.github.io/sekai-master-db-diff/cards.json"
CACHE_PATH = Path("cache/pjsk/cards.json")
CACHE_TTL = 60 * 60 * 24  # 24 hours

# Image cache directories
IMAGE_CACHE_DIR = Path("cache/pjsk/images")
GACHA_IMAGE_CACHE_DIR = Path("cache/pjsk/gacha_images")

# These are imported by gacha.py and card.py
CHARACTERS = {
    1: "Ichika Hoshino",
    2: "Saki Tenma",
    3: "Honami Mochizuki",
    4: "Shiho Hinomori",
    5: "Minori Hanasato",
    6: "Haruka Kiritani",
    7: "Airi Momoi",
    8: "Shizuku Hinomori",
    9: "Kohane Azusawa",
    10: "An Shiraishi",
    11: "Akito Shinonome",
    12: "Toya Aoyagi",
    13: "Tsukasa Tenma",
    14: "Emu Otori",
    15: "Nene Kusanagi",
    16: "Rui Kamishiro",
    17: "Kanade Yoisaki",
    18: "Mafuyu Asahina",
    19: "Ena Shinonome",
    20: "Mizuki Akiyama",
    21: "Hatsune Miku",
    22: "Kagamine Rin",
    23: "Kagamine Len",
    24: "Megurine Luka",
    25: "MEIKO",
    26: "KAITO",
}

# For card cog (detailed character info)
CHARACTERS_DETAILED = {
    1: {"name": "Ichika Hoshino", "jp": "星乃 一歌", "unit": "Leo/need", "aliases": ["ichika", "hoshino"]},
    2: {"name": "Saki Tenma", "jp": "天馬 咲希", "unit": "Leo/need", "aliases": ["saki", "tenma saki"]},
    3: {"name": "Honami Mochizuki", "jp": "望月 穂波", "unit": "Leo/need", "aliases": ["honami", "mochizuki", "hona"]},
    4: {"name": "Shiho Hinomori", "jp": "日野森 志歩", "unit": "Leo/need", "aliases": ["shiho", "hinomori shiho"]},
    5: {"name": "Minori Hanasato", "jp": "花里 みのり", "unit": "MORE MORE JUMP!", "aliases": ["minori", "hanasato"]},
    6: {"name": "Haruka Kiritani", "jp": "桐谷 遥", "unit": "MORE MORE JUMP!", "aliases": ["haruka", "kiritani"]},
    7: {"name": "Airi Momoi", "jp": "桃井 愛莉", "unit": "MORE MORE JUMP!", "aliases": ["airi", "momoi"]},
    8: {"name": "Shizuku Hinomori", "jp": "日野森 雫", "unit": "MORE MORE JUMP!", "aliases": ["shizuku", "hinomori shizuku"]},
    9: {"name": "Kohane Azusawa", "jp": "小豆沢 こはね", "unit": "Vivid BAD SQUAD", "aliases": ["kohane", "azusawa", "hamster"]},
    10: {"name": "An Shiraishi", "jp": "白石 杏", "unit": "Vivid BAD SQUAD", "aliases": ["an", "shiraishi"]},
    11: {"name": "Akito Shinonome", "jp": "東雲 彰人", "unit": "Vivid BAD SQUAD", "aliases": ["akito", "shinonome akito"]},
    12: {"name": "Toya Aoyagi", "jp": "青柳 冬弥", "unit": "Vivid BAD SQUAD", "aliases": ["toya", "touya", "aoyagi"]},
    13: {"name": "Tsukasa Tenma", "jp": "天馬 司", "unit": "Wonderlands x Showtime", "aliases": ["tsukasa", "tenma tsukasa", "star"]},
    14: {"name": "Emu Otori", "jp": "鳳 えむ", "unit": "Wonderlands x Showtime", "aliases": ["emu", "otori", "wonderhoi"]},
    15: {"name": "Nene Kusanagi", "jp": "草薙 寧々", "unit": "Wonderlands x Showtime", "aliases": ["nene", "kusanagi"]},
    16: {"name": "Rui Kamishiro", "jp": "神代 類", "unit": "Wonderlands x Showtime", "aliases": ["rui", "kamishiro"]},
    17: {"name": "Kanade Yoisaki", "jp": "宵崎 奏", "unit": "25-ji, Nightcord de.", "aliases": ["kanade", "yoisaki", "kc"]},
    18: {"name": "Mafuyu Asahina", "jp": "朝比奈 まふゆ", "unit": "25-ji, Nightcord de.", "aliases": ["mafuyu", "asahina"]},
    19: {"name": "Ena Shinonome", "jp": "東雲 絵名", "unit": "25-ji, Nightcord de.", "aliases": ["ena", "shinonome ena", "enanan"]},
    20: {"name": "Mizuki Akiyama", "jp": "暁山 瑞希", "unit": "25-ji, Nightcord de.", "aliases": ["mizuki", "akiyama", "amia"]},
    21: {"name": "Hatsune Miku", "jp": "初音ミク", "unit": "VIRTUAL SINGER", "aliases": ["miku", "hatsune miku"]},
    22: {"name": "Kagamine Rin", "jp": "鏡音リン", "unit": "VIRTUAL SINGER", "aliases": ["rin", "kagamine rin"]},
    23: {"name": "Kagamine Len", "jp": "鏡音レン", "unit": "VIRTUAL SINGER", "aliases": ["len", "kagamine len"]},
    24: {"name": "Megurine Luka", "jp": "巡音ルカ", "unit": "VIRTUAL SINGER", "aliases": ["luka", "megurine luka"]},
    25: {"name": "MEIKO", "jp": "MEIKO", "unit": "VIRTUAL SINGER", "aliases": ["meiko"]},
    26: {"name": "KAITO", "jp": "KAITO", "unit": "VIRTUAL SINGER", "aliases": ["kaito"]},
}

ATTR_COLORS = {
    "cool": 0x4170E8,
    "cute": 0xFB6797,
    "happy": 0xFFA916,
    "mysterious": 0x935DE6,
    "pure": 0x4BD260,
}

ATTR_EMOJIS = {
    "cool": "🔷",
    "cute": "🌸",
    "happy": "☀️",
    "mysterious": "🌙",
    "pure": "🍀",
}

RARITY_STARS = {
    "rarity_4": "⭐⭐⭐⭐",
    "rarity_birthday": "🎀 Birthday",
    "rarity_3": "⭐⭐⭐",
    "rarity_2": "⭐⭐",
    "rarity_1": "⭐",
}

RARITY_BORDER_COLORS = {
    "rarity_4": (255, 215, 0),
    "rarity_birthday": (255, 105, 180),
    "rarity_3": (230, 160, 40),
    "rarity_2": (180, 195, 205),
    "rarity_1": (130, 140, 150),
}


def get_rarity_num(rarity_type: str) -> int:
    if rarity_type == "rarity_4" or rarity_type == "rarity_birthday":
        return 4
    if rarity_type == "rarity_3":
        return 3
    if rarity_type == "rarity_2":
        return 2
    return 1


class CardData:
    """Singleton holder for card data loaded from the API/cache."""

    _instance: "CardData | None" = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "CardData":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._cards: list[dict[str, Any]] = []
        self.cards_by_rarity: dict[str, list[dict[str, Any]]] = {
            "rarity_4": [],
            "rarity_birthday": [],
            "rarity_3": [],
            "rarity_2": [],
            "rarity_1": [],
        }
        self._last_loaded = 0.0
        self._initialized = True

    async def ensure_loaded(self) -> None:
        """Load cards if not loaded or cache expired."""
        async with self._lock:
            if time.time() - self._last_loaded < CACHE_TTL and self._cards:
                return

            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = None

            # Try cache first
            if CACHE_PATH.exists() and (time.time() - CACHE_PATH.stat().st_mtime < CACHE_TTL):
                try:
                    with open(CACHE_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    log.warning(f"Error loading cached cards: {e}")

            # Fetch from API if needed
            if not data:
                session = get_shared_session()
                try:
                    async with session.get(CARDS_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                                json.dump(data, f)
                except Exception as e:
                    log.error(f"Failed to fetch cards.json: {e}")
                    if CACHE_PATH.exists():
                        with open(CACHE_PATH, "r", encoding="utf-8") as f:
                            data = json.load(f)

            if not data:
                return

            # Organize by rarity
            by_rarity: dict[str, list[dict[str, Any]]] = {k: [] for k in self.cards_by_rarity}
            for c in data:
                r = c.get("cardRarityType")
                if r in by_rarity:
                    by_rarity[r].append(c)

            self._cards = data
            self.cards_by_rarity = by_rarity
            self._last_loaded = time.time()
            log.info(
                f"Card data loaded: {len(by_rarity['rarity_4'])} 4★, "
                f"{len(by_rarity['rarity_3'])} 3★, {len(by_rarity['rarity_2'])} 2★ cards"
            )

    @property
    def all_cards(self) -> list[dict[str, Any]]:
        return self._cards

    def roll_one_card(self, guaranteed_3star: bool = False) -> dict[str, Any]:
        """Roll a single card based on standard Project Sekai rates."""
        import random
        r = random.random()
        if guaranteed_3star:
            if r < 0.03:
                rarity = "rarity_4"
            else:
                rarity = "rarity_3"
        else:
            if r < 0.03:
                rarity = "rarity_4"
            elif r < 0.115:
                rarity = "rarity_3"
            else:
                rarity = "rarity_2"

        pool = self.cards_by_rarity.get(rarity) or self.cards_by_rarity.get("rarity_2")
        if not pool:
            for p in self.cards_by_rarity.values():
                if p:
                    pool = p
                    break
        return random.choice(pool)


# Global singleton instance
card_data = CardData()
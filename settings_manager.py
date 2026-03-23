"""
Visionary Navigator — Ayarlar Yöneticisi
JSON tabanlı kalıcı ayar sistemi. Singleton.
"""

import json
import os
import logging
from typing import Any, Optional

logger = logging.getLogger("Settings")
logger.setLevel(logging.INFO)

SETTINGS_DIR = os.path.expanduser("~/.visionary")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

# Varsayılan ayarlar
DEFAULTS = {
    "gemini_api_key": "",
    "tts_enabled": True,
    "tts_voice": "tr-TR-AhmetNeural",
    "welcome_enabled": True,
    "music_url": "",
    "music_start_sec": 0,
    "social_accounts": {},
    "custom_sites": [],
    "ai_provider": "auto",  # "auto", "gemini", "local"
    "user_profile_summary": "",
}


class SettingsManager:
    """Singleton ayar yöneticisi — JSON okuma/yazma."""

    _instance: Optional["SettingsManager"] = None

    def __new__(cls) -> "SettingsManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        self._data: dict = {}
        self._load()
        self._loaded = True

    def _load(self) -> None:
        """JSON dosyasından ayarları yükle."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info("Ayarlar yüklendi.")
            except Exception as e:
                logger.warning(f"Ayar dosyası okunamadı: {e}")
                self._data = {}
        else:
            self._data = {}

        # Eksik anahtarları varsayılanlarla doldur
        for key, default in DEFAULTS.items():
            if key not in self._data:
                self._data[key] = default

    def save(self) -> None:
        """Ayarları JSON dosyasına kaydet."""
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.info("Ayarlar kaydedildi.")
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get_all(self) -> dict:
        return self._data.copy()

    @property
    def gemini_api_key(self) -> str:
        return self.get("gemini_api_key", "")

    @property
    def tts_enabled(self) -> bool:
        return self.get("tts_enabled", True)

    @property
    def tts_voice(self) -> str:
        return self.get("tts_voice", "tr-TR-AhmetNeural")

    @property
    def music_url(self) -> str:
        return self.get("music_url", "")

    @property
    def custom_sites(self) -> list:
        return self.get("custom_sites", [])

    @property
    def social_accounts(self) -> dict:
        return self.get("social_accounts", {})

    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key.strip())

"""
Application configuration
"""
import os
import json
from functools import lru_cache

# Project root (Spider_XHS/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

# ── Settings singleton ────────────────────────────────────────────────────────

_DEFAULTS = {
    "APP_NAME": "Spider_XHS",
    "APP_VERSION": "2.0.0",
    "DEBUG": False,
    "SECRET_KEY": "potato-xhs-helper-secret-change-me",
    "DATABASE_URL": f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'spider_xhs.db')}",
    "JWT_SECRET": "jwt-secret-change-in-production",
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": 1440,
    "FERNET_KEY": "",
    "LLM_PROVIDER": "deepseek",
    "LLM_API_KEY": "",
    "LLM_MODEL": "deepseek-v3",
    "LLM_BASE_URL": "",
    "COOKIES": "",
    "HOST": "0.0.0.0",
    "PORT": 5000,
}


class _Settings:
    """Simple settings class that reads from env + config file."""

    def __init__(self):
        self._values = dict(_DEFAULTS)
        # Load from .env
        env_path = os.path.join(PROJECT_ROOT, ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key in _DEFAULTS:
                            self._values[key] = val
        # Load from JSON config (overrides .env)
        config_file = os.path.join(CONFIG_DIR, "app_config.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Map legacy config keys
                key_map = {
                    "cookies": "COOKIES",
                    "llm_provider": "LLM_PROVIDER",
                    "llm_api_key": "LLM_API_KEY",
                    "llm_model": "LLM_MODEL",
                    "llm_base_url": "LLM_BASE_URL",
                }
                for old_key, new_key in key_map.items():
                    if old_key in saved and saved[old_key]:
                        self._values[new_key] = saved[old_key]
            except Exception:
                pass
        # Env vars always win
        for key in _DEFAULTS:
            env_val = os.environ.get(key)
            if env_val is not None:
                self._values[key] = env_val

    def __getattr__(self, name):
        if name.startswith("_"):
            return super().__getattribute__(name)
        return self._values.get(name)

    def save_to_json(self):
        """Persist LLM/cookie config to JSON."""
        config_file = os.path.join(CONFIG_DIR, "app_config.json")
        data = {
            "cookies": self._values.get("COOKIES", ""),
            "llm_provider": self._values.get("LLM_PROVIDER", ""),
            "llm_api_key": self._values.get("LLM_API_KEY", ""),
            "llm_model": self._values.get("LLM_MODEL", ""),
            "llm_base_url": self._values.get("LLM_BASE_URL", ""),
        }
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def update(self, **kwargs):
        """Update settings and persist."""
        for key, val in kwargs.items():
            upper = key.upper()
            if upper in _DEFAULTS:
                self._values[upper] = val
        self.save_to_json()

    def get_llm_config(self):
        return {
            "provider": self._values.get("LLM_PROVIDER", ""),
            "api_key": self._values.get("LLM_API_KEY", ""),
            "model": self._values.get("LLM_MODEL", ""),
            "base_url": self._values.get("LLM_BASE_URL", ""),
        }


@lru_cache()
def _get_settings():
    return _Settings()


settings = _get_settings()

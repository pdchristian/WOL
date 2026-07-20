"""Wake-on-LAN Application - Translations Utility.

Singleton class that manages multi-language support using JSON locale files.
Fallback chain: translation → English → key string.
Supported languages: en, de, fr, es.
"""

import importlib.resources
import json
from pathlib import Path
from typing import Optional


class Translations:
    """Singleton for managing UI translations.

    Usage:
        trans = Translations()
        trans.load("de")           # Load German on startup
        label = QLabel(trans.tr("menu.file.title"))
        trans.set_language("fr")   # Switch to French at runtime
    """

    _languages = {
        "en": "English",
        "de": "Deutsch",
        "fr": "Français",
        "es": "Español",
    }

    def __init__(self):
        if not hasattr(Translations, "_instance"):
            Translations._current_language = "en"
            Translations._translations: dict = {}
            Translations._instance = self

    def __getattr__(self, name):
        # Forward all attribute access to the singleton instance
        instance = getattr(Translations, "_instance", None)
        if instance is None:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return getattr(instance, name)

    @staticmethod
    def _locale_path(filename: str) -> Path:
        """Resolve a locale JSON file path inside the wol_app package."""
        try:
            # Python 3.9+
            return importlib.resources.files("wol_app.locales").joinpath(filename)
        except AttributeError:
            # Fallback for older Python versions
            return Path(__file__).parent / "locales" / filename

    def load(self, language: str) -> None:
        """Load the locale file for *language* (falls back to English)."""
        Translations._current_language = language
        locale_file = self._locale_path(f"{language}.json")
        try:
            text = locale_file.read_text(encoding="utf-8")
            Translations._translations = json.loads(text)
        except FileNotFoundError:
            # Fall back to English if requested locale is missing
            fallback = self._locale_path("en.json")
            Translations._translations = json.loads(
                fallback.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            Translations._translations = {}

    @staticmethod
    def tr(key: str, **format_kwargs) -> str:
        """Return the translated string for *key*.

        Fallback chain:
        1. Current language translation
        2. English translation (if current language is not English)
        3. The key string itself

        Supports ``.format()``-style placeholders via keyword arguments, e.g.:
            Translations.tr("status.waking_device", device_name="PC")
        """
        value = Translations._translations.get(key)

        # Fallback to English if key not found and current language is not English
        if value is None and Translations._current_language != "en":
            try:
                en_locale = Path(__file__).parent / "locales" / "en.json"
                en_translations = json.loads(en_locale.read_text(encoding="utf-8"))
                value = en_translations.get(key)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        # Final fallback: return the key itself
        if value is None:
            return key

        # Apply any format placeholders passed as keyword arguments
        if format_kwargs:
            value = value.format(**format_kwargs)

        return value

    @staticmethod
    def set_language(language: str) -> None:
        """Switch the active language at runtime (reloads locale file)."""
        Translations._current_language = language
        locale_file = Path(__file__).parent / "locales" / f"{language}.json"
        try:
            text = locale_file.read_text(encoding="utf-8")
            Translations._translations = json.loads(text)
        except FileNotFoundError:
            # Fall back to English if requested locale is missing
            fallback = Path(__file__).parent / "locales" / "en.json"
            Translations._translations = json.loads(
                fallback.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            Translations._translations = {}

    @staticmethod
    def get_language() -> str:
        """Return the current language code."""
        return Translations._current_language

    @staticmethod
    def available_languages() -> dict:
        """Return ``{code: native_name}`` for all supported languages."""
        return Translations._languages.copy()

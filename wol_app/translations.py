"""Wake-on-LAN Application - Translations Utility.

Singleton class that manages multi-language support using JSON locale files.
Fallback chain: translation → English → key string.
Supported languages: en, de, fr, es.
"""

import importlib.resources
import json
from pathlib import Path
from typing import Any, Self


class Translations:
    """Singleton for managing UI translations.

    Usage:
        trans = Translations()
        trans.load("de")           # Load German on startup
        label = QLabel(trans.tr("menu.file.title"))
        trans.set_language("fr")   # Switch to French at runtime
    """

    _languages: dict[str, str] = {
        "en": "English",
        "de": "Deutsch",
        "fr": "Français",
        "es": "Español",
    }

    def __init__(self) -> None:
        if not hasattr(Translations, "_instance"):
            Translations._current_language = "en"
            Translations._translations: dict = {}
            Translations._english_translations: dict = {}
            Translations._instance: Self = self

    def __getattr__(self, name):
        # Forward all attribute access to the singleton instance
        instance: Any | None = getattr(Translations, "_instance", None)
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

    @staticmethod
    def _load_locale_dict(filename: str) -> dict:
        """Load a locale JSON file into a dict."""
        locale_file: Path = Translations._locale_path(filename)
        try:
            text: str = locale_file.read_text(encoding="utf-8")
            return json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def load(self, language: str) -> None:
        """Load the locale file for *language* (falls back to English).

        Also pre-loads English translations into a cache so the fallback
        in ``tr()`` never touches the disk again.
        """
        Translations._current_language: str = language

        # Pre-load English into the cache (only once per session)
        if not Translations._english_translations:
            Translations._english_translations = self._load_locale_dict("en.json")

        # Load the requested locale
        if language == "en":
            Translations._translations = Translations._english_translations.copy()
        else:
            locale_dict = self._load_locale_dict(f"{language}.json")
            if locale_dict:
                Translations._translations = locale_dict
            else:
                # Fall back to English if requested locale is missing
                Translations._translations = Translations._english_translations.copy()

    @staticmethod
    def tr(key: str, **format_kwargs) -> str:
        """Return the translated string for *key*.

        Fallback chain:
        1. Current language translation
        2. Cached English translation (if current language is not English)
        3. The key string itself

        Supports ``.format()``-style placeholders via keyword arguments, e.g.:
            Translations.tr("status.waking_device", device_name="PC")
        """
        value = Translations._translations.get(key)

        # Fallback to cached English if key not found and current language is not English
        if value is None and Translations._current_language != "en":
            value = Translations._english_translations.get(key)

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
        Translations._current_language: str = language

        # Ensure English is cached
        if not Translations._english_translations:
            Translations._english_translations = Translations._load_locale_dict("en.json")

        if language == "en":
            Translations._translations = Translations._english_translations.copy()
        else:
            locale_dict = Translations._load_locale_dict(f"{language}.json")
            if locale_dict:
                Translations._translations = locale_dict
            else:
                Translations._translations = Translations._english_translations.copy()

    @staticmethod
    def get_language() -> str:
        """Return the current language code."""
        return Translations._current_language

    @staticmethod
    def available_languages() -> dict:
        """Return ``{code: native_name}`` for all supported languages."""
        return Translations._languages.copy()

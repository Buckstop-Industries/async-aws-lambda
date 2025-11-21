"""
Settings management for Lambda functions using Pydantic.

This module provides type-safe configuration management with environment variable support.
Requires pydantic and pydantic-settings to be installed.
"""

from functools import lru_cache
from typing import Any
from typing import TypeVar

try:
    from pydantic_settings import BaseSettings
except ImportError as e:
    raise ImportError(
        "Configuration support requires 'pydantic' and 'pydantic-settings'. "
        "Install with: pip install async-aws-lambda[config]"
    ) from e

T = TypeVar("T", bound=BaseSettings)


class Settings(BaseSettings):
    """
    Base settings class for Lambda functions.

    Extend this class to define your configuration schema with type hints.
    Settings are automatically loaded from environment variables.

    Example:
        class MySettings(Settings):
            DATABASE_URL: str
            API_KEY: str
            DEBUG: bool = False

        settings = MySettings()
    """

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",  # Allow extra .env fields
    }


@lru_cache
def get_settings(settings_class: type[T] = Settings) -> T:
    """
    Get cached settings instance.

    Settings are cached to avoid re-reading environment variables on every call.

    Args:
        settings_class: Settings class to instantiate (default: Settings)

    Returns:
        Cached settings instance

    Example:
        class AppSettings(Settings):
            API_KEY: str

        settings = get_settings(AppSettings)
    """
    return settings_class()


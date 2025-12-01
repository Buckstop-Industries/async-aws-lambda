"""
Settings management for Lambda functions using Pydantic.

This module provides type-safe configuration management with environment variable support.
Requires pydantic and pydantic-settings to be installed.
"""

from functools import lru_cache
from typing import Any, TypeVar

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

    This class extends Pydantic's BaseSettings to provide type-safe configuration
    management for Lambda functions. Settings are automatically loaded from
    environment variables, with support for .env files and type validation.

    Features:
        - Type-safe configuration with Pydantic validation
        - Automatic environment variable loading
        - Support for .env files
        - Type coercion and validation
        - Case-sensitive field names

    Attributes:
        model_config: Pydantic model configuration:
            - env_file: ".env" - Load from .env file if present
            - env_file_encoding: "utf-8" - Encoding for .env file
            - case_sensitive: True - Environment variable names are case-sensitive
            - extra: "ignore" - Ignore extra fields in .env file

    Note:
        - Extend this class to define your configuration schema
        - Use type hints for automatic type coercion
        - Provide default values for optional settings
        - Required fields without defaults will raise ValidationError if missing

    Example:
        Basic settings class::

            class MySettings(Settings):
                DATABASE_URL: str  # Required
                API_KEY: str        # Required
                DEBUG: bool = False  # Optional with default

            # Load from environment variables
            settings = MySettings()
            # Or use with @with_config decorator

        With validation::

            from pydantic import Field

            class AppSettings(Settings):
                DATABASE_URL: str = Field(..., min_length=10)
                PORT: int = Field(default=8080, ge=1, le=65535)
                DEBUG: bool = False

        Environment variables::

            # Set environment variables
            export DATABASE_URL="postgresql://localhost/db"
            export API_KEY="secret-key"
            export DEBUG="true"  # Automatically converted to bool

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

    This function returns a cached instance of the specified settings class.
    Settings are cached per class to avoid re-reading environment variables
    on every call, which improves performance in Lambda functions.

    Args:
        settings_class: Settings class to instantiate. Must be a subclass of
            Settings (which extends pydantic_settings.BaseSettings). Defaults
            to Settings if not provided.

    Returns:
        Cached settings instance of the specified class. The same instance is
        returned for subsequent calls with the same settings_class.

    Raises:
        ValidationError: If required settings fields are missing or invalid.
            This is raised by Pydantic during settings instantiation.

    Note:
        - Settings are cached per class using functools.lru_cache
        - Each settings class gets its own cached instance
        - Cache is cleared when the process restarts (new Lambda invocation)
        - Environment variables are read once per settings class

    Example:
        Get default settings::

            settings = get_settings()  # Uses Settings class
            assert isinstance(settings, Settings)

        Get custom settings::

            class AppSettings(Settings):
                API_KEY: str
                DEBUG: bool = False

            settings1 = get_settings(AppSettings)
            settings2 = get_settings(AppSettings)
            assert settings1 is settings2  # Same cached instance

        Different classes get different instances::

            class Settings1(Settings):
                pass

            class Settings2(Settings):
                pass

            s1 = get_settings(Settings1)
            s2 = get_settings(Settings2)
            assert s1 is not s2  # Different instances
    """
    return settings_class()

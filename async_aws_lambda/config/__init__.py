"""
Configuration management for Lambda functions.

This module provides optional configuration management with support for:
- Environment-based configuration
- AWS Secrets Manager integration
- Type-safe settings classes via Pydantic
"""

# Try to import config functionality (requires pydantic)
try:
    from .settings import Settings, get_settings
    from .secrets import get_secret_from_aws, SecretsBackend

    HAS_CONFIG = True
    __all__ = [
        "Settings",
        "get_settings",
        "get_secret_from_aws",
        "SecretsBackend",
    ]
except ImportError:
    HAS_CONFIG = False
    __all__ = []


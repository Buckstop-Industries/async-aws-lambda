"""
AWS Secrets Manager integration for Lambda configuration.

This module provides utilities for fetching secrets from AWS Secrets Manager.
Requires boto3 to be installed.
"""

import json
import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)


class SecretError(Exception):
    """Base exception for secret-related errors."""

    pass


class SecretNotFoundError(SecretError):
    """Raised when a secret is not found in AWS Secrets Manager."""

    pass


class SecretAccessError(SecretError):
    """Raised when there's an error accessing AWS Secrets Manager."""

    pass


try:
    import boto3.session
    from botocore.exceptions import ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class SecretsBackend(Protocol):
    """
    Protocol for secrets backend implementations.

    Allows custom secrets backends (AWS Secrets Manager, HashiCorp Vault, etc.)
    """

    def get_secret(self, secret_name: str, key: str | None = None) -> str:
        """
        Get secret value from backend.

        Args:
            secret_name: Name/identifier of the secret
            key: Optional key within the secret (if secret contains JSON)

        Returns:
            Secret value as string
        """
        ...


def get_secret_from_aws(
    secret_name: str, key: str | None = None, region_name: str | None = None
) -> str:
    """
    Get secret value from AWS Secrets Manager using boto3.

    This function retrieves secrets from AWS Secrets Manager. It supports both
    simple string secrets and JSON secrets (where you can extract specific keys).
    Secrets are retrieved synchronously and should be used during Lambda
    initialization, not in the handler itself for performance.

    Features:
        - Retrieve simple string secrets
        - Extract keys from JSON secrets
        - Automatic region detection from AWS_REGION environment variable
        - Proper error handling with custom exceptions
        - IAM permission error detection

    Args:
        secret_name: Name or ARN of the secret in AWS Secrets Manager.
            This is the identifier used when creating the secret in AWS.
        key: Optional key within a JSON secret. If the secret contains JSON
            and this parameter is provided, the function will parse the JSON
            and return the value of the specified key. If the key doesn't
            exist, raises SecretNotFoundError.
        region_name: AWS region where the secret is stored. Defaults to the
            AWS_REGION environment variable if set, otherwise defaults to
            "us-east-1". The region must match where the secret was created.

    Returns:
        Secret value as string. For JSON secrets with a key specified, returns
        the string representation of the key's value.

    Raises:
        ImportError: If boto3 is not installed. Install with:
            pip install async-aws-lambda[aws]
        ValueError: If secret_name is empty.
        SecretNotFoundError: If the secret is not found in AWS Secrets Manager
            or if a specified key doesn't exist in a JSON secret.
        SecretAccessError: If there's an error accessing AWS Secrets Manager,
            such as:
            - AccessDeniedException: Missing IAM permissions
            - Other AWS API errors
            - Invalid JSON when key is specified
        json.JSONDecodeError: If the secret contains invalid JSON when key is
            specified (wrapped in SecretAccessError).

    Note:
        - Requires IAM permissions: secretsmanager:GetSecretValue
        - Secrets are retrieved synchronously - consider caching for performance
        - Region must match where the secret was created
        - For Lambda functions, ensure the execution role has Secrets Manager
          permissions

    Example:
        Get simple string secret::

            api_key = get_secret_from_aws("myapp/api-key")
            # Returns: "your-api-key-here"

        Get key from JSON secret::

            # Secret contains: {"url": "postgresql://...", "password": "secret"}
            database_url = get_secret_from_aws("myapp/database", key="url")
            # Returns: "postgresql://..."

        Specify region::

            secret = get_secret_from_aws(
                "myapp/secret",
                region_name="us-west-2"
            )

        Use in settings initialization::

            from async_aws_lambda.config import Settings, get_secret_from_aws

            class AppSettings(Settings):
                DATABASE_URL: str
                API_KEY: str

            # Load DATABASE_URL from secret
            database_url = get_secret_from_aws("myapp/database-url", key="url")
            os.environ["DATABASE_URL"] = database_url

            settings = AppSettings()

        Error handling::

            try:
                secret = get_secret_from_aws("myapp/secret")
            except SecretNotFoundError:
                logger.error("Secret not found")
            except SecretAccessError as e:
                logger.error(f"Access error: {e}")
    """
    if not HAS_BOTO3:
        raise ImportError(
            "AWS Secrets Manager support requires 'boto3'. "
            "Install with: pip install async-aws-lambda[aws]"
        )

    if not secret_name:
        raise ValueError("secret_name cannot be empty")

    try:
        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(
            service_name="secretsmanager",
            region_name=region_name or os.environ.get("AWS_REGION", "us-east-1"),
        )

        # Get the secret value
        response = client.get_secret_value(SecretId=secret_name)
        secret_value = response.get("SecretString", "")

        if not secret_value:
            raise SecretNotFoundError(
                f"Secret '{secret_name}' exists but contains no SecretString value"
            )

        if key:
            # If key is specified, parse JSON and extract the key
            try:
                secret_data = json.loads(secret_value)
                key_value = secret_data.get(key)
                if key_value is None:
                    raise SecretNotFoundError(
                        f"Key '{key}' not found in secret '{secret_name}' JSON"
                    )
                return str(key_value)
            except json.JSONDecodeError as e:
                raise SecretAccessError(
                    f"Secret '{secret_name}' contains invalid JSON: {e}"
                ) from e
        else:
            return str(secret_value)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(
            f"Error fetching secret {secret_name}: {error_code} - {error_message}"
        )

        if error_code == "ResourceNotFoundException":
            raise SecretNotFoundError(
                f"Secret '{secret_name}' not found in AWS Secrets Manager"
            ) from e
        elif error_code == "AccessDeniedException":
            raise SecretAccessError(
                f"Access denied when fetching secret '{secret_name}'. "
                "Check IAM permissions."
            ) from e
        else:
            raise SecretAccessError(
                f"Error accessing secret '{secret_name}': {error_code} - "
                f"{error_message}"
            ) from e
    except (SecretNotFoundError, SecretAccessError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching secret {secret_name}: {e}")
        raise SecretAccessError(
            f"Unexpected error fetching secret '{secret_name}': {e}"
        ) from e

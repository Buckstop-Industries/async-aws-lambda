"""
AWS Secrets Manager integration for Lambda configuration.

This module provides utilities for fetching secrets from AWS Secrets Manager.
Requires boto3 to be installed.
"""

import json
import os
from typing import Any, Protocol

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

    Args:
        secret_name: Name of the secret in AWS Secrets Manager
        key: Optional key within the JSON secret (if secret contains JSON)
        region_name: AWS region (defaults to AWS_REGION env var or us-east-1)

    Returns:
        Secret value as string, or empty string if error

    Example:
        database_url = get_secret_from_aws("myapp/database-url", key="url")
        api_key = get_secret_from_aws("myapp/api-key")
    """
    if not HAS_BOTO3:
        raise ImportError(
            "AWS Secrets Manager support requires 'boto3'. "
            "Install with: pip install async-aws-lambda[aws]"
        )

    if not secret_name:
        return ""

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

        if key and secret_value:
            # If key is specified, parse JSON and extract the key
            try:
                secret_data = json.loads(secret_value)
                return str(secret_data.get(key, ""))
            except json.JSONDecodeError:
                return str(secret_value)
        else:
            return str(secret_value)

    except ClientError as e:
        # Log error but don't raise - return empty string
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching secret {secret_name}: {e}")
        return ""
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error fetching secret {secret_name}: {e}")
        return ""

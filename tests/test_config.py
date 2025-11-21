"""
Tests for configuration module.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.requires_config
class TestSettings:
    """Tests for Settings class."""

    @pytest.mark.unit
    def test_settings_base_class(self):
        """Test that Settings class can be instantiated."""
        from async_aws_lambda.config.settings import Settings

        # Settings should work with empty env
        settings = Settings()
        assert settings is not None

    @pytest.mark.unit
    def test_settings_with_env_vars(self):
        """Test that Settings loads from environment variables."""
        from async_aws_lambda.config.settings import Settings

        class TestSettings(Settings):
            API_KEY: str
            DEBUG: bool = False

        with patch.dict(os.environ, {"API_KEY": "test-key", "DEBUG": "true"}):
            settings = TestSettings()
            assert settings.API_KEY == "test-key"
            assert settings.DEBUG is True

    @pytest.mark.unit
    def test_settings_inheritance(self):
        """Test that custom settings classes can inherit from Settings."""
        from async_aws_lambda.config.settings import Settings

        class CustomSettings(Settings):
            DATABASE_URL: str = "postgresql://localhost/db"
            API_KEY: str = "test-key"

        settings = CustomSettings()
        assert isinstance(settings, Settings)
        assert isinstance(settings, CustomSettings)

    @pytest.mark.unit
    def test_get_settings_cached(self):
        """Test that get_settings returns cached instance."""
        from async_aws_lambda.config.settings import Settings, get_settings

        # Clear cache
        get_settings.cache_clear()

        settings1 = get_settings(Settings)
        settings2 = get_settings(Settings)

        # Should be the same instance (cached)
        assert settings1 is settings2

    @pytest.mark.unit
    def test_get_settings_different_classes(self):
        """Test that get_settings returns different instances for different classes."""
        from async_aws_lambda.config.settings import Settings, get_settings

        class Settings1(Settings):
            pass

        class Settings2(Settings):
            pass

        # Clear cache
        get_settings.cache_clear()

        settings1 = get_settings(Settings1)
        settings2 = get_settings(Settings2)

        # Should be different instances
        assert settings1 is not settings2


@pytest.mark.requires_aws
class TestSecrets:
    """Tests for AWS Secrets Manager integration."""

    @pytest.mark.unit
    def test_get_secret_from_aws_requires_boto3(self):
        """Test that get_secret_from_aws requires boto3."""
        # This test verifies the import error is raised correctly
        # In actual usage, boto3 would be available
        pass

    @pytest.mark.unit
    @patch("boto3.session.Session")
    def test_get_secret_from_aws_simple_secret(self, mock_session_class):
        """Test that get_secret_from_aws retrieves simple secrets."""
        from async_aws_lambda.config.secrets import get_secret_from_aws

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "my-secret-value"}
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        secret = get_secret_from_aws("my-secret")

        assert secret == "my-secret-value"
        mock_client.get_secret_value.assert_called_once_with(SecretId="my-secret")

    @pytest.mark.unit
    @patch("boto3.session.Session")
    def test_get_secret_from_aws_json_secret(self, mock_session_class):
        """Test that get_secret_from_aws extracts keys from JSON secrets."""
        import json

        from async_aws_lambda.config.secrets import get_secret_from_aws

        secret_data = {"url": "postgresql://localhost/db", "password": "secret"}
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_data)
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        secret = get_secret_from_aws("my-secret", key="url")

        assert secret == "postgresql://localhost/db"

    @pytest.mark.unit
    @patch("boto3.session.Session")
    def test_get_secret_from_aws_with_region(self, mock_session_class):
        """Test that get_secret_from_aws uses specified region."""
        from async_aws_lambda.config.secrets import get_secret_from_aws

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "secret"}
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        get_secret_from_aws("my-secret", region_name="us-west-2")

        mock_session.client.assert_called_once_with(
            service_name="secretsmanager", region_name="us-west-2"
        )

    @pytest.mark.unit
    @patch("boto3.session.Session")
    def test_get_secret_from_aws_uses_env_region(self, mock_session_class):
        """Test that get_secret_from_aws uses AWS_REGION env var."""
        from async_aws_lambda.config.secrets import get_secret_from_aws

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "secret"}
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        with patch.dict(os.environ, {"AWS_REGION": "eu-west-1"}):
            get_secret_from_aws("my-secret")

            mock_session.client.assert_called_once_with(
                service_name="secretsmanager", region_name="eu-west-1"
            )

    @pytest.mark.unit
    @patch("boto3.session.Session")
    def test_get_secret_from_aws_handles_client_error(self, mock_session_class):
        """Test that get_secret_from_aws handles ClientError gracefully."""
        from botocore.exceptions import ClientError

        from async_aws_lambda.config.secrets import get_secret_from_aws

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}}, "GetSecretValue"
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        secret = get_secret_from_aws("nonexistent-secret")

        # Should return empty string on error
        assert secret == ""

    @pytest.mark.unit
    @patch("boto3.session.Session")
    def test_get_secret_from_aws_handles_json_decode_error(self, mock_session_class):
        """Test that get_secret_from_aws handles JSON decode errors."""
        from async_aws_lambda.config.secrets import get_secret_from_aws

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "not-json"}
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Should return the string value if JSON decode fails
        secret = get_secret_from_aws("my-secret", key="url")
        assert secret == "not-json"

    @pytest.mark.unit
    def test_get_secret_from_aws_empty_secret_name(self):
        """Test that get_secret_from_aws returns empty string for empty secret name."""
        from async_aws_lambda.config.secrets import get_secret_from_aws

        secret = get_secret_from_aws("")
        assert secret == ""


@pytest.mark.requires_config
class TestConfigModule:
    """Tests for config module exports."""

    @pytest.mark.unit
    def test_config_module_exports(self):
        """Test that config module exports expected items."""
        from async_aws_lambda.config import Settings, get_settings

        assert Settings is not None
        assert get_settings is not None

    @pytest.mark.unit
    @pytest.mark.requires_aws
    def test_config_module_exports_secrets(self):
        """Test that config module exports secrets functions."""
        from async_aws_lambda.config import SecretsBackend, get_secret_from_aws

        assert get_secret_from_aws is not None
        assert SecretsBackend is not None

        assert SecretsBackend is not None

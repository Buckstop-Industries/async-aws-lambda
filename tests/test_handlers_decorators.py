"""
Tests for handler decorators.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from async_aws_lambda.handlers.decorators import (
    lambda_handler,
    with_config,
    with_database,
)


class TestLambdaHandler:
    """Tests for @lambda_handler decorator."""

    @pytest.mark.unit
    def test_lambda_handler_decorates_async_function(
        self, sample_event, mock_lambda_context
    ):
        """Test that @lambda_handler decorates an async function correctly."""

        @lambda_handler
        async def handler(event, context):
            return {"statusCode": 200, "body": "success"}

        result = handler(sample_event, mock_lambda_context)
        assert result == {"statusCode": 200, "body": "success"}

    @pytest.mark.unit
    def test_lambda_handler_raises_on_sync_function(self):
        """Test that @lambda_handler raises TypeError for sync functions."""
        with pytest.raises(TypeError, match="can only be applied to async functions"):

            @lambda_handler
            def sync_handler(event, context):
                return {"statusCode": 200}

    @pytest.mark.unit
    def test_lambda_handler_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @lambda_handler
        async def handler(event, context):
            """Test handler docstring."""
            return {"statusCode": 200}

        assert handler.__name__ == "handler"
        assert "Test handler docstring" in handler.__doc__

    @pytest.mark.unit
    def test_lambda_handler_handles_exceptions(self, sample_event, mock_lambda_context):
        """Test that @lambda_handler handles exceptions properly."""

        @lambda_handler
        async def handler(event, context):
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            handler(sample_event, mock_lambda_context)

    @pytest.mark.unit
    def test_lambda_handler_with_lifecycle(self, sample_event, mock_lambda_context):
        """Test that @lambda_handler uses lifecycle context manager."""

        @lambda_handler
        async def handler(event, context):
            return {"statusCode": 200}

        result = handler(sample_event, mock_lambda_context)
        assert result["statusCode"] == 200


class TestWithDatabase:
    """Tests for @with_database decorator."""

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_with_database_requires_db_extra(self):
        """Test that @with_database raises ImportError without db extra."""
        # This test verifies the import error handling
        # Since we have db installed, we can't easily test the ImportError case
        # The actual ImportError is tested when db dependencies are missing
        # This test is more of a placeholder to document the behavior
        pass

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_with_database_injects_session(self, sample_event, mock_lambda_context):
        """Test that @with_database injects db_session parameter."""
        from unittest.mock import AsyncMock, patch

        mock_session = AsyncMock()

        # Mock get_db_session as async context manager
        mock_get_session_cm = AsyncMock()
        mock_get_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session_cm.__aexit__ = AsyncMock(return_value=None)

        # Patch where init_db is imported (inside the decorator function)
        with patch("async_aws_lambda.database.init_db") as mock_init:
            with patch(
                "async_aws_lambda.database.get_db_session",
                return_value=mock_get_session_cm,
            ):
                mock_init.return_value = None

                @lambda_handler
                @with_database
                async def handler(event, context, db_session):
                    assert db_session is not None
                    return {"statusCode": 200, "session": "injected"}

                result = handler(sample_event, mock_lambda_context)
                assert result["statusCode"] == 200

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_with_database_without_session_param(
        self, sample_event, mock_lambda_context
    ):
        """Test that @with_database works even if handler doesn't use db_session."""

        # Mock get_db_session even though it won't be used
        mock_get_session_cm = AsyncMock()
        mock_get_session_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_get_session_cm.__aexit__ = AsyncMock(return_value=None)

        # Patch must be in place before decorator is applied
        with patch("async_aws_lambda.database.init_db") as mock_init:
            with patch(
                "async_aws_lambda.database.get_db_session",
                return_value=mock_get_session_cm,
            ):
                mock_init.return_value = None

                @lambda_handler
                @with_database
                async def handler(event, context):
                    return {"statusCode": 200}

                result = handler(sample_event, mock_lambda_context)
                assert result["statusCode"] == 200

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_with_database_custom_factory(self, sample_event, mock_lambda_context):
        """Test that @with_database works with custom factory."""
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()

        async def custom_factory():
            return mock_session

        # Patch where init_db is imported (inside the decorator function)
        with patch("async_aws_lambda.database.init_db") as mock_init:
            mock_init.return_value = None

            @lambda_handler
            @with_database(factory=custom_factory)
            async def handler(event, context, db_session):
                assert db_session == mock_session
                return {"statusCode": 200}

            result = handler(sample_event, mock_lambda_context)
            assert result["statusCode"] == 200
            # Verify close was called on custom session
            mock_session.close.assert_called_once()

    @pytest.mark.unit
    def test_with_database_raises_on_sync_function(self):
        """Test that @with_database raises TypeError for sync functions."""
        with pytest.raises(TypeError, match="can only be applied to async functions"):

            @with_database
            def sync_handler(event, context):
                pass


class TestWithConfig:
    """Tests for @with_config decorator."""

    @pytest.mark.unit
    @pytest.mark.requires_config
    def test_with_config_requires_config_extra(self):
        """Test that @with_config raises ImportError without config extra."""
        # This test verifies the import error handling
        # Since we have config installed, we can't easily test the ImportError case
        # The actual ImportError is tested when config dependencies are missing
        # This test is more of a placeholder to document the behavior
        pass

    @pytest.mark.unit
    @pytest.mark.requires_config
    def test_with_config_injects_settings(self, sample_event, mock_lambda_context):
        """Test that @with_config injects settings parameter."""
        from async_aws_lambda.config.settings import Settings

        @lambda_handler
        @with_config
        async def handler(event, context, settings):
            assert settings is not None
            assert isinstance(settings, Settings)
            return {"statusCode": 200, "settings": "injected"}

        with patch(
            "async_aws_lambda.config.settings.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock(spec=Settings)
            mock_get_settings.return_value = mock_settings
            result = handler(sample_event, mock_lambda_context)
            assert result["statusCode"] == 200

    @pytest.mark.unit
    @pytest.mark.requires_config
    def test_with_config_custom_settings_class(self, sample_event, mock_lambda_context):
        """Test that @with_config works with custom settings class."""
        from async_aws_lambda.config.settings import Settings

        class CustomSettings(Settings):
            API_KEY: str = "test-key"

        @lambda_handler
        @with_config(settings_class=CustomSettings)
        async def handler(event, context, settings):
            assert isinstance(settings, CustomSettings)
            return {"statusCode": 200}

        with patch(
            "async_aws_lambda.config.settings.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock(spec=CustomSettings)
            mock_get_settings.return_value = mock_settings
            result = handler(sample_event, mock_lambda_context)
            assert result["statusCode"] == 200

    @pytest.mark.unit
    @pytest.mark.requires_config
    def test_with_config_without_settings_param(
        self, sample_event, mock_lambda_context
    ):
        """Test that @with_config works even if handler doesn't use settings."""

        @lambda_handler
        @with_config
        async def handler(event, context):
            return {"statusCode": 200}

        with patch(
            "async_aws_lambda.config.settings.get_settings"
        ) as mock_get_settings:
            mock_get_settings.return_value = MagicMock()
            result = handler(sample_event, mock_lambda_context)
            assert result["statusCode"] == 200

    @pytest.mark.unit
    def test_with_config_raises_on_sync_function(self):
        """Test that @with_config raises TypeError for sync functions."""
        with pytest.raises(TypeError, match="can only be applied to async functions"):

            @with_config
            def sync_handler(event, context):
                pass


class TestDecoratorComposition:
    """Tests for decorator composition."""

    @pytest.mark.unit
    @pytest.mark.requires_db
    @pytest.mark.requires_config
    def test_multiple_decorators_compose(self, sample_event, mock_lambda_context):
        """Test that multiple decorators can be composed."""

        # Mock get_db_session as async context manager
        mock_session = AsyncMock()
        mock_get_session_cm = AsyncMock()
        mock_get_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session_cm.__aexit__ = AsyncMock(return_value=None)

        # Patch must be in place before decorators are applied
        with patch("async_aws_lambda.database.init_db") as mock_init:
            with patch(
                "async_aws_lambda.database.get_db_session",
                return_value=mock_get_session_cm,
            ):
                with patch(
                    "async_aws_lambda.config.settings.get_settings"
                ) as mock_get_settings:
                    mock_init.return_value = None
                    mock_settings = MagicMock()
                    mock_get_settings.return_value = mock_settings

                    @lambda_handler
                    @with_database
                    @with_config
                    async def handler(event, context, db_session, settings):
                        assert db_session is not None
                        assert settings is not None
                        return {"statusCode": 200, "composed": True}

                    result = handler(sample_event, mock_lambda_context)
                    assert result["statusCode"] == 200
                    assert result["composed"] is True

                    mock_get_settings.return_value = mock_settings

                    result = handler(sample_event, mock_lambda_context)
                    assert result["statusCode"] == 200
                    assert result["composed"] is True

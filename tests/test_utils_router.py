"""
Tests for router utility.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from async_aws_lambda.utils.router import handler


class TestRouter:
    """Tests for Lambda function router."""

    @pytest.mark.unit
    def test_router_requires_function_id(self, sample_event, mock_lambda_context):
        """Test that router requires LAMBDA_FUNCTION_ID environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="LAMBDA_FUNCTION_ID"):
                handler(sample_event, mock_lambda_context)

    @pytest.mark.unit
    @patch("importlib.import_module")
    def test_router_imports_handler_module(
        self, mock_import, sample_event, mock_lambda_context
    ):
        """Test that router imports the correct handler module."""
        mock_module = MagicMock()
        mock_handler = MagicMock(return_value={"statusCode": 200})
        mock_module.handler = mock_handler
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"LAMBDA_FUNCTION_ID": "my_function"}):
            result = handler(sample_event, mock_lambda_context)

            mock_import.assert_called_once_with("my_function.handler")
            assert result == {"statusCode": 200}

    @pytest.mark.unit
    @patch("importlib.import_module")
    def test_router_raises_on_missing_handler_attribute(
        self, mock_import, sample_event, mock_lambda_context
    ):
        """Test that router raises AttributeError if module lacks handler attribute."""
        mock_module = MagicMock()
        del mock_module.handler  # Remove handler attribute
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"LAMBDA_FUNCTION_ID": "my_function"}):
            with pytest.raises(
                AttributeError, match="does not have a 'handler' attribute"
            ):
                handler(sample_event, mock_lambda_context)

    @pytest.mark.unit
    @patch("importlib.import_module")
    def test_router_raises_on_import_error(
        self, mock_import, sample_event, mock_lambda_context
    ):
        """Test that router raises ImportError if module cannot be imported."""
        mock_import.side_effect = ImportError("No module named 'my_function'")

        with patch.dict(os.environ, {"LAMBDA_FUNCTION_ID": "my_function"}):
            with pytest.raises(
                ImportError, match="Lambda function 'my_function' not found"
            ):
                handler(sample_event, mock_lambda_context)

    @pytest.mark.unit
    @patch("importlib.import_module")
    def test_router_calls_handler_with_event_and_context(
        self, mock_import, sample_event, mock_lambda_context
    ):
        """Test that router calls handler with event and context."""
        mock_module = MagicMock()
        mock_handler = MagicMock(return_value={"statusCode": 200})
        mock_module.handler = mock_handler
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"LAMBDA_FUNCTION_ID": "my_function"}):
            handler(sample_event, mock_lambda_context)

            mock_handler.assert_called_once_with(sample_event, mock_lambda_context)

    @pytest.mark.unit
    @patch("importlib.import_module")
    def test_router_validates_handler_protocol(
        self, mock_import, sample_event, mock_lambda_context
    ):
        """Test that router validates handler implements LambdaHandler protocol."""
        from async_aws_lambda.handlers.protocols import LambdaHandler

        mock_module = MagicMock()

        # Create a handler that implements the protocol
        def valid_handler(event, context):
            return {"statusCode": 200}

        mock_module.handler = valid_handler
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"LAMBDA_FUNCTION_ID": "my_function"}):
            result = handler(sample_event, mock_lambda_context)
            assert result == {"statusCode": 200}

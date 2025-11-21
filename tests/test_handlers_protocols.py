"""
Tests for Lambda handler protocols.
"""

import pytest

from async_aws_lambda.handlers.protocols import (
    AsyncLambdaHandler,
    DatabaseFactory,
    LambdaHandler,
)


class TestLambdaHandlerProtocol:
    """Tests for LambdaHandler protocol."""

    @pytest.mark.unit
    def test_lambda_handler_protocol_implementation(self):
        """Test that a function implementing LambdaHandler protocol is recognized."""

        def handler(event, context):
            return {"statusCode": 200}

        assert isinstance(handler, LambdaHandler)

    @pytest.mark.unit
    def test_lambda_handler_protocol_runtime_check(self):
        """Test runtime checkable protocol."""

        class CustomHandler:
            def __call__(self, event, context):
                return {"statusCode": 200}

        handler = CustomHandler()
        assert isinstance(handler, LambdaHandler)


class TestAsyncLambdaHandlerProtocol:
    """Tests for AsyncLambdaHandler protocol."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_lambda_handler_protocol_implementation(self):
        """Test that an async function implementing AsyncLambdaHandler protocol is recognized."""

        async def handler(event, context):
            return {"statusCode": 200}

        assert isinstance(handler, AsyncLambdaHandler)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_lambda_handler_protocol_runtime_check(self):
        """Test runtime checkable protocol."""

        class CustomAsyncHandler:
            async def __call__(self, event, context):
                return {"statusCode": 200}

        handler = CustomAsyncHandler()
        assert isinstance(handler, AsyncLambdaHandler)


class TestDatabaseFactoryProtocol:
    """Tests for DatabaseFactory protocol."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_database_factory_protocol_implementation(self):
        """Test that a function implementing DatabaseFactory protocol is recognized."""

        async def factory():
            return "mock_session"

        assert isinstance(factory, DatabaseFactory)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_database_factory_protocol_runtime_check(self):
        """Test runtime checkable protocol."""

        class CustomFactory:
            async def __call__(self):
                return "mock_session"

        factory = CustomFactory()
        assert isinstance(factory, DatabaseFactory)

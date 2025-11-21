"""
Pytest configuration and shared fixtures.
"""

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_lambda_context() -> Any:
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = "test-function"
    context.function_version = "$LATEST"
    context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    )
    context.memory_limit_in_mb = 128
    context.aws_request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/test-function"
    context.log_stream_name = "2024/01/01/[$LATEST]test-stream"
    return context


@pytest.fixture
def sample_event() -> dict[str, Any]:
    """Create a sample Lambda event."""
    return {
        "httpMethod": "GET",
        "path": "/test",
        "headers": {"Content-Type": "application/json"},
        "body": None,
    }


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def reset_cleanup_handlers():
    """Reset cleanup handlers before and after tests."""
    import async_aws_lambda.handlers.lifecycle as lifecycle_module

    # Reset before test
    with lifecycle_module._cleanup_lock:
        lifecycle_module._cleanup_handlers.clear()
        lifecycle_module._cleanup_registered = False

    yield

    # Reset after test
    with lifecycle_module._cleanup_lock:
        lifecycle_module._cleanup_handlers.clear()
        lifecycle_module._cleanup_registered = False


@pytest.fixture(autouse=True)
def reset_database_state():
    """Reset database state before and after each test."""
    try:
        from async_aws_lambda.database import session as db_session_module

        # Reset before test
        db_session_module._initialized = False
        db_session_module._engine = None
        db_session_module._async_session_maker = None

        yield

        # Clean up after test
        db_session_module._initialized = False
        db_session_module._engine = None
        db_session_module._async_session_maker = None
    except ImportError:
        # Database module not available, skip
        yield

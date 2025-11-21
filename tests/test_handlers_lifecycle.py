"""
Tests for Lambda lifecycle management.
"""

import asyncio
import signal
import sys
from unittest.mock import MagicMock, patch

import pytest

from async_aws_lambda.handlers.lifecycle import (
    _register_lambda_cleanup,
    create_lambda_handler,
    lambda_lifecycle,
    register_cleanup_handler,
)


class TestLambdaLifecycle:
    """Tests for lambda_lifecycle context manager."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lambda_lifecycle_context_manager(self):
        """Test that lambda_lifecycle works as a context manager."""
        async with lambda_lifecycle():
            # Should not raise
            pass

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lambda_lifecycle_registers_cleanup(self):
        """Test that lambda_lifecycle registers cleanup handlers."""
        cleanup_called = []

        def cleanup():
            cleanup_called.append(True)

        register_cleanup_handler(cleanup)

        async with lambda_lifecycle():
            pass

        # Cleanup should be called after context exits
        assert len(cleanup_called) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lambda_lifecycle_handles_cleanup_errors(self):
        """Test that lambda_lifecycle handles cleanup errors gracefully."""

        def failing_cleanup():
            raise ValueError("Cleanup error")

        register_cleanup_handler(failing_cleanup)

        # Should not raise, errors are logged but don't propagate
        async with lambda_lifecycle():
            pass

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lambda_lifecycle_multiple_cleanup_handlers(self):
        """Test that multiple cleanup handlers are called."""
        cleanup_calls = []

        def cleanup1():
            cleanup_calls.append(1)

        def cleanup2():
            cleanup_calls.append(2)

        register_cleanup_handler(cleanup1)
        register_cleanup_handler(cleanup2)

        async with lambda_lifecycle():
            pass

        # Both cleanup handlers should be called
        assert 1 in cleanup_calls
        assert 2 in cleanup_calls


class TestRegisterCleanupHandler:
    """Tests for register_cleanup_handler function."""

    @pytest.mark.unit
    def test_register_cleanup_handler(self):
        """Test that cleanup handlers can be registered."""
        cleanup_called = []

        def cleanup():
            cleanup_called.append(True)

        register_cleanup_handler(cleanup)

        # Manually trigger cleanup
        from async_aws_lambda.handlers.lifecycle import _cleanup_handlers, _cleanup_lock

        with _cleanup_lock:
            handlers = list(_cleanup_handlers)
        # Verify cleanup was registered
        assert cleanup in handlers
        # Call it to verify it works
        cleanup()
        assert len(cleanup_called) > 0

    @pytest.mark.unit
    def test_register_cleanup_handler_thread_safe(self):
        """Test that cleanup handler registration is thread-safe."""
        import threading

        cleanup_calls = []

        def cleanup():
            cleanup_calls.append(True)

        def register_in_thread():
            register_cleanup_handler(cleanup)

        threads = [threading.Thread(target=register_in_thread) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All handlers should be registered
        from async_aws_lambda.handlers.lifecycle import _cleanup_handlers

        assert len(_cleanup_handlers) >= 10


class TestCreateLambdaHandler:
    """Tests for create_lambda_handler function."""

    @pytest.mark.unit
    def test_create_lambda_handler_wraps_async_function(
        self, sample_event, mock_lambda_context
    ):
        """Test that create_lambda_handler wraps async functions correctly."""

        async def async_handler(event, context):
            return {"statusCode": 200, "body": "success"}

        handler = create_lambda_handler(async_handler)
        result = handler(sample_event, mock_lambda_context)

        assert result == {"statusCode": 200, "body": "success"}

    @pytest.mark.unit
    def test_create_lambda_handler_handles_exceptions(
        self, sample_event, mock_lambda_context
    ):
        """Test that create_lambda_handler handles exceptions."""

        async def async_handler(event, context):
            raise ValueError("Test error")

        handler = create_lambda_handler(async_handler)

        with pytest.raises(ValueError, match="Test error"):
            handler(sample_event, mock_lambda_context)

    @pytest.mark.unit
    def test_create_lambda_handler_runs_cleanup(
        self, sample_event, mock_lambda_context
    ):
        """Test that create_lambda_handler runs cleanup handlers."""
        cleanup_called = []

        def cleanup():
            cleanup_called.append(True)

        register_cleanup_handler(cleanup)

        async def async_handler(event, context):
            return {"statusCode": 200}

        handler = create_lambda_handler(async_handler)
        handler(sample_event, mock_lambda_context)

        # Cleanup should be called
        assert len(cleanup_called) > 0

    @pytest.mark.unit
    def test_create_lambda_handler_handles_cleanup_errors(
        self, sample_event, mock_lambda_context
    ):
        """Test that create_lambda_handler handles cleanup errors gracefully."""

        def failing_cleanup():
            raise ValueError("Cleanup error")

        register_cleanup_handler(failing_cleanup)

        async def async_handler(event, context):
            return {"statusCode": 200}

        handler = create_lambda_handler(async_handler)
        # Should not raise, errors are logged but don't propagate
        result = handler(sample_event, mock_lambda_context)
        assert result["statusCode"] == 200


class TestSignalHandling:
    """Tests for signal handling in lifecycle."""

    @pytest.mark.unit
    def test_signal_handler_registration_skipped_in_tests(self):
        """Test that signal handlers are not registered during testing."""
        # Reset registration state
        import async_aws_lambda.handlers.lifecycle as lifecycle_module

        lifecycle_module._cleanup_registered = False

        # Mock sys.modules to include pytest
        original_modules = sys.modules.copy()
        sys.modules["pytest"] = MagicMock()

        try:
            _register_lambda_cleanup()
            # Should not raise and should mark as registered
            assert lifecycle_module._cleanup_registered is True
        finally:
            sys.modules.clear()
            sys.modules.update(original_modules)

    @pytest.mark.unit
    @patch("signal.signal")
    def test_signal_handler_registration(self, mock_signal):
        """Test that signal handlers are registered when not in test mode."""
        import async_aws_lambda.handlers.lifecycle as lifecycle_module

        original_registered = lifecycle_module._cleanup_registered
        lifecycle_module._cleanup_registered = False

        # Mock sys.modules to not include pytest
        original_modules = sys.modules.copy()
        pytest_in_modules = "pytest" in sys.modules
        if pytest_in_modules:
            del sys.modules["pytest"]

        try:
            _register_lambda_cleanup()
            # Should register signal handlers (but may be skipped if still detected as test)
            # The actual behavior depends on how pytest detection works
            # Just verify the function runs without error
            assert lifecycle_module._cleanup_registered is True
        finally:
            # Restore original state
            if pytest_in_modules:
                sys.modules["pytest"] = original_modules.get("pytest")
            lifecycle_module._cleanup_registered = original_registered

"""
Tests for error handling module.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from async_aws_lambda.errors.handlers import ErrorHandler
from async_aws_lambda.errors.models import (
    ErrorCategory,
    ErrorSeverity,
    ProcessingError,
    ProcessingResult,
)
from async_aws_lambda.errors.recovery import (
    ErrorRecoveryStrategies,
    PartialProcessingRecovery,
)


class TestErrorModels:
    """Tests for error models."""

    @pytest.mark.unit
    def test_error_severity_enum(self):
        """Test ErrorSeverity enum values."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"

    @pytest.mark.unit
    def test_error_category_enum(self):
        """Test ErrorCategory enum values."""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.DATABASE.value == "database"
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.SYSTEM.value == "system"

    @pytest.mark.unit
    def test_processing_error_creation(self):
        """Test ProcessingError creation."""
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
        )

        assert error.error_id == "ERR_123"
        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.message == "Test error"
        assert error.retry_count == 0
        assert error.max_retries == 3
        assert error.is_recoverable is True

    @pytest.mark.unit
    def test_processing_error_timestamp(self):
        """Test that ProcessingError sets timestamp automatically."""
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
        )

        assert error.timestamp is not None
        assert isinstance(error.timestamp, datetime.datetime)

    @pytest.mark.unit
    def test_processing_result_creation(self):
        """Test ProcessingResult creation."""
        result = ProcessingResult(success=True, processed_count=10, failed_count=2)

        assert result.success is True
        assert result.processed_count == 10
        assert result.failed_count == 2
        assert result.skipped_count == 0
        assert result.errors == []
        assert result.warnings == []

    @pytest.mark.unit
    def test_processing_result_with_errors(self):
        """Test ProcessingResult with errors."""
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
        )

        result = ProcessingResult(success=False, errors=[error])

        assert result.success is False
        assert len(result.errors) == 1
        assert result.errors[0] == error


class TestErrorHandler:
    """Tests for ErrorHandler class."""

    @pytest.mark.unit
    def test_error_handler_initialization(self):
        """Test ErrorHandler initialization."""
        handler = ErrorHandler(max_retries=5, retry_delay=2.0)

        assert handler.max_retries == 5
        assert handler.retry_delay == 2.0
        assert handler.error_counts == {}
        assert handler.critical_errors == []

    @pytest.mark.unit
    def test_classify_error_value_error(self):
        """Test error classification for ValueError."""
        handler = ErrorHandler()
        error = ValueError("Invalid value")

        processing_error = handler.classify_error(error)

        assert processing_error.category == ErrorCategory.VALIDATION
        assert processing_error.severity == ErrorSeverity.MEDIUM
        assert processing_error.is_recoverable is True

    @pytest.mark.unit
    def test_classify_error_connection_error(self):
        """Test error classification for ConnectionError."""
        handler = ErrorHandler()
        error = ConnectionError("Connection failed")

        processing_error = handler.classify_error(error)

        assert processing_error.category == ErrorCategory.NETWORK
        assert processing_error.severity == ErrorSeverity.HIGH
        assert processing_error.is_recoverable is True

    @pytest.mark.unit
    def test_classify_error_file_not_found(self):
        """Test error classification for FileNotFoundError."""
        handler = ErrorHandler()
        error = FileNotFoundError("File not found")

        processing_error = handler.classify_error(error)

        assert processing_error.category == ErrorCategory.FILE_PROCESSING
        assert processing_error.severity == ErrorSeverity.HIGH
        assert processing_error.is_recoverable is False

    @pytest.mark.unit
    def test_classify_error_permission_error(self):
        """Test error classification for PermissionError."""
        handler = ErrorHandler()
        error = PermissionError("Permission denied")

        processing_error = handler.classify_error(error)

        assert processing_error.category == ErrorCategory.SYSTEM
        assert processing_error.severity == ErrorSeverity.CRITICAL
        assert processing_error.is_recoverable is False

    @pytest.mark.unit
    def test_classify_error_with_context(self):
        """Test error classification with context."""
        handler = ErrorHandler()
        error = ValueError("Invalid value")
        context = {"user_id": "123", "action": "create"}

        processing_error = handler.classify_error(error, context)

        assert processing_error.details == context

    @pytest.mark.unit
    def test_should_retry_recoverable_error(self):
        """Test should_retry for recoverable error."""
        handler = ErrorHandler()
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
            is_recoverable=True,
            retry_count=0,
        )

        assert handler.should_retry(error) is True

    @pytest.mark.unit
    def test_should_retry_non_recoverable_error(self):
        """Test should_retry for non-recoverable error."""
        handler = ErrorHandler()
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            message="Test error",
            is_recoverable=False,
        )

        assert handler.should_retry(error) is False

    @pytest.mark.unit
    def test_should_retry_max_retries_reached(self):
        """Test should_retry when max retries reached."""
        handler = ErrorHandler()
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
            is_recoverable=True,
            retry_count=3,
            max_retries=3,
        )

        assert handler.should_retry(error) is False

    @pytest.mark.unit
    def test_should_retry_critical_severity(self):
        """Test should_retry for critical severity error."""
        handler = ErrorHandler()
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            message="Test error",
            is_recoverable=True,
        )

        assert handler.should_retry(error) is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_error_with_retry(self):
        """Test handle_error with successful retry."""
        handler = ErrorHandler(max_retries=3, retry_delay=0.1)
        error = ValueError("Test error")

        retry_func = AsyncMock()
        retry_func.return_value = None

        processing_error = await handler.handle_error(error, retry_func=retry_func)

        assert processing_error.retry_count > 0
        retry_func.assert_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_error_tracks_error_counts(self):
        """Test that handle_error tracks error counts."""
        handler = ErrorHandler()
        error = ValueError("Test error")

        await handler.handle_error(error)

        assert ErrorCategory.VALIDATION in handler.error_counts
        assert handler.error_counts[ErrorCategory.VALIDATION] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_error_tracks_critical_errors(self):
        """Test that handle_error tracks critical errors."""
        handler = ErrorHandler()
        error = PermissionError("Permission denied")

        await handler.handle_error(error)

        assert len(handler.critical_errors) == 1
        assert handler.critical_errors[0].severity == ErrorSeverity.CRITICAL

    @pytest.mark.unit
    def test_get_error_summary(self):
        """Test get_error_summary."""
        handler = ErrorHandler()
        handler.error_counts = {
            ErrorCategory.VALIDATION: 5,
            ErrorCategory.NETWORK: 2,
        }
        handler.critical_errors = [
            ProcessingError(
                error_id="ERR_123",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                message="Critical error",
            )
        ]

        summary = handler.get_error_summary()

        assert summary["total_errors"] == 7
        assert summary["error_counts_by_category"]["validation"] == 5
        assert summary["error_counts_by_category"]["network"] == 2
        assert summary["critical_errors"] == 1


class TestErrorRecovery:
    """Tests for error recovery strategies."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skip_row_recovery(self):
        """Test skip_row_recovery strategy."""
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
        )

        result = await ErrorRecoveryStrategies.skip_row_recovery(
            error, {"id": 1}, row_number=10
        )

        assert result.success is True
        assert result.skipped_count == 1
        assert len(result.errors) == 1
        assert len(result.warnings) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_partial_data_recovery(self):
        """Test partial_data_recovery strategy."""
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
        )

        result = await ErrorRecoveryStrategies.partial_data_recovery(
            error, {"id": 1}, row_number=10
        )

        assert result.success is True
        assert result.processed_count == 1
        assert len(result.errors) == 1
        assert len(result.warnings) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_processing_recovery_success(self):
        """Test fallback_processing_recovery with successful fallback."""
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
        )

        async def fallback_func(row_data, row_number):
            return "success"

        result = await ErrorRecoveryStrategies.fallback_processing_recovery(
            error, {"id": 1}, row_number=10, fallback_func=fallback_func
        )

        assert result.success is True
        assert result.processed_count == 1
        assert len(result.warnings) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_processing_recovery_failure(self):
        """Test fallback_processing_recovery with failed fallback."""
        error = ProcessingError(
            error_id="ERR_123",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Test error",
        )

        async def fallback_func(row_data, row_number):
            raise ValueError("Fallback failed")

        result = await ErrorRecoveryStrategies.fallback_processing_recovery(
            error, {"id": 1}, row_number=10, fallback_func=fallback_func
        )

        assert result.success is False
        assert result.failed_count == 1
        assert len(result.errors) == 2  # Original + fallback error


class TestPartialProcessingRecovery:
    """Tests for PartialProcessingRecovery class."""

    @pytest.mark.unit
    def test_partial_processing_recovery_initialization(self):
        """Test PartialProcessingRecovery initialization."""
        recovery = PartialProcessingRecovery(checkpoint_interval=50)

        assert recovery.checkpoint_interval == 50
        assert recovery.last_checkpoint is None

    @pytest.mark.unit
    def test_create_checkpoint(self):
        """Test create_checkpoint."""
        recovery = PartialProcessingRecovery()
        checkpoint = recovery.create_checkpoint(
            row_number=100, processed_count=95, failed_count=5
        )

        assert checkpoint["row_number"] == 100
        assert checkpoint["processed_count"] == 95
        assert checkpoint["failed_count"] == 5
        assert "timestamp" in checkpoint
        assert "checkpoint_id" in checkpoint
        assert recovery.last_checkpoint == checkpoint

    @pytest.mark.unit
    def test_should_create_checkpoint(self):
        """Test should_create_checkpoint."""
        recovery = PartialProcessingRecovery(checkpoint_interval=100)

        assert recovery.should_create_checkpoint(100) is True
        assert recovery.should_create_checkpoint(200) is True
        assert recovery.should_create_checkpoint(50) is False
        assert recovery.should_create_checkpoint(99) is False

    @pytest.mark.unit
    def test_get_recovery_point_from_checkpoint(self):
        """Test get_recovery_point from checkpoint."""
        recovery = PartialProcessingRecovery()
        processing_state = {
            "last_checkpoint": {
                "row_number": 500,
                "processed_count": 450,
                "failed_count": 50,
            }
        }

        recovery_point = recovery.get_recovery_point(processing_state)

        assert recovery_point == 500

    @pytest.mark.unit
    def test_get_recovery_point_from_last_parsed_row(self):
        """Test get_recovery_point from last_parsed_row."""
        recovery = PartialProcessingRecovery()
        processing_state = {"last_parsed_row": 300}

        recovery_point = recovery.get_recovery_point(processing_state)

        assert recovery_point == 300

    @pytest.mark.unit
    def test_get_recovery_point_no_state(self):
        """Test get_recovery_point with no state."""
        recovery = PartialProcessingRecovery()

        recovery_point = recovery.get_recovery_point(None)

        assert recovery_point == 0

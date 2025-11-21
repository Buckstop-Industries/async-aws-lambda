"""
Recovery strategies for error handling.
"""

import datetime
from collections.abc import Callable
import logging
import time
from typing import Any

from .models import ErrorCategory, ProcessingError, ProcessingResult

logger = logging.getLogger(__name__)


class PartialProcessingRecovery:
    """Handles partial processing recovery for large files."""

    def __init__(self, checkpoint_interval: int = 100) -> None:
        """
        Initialize recovery handler.

        Args:
            checkpoint_interval: Number of rows to process before creating checkpoint
        """
        self.checkpoint_interval = checkpoint_interval
        self.last_checkpoint: dict[str, Any] | None = None

    def create_checkpoint(
        self, row_number: int, processed_count: int, failed_count: int
    ) -> dict[str, Any]:
        """
        Create a processing checkpoint.

        Args:
            row_number: Current row number
            processed_count: Number of successfully processed rows
            failed_count: Number of failed rows

        Returns:
            Checkpoint data
        """
        checkpoint = {
            "row_number": row_number,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "checkpoint_id": f"CP_{int(time.time())}_{row_number}",
        }

        self.last_checkpoint = checkpoint
        logger.info(f"Created checkpoint at row {row_number}")
        return checkpoint

    def should_create_checkpoint(self, row_number: int) -> bool:
        """
        Determine if a checkpoint should be created.

        Args:
            row_number: Current row number

        Returns:
            True if checkpoint should be created
        """
        return row_number % self.checkpoint_interval == 0

    def get_recovery_point(self, processing_state: dict[str, Any] | None) -> int:
        """
        Get the recovery point from processing state.

        Args:
            processing_state: Current processing state

        Returns:
            Row number to resume from
        """
        if not processing_state:
            return 0

        last_checkpoint = processing_state.get("last_checkpoint")
        if last_checkpoint:
            return int(last_checkpoint.get("row_number", 0))

        return int(processing_state.get("last_parsed_row", 0))


class ErrorRecoveryStrategies:
    """Different recovery strategies for various error types."""

    @staticmethod
    async def skip_row_recovery(
        error: ProcessingError,
        row_data: dict[str, Any],  # noqa: ARG004
        row_number: int,
    ) -> ProcessingResult:
        """
        Recovery strategy: Skip the problematic row and continue.

        Args:
            error: The processing error
            row_data: Data for the problematic row
            row_number: Row number that failed

        Returns:
            ProcessingResult indicating row was skipped
        """
        logger.warning(
            f"Skipping row {row_number} due to error: {error.message}"
        )

        return ProcessingResult(
            success=True,
            skipped_count=1,
            errors=[error],
            warnings=[f"Row {row_number} skipped: {error.message}"],
        )

    @staticmethod
    async def partial_data_recovery(
        error: ProcessingError,
        row_data: dict[str, Any],  # noqa: ARG004
        row_number: int,
    ) -> ProcessingResult:
        """
        Recovery strategy: Process row with partial data.

        Args:
            error: The processing error
            row_data: Data for the problematic row
            row_number: Row number that failed

        Returns:
            ProcessingResult with partial processing
        """
        logger.warning(
            f"Processing row {row_number} with partial data due to: {error.message}"
        )

        return ProcessingResult(
            success=True,
            processed_count=1,
            errors=[error],
            warnings=[f"Row {row_number} processed with partial data"],
        )

    @staticmethod
    async def fallback_processing_recovery(
        error: ProcessingError,
        row_data: dict[str, Any],
        row_number: int,
        fallback_func: Callable[[dict[str, Any], int], Any],
    ) -> ProcessingResult:
        """
        Recovery strategy: Use fallback processing method.

        Args:
            error: The processing error
            row_data: Data for the problematic row
            row_number: Row number that failed
            fallback_func: Fallback processing function

        Returns:
            ProcessingResult from fallback processing
        """
        logger.info(f"Using fallback processing for row {row_number}")

        try:
            await fallback_func(row_data, row_number)
            return ProcessingResult(
                success=True,
                processed_count=1,
                warnings=[f"Row {row_number} processed using fallback method"],
            )
        except Exception as fallback_error:
            logger.error(f"Fallback processing also failed: {fallback_error}")
            return ProcessingResult(
                success=False,
                failed_count=1,
                errors=[
                    error,
                    ProcessingError(
                        error_id=f"FALLBACK_{int(time.time())}",
                        category=ErrorCategory.BUSINESS_LOGIC,
                        severity=error.severity,
                        message=f"Fallback processing failed: {fallback_error}",
                    ),
                ],
            )


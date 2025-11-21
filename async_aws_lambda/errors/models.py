"""
Error models and data classes for error handling.
"""

from dataclasses import dataclass
import datetime
from datetime import timedelta
from enum import Enum
from typing import Any


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    VALIDATION = "validation"
    DATABASE = "database"
    FILE_PROCESSING = "file_processing"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"


@dataclass
class ProcessingError:
    """Structured error information."""

    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: dict[str, Any] | None = None
    timestamp: datetime.datetime | None = None
    retry_count: int = 0
    max_retries: int = 3
    is_recoverable: bool = True

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.datetime.now(datetime.UTC)


@dataclass
class ProcessingResult:
    """Result of processing operation."""

    success: bool
    processed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    pending_research_count: int = 0
    errors: list[ProcessingError] | None = None
    warnings: list[str] | None = None
    processing_time: timedelta | None = None

    def __post_init__(self) -> None:
        """Initialize default values for optional fields."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


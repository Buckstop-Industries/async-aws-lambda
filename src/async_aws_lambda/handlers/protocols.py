"""
Lambda function protocols and type definitions.

This module defines the contracts that Lambda handlers must implement
for type safety and consistent behavior across the application.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LambdaHandler(Protocol):
    """
    Protocol defining the contract for Lambda function handlers.

    All Lambda handlers must implement this callable interface to ensure
    consistent behavior and type safety across the application.
    """

    def __call__(self, event: dict[str, Any], context: Any) -> dict[str, Any]:
        """
        Execute the Lambda handler with the given event and context.

        Args:
            event: The Lambda event data
            context: The Lambda context object

        Returns:
            Response dictionary with statusCode and body
        """
        ...


@runtime_checkable
class AsyncLambdaHandler(Protocol):
    """
    Protocol defining the contract for async Lambda function handlers.

    This is the protocol that user-defined handlers implement before being
    wrapped by the @lambda_handler decorator.
    """

    async def __call__(self, event: dict[str, Any], context: Any) -> dict[str, Any]:
        """
        Execute the async Lambda handler with the given event and context.

        Args:
            event: The Lambda event data
            context: The Lambda context object

        Returns:
            Response dictionary with statusCode and body
        """
        ...


@runtime_checkable
class DatabaseFactory(Protocol):
    """
    Protocol for database session factory functions.

    Used to allow custom database backends via dependency injection.
    """

    async def __call__(self) -> Any:
        """
        Create and return a database session.

        Returns:
            Database session object (typically AsyncSession)
        """
        ...

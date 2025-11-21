"""
Lambda function router that dispatches to specific handlers based on environment variable.

This module provides a router that can dispatch to different Lambda handlers based on
the LAMBDA_FUNCTION_ID environment variable. This is useful when deploying multiple
Lambda functions from a single codebase.
"""

import importlib
import os
from typing import Any

from ..handlers.protocols import LambdaHandler


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Router handler that dispatches to specific Lambda function based on LAMBDA_FUNCTION_ID
    environment variable.

    Args:
        event: Lambda event data
        context: Lambda context object

    Returns:
        Response from the routed handler

    Raises:
        ValueError: If LAMBDA_FUNCTION_ID environment variable is not set
        ImportError: If the specified handler module cannot be imported
        AttributeError: If the handler module does not have a handler attribute

    Example:
        Set LAMBDA_FUNCTION_ID environment variable:
        export LAMBDA_FUNCTION_ID=my_function

        Then the router will look for:
        - my_function.handler module
        - handler attribute in that module
    """
    function_id = os.environ.get("LAMBDA_FUNCTION_ID")

    if not function_id:
        raise ValueError("LAMBDA_FUNCTION_ID environment variable is required")

    try:
        # Import the specific function handler
        # Assuming handlers are in the same package structure
        module_name = f"{function_id}.handler"
        module = importlib.import_module(module_name)

        # Check that the module has a handler attribute
        if not hasattr(module, "handler"):
            raise AttributeError(
                f"Module '{function_id}' does not have a 'handler' attribute"
            )

        # Get and validate the handler
        handler_func: LambdaHandler = module.handler

        # Runtime check that handler implements the protocol
        if not isinstance(handler_func, LambdaHandler):
            raise TypeError(
                f"Handler in '{function_id}' does not implement LambdaHandler protocol"
            )

        # Call the handler function
        return handler_func(event, context)  # type: ignore

    except ImportError as e:
        raise ImportError(f"Lambda function '{function_id}' not found: {e}") from e

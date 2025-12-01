"""
Example Lambda handler using async-aws-lambda with database support.

This example demonstrates:
- Using @lambda_handler decorator
- Using @with_database decorator for database session injection
- Working with SQLite for local testing
- Working with PostgreSQL for production

To test locally with SAM CLI:
1. Install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
2. Set DATABASE_URL environment variable (see README.md)
3. Run: sam local invoke ExampleFunction --event events/event.json
"""

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from async_aws_lambda import lambda_handler, with_database


@lambda_handler
@with_database
async def handler(event: dict, context: Any, db_session: AsyncSession) -> dict:
    """
    Example Lambda handler with database support.

    This handler:
    - Receives a database session automatically via @with_database
    - Performs a simple database query
    - Returns a response

    Args:
        event: Lambda event dictionary
        context: Lambda context object
        db_session: Injected database session (AsyncSession)

    Returns:
        Response dictionary with statusCode and body
    """
    try:
        # Example: Execute a simple query
        result = await db_session.execute(text("SELECT 1 as test_value"))
        row = result.fetchone()
        test_value = row[0] if row else None

        # Example: You can also use SQLAlchemy models here
        # from your_models import User
        # result = await db_session.execute(select(User))
        # users = result.scalars().all()

        return {
            "statusCode": 200,
            "body": {
                "message": "Database connection successful",
                "test_value": test_value,
                "event": event,
            },
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "message": "Database operation failed",
            },
        }

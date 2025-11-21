"""
SQLAlchemy base classes for Lambda functions.

This module provides a base class for SQLAlchemy models optimized for Lambda use.
Requires sqlalchemy to be installed.
"""

from typing import Any

try:
    from sqlalchemy import MetaData
    from sqlalchemy.orm import DeclarativeBase
    HAS_SQLALCHEMY = True
except ImportError as e:
    raise ImportError(
        "Database support requires 'sqlalchemy[asyncio]'. "
        "Install with: pip install async-aws-lambda[db]"
    ) from e

# SQLAlchemy metadata with naming convention
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    """
    Base class for SQLAlchemy models in Lambda functions.

    Use this as the base class for your models:

    Example:
        from async_aws_lambda.database import Base

        class User(Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str]
    """

    metadata = metadata


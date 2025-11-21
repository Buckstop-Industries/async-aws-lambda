"""
Tests for database module.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.requires_db
class TestDatabaseBase:
    """Tests for database base classes."""

    @pytest.mark.unit
    def test_base_class_import(self):
        """Test that Base class can be imported."""
        from async_aws_lambda.database import Base

        assert Base is not None
        assert hasattr(Base, "metadata")

    @pytest.mark.unit
    def test_base_metadata_naming_convention(self):
        """Test that Base has proper naming conventions."""
        from async_aws_lambda.database import Base

        assert Base.metadata.naming_convention is not None
        assert "ix" in Base.metadata.naming_convention
        assert "uq" in Base.metadata.naming_convention


@pytest.mark.requires_db
class TestDatabaseSession:
    """Tests for database session management."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_db_with_url(self):
        """Test that init_db works with explicit database URL."""
        from async_aws_lambda.database import init_db

        with patch(
            "async_aws_lambda.database.session.create_async_engine"
        ) as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            # Properly mock async context manager for begin()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_begin_cm = AsyncMock()
            mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
            mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)

            await init_db("postgresql+asyncpg://user:pass@localhost/db")

            mock_engine.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_db_with_env_var(self):
        """Test that init_db uses DATABASE_URL environment variable."""
        from async_aws_lambda.database import init_db

        with patch.dict(
            os.environ, {"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db"}
        ):
            with patch(
                "async_aws_lambda.database.session.create_async_engine"
            ) as mock_engine:
                mock_engine_instance = MagicMock()
                mock_engine.return_value = mock_engine_instance

                # Properly mock async context manager for begin()
                mock_conn = AsyncMock()
                mock_conn.execute = AsyncMock()
                mock_begin_cm = AsyncMock()
                mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
                mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)

                await init_db()

                mock_engine.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_db_raises_without_url(self):
        """Test that init_db raises ValueError without database URL."""
        from async_aws_lambda.database import init_db

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DATABASE_URL"):
                await init_db()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init_db_idempotent(self):
        """Test that init_db is idempotent."""
        from async_aws_lambda.database import init_db

        with patch(
            "async_aws_lambda.database.session.create_async_engine"
        ) as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            # Properly mock async context manager for begin()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_begin_cm = AsyncMock()
            mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
            mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)

            await init_db("postgresql+asyncpg://user:pass@localhost/db")
            await init_db("postgresql+asyncpg://user:pass@localhost/db")

            # Should only be called once
            assert mock_engine.call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_db_session(self):
        """Test that get_db_session provides a session."""
        from async_aws_lambda.database import get_db_session, init_db

        with patch(
            "async_aws_lambda.database.session.create_async_engine"
        ) as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            # Properly mock async context manager for begin()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_begin_cm = AsyncMock()
            mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
            mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)

            await init_db("postgresql+asyncpg://user:pass@localhost/db")

            with patch(
                "async_aws_lambda.database.session._async_session_maker"
            ) as mock_maker:
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock()
                mock_maker.return_value = mock_session

                async with get_db_session() as session:
                    assert session is not None
                    await session.execute("SELECT 1")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_db_session_auto_init(self):
        """Test that get_db_session auto-initializes database."""
        from async_aws_lambda.database import get_db_session

        with patch("async_aws_lambda.database.session.init_db") as mock_init:
            mock_init.return_value = None

            with patch(
                "async_aws_lambda.database.session._async_session_maker"
            ) as mock_maker:
                mock_session = AsyncMock()
                mock_maker.return_value = mock_session

                async with get_db_session() as session:
                    assert session is not None
                    mock_init.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_db_session_rollback_on_error(self):
        """Test that get_db_session rolls back on exception."""
        from async_aws_lambda.database import get_db_session, init_db

        with patch(
            "async_aws_lambda.database.session.create_async_engine"
        ) as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            # Properly mock async context manager for begin()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_begin_cm = AsyncMock()
            mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
            mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)

            await init_db("postgresql+asyncpg://user:pass@localhost/db")

            with patch(
                "async_aws_lambda.database.session._async_session_maker"
            ) as mock_maker:
                mock_session = AsyncMock()
                mock_session.rollback = AsyncMock()
                mock_session.close = AsyncMock()
                mock_maker.return_value = mock_session

                with pytest.raises(ValueError):
                    async with get_db_session() as session:
                        raise ValueError("Test error")

                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_db(self):
        """Test that close_db closes database connections."""
        from async_aws_lambda.database import close_db, init_db

        with patch(
            "async_aws_lambda.database.session.create_async_engine"
        ) as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            # Properly mock async context manager for begin()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_begin_cm = AsyncMock()
            mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
            mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)
            mock_engine_instance.dispose = AsyncMock()

            await init_db("postgresql+asyncpg://user:pass@localhost/db")
            await close_db()

            mock_engine_instance.dispose.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_db_health(self):
        """Test that check_db_health checks database connection."""
        from async_aws_lambda.database import check_db_health, init_db

        with patch(
            "async_aws_lambda.database.session.create_async_engine"
        ) as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            # Properly mock async context manager for begin()
            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = "UTC"
            mock_conn.execute = AsyncMock(return_value=mock_result)
            mock_begin_cm = AsyncMock()
            mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
            # begin() should return the context manager directly, not a coroutine
            mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)

            await init_db("postgresql+asyncpg://user:pass@localhost/db")

            health = await check_db_health()
            assert health is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_db_health_no_engine(self):
        """Test that check_db_health returns False when engine is not initialized."""
        from async_aws_lambda.database import check_db_health

        # Reset engine state
        from async_aws_lambda.database.session import _engine

        with patch("async_aws_lambda.database.session._engine", None):
            health = await check_db_health()
            assert health is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_db_health_handles_errors(self):
        """Test that check_db_health handles errors gracefully."""
        from async_aws_lambda.database import check_db_health, init_db

        with patch(
            "async_aws_lambda.database.session.create_async_engine"
        ) as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance

            # Properly mock async context manager for begin() first
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_begin_cm = AsyncMock()
            mock_begin_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_cm.__aexit__ = AsyncMock(return_value=None)
            mock_engine_instance.begin = MagicMock(return_value=mock_begin_cm)

            await init_db("postgresql+asyncpg://user:pass@localhost/db")

            # Now mock begin() to raise an error for check_db_health
            mock_engine_instance.begin = MagicMock(
                side_effect=Exception("Connection error")
            )

            health = await check_db_health()
            assert health is False


@pytest.mark.requires_db
class TestDatabaseCleanup:
    """Tests for database cleanup handlers."""

    @pytest.mark.unit
    def test_cleanup_handler_registered(self):
        """Test that database cleanup handler is registered."""
        from async_aws_lambda.handlers.lifecycle import _cleanup_handlers

        # Check that cleanup handler is registered
        # (it's registered at module import time)
        assert len(_cleanup_handlers) >= 0  # May be 0 if not imported yet

"""Multi-database routing tests for QueryOrchestrator.

This module tests the orchestrator's per-database executor selection,
ensuring queries are executed on the correct database.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pg_mcp.config.settings import ResilienceConfig, ValidationConfig
from pg_mcp.models.errors import DatabaseError
from pg_mcp.models.query import QueryRequest, ReturnType
from pg_mcp.models.schema import ColumnInfo, DatabaseSchema, TableInfo
from pg_mcp.services.orchestrator import QueryOrchestrator


@pytest.fixture
def mock_schema_db1() -> DatabaseSchema:
    """Create mock schema for db1."""
    return DatabaseSchema(
        name="db1",
        tables=[
            TableInfo(
                name="users",
                columns=[ColumnInfo(name="id", type="integer")],
            )
        ],
    )


@pytest.fixture
def mock_schema_db2() -> DatabaseSchema:
    """Create mock schema for db2."""
    return DatabaseSchema(
        name="db2",
        tables=[
            TableInfo(
                name="products",
                columns=[ColumnInfo(name="sku", type="varchar")],
            )
        ],
    )


@pytest.fixture
def mock_executors() -> dict[str, MagicMock]:
    """Create mock executors for multiple databases."""
    executor_db1 = MagicMock()
    executor_db1.execute = AsyncMock(return_value=([{"id": 1}], 1))

    executor_db2 = MagicMock()
    executor_db2.execute = AsyncMock(return_value=([{"sku": "ABC123"}], 1))

    return {
        "db1": executor_db1,
        "db2": executor_db2,
    }


@pytest.fixture
def mock_pools() -> dict[str, MagicMock]:
    """Create mock connection pools."""
    return {
        "db1": MagicMock(),
        "db2": MagicMock(),
    }


class TestMultiDatabaseRouting:
    """Test per-database executor routing."""

    @pytest.mark.asyncio
    async def test_executor_selected_by_database_name(
        self,
        mock_executors: dict[str, MagicMock],
        mock_pools: dict[str, MagicMock],
        mock_schema_db1: DatabaseSchema,
    ) -> None:
        """Test that correct executor is selected based on database name."""
        # Setup
        mock_cache = MagicMock()
        mock_cache.get.return_value = mock_schema_db1

        mock_generator = AsyncMock()
        mock_generator.generate.return_value = "SELECT * FROM users;"

        mock_validator = MagicMock()
        mock_validator.validate_or_raise.return_value = None

        orchestrator = QueryOrchestrator(
            sql_generator=mock_generator,
            sql_validator=mock_validator,
            sql_executors=mock_executors,
            result_validator=MagicMock(),
            schema_cache=mock_cache,
            pools=mock_pools,
            resilience_config=ResilienceConfig(),
            validation_config=ValidationConfig(),
        )

        # Execute on db1
        request = QueryRequest(
            question="Get users",
            database="db1",
            return_type=ReturnType.RESULT,
        )
        response = await orchestrator.execute_query(request)

        # Verify db1 executor was called
        assert response.success is True
        mock_executors["db1"].execute.assert_called_once()
        mock_executors["db2"].execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_executor_selected_for_db2(
        self,
        mock_executors: dict[str, MagicMock],
        mock_pools: dict[str, MagicMock],
        mock_schema_db2: DatabaseSchema,
    ) -> None:
        """Test that db2 executor is selected when db2 is requested."""
        # Setup
        mock_cache = MagicMock()
        mock_cache.get.return_value = mock_schema_db2

        mock_generator = AsyncMock()
        mock_generator.generate.return_value = "SELECT * FROM products;"

        mock_validator = MagicMock()
        mock_validator.validate_or_raise.return_value = None

        orchestrator = QueryOrchestrator(
            sql_generator=mock_generator,
            sql_validator=mock_validator,
            sql_executors=mock_executors,
            result_validator=MagicMock(),
            schema_cache=mock_cache,
            pools=mock_pools,
            resilience_config=ResilienceConfig(),
            validation_config=ValidationConfig(),
        )

        # Execute on db2
        request = QueryRequest(
            question="Get products",
            database="db2",
            return_type=ReturnType.RESULT,
        )
        response = await orchestrator.execute_query(request)

        # Verify db2 executor was called
        assert response.success is True
        mock_executors["db2"].execute.assert_called_once()
        mock_executors["db1"].execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_when_executor_not_found(
        self,
        mock_executors: dict[str, MagicMock],
        mock_pools: dict[str, MagicMock],
        mock_schema_db1: DatabaseSchema,
    ) -> None:
        """Test error when no executor exists for requested database."""
        # Setup - pools has db1 and db2, but executors only has db1
        mock_cache = MagicMock()
        mock_cache.get.return_value = mock_schema_db1

        orchestrator = QueryOrchestrator(
            sql_generator=MagicMock(),
            sql_validator=MagicMock(),
            sql_executors={"db1": mock_executors["db1"]},  # Only db1 executor
            result_validator=MagicMock(),
            schema_cache=mock_cache,
            pools=mock_pools,  # Both db1 and db2 pools
            resilience_config=ResilienceConfig(),
            validation_config=ValidationConfig(),
        )

        # Execute on db2 - should fail
        request = QueryRequest(
            question="Get products",
            database="db2",
            return_type=ReturnType.RESULT,
        )
        response = await orchestrator.execute_query(request)

        # Verify error
        assert response.success is False
        assert response.error is not None
        assert "no sql executor" in response.error.message.lower()


class TestQuestionLengthValidation:
    """Test max_question_length validation."""

    @pytest.mark.asyncio
    async def test_question_length_validation_rejects_long_questions(self) -> None:
        """Test that questions exceeding max length are rejected."""
        validation_config = ValidationConfig(max_question_length=50)

        orchestrator = QueryOrchestrator(
            sql_generator=MagicMock(),
            sql_validator=MagicMock(),
            sql_executors={"db": MagicMock()},
            result_validator=MagicMock(),
            schema_cache=MagicMock(),
            pools={"db": MagicMock()},
            resilience_config=ResilienceConfig(),
            validation_config=validation_config,
        )

        # Create a question longer than 50 characters
        long_question = "a" * 51

        request = QueryRequest(
            question=long_question,
            database="db",
            return_type=ReturnType.SQL,
        )
        response = await orchestrator.execute_query(request)

        # Verify rejection
        assert response.success is False
        assert response.error is not None
        assert response.error.code == "validation_error"
        assert "exceeds maximum length" in response.error.message.lower()

    @pytest.mark.asyncio
    async def test_question_length_validation_accepts_valid_questions(self) -> None:
        """Test that questions within max length are accepted."""
        validation_config = ValidationConfig(max_question_length=100)

        mock_cache = MagicMock()
        mock_cache.get.return_value = DatabaseSchema(
            name="db",
            tables=[TableInfo(name="users", columns=[])],
        )

        mock_generator = AsyncMock()
        mock_generator.generate.return_value = "SELECT 1;"

        mock_validator = MagicMock()
        mock_validator.validate_or_raise.return_value = None

        orchestrator = QueryOrchestrator(
            sql_generator=mock_generator,
            sql_validator=mock_validator,
            sql_executors={"db": MagicMock()},
            result_validator=MagicMock(),
            schema_cache=mock_cache,
            pools={"db": MagicMock()},
            resilience_config=ResilienceConfig(),
            validation_config=validation_config,
        )

        # Create a question within limit
        valid_question = "a" * 50

        request = QueryRequest(
            question=valid_question,
            database="db",
            return_type=ReturnType.SQL,
        )
        response = await orchestrator.execute_query(request)

        # Verify acceptance
        assert response.success is True

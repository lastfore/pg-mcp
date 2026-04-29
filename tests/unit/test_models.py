"""Tests for data models.

This module tests Pydantic models including QueryResponse, ErrorDetail, and others.
"""

import pytest
from pydantic import ValidationError

from pg_mcp.models.query import (
    ErrorDetail,
    QueryRequest,
    QueryResponse,
    QueryResult,
    ResultValidationResult,
    ReturnType,
    ValidationResult,
)


class TestQueryRequest:
    """Test QueryRequest model."""

    def test_valid_request(self) -> None:
        """Test creating a valid query request."""
        request = QueryRequest(
            question="How many users?",
            database="test_db",
            return_type=ReturnType.RESULT,
        )
        assert request.question == "How many users?"
        assert request.database == "test_db"
        assert request.return_type == ReturnType.RESULT

    def test_question_stripped(self) -> None:
        """Test that question is stripped of whitespace."""
        request = QueryRequest(question="  Test question  ")
        assert request.question == "Test question"

    def test_empty_question_rejected(self) -> None:
        """Test that empty questions are rejected."""
        with pytest.raises(ValidationError):
            QueryRequest(question="")

    def test_question_too_long_rejected(self) -> None:
        """Test that questions exceeding max_length are rejected."""
        with pytest.raises(ValidationError):
            QueryRequest(question="a" * 10001)  # Max is 10000


class TestQueryResponse:
    """Test QueryResponse model including to_dict behavior."""

    def test_to_dict_always_includes_tokens_used(self) -> None:
        """Test that to_dict always includes tokens_used field."""
        response = QueryResponse(
            success=True,
            generated_sql="SELECT 1",
            tokens_used=None,  # Explicitly None
        )

        result = response.to_dict()

        assert "tokens_used" in result
        assert result["tokens_used"] == 0  # Should default to 0

    def test_to_dict_preserves_tokens_used_when_set(self) -> None:
        """Test that to_dict preserves tokens_used when set."""
        response = QueryResponse(
            success=True,
            generated_sql="SELECT 1",
            tokens_used=150,
        )

        result = response.to_dict()

        assert result["tokens_used"] == 150

    def test_to_dict_success_response(self) -> None:
        """Test to_dict for successful response."""
        response = QueryResponse(
            success=True,
            generated_sql="SELECT * FROM users",
            data=QueryResult(
                columns=["id", "name"],
                rows=[{"id": 1, "name": "Alice"}],
                row_count=1,
                execution_time_ms=100.0,
            ),
            confidence=95,
            tokens_used=200,
        )

        result = response.to_dict()

        assert result["success"] is True
        assert result["generated_sql"] == "SELECT * FROM users"
        assert result["confidence"] == 95
        assert result["tokens_used"] == 200
        assert result["data"]["columns"] == ["id", "name"]

    def test_to_dict_error_response(self) -> None:
        """Test to_dict for error response."""
        response = QueryResponse(
            success=False,
            error=ErrorDetail(
                code="security_violation",
                message="DELETE not allowed",
            ),
            confidence=0,
            tokens_used=None,
        )

        result = response.to_dict()

        assert result["success"] is False
        assert result["error"]["code"] == "security_violation"
        assert result["tokens_used"] == 0  # Should default to 0


class TestErrorDetail:
    """Test ErrorDetail model."""

    def test_error_detail_creation(self) -> None:
        """Test creating ErrorDetail."""
        error = ErrorDetail(
            code="test_error",
            message="Test message",
            details={"key": "value"},
        )

        assert error.code == "test_error"
        assert error.message == "Test message"
        assert error.details == {"key": "value"}

    def test_error_detail_optional_details(self) -> None:
        """Test ErrorDetail with no details."""
        error = ErrorDetail(
            code="simple_error",
            message="Simple message",
        )

        assert error.details is None


class TestValidationResult:
    """Test ValidationResult model."""

    def test_is_safe_property(self) -> None:
        """Test is_safe property calculation."""
        # Safe: valid, select, no modification, no blocked functions
        safe_result = ValidationResult(
            is_valid=True,
            is_select=True,
            allows_data_modification=False,
            uses_blocked_functions=[],
        )
        assert safe_result.is_safe is True

        # Unsafe: allows modification
        unsafe_mod = ValidationResult(
            is_valid=True,
            is_select=True,
            allows_data_modification=True,
            uses_blocked_functions=[],
        )
        assert unsafe_mod.is_safe is False

        # Unsafe: uses blocked functions
        unsafe_func = ValidationResult(
            is_valid=True,
            is_select=True,
            allows_data_modification=False,
            uses_blocked_functions=["pg_sleep"],
        )
        assert unsafe_func.is_safe is False

        # Unsafe: not valid
        unsafe_valid = ValidationResult(
            is_valid=False,
            is_select=True,
            allows_data_modification=False,
            uses_blocked_functions=[],
        )
        assert unsafe_valid.is_safe is False


class TestResultValidationResult:
    """Test ResultValidationResult model."""

    def test_acceptable_when_confidence_high(self) -> None:
        """Test that is_acceptable reflects confidence."""
        result = ResultValidationResult(
            confidence=85,
            explanation="Results look good",
            is_acceptable=True,
        )
        assert result.is_acceptable is True

    def test_not_acceptable_when_confidence_low(self) -> None:
        """Test that low confidence marks as not acceptable."""
        result = ResultValidationResult(
            confidence=30,
            explanation="Results don't match question",
            is_acceptable=False,
        )
        assert result.is_acceptable is False


class TestQueryResult:
    """Test QueryResult model."""

    def test_row_count_matches_rows(self) -> None:
        """Test that row_count is validated against rows length."""
        result = QueryResult(
            columns=["id"],
            rows=[{"id": 1}, {"id": 2}, {"id": 3}],
            row_count=0,  # Should be overridden
            execution_time_ms=50.0,
        )

        # Validator should update row_count to match len(rows)
        assert result.row_count == 3

    def test_empty_result(self) -> None:
        """Test empty query result."""
        result = QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=10.0,
        )

        assert result.row_count == 0

"""Security field tests for SQLValidator.

This module tests blocked_tables, blocked_columns, and allow_explain configuration.
"""

import pytest

from pg_mcp.config.settings import SecurityConfig
from pg_mcp.models.errors import SecurityViolationError, SQLParseError
from pg_mcp.services.sql_validator import SQLValidator


class TestBlockedTables:
    """Test blocked tables configuration."""

    @pytest.fixture
    def config(self) -> SecurityConfig:
        """Create default security config."""
        return SecurityConfig()

    def test_blocked_table_access_rejected(self, config: SecurityConfig) -> None:
        """Test that queries accessing blocked tables are rejected."""
        validator = SQLValidator(
            config=config,
            blocked_tables=["passwords", "secrets"],
            blocked_columns=[],
            allow_explain=False,
        )

        with pytest.raises(SecurityViolationError) as exc_info:
            validator.validate_or_raise("SELECT * FROM passwords")

        assert "blocked" in str(exc_info.value).lower()
        assert "passwords" in str(exc_info.value).lower()

    def test_blocked_table_case_insensitive(self, config: SecurityConfig) -> None:
        """Test that table blocking is case insensitive."""
        validator = SQLValidator(
            config=config,
            blocked_tables=["USERS"],
            blocked_columns=[],
            allow_explain=False,
        )

        with pytest.raises(SecurityViolationError) as exc_info:
            validator.validate_or_raise("SELECT * FROM users")

        assert "blocked" in str(exc_info.value).lower()

    def test_non_blocked_table_allowed(self, config: SecurityConfig) -> None:
        """Test that queries on non-blocked tables are allowed."""
        validator = SQLValidator(
            config=config,
            blocked_tables=["passwords"],
            blocked_columns=[],
            allow_explain=False,
        )

        # Should not raise
        result = validator.validate("SELECT * FROM users")
        assert result[0] is True
        assert result[1] is None


class TestBlockedColumns:
    """Test blocked columns configuration."""

    @pytest.fixture
    def config(self) -> SecurityConfig:
        """Create default security config."""
        return SecurityConfig()

    def test_blocked_column_access_rejected(self, config: SecurityConfig) -> None:
        """Test that queries accessing blocked columns are rejected."""
        validator = SQLValidator(
            config=config,
            blocked_tables=[],
            blocked_columns=["password_hash", "ssn"],
            allow_explain=False,
        )

        with pytest.raises(SecurityViolationError) as exc_info:
            validator.validate_or_raise("SELECT password_hash FROM users")

        assert "blocked" in str(exc_info.value).lower()
        assert "password_hash" in str(exc_info.value).lower()

    def test_blocked_column_case_insensitive(self, config: SecurityConfig) -> None:
        """Test that column blocking is case insensitive."""
        validator = SQLValidator(
            config=config,
            blocked_tables=[],
            blocked_columns=["EMAIL"],
            allow_explain=False,
        )

        with pytest.raises(SecurityViolationError) as exc_info:
            validator.validate_or_raise("SELECT email FROM users")

        assert "blocked" in str(exc_info.value).lower()


class TestAllowExplain:
    """Test allow_explain configuration."""

    @pytest.fixture
    def config(self) -> SecurityConfig:
        """Create default security config."""
        return SecurityConfig()

    def test_explain_blocked_by_default(self, config: SecurityConfig) -> None:
        """Test that EXPLAIN is blocked when allow_explain=False."""
        validator = SQLValidator(
            config=config,
            blocked_tables=[],
            blocked_columns=[],
            allow_explain=False,
        )

        with pytest.raises(SecurityViolationError) as exc_info:
            validator.validate_or_raise("EXPLAIN SELECT * FROM users")

        assert "explain" in str(exc_info.value).lower()

    def test_explain_allowed_when_configured(self, config: SecurityConfig) -> None:
        """Test that EXPLAIN is allowed when allow_explain=True."""
        validator = SQLValidator(
            config=config,
            blocked_tables=[],
            blocked_columns=[],
            allow_explain=True,
        )

        # Should not raise
        result = validator.validate("EXPLAIN SELECT * FROM users")
        assert result[0] is True
        assert result[1] is None

    def test_explain_analyze_always_blocked(self, config: SecurityConfig) -> None:
        """Test that EXPLAIN ANALYZE is always blocked (executes query)."""
        validator = SQLValidator(
            config=config,
            blocked_tables=[],
            blocked_columns=[],
            allow_explain=True,  # Even with allow_explain=True
        )

        with pytest.raises(SecurityViolationError) as exc_info:
            validator.validate_or_raise("EXPLAIN ANALYZE SELECT * FROM users")

        assert "analyze" in str(exc_info.value).lower() or "execute" in str(exc_info.value).lower()


class TestSecurityConfigIntegration:
    """Test SecurityConfig integration with SQLValidator."""

    def test_security_config_blocked_tables_passed_to_validator(self) -> None:
        """Test that SecurityConfig blocked_tables are passed to validator."""
        config = SecurityConfig(
            blocked_tables=["sensitive_data"],
            blocked_columns={},
            allow_explain=False,
        )

        validator = SQLValidator(
            config=config,
            blocked_tables=config.blocked_tables,
            blocked_columns=list(config.blocked_columns.keys()),
            allow_explain=config.allow_explain,
        )

        with pytest.raises(SecurityViolationError) as exc_info:
            validator.validate_or_raise("SELECT * FROM sensitive_data")

        assert "blocked" in str(exc_info.value).lower()

    def test_security_config_allow_explain_passed_to_validator(self) -> None:
        """Test that SecurityConfig allow_explain is passed to validator."""
        config = SecurityConfig(
            blocked_tables=[],
            blocked_columns={},
            allow_explain=True,
        )

        validator = SQLValidator(
            config=config,
            blocked_tables=config.blocked_tables,
            blocked_columns=list(config.blocked_columns.keys()),
            allow_explain=config.allow_explain,
        )

        # Should not raise
        result = validator.validate("EXPLAIN SELECT * FROM users")
        assert result[0] is True

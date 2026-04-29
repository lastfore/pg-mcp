"""Tests for configuration settings.

This module tests the Settings and configuration classes.
"""

import os
from unittest.mock import patch

import pytest

from pg_mcp.config.settings import (
    DatabaseConfig,
    ResilienceConfig,
    SecurityConfig,
    Settings,
)


class TestDatabaseConfig:
    """Test DatabaseConfig settings."""

    def test_default_values(self) -> None:
        """Test default database configuration values."""
        config = DatabaseConfig()

        assert config.host == "localhost"
        assert config.port == 5432
        assert config.name == "postgres"
        assert config.user == "postgres"
        assert config.min_pool_size == 5
        assert config.max_pool_size == 20

    def test_dsn_format(self) -> None:
        """Test DSN string format."""
        config = DatabaseConfig(
            host="db.example.com",
            port=5433,
            name="mydb",
            user="admin",
            password="secret123",
        )

        assert config.dsn == "postgresql://admin:secret123@db.example.com:5433/mydb"

    def test_safe_dsn_masks_password(self) -> None:
        """Test that safe_dsn masks password."""
        config = DatabaseConfig(
            host="db.example.com",
            user="admin",
            password="secret123",
        )

        assert "secret123" not in config.safe_dsn
        assert "***" in config.safe_dsn


class TestSecurityConfig:
    """Test SecurityConfig settings."""

    def test_default_blocked_functions(self) -> None:
        """Test default blocked functions list."""
        config = SecurityConfig()

        assert "pg_sleep" in config.blocked_functions
        assert "pg_read_file" in config.blocked_functions

    def test_blocked_tables_parsing(self) -> None:
        """Test blocked_tables parsing from string."""
        config = SecurityConfig(blocked_tables="users,passwords,secrets")

        assert "users" in config.blocked_tables
        assert "passwords" in config.blocked_tables
        assert "secrets" in config.blocked_tables

    def test_blocked_tables_list(self) -> None:
        """Test blocked_tables as list."""
        config = SecurityConfig(blocked_tables=["table1", "table2"])

        assert "table1" in config.blocked_tables
        assert "table2" in config.blocked_tables

    def test_allow_explain_default(self) -> None:
        """Test default allow_explain value."""
        config = SecurityConfig()

        assert config.allow_explain is False

    def test_allow_explain_configurable(self) -> None:
        """Test allow_explain can be configured."""
        config = SecurityConfig(allow_explain=True)

        assert config.allow_explain is True


class TestResilienceConfig:
    """Test ResilienceConfig settings."""

    def test_default_retry_values(self) -> None:
        """Test default retry configuration."""
        config = ResilienceConfig()

        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.backoff_factor == 2.0

    def test_rate_limit_defaults(self) -> None:
        """Test default rate limit values."""
        config = ResilienceConfig()

        assert config.query_rate_limit == 100
        assert config.llm_rate_limit == 10

    def test_custom_rate_limits(self) -> None:
        """Test custom rate limit configuration."""
        config = ResilienceConfig(
            query_rate_limit=50,
            llm_rate_limit=5,
        )

        assert config.query_rate_limit == 50
        assert config.llm_rate_limit == 5


class TestSettingsMultiDatabase:
    """Test Settings multi-database support."""

    @pytest.fixture(autouse=True)
    def mock_api_key(self):
        """Provide mock API key for tests."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123456789"}):
            yield

    def test_single_database_backward_compat(self) -> None:
        """Test that single database config populates databases list."""
        settings = Settings()

        # databases should be auto-populated from database
        assert len(settings.databases) == 1
        assert settings.databases[0].name == settings.database.name

    def test_get_database_config_by_name(self) -> None:
        """Test retrieving database config by name."""
        # Get default database name from settings
        settings = Settings()
        default_name = settings.databases[0].name

        # Test retrieving the default database by name
        config = settings.get_database_config(default_name)
        assert config is not None
        assert config.name == default_name

    def test_get_database_config_none(self) -> None:
        """Test retrieving default database config."""
        settings = Settings()

        config = settings.get_database_config(None)
        assert config is not None

    def test_get_database_names(self) -> None:
        """Test retrieving all database names."""
        settings = Settings()

        names = settings.get_database_names()
        assert len(names) == 1
        assert names[0] == settings.database.name


class TestSettingsEnvironment:
    """Test environment-based configuration."""

    def test_production_detection(self) -> None:
        """Test production environment detection."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "OPENAI_API_KEY": "sk-test123456789",
        }):
            settings = Settings()

            assert settings.is_production is True
            assert settings.is_development is False

    def test_development_detection(self) -> None:
        """Test development environment detection."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "OPENAI_API_KEY": "sk-test123456789",
        }):
            settings = Settings()

            assert settings.is_development is True
            assert settings.is_production is False

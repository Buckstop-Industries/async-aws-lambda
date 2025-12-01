# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-XX

### Changed

- **BREAKING**: `get_secret_from_aws()` now raises exceptions instead of returning empty strings
  - Raises `SecretNotFoundError` when secret is not found
  - Raises `SecretAccessError` when there's an access error
  - Raises `ValueError` when `secret_name` is empty
  - This improves error visibility and prevents silent failures

### Security

- Fixed SQL injection vulnerability in `PostgresBackend.get_initialization_queries()`
  - Added input validation for `application_name` parameter
  - Properly escapes single quotes in SQL string literals
  - Validates application name contains only safe characters (alphanumeric, underscore, hyphen, dot, space)
  - Maximum length validation (63 characters, PostgreSQL identifier limit)

### Fixed

- Removed duplicate `pass` statement in `database/session.py`

### Added

- New exception classes for secret management:
  - `SecretError` - Base exception for secret-related errors
  - `SecretNotFoundError` - Raised when a secret is not found
  - `SecretAccessError` - Raised when there's an error accessing secrets
- GitHub Actions workflow for automated testing
  - Runs tests on push and pull requests
  - Includes linting with ruff
  - Includes type checking with mypy
  - Includes test coverage reporting

### Changed

- Development status updated from Alpha to Beta

## [0.1.0] - 2024-01-XX

### Added

- Initial release
- `@lambda_handler` decorator for async Lambda handlers (zero dependencies)
- `@with_database` optional decorator for database session injection
- `@with_config` optional decorator for configuration injection
- Lifecycle management with automatic cleanup
- Error handling framework with retry logic
- Database session management optimized for Lambda
- Configuration management with Pydantic
- AWS Secrets Manager integration
- Full type hints and mypy support
- Comprehensive documentation

### Features

- Zero default dependencies (core library works with stdlib only)
- Optional database support via `[db]` extra
- Optional configuration support via `[config]` extra
- Optional AWS services support via `[aws]` extra
- Composable decorators for flexible handler configuration
- Type-safe configuration and database sessions

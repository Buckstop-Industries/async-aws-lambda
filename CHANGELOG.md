# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

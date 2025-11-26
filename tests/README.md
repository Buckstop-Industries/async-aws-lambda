# Test Suite for async-aws-lambda

This directory contains comprehensive tests for the async-aws-lambda library.

## Test Structure

- `test_handlers_decorators.py` - Tests for `@lambda_handler`, `@with_database`, and `@with_config` decorators
- `test_handlers_lifecycle.py` - Tests for Lambda lifecycle management and cleanup handlers
- `test_handlers_protocols.py` - Tests for protocol definitions (LambdaHandler, AsyncLambdaHandler, DatabaseFactory)
- `test_database.py` - Tests for database session management and initialization
- `test_config.py` - Tests for configuration management (Settings, AWS Secrets Manager)
- `test_errors.py` - Tests for error handling and classification

## Running Tests

### Install Test Dependencies

```bash
pip install -e ".[dev]"
```

Or with all optional dependencies:

```bash
pip install -e ".[all,dev]"
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest -m unit

# Tests requiring database
pytest -m requires_db

# Tests requiring config dependencies
pytest -m requires_config

# Tests requiring AWS dependencies
pytest -m requires_aws
```

### Run Specific Test Files

```bash
pytest tests/test_handlers_decorators.py
pytest tests/test_database.py
```

### Run with Coverage

```bash
pytest --cov=async_aws_lambda --cov-report=html
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit` - Unit tests (no external dependencies)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.requires_db` - Tests requiring database dependencies
- `@pytest.mark.requires_config` - Tests requiring config dependencies (Pydantic)
- `@pytest.mark.requires_aws` - Tests requiring AWS dependencies (boto3)

## Fixtures

Common fixtures are defined in `conftest.py`:

- `mock_lambda_context` - Mock AWS Lambda context object
- `sample_event` - Sample Lambda event dictionary
- `event_loop` - Event loop for async tests
- `reset_cleanup_handlers` - Fixture to reset cleanup handlers between tests

## Notes

- Most tests use mocks to avoid requiring actual database connections or AWS services
- Tests marked with `@pytest.mark.requires_db` may need database dependencies installed
- Tests marked with `@pytest.mark.requires_config` may need Pydantic installed
- Tests marked with `@pytest.mark.requires_aws` may need boto3 installed

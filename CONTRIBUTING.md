# Contributing to async-aws-lambda

Thank you for your interest in contributing to async-aws-lambda! This document provides guidelines and instructions for contributing.

## Development Setup

1. Clone the repository:

```bash
git clone https://github.com/bucktop-industries/async-aws-lambda.git
cd async-aws-lambda
```

2. Install development dependencies:

```bash
pip install -e ".[all,dev]"
```

3. Run tests:

```bash
pytest
```

## Code Style

- Follow PEP 8 style guide
- Use Black for code formatting (88 character line length)
- Use type hints for all functions
- Ensure mypy strict mode passes
- Maximum line length: 88 characters

## Commit Messages

- Use clear, descriptive commit messages
- Include issue numbers when applicable
- Format: `[ASANA-TICKET-ID] Description`

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Ensure mypy strict mode passes
6. Update documentation if needed
7. Submit pull request with description

## Testing

- Write tests for all new features
- Ensure 90%+ test coverage
- Test with and without optional dependencies
- Test error scenarios

## Documentation

- Update README.md for user-facing changes
- Add docstrings to all public functions
- Include type hints in docstrings
- Update examples if applicable

## Optional Dependencies

When adding features that require optional dependencies:

1. Wrap imports in try/except ImportError
2. Raise helpful error messages if dependencies missing
3. Document the required extra in README
4. Add to appropriate `[project.optional-dependencies]` section in pyproject.toml

## Questions?

Open an issue or contact the maintainers.

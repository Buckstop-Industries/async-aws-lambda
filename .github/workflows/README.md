# GitHub Actions Workflows

This directory contains GitHub Actions workflows for CI/CD.

## Workflows

### `test.yml`

Runs on every push and pull request to `main` and `develop` branches.

**Jobs:**

- **test**: Runs linting, type checking, and tests
  - Linting with ruff
  - Type checking with mypy
  - Unit tests with pytest
  - Coverage reporting to Codecov

### `build-and-publish.yml`

Runs when a version tag is pushed (e.g., `v0.2.0`) or manually triggered.

**Jobs:**

- **build**: Builds the Python package

  - Creates source distribution and wheel
  - Validates package with twine check
  - Uploads artifacts for later use

- **docs**: Generates Sphinx documentation

  - Sets up Sphinx configuration
  - Generates API documentation from docstrings
  - Builds HTML documentation
  - Uploads documentation artifacts

- **publish**: Publishes to PyPI and creates GitHub release
  - Downloads build artifacts
  - Publishes to PyPI (requires `PYPI_API_TOKEN` secret)
  - Creates GitHub release with changelog

## Setup

### PyPI Publishing

To enable PyPI publishing, you need to:

1. Create a PyPI API token:

   - Go to https://pypi.org/manage/account/token/
   - Create a new API token with "Upload packages" scope
   - Copy the token (starts with `pypi-`)

2. Add the token as a GitHub secret:

   - Go to your repository Settings → Secrets and variables → Actions
   - Add a new secret named `PYPI_API_TOKEN`
   - Paste your PyPI API token

3. Create a GitHub environment (optional but recommended):
   - Go to Settings → Environments
   - Create a new environment named `pypi`
   - Add the `PYPI_API_TOKEN` secret to this environment
   - This provides better security and audit trail

### Publishing a Release

To publish a new version:

1. Update the version in `pyproject.toml` and `async_aws_lambda/__init__.py`
2. Update `CHANGELOG.md` with the new version
3. Commit and push your changes
4. Create and push a version tag:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
5. The workflow will automatically:
   - Build the package
   - Generate documentation
   - Publish to PyPI
   - Create a GitHub release

### Manual Trigger

You can also manually trigger the build and publish workflow:

1. Go to Actions → Build and Publish
2. Click "Run workflow"
3. Optionally specify a version
4. Click "Run workflow"

## Documentation

The documentation is generated using Sphinx with the Read the Docs theme. It includes:

- API reference generated from docstrings
- Module documentation
- Search functionality
- Index pages

Documentation artifacts are uploaded but not automatically published. To publish documentation:

1. Download the documentation artifact from the workflow run
2. Host it on GitHub Pages, Read the Docs, or another hosting service

## Troubleshooting

### Build fails

- Check that `pyproject.toml` is valid
- Ensure all required fields are present
- Verify Python version compatibility

### PyPI upload fails

- Verify `PYPI_API_TOKEN` secret is set correctly
- Check that the package name isn't already taken
- Ensure the version number is unique (not already published)

### Documentation generation fails

- Check that docstrings are properly formatted
- Verify Sphinx dependencies are installed
- Check for syntax errors in docstrings

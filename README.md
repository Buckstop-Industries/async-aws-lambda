# async-aws-lambda

A lightweight, zero-dependency library for building async AWS Lambda functions with optional database support, configuration management, lifecycle management, and error handling.

## Features

- **Zero Dependencies** - Core library works with only Python standard library
- **Async Support** - Full async/await support for Lambda handlers
- **Optional Database** - Optional SQLAlchemy integration via `[db]` extra
- **Optional Configuration** - Optional Pydantic settings via `[config]` extra
- **Lifecycle Management** - Automatic cleanup and resource management
- **Type Safe** - Full type hints and mypy support
- **Composable Decorators** - Stack decorators for different features

## Installation

```bash
# Minimal installation (zero dependencies)
pip install async-aws-lambda

# With database support (SQLAlchemy)
pip install async-aws-lambda[db]

# With configuration support (Pydantic)
pip install async-aws-lambda[config]

# With AWS services (boto3 for Secrets Manager)
pip install async-aws-lambda[aws]

# With everything
pip install async-aws-lambda[all]
```

## Quick Start

### Minimal Handler (Zero Dependencies)

```python
from async_aws_lambda import lambda_handler

@lambda_handler
async def handler(event, context):
    return {
        "statusCode": 200,
        "body": "Hello from async Lambda!"
    }
```

### With Database Support

```python
from async_aws_lambda import lambda_handler, with_database
from sqlalchemy.ext.asyncio import AsyncSession

@lambda_handler
@with_database
async def handler(event, context, db_session: AsyncSession):
    # Database automatically available
    result = await db_session.execute("SELECT 1")
    return {"statusCode": 200, "body": str(result.scalar())}
```

Set the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"
```

### With Configuration

```python
from async_aws_lambda import lambda_handler, with_config
from async_aws_lambda.config import Settings

class MySettings(Settings):
    API_KEY: str
    DEBUG: bool = False
    DATABASE_URL: str

@lambda_handler
@with_config
async def handler(event, context, settings: MySettings):
    if settings.DEBUG:
        print(f"API Key: {settings.API_KEY}")
    return {"statusCode": 200}
```

### Full Stack Example

```python
from async_aws_lambda import lambda_handler, with_database, with_config
from async_aws_lambda.config import Settings
from sqlalchemy.ext.asyncio import AsyncSession

class AppSettings(Settings):
    DATABASE_URL: str
    API_KEY: str

@lambda_handler
@with_database
@with_config
async def handler(
    event,
    context,
    db_session: AsyncSession,
    settings: AppSettings
):
    # All features available
    return {"statusCode": 200}
```

## Deployment

### Handler Reference

When deploying your Lambda function, you need to specify the handler reference. The format depends on your deployment method:

#### Zip Deploy (Traditional Lambda)

For zip-based deployments, reference your handler using the format: `filename.function_name`

**Example handler file (`handler.py`):**

```python
from async_aws_lambda import lambda_handler

@lambda_handler
async def handler(event, context):
    return {"statusCode": 200, "body": "Hello from Lambda!"}
```

**Lambda Configuration:**

- **Handler**: `handler.handler`
- **Runtime**: Python 3.13 (or your Python version)

**AWS CLI deploy:**

```bash
zip function.zip handler.py
aws lambda update-function-code \
  --function-name my-function \
  --zip-file fileb://function.zip
```

**SAM Template:**

```yaml
Resources:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: handler.handler
      Runtime: python3.13
      CodeUri: ./
```

**Terraform:**

```hcl
resource "aws_lambda_function" "my_function" {
  filename      = "function.zip"
  function_name = "my-function"
  handler       = "handler.handler"
  runtime       = "python3.13"
  source_code_hash = filebase64sha256("function.zip")
}
```

#### Container Image Deploy (Dockerfile)

For container-based Lambda deployments, use the `CMD` instruction to specify the handler.

**Example handler file (`handler.py`):**

```python
from async_aws_lambda import lambda_handler

@lambda_handler
async def handler(event, context):
    return {"statusCode": 200, "body": "Hello from Lambda!"}
```

**Dockerfile:**

```dockerfile
FROM public.ecr.aws/lambda/python:3.13

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY handler.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "handler.handler" ]
```

**SAM Template (Container):**

```yaml
Resources:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageUri: my-lambda-function:latest
      ImageConfig:
        Command: ["handler.handler"]
```

**Note:** The handler reference format is `module.function_name` where:

- `module` is the Python file name (without `.py` extension)
- `function_name` is the name of the function decorated with `@lambda_handler`

## Decorators

### `@lambda_handler`

The main decorator that wraps async handlers for Lambda runtime compatibility.

**Required**: Yes (only required decorator)

**Features**:

- Converts async handlers to sync Lambda-compatible handlers
- Manages Lambda lifecycle (cleanup, signals)
- Basic error handling
- Zero dependencies

### `@with_database`

Optional decorator for database session injection.

**Required**: No (optional)

**Features**:

- Injects `db_session` parameter (AsyncSession)
- Automatic connection management
- Lambda-optimized connection pooling
- Requires `async-aws-lambda[db]` extra

**Custom Database Factory**:

```python
async def my_db_factory():
    # Custom database connection logic
    return custom_session

@lambda_handler
@with_database(factory=my_db_factory)
async def handler(event, context, db_session):
    pass
```

### `@with_config`

Optional decorator for configuration injection.

**Required**: No (optional)

**Features**:

- Injects `settings` parameter
- Type-safe configuration via Pydantic
- Environment variable loading
- Requires `async-aws-lambda[config]` extra

**Custom Settings Class**:

```python
@lambda_handler
@with_config(settings_class=MyCustomSettings)
async def handler(event, context, settings: MyCustomSettings):
    pass
```

## Error Handling

Optional error handling framework for structured error management:

```python
from async_aws_lambda.errors import ErrorHandler, ProcessingError

error_handler = ErrorHandler(max_retries=3, retry_delay=1.0)

try:
    # Your code here
    pass
except Exception as e:
    error = error_handler.classify_error(e, context={"key": "value"})
    if error_handler.should_retry(error):
        # Retry logic
        pass
```

## Database Configuration

Database sessions are optimized for Lambda:

- **Pool Size**: 2 connections (configurable)
- **Max Overflow**: 3 connections (configurable)
- **Connection Recycle**: 300 seconds
- **Pre-ping**: Enabled for connection health checks
- **Automatic Cleanup**: Connections closed on handler completion

### Custom Database Configuration

```python
from async_aws_lambda.database import init_db

# Initialize with custom settings
await init_db(
    database_url="postgresql+asyncpg://...",
    pool_size=5,
    max_overflow=10,
    pool_recycle=600,
    echo=True,  # Enable SQL logging
)
```

## Configuration with Secrets

Integrate with AWS Secrets Manager:

```python
from async_aws_lambda.config import get_secret_from_aws

# Get secret from AWS Secrets Manager
database_url = get_secret_from_aws(
    "myapp/database-url",
    key="url",  # Optional: extract key from JSON secret
    region_name="us-east-1"
)
```

## Lifecycle Management

The library automatically manages Lambda lifecycle:

- **Signal Handling**: SIGTERM and SIGINT are caught for graceful shutdown
- **Resource Cleanup**: Database connections and other resources are cleaned up
- **Error Recovery**: Errors during cleanup don't crash the handler

## Type Safety

Full type hints and mypy support:

```bash
# Run mypy
mypy --strict your_lambda_handler.py
```

## Examples

See the [examples](./examples/) directory for more usage patterns.

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

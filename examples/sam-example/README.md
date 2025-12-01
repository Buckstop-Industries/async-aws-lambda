# SAM CLI Example for async-aws-lambda

This example demonstrates how to use `async-aws-lambda` with the AWS SAM CLI for local testing and development.

## Prerequisites

1. **AWS SAM CLI**: Install from [AWS SAM CLI Documentation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)

2. **Python 3.13**: This example requires Python 3.13

3. **Docker**: SAM CLI uses Docker for local testing. Install Docker Desktop or Docker Engine.

## Setup

1. **Prerequisites**: Ensure Docker is running

2. **Build the Docker image**:

   ```bash
   # Build from the project root (not the example directory)
   cd /path/to/async-aws-lambda
   docker build -f examples/sam-example/Dockerfile -t example-function:latest .
   ```

3. **Set up database**:

   **Option A: SQLite (Simplest for quick testing)**
   
   ```bash
   # Uses in-memory database by default (no setup needed)
   # Or use a file-based database:
   mkdir -p /tmp
   export DATABASE_URL="sqlite+aiosqlite:///tmp/example.db"
   ```

   **Option B: PostgreSQL (For production-like testing)**
   
   Start PostgreSQL using docker-compose:
   
   ```bash
   cd examples/sam-example
   docker-compose up -d
   ```
   
   Wait for PostgreSQL to be ready (check with `docker-compose ps`), then use:
   
   ```bash
   # Note: docker-compose uses port 5433 to avoid conflicts
   export DATABASE_URL="postgresql+asyncpg://testuser:testpass@localhost:5433/testdb"
   ```
   
   Or if you have a local PostgreSQL instance:
   
   ```bash
   export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/mydb"
   ```

## Running Locally

### Option 1: Invoke Function Directly

Build the application (SAM will detect and use the Dockerfile):

```bash
cd examples/sam-example
sam build
```

Then invoke the function:

**With SQLite (default):**
```bash
sam local invoke ExampleFunction \
  --event events/event.json
```

**With PostgreSQL:**
```bash
# Make sure PostgreSQL is running (docker-compose up -d)
sam local invoke ExampleFunction \
  --event events/event.json \
  --parameter-overrides "DatabaseUrl=postgresql+asyncpg://testuser:testpass@host.docker.internal:5432/testdb"
```

**Note**: Use `host.docker.internal` instead of `localhost` when connecting from the Lambda container to services on your host machine.

### Option 2: Start Local API Server

Build the application:

```bash
cd examples/sam-example
sam build
```

Start the API server:

**With SQLite (default):**
```bash
sam local start-api
```

**With PostgreSQL:**
```bash
sam local start-api \
  --parameter-overrides "DatabaseUrl=postgresql+asyncpg://testuser:testpass@host.docker.internal:5433/testdb"
```

Then test with:

```bash
curl http://localhost:3000/hello
```

## Testing with Different Databases

### SQLite (Default)

SQLite is the default and requires no setup:

```bash
cd examples/sam-example
sam build
sam local invoke ExampleFunction --event events/event.json
```

### PostgreSQL

1. Start PostgreSQL using docker-compose:

   ```bash
   cd examples/sam-example
   docker-compose up -d
   ```

2. Wait for PostgreSQL to be ready (check with `docker-compose ps`)

3. Build and invoke with PostgreSQL:

   ```bash
   sam build
   sam local invoke ExampleFunction \
     --event events/event.json \
     --parameter-overrides "DatabaseUrl=postgresql+asyncpg://testuser:testpass@host.docker.internal:5433/testdb"
   ```

4. Stop PostgreSQL when done:

   ```bash
   docker-compose down
   ```

## Configuration

### Database URL Format

The `DATABASE_URL` environment variable supports different database backends:

- **SQLite**: `sqlite+aiosqlite:///path/to/database.db`
  - Use absolute paths: `sqlite+aiosqlite:///tmp/example.db`
  - Use relative paths: `sqlite+aiosqlite:///./example.db`
  - In-memory: `sqlite+aiosqlite:///:memory:`

- **PostgreSQL**: `postgresql+asyncpg://user:password@host:port/database`
  - Example: `postgresql+asyncpg://postgres:password@localhost:5432/mydb`
  - **Important**: When connecting from SAM local containers, use `host.docker.internal` instead of `localhost`:
    - `postgresql+asyncpg://testuser:testpass@host.docker.internal:5433/testdb`

### Template Parameters

You can override the database URL by passing it as a parameter:

**SQLite:**
```bash
sam local invoke ExampleFunction \
  --event events/event.json \
  --parameter-overrides "DatabaseUrl=sqlite+aiosqlite:///tmp/example.db"
```

**PostgreSQL:**
```bash
# Make sure PostgreSQL is running (docker-compose up -d)
sam local invoke ExampleFunction \
  --event events/event.json \
  --parameter-overrides "DatabaseUrl=postgresql+asyncpg://testuser:testpass@host.docker.internal:5433/testdb"
```

### Docker Image

The example uses a Docker image that:
- Installs the `async-aws-lambda` package from the parent directory
- Includes all required dependencies
- Sets up the Lambda handler correctly

To rebuild after making changes:

```bash
cd examples/sam-example
sam build
```

## Project Structure

```
sam-example/
├── handler.py          # Lambda handler function
├── template.yaml       # SAM template (uses Docker image)
├── docker-compose.yml  # PostgreSQL for local testing
├── samconfig.toml     # SAM CLI configuration
├── requirements.txt   # Python dependencies
├── events/
│   └── event.json     # Sample event for testing
└── README.md          # This file
```

**Note**: The `Dockerfile` is located in the project root (`../../Dockerfile`) because the build context is the project root.

## Handler Details

The example handler (`handler.py`) demonstrates:

- Using `@lambda_handler` decorator for async Lambda functions
- Using `@with_database` decorator for automatic database session injection
- Executing database queries with SQLAlchemy
- Error handling

## Customizing the Example

### Adding SQLAlchemy Models

You can create models using the `Base` class from `async_aws_lambda.database`:

```python
from async_aws_lambda.database import Base
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
```

Then use them in your handler:

```python
from sqlalchemy import select

@lambda_handler
@with_database
async def handler(event, context, db_session: AsyncSession):
    result = await db_session.execute(select(User))
    users = result.scalars().all()
    return {"statusCode": 200, "body": [{"id": u.id, "name": u.name} for u in users]}
```

## Troubleshooting

### Database Connection Issues

1. **SQLite**: Ensure the directory exists and is writable
   ```bash
   mkdir -p /tmp
   chmod 777 /tmp
   ```

2. **PostgreSQL**: Ensure PostgreSQL is running and accessible
   ```bash
   # Test connection
   psql -h localhost -U user -d mydb
   ```

### SAM CLI Issues

1. **Docker not running**: Ensure Docker Desktop or Docker Engine is running
2. **Port conflicts**: If port 3000 is in use, SAM will use the next available port
3. **Build errors**: Try `sam build --use-container` to build in a clean container

## Next Steps

- Add more complex database operations
- Add configuration management with `@with_config`
- Add error handling with the error handling framework
- Deploy to AWS using `sam deploy`

## Resources

- [AWS SAM CLI Documentation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
- [async-aws-lambda Documentation](../../README.md)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)


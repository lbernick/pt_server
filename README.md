# PT Server

A FastAPI-based REST API server.

## Setup

### Prerequisites

- Python 3.11 or higher
- pip
- Docker and Docker Compose (for database)

### Installation

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
```bash
# On macOS/Linux
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root (copy from `.env.example`):
```bash
cp .env.example .env
```

Then edit `.env` and add your actual API key:
```bash
ANTHROPIC_API_KEY=your_api_key_here
DATABASE_URL=postgresql://pt_user:pt_password@localhost:5432/pt_server
```

5. Start the database:
```bash
docker-compose up -d
```

This will start:
- PostgreSQL database on `localhost:5432`
- pgAdmin UI on `http://localhost:5050` (optional, for database management)

## Running the Server

Start the development server:
```bash
uvicorn main:app --reload --app-dir=src
```

The server will start at `http://localhost:8000`. The `--reload` option enables auto-reload on code changes.
If you want to connect to the server from your phone (e.g. using the Expo Go app), you must run the server with `--host 0.0.0.0`.

## API Documentation

Once the server is running, you can access:

- Interactive API documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative API documentation (ReDoc): `http://localhost:8000/redoc`

## Available Endpoints

### GET /
Returns a welcome message.

### GET /health
Health check endpoint.

### POST /api/v1/chat
Chat with AI

## Code Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for code formatting and linting.

### Format code

Use the provided script:
```bash
./scripts/format.sh
```

Or run ruff commands directly:
```bash
# Format code
ruff format .

# Check and fix linting issues
ruff check --fix .

# Just check without fixing
ruff check .
```

## Testing

Run tests with pytest:
```bash
pytest
```

Run tests with verbose output:
```bash
pytest -v
```

Run tests with coverage:
```bash
pytest --cov=. --cov-report=term-missing
```

## Database Management

### Starting/Stopping the Database

Start the database:
```bash
docker-compose up -d
```

Stop the database:
```bash
docker-compose down
```

View database logs:
```bash
docker-compose logs -f postgres
```

### pgAdmin (Database UI)

Access pgAdmin at `http://localhost:5050`
- Email: `admin@example.com`
- Password: `admin`

To connect to the database in pgAdmin:
- Host: `postgres` (or `host.docker.internal` on Mac/Windows)
- Port: `5432`
- Database: `pt_server`
- Username: `pt_user`
- Password: `pt_password`

### Connecting to PostgreSQL CLI

```bash
docker-compose exec postgres psql -U pt_user -d pt_server
```

### Database Migrations

This project uses Alembic for database migrations.

#### Create a new migration

After making changes to models in `src/models_db.py`, generate a migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

#### Apply migrations

Apply all pending migrations:
```bash
alembic upgrade head
```

#### Rollback migrations

Rollback the last migration:
```bash
alembic downgrade -1
```

#### View migration history

```bash
alembic history
```

#### Check current migration version

```bash
alembic current
```

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

Then edit `.env` and add your configuration:
```bash
ANTHROPIC_API_KEY=your_api_key_here
DATABASE_URL=postgresql://pt_user:pt_password@localhost:5432/pt_server
FIREBASE_PROJECT_ID=your_firebase_project_id
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=./firebase-service-account.json
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

## Authentication

All API endpoints (except `/` and `/health`) require Firebase authentication. Users must include a valid Firebase ID token in the `Authorization` header of their requests.

### Local Development with Firebase Auth Emulator

For local testing without setting up a real Firebase project, use the Firebase Auth Emulator:

#### 1. Install Firebase CLI

```bash
npm install -g firebase-tools
```

#### 2. Initialize Firebase Emulator

In your project directory:
```bash
firebase init emulators
```

Select "Authentication Emulator" and use the default port (9099).

#### 3. Start the Emulator

```bash
firebase emulators:start --only auth
```

The emulator UI will be available at `http://localhost:4000`.

#### 4. Update Your `.env` File

Add this line to connect to the emulator:
```bash
FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
```

#### 5. Create a Test User

Visit `http://localhost:4000`, go to the Authentication tab, and create a test user with an email and password.

#### 6. Get a Test Token

Use this Python script to get an ID token for testing:

```bash
python scripts/get_test_token.py
```

#### 7. Make Authenticated Requests

Use the token from step 6 in your API requests:

```bash
TOKEN="your_id_token_here"

curl -X GET http://localhost:8000/api/v1/templates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

### Using Real Firebase (Production)

For production or testing with real Firebase:

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable Authentication providers (Email/Password, Google, etc.)
3. Download service account key from Project Settings → Service Accounts
4. Save as `firebase-service-account.json` in project root
5. Update `.env` with your project ID
6. Remove `FIREBASE_AUTH_EMULATOR_HOST` from `.env`

See `AUTHENTICATION_IMPLEMENTATION.md` for detailed Firebase setup instructions.

## Available Endpoints

### GET /
Returns a welcome message.

### GET /health
Health check endpoint.

### POST /api/v1/chat
Chat with AI

### POST /api/v1/generate-training-plan
Generate a personalized weekly training plan based on user's fitness profile. **Requires authentication.**

**Example CURL command:**
```bash
curl -X POST http://localhost:8000/api/v1/generate-training-plan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fitness_goals": ["build strength", "muscle gain"],
    "experience_level": "intermediate",
    "current_routine": "3 day push/pull/legs split",
    "days_per_week": 4,
    "equipment_available": ["barbell", "dumbbells", "squat rack", "bench"],
    "injuries_limitations": [],
    "preferences": "prefer compound movements"
  }'
```

**Response format:**
```json
{
  "description": "4-day upper/lower strength training split",
  "templates": [
    {
      "name": "Upper Body Strength",
      "description": "Focus on compound pressing and pulling",
      "exercises": ["Bench Press", "Barbell Rows", "Overhead Press"]
    }
  ],
  "microcycle": [0, 1, -1, 0, 1, -1, -1]
}
```

Note: The `microcycle` array represents which template to use each day (Monday=index 0), where `-1` indicates a rest day.

### GET /api/v1/training-plan
Get the user's current training plan. Returns the most recently created training plan for the authenticated user. **Requires authentication.**

**Example CURL command:**
```bash
curl http://localhost:8000/api/v1/training-plan \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
{
  "id": "uuid-456",
  "description": "4-day upper/lower strength training split",
  "templates": [
    {
      "id": "uuid-789",
      "name": "Upper Body Strength",
      "description": "Focus on compound pressing and pulling",
      "exercises": ["Bench Press", "Barbell Rows", "Overhead Press"]
    },
    {
      "id": "uuid-790",
      "name": "Lower Body Power",
      "description": "Build leg strength",
      "exercises": ["Back Squat", "Romanian Deadlift"]
    }
  ],
  "microcycle": [0, 1, -1, 0, 1, -1, -1],
  "created_at": "2025-12-01T10:30:00Z",
  "updated_at": "2025-12-01T10:30:00Z"
}
```

Returns 404 if no training plan exists.

### GET /api/v1/templates
List all workout templates for the authenticated user with pagination. **Requires authentication.**

**Example CURL command:**
```bash
curl http://localhost:8000/api/v1/templates \
  -H "Authorization: Bearer $TOKEN"
```

**With pagination:**
```bash
curl "http://localhost:8000/api/v1/templates?skip=0&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
[
  {
    "id": "uuid-123",
    "name": "Upper Body Strength",
    "description": "Focus on compound pressing and pulling",
    "exercises": ["Bench Press", "Barbell Rows", "Overhead Press"]
  }
]
```

### GET /api/v1/templates/:id
Get a specific workout template by ID. Only returns templates that belong to the authenticated user. **Requires authentication.**

**Example CURL command:**
```bash
curl http://localhost:8000/api/v1/templates/uuid-123 \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
{
  "id": "uuid-123",
  "name": "Upper Body Strength",
  "description": "Focus on compound pressing and pulling",
  "exercises": ["Bench Press", "Barbell Rows", "Overhead Press"]
}
```

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

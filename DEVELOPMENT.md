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

#### Using Real Firebase (Production)

For production or testing with real Firebase:

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable Authentication providers (Email/Password, Google, etc.)
3. Download service account key from Project Settings → Service Accounts
4. Save as `firebase-service-account.json` in project root
5. Update `.env` with your project ID
6. Remove `FIREBASE_AUTH_EMULATOR_HOST` from `.env`

### Firebase Setup Instructions

#### Creating a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" or select existing project
3. Follow the setup wizard

#### Setting Up Authentication

1. In Firebase Console, go to **Authentication** → **Sign-in method**
2. Enable your desired sign-in providers (Email/Password, Google, etc.)
3. Configure OAuth redirect URLs if using social login

#### Getting Service Account Credentials

1. Go to **Project Settings** (gear icon) → **Service accounts**
2. Click "Generate new private key"
3. Save the JSON file as `firebase-service-account.json` in project root
4. Update `.env`:
   ```bash
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_SERVICE_ACCOUNT_KEY_PATH=./firebase-service-account.json
   ```

#### Alternative: Application Default Credentials (Production)

For production deployments (Google Cloud, Cloud Run, etc.):
1. Don't include service account file
2. Use Application Default Credentials
3. Only set `FIREBASE_PROJECT_ID` in environment

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
      "exercises": [
        {
          "name": "Bench Press",
          "sets": 4,
          "rep_min": 6,
          "rep_max": 8
        },
        {
          "name": "Barbell Rows",
          "sets": 4,
          "rep_min": 8,
          "rep_max": 10
        },
        {
          "name": "Overhead Press",
          "sets": 3,
          "rep_min": 8,
          "rep_max": 12
        }
      ]
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
      "exercises": [
        {
          "name": "Bench Press",
          "sets": 4,
          "rep_min": 6,
          "rep_max": 8
        },
        {
          "name": "Barbell Rows",
          "sets": 4,
          "rep_min": 8,
          "rep_max": 10
        },
        {
          "name": "Overhead Press",
          "sets": 3,
          "rep_min": 8,
          "rep_max": 12
        }
      ]
    },
    {
      "id": "uuid-790",
      "name": "Lower Body Power",
      "description": "Build leg strength",
      "exercises": [
        {
          "name": "Back Squat",
          "sets": 5,
          "rep_min": 5,
          "rep_max": 5
        },
        {
          "name": "Romanian Deadlift",
          "sets": 3,
          "rep_min": 8,
          "rep_max": 10
        }
      ]
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
    "exercises": [
      {
        "name": "Bench Press",
        "sets": 4,
        "rep_min": 6,
        "rep_max": 8
      },
      {
        "name": "Barbell Rows",
        "sets": 4,
        "rep_min": 8,
        "rep_max": 10
      },
      {
        "name": "Overhead Press",
        "sets": 3,
        "rep_min": 8,
        "rep_max": 12
      }
    ]
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
  "exercises": [
    {
      "name": "Bench Press",
      "sets": 4,
      "rep_min": 6,
      "rep_max": 8
    },
    {
      "name": "Barbell Rows",
      "sets": 4,
      "rep_min": 8,
      "rep_max": 10
    },
    {
      "name": "Overhead Press",
      "sets": 3,
      "rep_min": 8,
      "rep_max": 12
    }
  ]
}
```

### GET /api/v1/workouts

List workouts for the authenticated user with optional date filtering and pagination. **Requires authentication.**

**Query Parameters:**
- `skip` (int, default=0): Number of workouts to skip
- `limit` (int, default=100): Maximum number of workouts to return
- `date` (string, optional): Filter by date in YYYY-MM-DD format

**Example: Get all workouts**
```bash
curl http://localhost:8000/api/v1/workouts \
  -H "Authorization: Bearer $TOKEN"
```

**Example: Get today's workouts**
```bash
curl "http://localhost:8000/api/v1/workouts?date=$(date +%Y-%m-%d)" \
  -H "Authorization: Bearer $TOKEN"
```

**Example: Get workouts for a specific date**
```bash
curl "http://localhost:8000/api/v1/workouts?date=2025-12-09" \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
[
  {
    "id": "uuid-123",
    "template_id": "uuid-456",
    "date": "2025-12-09",
    "start_time": "2025-12-09T09:00:00",
    "end_time": "2025-12-09T10:30:00",
    "exercises": null
  }
]
```

### POST /api/v1/workouts

Create a new workout for the authenticated user. **Requires authentication.**

**Example CURL command:**
```bash
curl -X POST http://localhost:8000/api/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-09",
    "start_time": "2025-12-09T09:00:00",
    "end_time": "2025-12-09T10:30:00"
  }'
```

**Minimal example (only date required):**
```bash
curl -X POST http://localhost:8000/api/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-09"
  }'
```

**Response format:**
```json
{
  "id": "uuid-123",
  "template_id": null,
  "date": "2025-12-09",
  "start_time": "2025-12-09T09:00:00",
  "end_time": "2025-12-09T10:30:00",
  "exercises": null
}
```

### GET /api/v1/workouts/:id

Get a specific workout by ID. Only returns workouts that belong to the authenticated user. **Requires authentication.**

**Example CURL command:**
```bash
curl http://localhost:8000/api/v1/workouts/uuid-123 \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
{
  "id": "uuid-123",
  "template_id": "uuid-456",
  "date": "2025-12-09",
  "start_time": "2025-12-09T09:00:00",
  "end_time": "2025-12-09T10:30:00",
  "exercises": [...]
}
```

Returns 404 if workout not found or doesn't belong to the user.

### PATCH /api/v1/workouts/:id

Partially update an existing workout. Only provided fields will be updated. **Requires authentication.**

**Example CURL command:**
```bash
curl -X PATCH http://localhost:8000/api/v1/workouts/uuid-123 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-10",
    "start_time": "2025-12-10T14:00:00",
    "end_time": "2025-12-10T15:30:00"
  }'
```

**Partial update example (only date):**
```bash
curl -X PATCH http://localhost:8000/api/v1/workouts/uuid-123 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-10"
  }'
```

**Response format:**
```json
{
  "id": "uuid-123",
  "template_id": "uuid-456",
  "date": "2025-12-10",
  "start_time": "2025-12-10T14:00:00",
  "end_time": "2025-12-10T15:30:00",
  "exercises": [...]
}
```

Returns 404 if workout not found or doesn't belong to the user.

### POST /api/v1/workouts/:id/start

Start a workout by setting the start time to now. **Requires authentication.**

Can only start workouts that haven't been started yet and are scheduled for today. If the workout has a template but no exercises, this will automatically snapshot the template exercises.

**Example CURL command:**
```bash
curl -X POST http://localhost:8000/api/v1/workouts/uuid-123/start \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
{
  "id": "uuid-123",
  "template_id": "uuid-456",
  "date": "2025-12-10",
  "start_time": "2025-12-10T14:30:00",
  "end_time": null,
  "exercises": [
    {
      "name": "Bench Press",
      "target_sets": 4,
      "target_rep_min": 6,
      "target_rep_max": 8,
      "sets": [
        {
          "reps": null,
          "weight": null,
          "completed": false,
          "notes": null
        }
      ],
      "notes": null
    }
  ]
}
```

Returns 400 if:
- Workout has already been started
- Workout is not scheduled for today (e.g., scheduled for future or past dates)

Returns 404 if workout not found or doesn't belong to the user.

### POST /api/v1/workouts/:id/cancel

Cancel a workout in progress by clearing the start time. **Requires authentication.**

Can only cancel workouts that are in progress (start_time is set, end_time is None).

**Example CURL command:**
```bash
curl -X POST http://localhost:8000/api/v1/workouts/uuid-123/cancel \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
{
  "id": "uuid-123",
  "template_id": "uuid-456",
  "date": "2025-12-10",
  "start_time": null,
  "end_time": null,
  "exercises": [...]
}
```

Returns 400 if workout has not been started or has already been finished. Returns 404 if workout not found or doesn't belong to the user.

### POST /api/v1/workouts/:id/finish

Finish a workout by setting the end time to now. **Requires authentication.**

Can only finish workouts that are in progress (start_time is set, end_time is None).

**Example CURL command:**
```bash
curl -X POST http://localhost:8000/api/v1/workouts/uuid-123/finish \
  -H "Authorization: Bearer $TOKEN"
```

**Response format:**
```json
{
  "id": "uuid-123",
  "template_id": "uuid-456",
  "date": "2025-12-10",
  "start_time": "2025-12-10T14:30:00",
  "end_time": "2025-12-10T15:45:00",
  "exercises": [...]
}
```

Returns 400 if workout has not been started or has already been finished. Returns 404 if workout not found or doesn't belong to the user.

### DELETE /api/v1/workouts/:id

Delete a workout. **Requires authentication.**

**Example CURL command:**
```bash
curl -X DELETE http://localhost:8000/api/v1/workouts/uuid-123 \
  -H "Authorization: Bearer $TOKEN"
```

Returns 204 No Content on success. Returns 404 if workout not found or doesn't belong to the user.

### POST /api/v1/workouts/:id/suggest

Get AI-powered rep and weight suggestions for a scheduled workout based on template prescription and workout history. **Requires authentication.**

This endpoint analyzes the last 4 weeks of completed workouts to provide personalized suggestions for sets, reps, and weights. The suggestions are returned but **NOT** automatically applied to the workout, allowing you to review and modify them before use.

**Requirements:**
- Workout must exist and belong to the authenticated user
- Workout must have a template (cannot suggest for workouts without templates)
- Workout must not be completed (end_time must be None)

**Request Body (all fields optional):**
```json
{
  "training_phase": "hypertrophy",
  "goal": "progressive overload",
  "notes": "Feeling strong today"
}
```

**Example: Get basic suggestions**
```bash
curl -X POST http://localhost:8000/api/v1/workouts/uuid-123/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Example: Get suggestions with training context**
```bash
curl -X POST http://localhost:8000/api/v1/workouts/uuid-123/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "training_phase": "hypertrophy",
    "goal": "progressive overload",
    "notes": "Feeling strong, ready to increase weight"
  }'
```

**Example: Get suggestions during deload week**
```bash
curl -X POST http://localhost:8000/api/v1/workouts/uuid-123/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "training_phase": "deload",
    "goal": "recovery",
    "notes": "Feeling fatigued from last week"
  }'
```

**Response format:**
```json
{
  "exercises": [
    {
      "name": "Bench Press",
      "sets": [
        {
          "reps": 8,
          "weight": 185.0
        },
        {
          "reps": 8,
          "weight": 185.0
        },
        {
          "reps": 7,
          "weight": 185.0
        },
        {
          "reps": 6,
          "weight": 185.0
        }
      ],
      "notes": "Strong progression trend over last 4 weeks, ready for weight increase"
    },
    {
      "name": "Barbell Rows",
      "sets": [
        {
          "reps": 10,
          "weight": 135.0
        },
        {
          "reps": 10,
          "weight": 135.0
        },
        {
          "reps": 9,
          "weight": 135.0
        },
        {
          "reps": 8,
          "weight": 135.0
        }
      ],
      "notes": "First time performing this exercise - focus on form"
    }
  ],
  "overall_notes": "Focus on controlled tempo for hypertrophy adaptation"
}
```

**How to apply suggestions:**

The suggestions endpoint is read-only and does not modify your workout. To apply the suggestions:

1. Get suggestions using this endpoint
2. Review the AI's recommendations
3. Modify as needed based on how you feel
4. Apply using `PATCH /api/v1/workouts/:id/exercises`

**Example workflow:**
```bash
# 1. Get suggestions
SUGGESTIONS=$(curl -X POST http://localhost:8000/api/v1/workouts/uuid-123/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}')

# 2. Review suggestions (JSON output)
echo $SUGGESTIONS | jq

# 3. Apply suggestions (or modified version) to workout
curl -X PATCH http://localhost:8000/api/v1/workouts/uuid-123/exercises \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exercises": [
      {
        "name": "Bench Press",
        "target_sets": 4,
        "target_rep_min": 6,
        "target_rep_max": 8,
        "sets": [
          {"reps": 8, "weight": 185.0, "completed": false, "notes": null},
          {"reps": 8, "weight": 185.0, "completed": false, "notes": null},
          {"reps": 7, "weight": 185.0, "completed": false, "notes": null},
          {"reps": 6, "weight": 185.0, "completed": false, "notes": null}
        ],
        "notes": null
      }
    ]
  }'
```

**Error responses:**
- 400: Cannot generate suggestions for completed workouts
- 400: Cannot generate suggestions for workouts without a template
- 404: Workout not found

**How it works:**

1. Queries the last 4 weeks (28 days) of completed workouts
2. Analyzes performance trends per exercise (weights, reps, progression)
3. Considers template prescription (target sets and rep ranges)
4. Applies progressive overload principles
5. Adapts to training context (if provided)
6. Returns personalized suggestions with rationale

**Training phases:**
- `hypertrophy`: Focus on muscle growth (moderate weight, higher volume)
- `strength`: Focus on maximal strength (heavier weight, lower reps)
- `endurance`: Focus on muscular endurance (lighter weight, higher reps)
- `deload`: Recovery week (reduced weight/volume)

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

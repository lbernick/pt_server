# PT Server

A FastAPI-based REST API server.

## Setup

### Prerequisites

- Python 3.11 or higher
- pip

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

4. Create a `.env` file in the project root:
```bash
ANTHROPIC_API_KEY=your_api_key_here
```

## Running the Server

Start the development server:
```bash
uvicorn main:app --reload
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
./format.sh
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

# Firebase Authentication Implementation Plan

This document outlines the complete implementation plan for adding Firebase authentication to the PT Server.

## Overview

We're adding Firebase Authentication to secure all API endpoints and ensure users can only access their own data. The implementation uses Firebase Admin SDK for server-side token verification and integrates with FastAPI's dependency injection system.

## Implementation Steps

### 1. Firebase Infrastructure Setup ✅

**Files Modified:**
- `requirements.txt` - Added `firebase-admin==6.5.0`
- `.env.example` - Added Firebase configuration variables
- `.gitignore` - Added `firebase-service-account.json`

**New Files:**
- `src/firebase_config.py` - Firebase Admin SDK initialization

**Key Features:**
- Lazy initialization with `@lru_cache` decorator
- Support for both service account file and Application Default Credentials
- Environment variable configuration

### 2. Authentication System ✅

**New File:** `src/auth.py`

**Three Dependency Injection Functions:**

1. **`verify_firebase_token()`** - Base authentication
   - Verifies Firebase ID token from Authorization header
   - Returns `FirebaseUser` object with uid, email, claims
   - Returns 401 for invalid/missing tokens

2. **`get_or_create_user()`** - Full authentication (most common)
   - Calls `verify_firebase_token()` internally
   - Auto-creates local database user on first login
   - Returns `AuthenticatedUser` with both Firebase and local user info
   - Use this for most authenticated endpoints

3. **`optional_auth()`** - Optional authentication
   - Returns `None` if no token provided
   - Returns `FirebaseUser` if valid token provided
   - Use for endpoints that can work with or without auth

**Data Models:**
```python
class FirebaseUser(BaseModel):
    uid: str
    email: Optional[str] = None
    email_verified: bool = False
    claims: dict = {}

class AuthenticatedUser(BaseModel):
    firebase_uid: str
    user_id: UUID  # Local database user ID
    email: str
    firebase_user: FirebaseUser
```

### 3. Database Schema Updates ✅

**File Modified:** `src/models.py`

**Changes to `UserDB`:**
- Added `firebase_uid` column (unique, indexed)
- This links Firebase users to local database records

**Changes to All Data Models:**
- `WorkoutDB` - Added `user_id` foreign key
- `TemplateDB` - Added `user_id` foreign key
- `TrainingPlanDB` - Added `user_id` foreign key

**Migration:**
- Migration file: `c54a91116625_add_firebase_uid_and_user_id_foreign_.py`
- All user_id columns are indexed for query performance

### 4. Endpoint Updates ✅

**Files Modified:**

1. **`src/workouts_api.py`** - All 5 endpoints now authenticated
   - `POST /api/v1/workouts` - Create workout
   - `GET /api/v1/workouts` - List workouts (user-filtered)
   - `GET /api/v1/workouts/:id` - Get workout (user-filtered)
   - `PATCH /api/v1/workouts/:id` - Update workout (user-filtered)
   - `DELETE /api/v1/workouts/:id` - Delete workout (user-filtered)

2. **`src/templates_api.py`** - Both endpoints authenticated
   - `GET /api/v1/templates` - List templates (user-filtered)
   - `GET /api/v1/templates/:id` - Get template (user-filtered)

3. **`src/workout.py`** - Training plan endpoints authenticated
   - `POST /api/v1/generate-training-plan` - Generate plan
   - `GET /api/v1/training-plan` - Get user's most recent plan (user-filtered)
   - Updated `save_training_plan_to_db()` to accept `user_id` parameter

4. **`src/onboarding.py`** - Onboarding requires authentication
   - `POST /api/v1/onboarding/message` - Chat with onboarding assistant

**Pattern Used in All Endpoints:**
```python
from auth import AuthenticatedUser, get_or_create_user

@router.get("/endpoint")
def my_endpoint(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
):
    # Query with user_id filter
    items = db.query(Model).filter(Model.user_id == user.user_id).all()
    # Or create with user_id
    new_item = Model(user_id=user.user_id, ...)
```

### 5. Test Infrastructure ✅

**File Modified:** `src/conftest.py`

**New Fixtures Added:**
1. `mock_firebase_auth` - Mocks Firebase Admin SDK
2. `test_firebase_user` - Sample Firebase user data
3. `test_user` - Sample database user
4. `test_authenticated_user` - Combined authenticated user context

**Test Files Updated:**
- `src/test_workouts_api.py` - 12 tests ✅
- `src/test_templates_api.py` - 9 tests ✅
- `src/test_onboarding.py` - 4 tests ✅
- `src/test_workout.py` - 16 tests ✅
- `src/test_main.py` - 2 tests ✅

**Total: 43/43 tests passing** ✅

**Pattern Used in Test Files:**
```python
@pytest.fixture
def client(db_session, test_authenticated_user, mock_firebase_auth):
    """Create test client with database and auth overrides."""
    def override_get_db():
        yield db_session

    def override_auth():
        return test_authenticated_user

    mock_firebase_auth.verify_id_token.return_value = {
        "uid": test_authenticated_user.firebase_uid,
        "email": test_authenticated_user.email,
        "email_verified": True,
    }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_or_create_user] = override_auth

    yield TestClient(app)
    app.dependency_overrides.clear()
```

## Firebase Setup Instructions

### Creating a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" or select existing project
3. Follow the setup wizard

### Setting Up Authentication

1. In Firebase Console, go to **Authentication** → **Sign-in method**
2. Enable your desired sign-in providers (Email/Password, Google, etc.)
3. Configure OAuth redirect URLs if using social login

### Getting Service Account Credentials

1. Go to **Project Settings** (gear icon) → **Service accounts**
2. Click "Generate new private key"
3. Save the JSON file as `firebase-service-account.json` in project root
4. Update `.env`:
   ```bash
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_SERVICE_ACCOUNT_KEY_PATH=./firebase-service-account.json
   ```

### Alternative: Application Default Credentials (Production)

For production deployments (Google Cloud, Cloud Run, etc.):
1. Don't include service account file
2. Use Application Default Credentials
3. Only set `FIREBASE_PROJECT_ID` in environment

## Client-Side Integration

### Getting an ID Token (Example with Firebase JS SDK)

```javascript
import { getAuth } from 'firebase/auth';

// After user signs in
const auth = getAuth();
const user = auth.currentUser;
const idToken = await user.getIdToken();

// Use token in API requests
fetch('http://localhost:8000/api/v1/workouts', {
  headers: {
    'Authorization': `Bearer ${idToken}`,
    'Content-Type': 'application/json',
  }
});
```

### Example: React Native with Firebase

```javascript
import auth from '@react-native-firebase/auth';

// Get current user's token
const user = auth().currentUser;
const idToken = await user.getIdToken();

// Make authenticated request
const response = await fetch('http://your-server.com/api/v1/workouts', {
  headers: {
    'Authorization': `Bearer ${idToken}`,
    'Content-Type': 'application/json',
  }
});
```

## API Usage Examples

### Authenticated Request

```bash
# Get ID token from Firebase client
TOKEN="your_firebase_id_token"

# Make authenticated request
curl -X GET http://localhost:8000/api/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

### Creating a Workout (Authenticated)

```bash
curl -X POST http://localhost:8000/api/v1/workouts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-12-03",
    "start_time": "2025-12-03T09:00:00",
    "end_time": "2025-12-03T10:30:00"
  }'
```

### Response Codes

- **200/201** - Success
- **401** - Unauthorized (missing or invalid token)
- **403** - Forbidden (valid token but no access to resource)
- **404** - Not found (or doesn't belong to user)

## Security Features

### Data Isolation
- All queries filter by `user_id` automatically
- Users can only see/modify their own data
- Database foreign keys ensure referential integrity

### Token Verification
- Firebase ID tokens are verified on every request
- Tokens expire after 1 hour (Firebase default)
- Invalid tokens return 401 immediately

### Auto-User Creation
- First login automatically creates local user record
- Links Firebase UID to local database user
- Email stored for reference

## Testing Authentication

### Running Tests

```bash
# Run all tests
pytest src/ -v

# Run specific test file
pytest src/test_workouts_api.py -v

# Run with coverage
pytest src/ --cov=src --cov-report=term-missing
```

### Manual Testing with Firebase Auth Emulator

1. Install Firebase emulator:
```bash
npm install -g firebase-tools
firebase init emulators  # Select Auth emulator
firebase emulators:start
```

2. Update `.env` to point to emulator:
```bash
FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
```

3. Create test users via emulator UI at http://localhost:4000

## Troubleshooting

### Common Issues

1. **"No module named 'firebase_admin'"**
   - Solution: `pip install firebase-admin==6.5.0`

2. **"FIREBASE_PROJECT_ID environment variable is required"**
   - Solution: Add `FIREBASE_PROJECT_ID` to `.env` file

3. **"Invalid authentication token"**
   - Check token hasn't expired (1 hour lifetime)
   - Verify token is from correct Firebase project
   - Ensure Authorization header format: `Bearer <token>`

4. **"Template not found" (but it exists)**
   - Template belongs to different user
   - Endpoints filter by user_id automatically

### Debugging Tips

- Check Firebase token payload: Decode at [jwt.io](https://jwt.io)
- Enable Firebase debug logging in `firebase_config.py`
- Use `pytest -v -s` to see print statements in tests
- Check database directly: `docker-compose exec postgres psql -U pt_user -d pt_server`

## Migration from Unauthenticated System

If you have existing data:

1. **Create a migration script** to associate existing data with users:
```python
# migration_script.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import UserDB, WorkoutDB, TemplateDB

# Create default user or prompt for user assignment
default_user = db.query(UserDB).first()

# Update existing records
db.query(WorkoutDB).filter(WorkoutDB.user_id == None).update(
    {"user_id": default_user.id}
)
db.commit()
```

2. **Or start fresh** (if in development):
```bash
# Drop and recreate database
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

## Next Steps

- [ ] Add refresh token support (optional)
- [ ] Add role-based access control (admin users)
- [ ] Add API rate limiting per user
- [ ] Add user profile endpoints (GET/PATCH /api/v1/users/me)
- [ ] Add email verification requirement (optional)
- [ ] Add logging for authentication events
- [ ] Add metrics for authentication (success/failure rates)

## Resources

- [Firebase Admin SDK Documentation](https://firebase.google.com/docs/admin/setup)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Firebase Authentication Best Practices](https://firebase.google.com/docs/auth/admin/verify-id-tokens)

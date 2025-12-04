"""Firebase Authentication dependencies and utilities."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from firebase_admin import auth
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from firebase_config import get_firebase_auth
from models import UserDB


class FirebaseUser(BaseModel):
    """Represents a verified Firebase user from token.

    This is the context object injected into authenticated endpoints.
    """

    uid: str  # Firebase UID
    email: Optional[str] = None
    email_verified: bool = False

    # Additional Firebase claims
    claims: dict = {}


class AuthenticatedUser(BaseModel):
    """Represents a fully authenticated user with local DB record.

    This includes both Firebase data and local database user info.
    """

    firebase_uid: str
    user_id: UUID  # Local database user ID
    email: str
    firebase_user: FirebaseUser


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header.

    Args:
        request: FastAPI Request object

    Returns:
        Token string or None if not present
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None

    return auth_header[7:]  # Remove "Bearer " prefix


async def verify_firebase_token(
    request: Request,
    auth_instance: auth = Depends(get_firebase_auth),
) -> FirebaseUser:
    """Verify Firebase ID token and return user info.

    This is the base authentication dependency. Use this when you need
    to verify authentication but don't need local user data.

    Args:
        request: FastAPI Request object
        auth_instance: Firebase auth instance

    Returns:
        FirebaseUser with verified user data

    Raises:
        HTTPException: 401 if token is invalid/missing

    Example:
        @app.get("/protected")
        async def protected(user: FirebaseUser = Depends(verify_firebase_token)):
            return {"firebase_uid": user.uid}
    """
    token = extract_token_from_request(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Verify the token with Firebase
        decoded_token = auth_instance.verify_id_token(token)

        return FirebaseUser(
            uid=decoded_token["uid"],
            email=decoded_token.get("email"),
            email_verified=decoded_token.get("email_verified", False),
            claims=decoded_token,
        )

    except auth.InvalidIdTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err
    except auth.ExpiredIdTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err
    except Exception as e:
        # Catch any other Firebase auth errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_or_create_user(
    firebase_user: FirebaseUser = Depends(verify_firebase_token),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """Get or create local user from Firebase authentication.

    This dependency provides the full authenticated user context including
    local database record. Use this for most authenticated endpoints.

    Creates a new user record on first login if one doesn't exist.

    Args:
        firebase_user: Verified Firebase user from token
        db: Database session

    Returns:
        AuthenticatedUser with both Firebase and local DB data

    Raises:
        HTTPException: 401 if authentication fails
        HTTPException: 500 if user creation fails

    Example:
        @app.get("/api/v1/profile")
        async def get_profile(user: AuthenticatedUser = Depends(get_or_create_user)):
            return {"user_id": user.user_id, "email": user.email}
    """
    if not firebase_user.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User email is required",
        )

    # Look up user by Firebase UID
    user = db.query(UserDB).filter(UserDB.firebase_uid == firebase_user.uid).first()

    # Create user if doesn't exist (first-time login)
    if not user:
        try:
            user = UserDB(
                firebase_uid=firebase_user.uid,
                email=firebase_user.email,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user: {str(e)}",
            ) from e

    return AuthenticatedUser(
        firebase_uid=firebase_user.uid,
        user_id=user.id,
        email=user.email,
        firebase_user=firebase_user,
    )


# Optional authentication dependency
async def optional_auth(
    request: Request,
    auth_instance: auth = Depends(get_firebase_auth),
) -> Optional[FirebaseUser]:
    """Optional authentication - returns None if not authenticated.

    Use this for endpoints that can work with or without authentication.

    Args:
        request: FastAPI Request object
        auth_instance: Firebase auth instance

    Returns:
        FirebaseUser if authenticated, None otherwise

    Example:
        @app.get("/api/v1/public-or-private")
        async def mixed(user: Optional[FirebaseUser] = Depends(optional_auth)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello anonymous"}
    """
    token = extract_token_from_request(request)

    if not token:
        return None

    try:
        decoded_token = auth_instance.verify_id_token(token)
        return FirebaseUser(
            uid=decoded_token["uid"],
            email=decoded_token.get("email"),
            email_verified=decoded_token.get("email_verified", False),
            claims=decoded_token,
        )
    except Exception:
        # If token verification fails, treat as unauthenticated
        return None

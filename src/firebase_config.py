"""Firebase Admin SDK configuration and initialization."""

import os
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials


@lru_cache(maxsize=1)
def initialize_firebase() -> firebase_admin.App:
    """Initialize Firebase Admin SDK (cached, only runs once).

    Returns:
        firebase_admin.App instance

    Raises:
        ValueError: If required environment variables are missing
    """
    # Check if already initialized
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass  # Not initialized yet

    # Get configuration from environment
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY_PATH")

    if not project_id:
        raise ValueError("FIREBASE_PROJECT_ID environment variable is required")

    # Initialize with service account (production) or default credentials (local)
    if service_account_path and os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        return firebase_admin.initialize_app(cred)
    else:
        # For development/testing without service account
        # Uses Application Default Credentials
        cred = credentials.ApplicationDefault()
        return firebase_admin.initialize_app(cred, {"projectId": project_id})


def get_firebase_auth() -> auth:
    """Get Firebase Auth instance (ensures Firebase is initialized).

    Returns:
        firebase_admin.auth module
    """
    initialize_firebase()
    return auth

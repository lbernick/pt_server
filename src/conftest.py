"""Pytest configuration and shared fixtures."""

import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from auth import AuthenticatedUser, FirebaseUser
from database import Base
from models import UserDB


def get_test_db_url():
    """Get the test database URL from environment or use default."""
    # Use a separate test database
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://pt_user:pt_password@localhost:5432/pt_server_test",
    )


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine that persists for the entire test session."""
    db_url = get_test_db_url()

    # Parse the database URL to create/drop the test database
    base_url = db_url.rsplit("/", 1)[0]
    db_name = db_url.rsplit("/", 1)[1]

    # Create a connection to postgres database to create/drop test database
    admin_engine = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")

    # Drop and recreate the test database for a clean state
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        conn.execute(text(f"CREATE DATABASE {db_name}"))

    admin_engine.dispose()

    # Create engine for the test database
    engine = create_engine(db_url, echo=False)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Teardown: drop all tables and close connections
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

    # Drop the test database after all tests
    admin_engine = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    admin_engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Create a new database session for each test.

    This fixture creates a transaction for each test and rolls it back
    after the test completes, ensuring test isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create a session bound to the connection
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=connection
    )
    session = TestingSessionLocal()

    yield session

    # Rollback the transaction and close the connection
    session.close()
    transaction.rollback()
    connection.close()


# Authentication fixtures


@pytest.fixture
def mock_firebase_auth():
    """Mock Firebase auth for testing."""
    with patch("auth.get_firebase_auth") as mock:
        mock_auth = MagicMock()
        mock.return_value = mock_auth
        yield mock_auth


@pytest.fixture
def test_firebase_user() -> FirebaseUser:
    """Create a test Firebase user."""
    return FirebaseUser(
        uid="test_firebase_uid_123",
        email="test@example.com",
        email_verified=True,
        claims={"uid": "test_firebase_uid_123", "email": "test@example.com"},
    )


@pytest.fixture
def test_user(db_session: Session, test_firebase_user: FirebaseUser) -> UserDB:
    """Create a test user in the database."""
    user = UserDB(
        firebase_uid=test_firebase_user.uid,
        email=test_firebase_user.email,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_authenticated_user(
    test_user: UserDB, test_firebase_user: FirebaseUser
) -> AuthenticatedUser:
    """Create a test authenticated user context."""
    return AuthenticatedUser(
        firebase_uid=test_user.firebase_uid,
        user_id=test_user.id,
        email=test_user.email,
        firebase_user=test_firebase_user,
    )

"""Pytest configuration and shared fixtures."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import Base


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

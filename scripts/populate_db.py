#!/usr/bin/env python3
"""Script to populate the database with test workout data."""

import os
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from database import SessionLocal
from models import UserDB, WorkoutDB

# Load environment variables
load_dotenv()


def create_test_workouts():
    """Create test workout records in the database."""
    db = SessionLocal()
    try:
        # Clear existing workouts
        db.query(WorkoutDB).delete()
        db.commit()
        print("Cleared existing workouts")

        # Create test workouts
        today = date.today()
        workouts = [
            WorkoutDB(
                date=today - timedelta(days=7),
                start_time=datetime(today.year, today.month, today.day - 7, 9, 0),
                end_time=datetime(today.year, today.month, today.day - 7, 10, 30),
            ),
            WorkoutDB(
                date=today - timedelta(days=5),
                start_time=datetime(today.year, today.month, today.day - 5, 14, 0),
                end_time=datetime(today.year, today.month, today.day - 5, 15, 15),
            ),
            WorkoutDB(
                date=today - timedelta(days=3),
                start_time=datetime(today.year, today.month, today.day - 3, 8, 30),
                end_time=datetime(today.year, today.month, today.day - 3, 10, 0),
            ),
            WorkoutDB(
                date=today - timedelta(days=1),
                start_time=datetime(today.year, today.month, today.day - 1, 16, 0),
                end_time=datetime(today.year, today.month, today.day - 1, 17, 30),
            ),
            WorkoutDB(
                date=today,
                start_time=None,
                end_time=None,
            ),
        ]

        db.add_all(workouts)
        db.commit()

        print(f"\nCreated {len(workouts)} test workouts:")
        for workout in workouts:
            db.refresh(workout)
            print(
                f"  - ID: {workout.id}, Date: {workout.date}, "
                f"Start: {workout.start_time}, End: {workout.end_time}"
            )

        print("\nDatabase populated successfully!")

    except Exception as e:
        print(f"Error populating database: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def create_test_user_with_onboarding():
    """Create a test user with partial onboarding data.

    This is useful for testing the resume onboarding flow.
    """
    db = SessionLocal()
    try:
        # Check if test user exists
        test_user = db.query(UserDB).filter(UserDB.email == "test@example.com").first()

        if not test_user:
            print("No test user found. Please create a test user first.")
            print("Use the Firebase Auth Emulator to create: test@example.com")
            return

        # Update with partial onboarding data
        test_user.onboarding_data = {
            "fitness_goals": ["build strength"],
            "experience_level": "intermediate",
            "current_routine": None,
            "days_per_week": None,
            "equipment_available": None,
            "injuries_limitations": None,
            "preferences": None,
        }

        db.commit()
        print(
            f"\nUpdated test user ({test_user.email}) " "with partial onboarding data:"
        )
        print("  - Goals: build strength")
        print("  - Experience: intermediate")
        print("  - Other fields: Not yet collected")
        print("\nUser can now resume onboarding from this state!")

    except Exception as e:
        print(f"Error updating test user: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Populate database with test data")
    parser.add_argument(
        "--workouts",
        action="store_true",
        help="Create test workout records",
    )
    parser.add_argument(
        "--onboarding",
        action="store_true",
        help="Add partial onboarding data to test user",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all population functions",
    )

    args = parser.parse_args()

    # If no args, default to --all
    if not (args.workouts or args.onboarding or args.all):
        args.all = True

    if args.all or args.workouts:
        create_test_workouts()

    if args.all or args.onboarding:
        create_test_user_with_onboarding()

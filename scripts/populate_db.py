#!/usr/bin/env python3
"""Script to populate the database with test workout data."""

import os
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from database import SessionLocal
from models import TemplateDB, UserDB, WorkoutDB

# Load environment variables
load_dotenv()


def create_test_workouts():
    """Create test workout records with optional template references."""
    db = SessionLocal()
    try:
        # Find the first user (or create if none exists)
        test_user = db.query(UserDB).first()
        if not test_user:
            print("No users found. Please create a test user first.")
            print("Use the Firebase Auth Emulator to create: test@example.com")
            return

        # Clear existing workouts for this user
        db.query(WorkoutDB).filter(WorkoutDB.user_id == test_user.id).delete()
        db.commit()
        print(f"Cleared existing workouts for user {test_user.email}")

        # Create a sample template
        template = TemplateDB(
            user_id=test_user.id,
            name="Full Body Strength",
            description="Compound movements for overall strength",
            exercises=[
                {"name": "Squat", "sets": 3, "rep_min": 8, "rep_max": 10},
                {"name": "Bench Press", "sets": 3, "rep_min": 8, "rep_max": 10},
                {"name": "Deadlift", "sets": 3, "rep_min": 5, "rep_max": 8},
            ],
        )
        db.add(template)
        db.flush()  # Get the template ID
        print(f"Created template: {template.name}")

        # Create test workouts - some with template, some without
        today = date.today()
        workouts = [
            WorkoutDB(
                user_id=test_user.id,
                template_id=template.id,  # Link to template
                date=today - timedelta(days=7),
                start_time=datetime(today.year, today.month, today.day - 7, 9, 0),
                end_time=datetime(today.year, today.month, today.day - 7, 10, 30),
            ),
            WorkoutDB(
                user_id=test_user.id,
                template_id=None,  # No template
                date=today - timedelta(days=5),
                start_time=datetime(today.year, today.month, today.day - 5, 14, 0),
                end_time=datetime(today.year, today.month, today.day - 5, 15, 15),
            ),
            WorkoutDB(
                user_id=test_user.id,
                template_id=template.id,  # Link to template
                date=today - timedelta(days=3),
                start_time=datetime(today.year, today.month, today.day - 3, 8, 30),
                end_time=datetime(today.year, today.month, today.day - 3, 10, 0),
            ),
            WorkoutDB(
                user_id=test_user.id,
                template_id=None,  # No template
                date=today - timedelta(days=1),
                start_time=datetime(today.year, today.month, today.day - 1, 16, 0),
                end_time=datetime(today.year, today.month, today.day - 1, 17, 30),
            ),
            WorkoutDB(
                user_id=test_user.id,
                template_id=template.id,  # Link to template
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
            template_info = (
                f"Template: {template.name}"
                if workout.template_id
                else "No template"
            )
            print(
                f"  - ID: {workout.id}, Date: {workout.date}, "
                f"Start: {workout.start_time}, End: {workout.end_time}, "
                f"{template_info}"
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

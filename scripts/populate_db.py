#!/usr/bin/env python3
"""Script to populate the database with test workout data."""

import os
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from database import SessionLocal
from models import WorkoutDB

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


if __name__ == "__main__":
    create_test_workouts()

#!/usr/bin/env python3
"""
Get a Firebase Auth ID token for local testing with the Firebase Auth Emulator.

Usage:
    python get_test_token.py

Make sure the Firebase Auth Emulator is running on localhost:9099 before using this script.
"""

import sys

import requests

FIREBASE_API_KEY = "demo-key"  # Use any value for emulator
EMAIL = "test@example.com"
PASSWORD = "hello1234"


def get_test_token():
    """Get an ID token from Firebase Auth Emulator."""
    url = f"http://localhost:9099/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"

    try:
        response = requests.post(
            url, json={"email": EMAIL, "password": PASSWORD, "returnSecureToken": True}
        )

        if response.status_code == 200:
            data = response.json()
            token = data["idToken"]
            print(f"✓ Successfully authenticated as {EMAIL}")
            print(f"\nID Token:\n{token}")
            print("\nUse this in your requests:")
            print(f'export TOKEN="{token}"')
            print("\nOr use directly in curl:")
            print(
                f'curl -H "Authorization: Bearer {token}" http://localhost:8000/api/v1/templates'
            )
            return token
        else:
            print(f"✗ Error: {response.status_code}")
            print(f"Response: {response.text}")
            print("\nMake sure:")
            print(
                "1. Firebase Auth Emulator is running (firebase emulators:start --only auth)"
            )
            print(
                f"2. User {EMAIL} exists in the emulator (create at http://localhost:4000)"
            )
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        print("✗ Connection Error: Could not connect to Firebase Auth Emulator")
        print("\nMake sure the emulator is running:")
        print("  firebase emulators:start --only auth")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("Firebase Auth Emulator - Get Test Token")
    print("=" * 50)
    get_test_token()

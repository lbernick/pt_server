"""Anthropic client configuration for dependency injection."""

import os

from anthropic import Anthropic


def get_anthropic_client() -> Anthropic:
    """Dependency function that returns the Anthropic client.

    This centralizes the client configuration so it only needs to be
    defined once, and all endpoints/routers can use it via dependency injection.
    """
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

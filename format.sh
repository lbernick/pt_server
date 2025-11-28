#!/bin/bash

# Format code with ruff
echo "Formatting code with ruff..."
ruff format .

# Check and fix linting issues
echo "Checking and fixing linting issues..."
ruff check --fix .

echo "Done!"

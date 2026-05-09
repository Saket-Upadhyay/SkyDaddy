#!/bin/bash

# Exit immediately if any command fails
set -e

# Check if API_KEY is set
if [ -z "$API_KEY" ]; then
  echo "Error: API_KEY environment variable is not set."
  exit 1
fi

# Define coverage file and repo root
COVERAGE_FILE="SkyDaddy/coverage.xml"
REPO_ROOT="SkyDaddy/"

# Check if coverage file exists
if [ ! -f "$COVERAGE_FILE" ]; then
  echo "Error: Coverage file '$COVERAGE_FILE' not found."
  exit 1
fi

# Upload coverage to Codecov
./codecovuploader/codecov -t "$API_KEY" -f "$COVERAGE_FILE" -R "$REPO_ROOT"
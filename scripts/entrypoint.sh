#!/bin/bash
set -e

# Run database migrations before starting the server
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Start the application
exec "$@"

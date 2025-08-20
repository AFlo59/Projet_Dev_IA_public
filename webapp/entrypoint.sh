#!/bin/bash
set -e

echo "🔄 Starting application with database connectivity checks..."

# Wait for unified database
echo "Checking database connection: $APP_DB_HOST:$APP_DB_PORT"

# Set a timeout of 60 seconds for the database check
max_retries=30
counter=0
until pg_isready -h $APP_DB_HOST -p $APP_DB_PORT -U $DB_ADMIN_USER -d $APP_DB_NAME || [ $counter -eq $max_retries ]; do
    echo "Waiting for database ($APP_DB_HOST:$APP_DB_PORT)... Attempt $counter of $max_retries"
    counter=$((counter+1))
    sleep 2
done

if [ $counter -eq $max_retries ]; then
    echo "⚠️ Warning: Could not connect to database after $max_retries attempts. Continuing anyway..."
else
    echo "✅ Database is available"
fi

# Start the application
echo "Starting web application..."
exec dotnet DnDGameMaster.WebApp.dll 
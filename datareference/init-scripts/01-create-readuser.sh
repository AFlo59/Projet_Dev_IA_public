#!/bin/bash
set -e

# Script to create the readuser with read-only privileges

# Create the readuser if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$ 
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_READ_USER') THEN
            CREATE USER $DB_READ_USER WITH PASSWORD '$DB_READ_PASSWORD';
            RAISE NOTICE 'User $DB_READ_USER created successfully';
        ELSE
            RAISE NOTICE 'User $DB_READ_USER already exists';
        END IF;
    END
    \$\$;
    
    -- Grant connection privileges
    GRANT CONNECT ON DATABASE $POSTGRES_DB TO $DB_READ_USER;
    
    -- Get all schemas
    DO \$\$
    DECLARE
        schema_rec RECORD;
    BEGIN
        FOR schema_rec IN 
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        LOOP
            -- Grant USAGE on each schema
            EXECUTE 'GRANT USAGE ON SCHEMA ' || schema_rec.schema_name || ' TO ' || '$DB_READ_USER';
            
            -- Grant SELECT on all tables in the schema
            EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA ' || schema_rec.schema_name || ' TO ' || '$DB_READ_USER';
            
            -- Set default privileges for future tables
            EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA ' || schema_rec.schema_name || 
                ' GRANT SELECT ON TABLES TO ' || '$DB_READ_USER';
        END LOOP;
    END
    \$\$;
    
    -- Confirm the user was created
    \du $DB_READ_USER;
EOSQL

echo "✅ Readuser setup completed" 
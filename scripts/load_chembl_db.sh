#!/bin/bash

# ChEMBL Database Loading Script
# This script loads the ChEMBL PostgreSQL dump into the PostgreSQL container

set -e  # Exit on error

# Configuration
CONTAINER_NAME="chembl_postgres"
DB_USER="airflow_user"
DB_NAME="chembl_36"
DUMP_FILE="./chembl_36/chembl_36_postgresql/chembl_36_postgresql.dmp"

echo "================================================"
echo "ChEMBL Database Loading Script"
echo "================================================"
echo ""

# Step 1: Check if container is running
echo "[1/5] Checking if PostgreSQL container is running..."
if ! docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: PostgreSQL container '$CONTAINER_NAME' is not running."
    echo "Please start it with: docker-compose -f DockerCompose.yml up -d postgres-db"
    exit 1
fi
echo "✅ Container is running"
echo ""

# Step 2: Check if dump file exists
echo "[2/5] Checking if dump file exists..."
if [ ! -f "$DUMP_FILE" ]; then
    echo "❌ Error: Dump file not found at $DUMP_FILE"
    echo "Please extract the archive first: tar -xzf chembl_36_postgresql.tar.gz"
    exit 1
fi
echo "✅ Dump file found ($(du -h "$DUMP_FILE" | cut -f1))"
echo ""

# Step 3: Create database
echo "[3/5] Creating database '$DB_NAME'..."
# Check if database already exists
DB_EXISTS=$(docker exec -i $CONTAINER_NAME psql -U $DB_USER -d chembl -t -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" | xargs)
if [ "$DB_EXISTS" = "1" ]; then
    echo "⚠️  Database '$DB_NAME' already exists. Dropping it..."
    # Terminate existing connections
    docker exec -i $CONTAINER_NAME psql -U $DB_USER -d chembl -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
    docker exec -i $CONTAINER_NAME psql -U $DB_USER -d chembl -c "DROP DATABASE IF EXISTS $DB_NAME;"
fi
docker exec -i $CONTAINER_NAME psql -U $DB_USER -d chembl -c "CREATE DATABASE $DB_NAME;"
echo "✅ Database created"
echo ""

# Step 4: Copy dump file to container
echo "[4/5] Copying dump file to container..."
docker cp "$DUMP_FILE" $CONTAINER_NAME:/tmp/chembl_36.dmp
echo "✅ Dump file copied"
echo ""

# Step 5: Restore database
echo "[5/5] Restoring database (this may take 5-15 minutes)..."
echo "⏳ Please wait..."
docker exec -i $CONTAINER_NAME pg_restore \
    --no-owner \
    --no-privileges \
    -U $DB_USER \
    -d $DB_NAME \
    /tmp/chembl_36.dmp

echo ""
echo "✅ Database restored successfully!"
echo ""

# Cleanup
echo "Cleaning up temporary files..."
docker exec -i $CONTAINER_NAME rm /tmp/chembl_36.dmp
echo ""

# Verification
echo "================================================"
echo "Verification"
echo "================================================"
echo ""
echo "Checking database tables..."
TABLE_COUNT=$(docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
echo "✅ Found $TABLE_COUNT tables in the database"
echo ""

echo "Sample query - Top 5 molecule ChEMBL IDs:"
docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c "SELECT chembl_id FROM molecule_dictionary LIMIT 5;"
echo ""

echo "================================================"
echo "✅ ChEMBL Database Successfully Loaded!"
echo "================================================"
echo ""
echo "Database Details:"
echo "  - Container: $CONTAINER_NAME"
echo "  - Database: $DB_NAME"
echo "  - User: $DB_USER"
echo "  - Host: localhost"
echo "  - Port: 5432"
echo ""
echo "Connection string:"
echo "  postgresql://$DB_USER:airflow_pass@localhost:5432/$DB_NAME"
echo ""
echo "To connect from Airflow, update your connection to use database: $DB_NAME"
echo ""

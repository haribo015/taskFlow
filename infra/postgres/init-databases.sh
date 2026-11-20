#!/bin/sh
# Creates one database per microservice (database-per-service pattern on a shared instance).
# Executed once by the official postgres image on first start (empty volume).
set -eu

for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' ' '); do
  echo "Creating database '$db'"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE DATABASE "$db";
EOSQL
done

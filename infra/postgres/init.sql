-- Initialize PostgreSQL extensions for Pulse
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Connection and query safety settings
ALTER DATABASE pulse SET statement_timeout = '30s';
ALTER DATABASE pulse SET log_min_duration_statement = 1000;
ALTER DATABASE pulse SET log_connections = on;
ALTER DATABASE pulse SET log_disconnections = on;

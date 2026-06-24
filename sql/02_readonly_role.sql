-- Engine: PostgreSQL
-- Least-privilege role that LLM-generated SQL runs as.
-- This is the executor-side half of the safety model: even if a malicious
-- statement slips past the static guard, this role cannot mutate anything.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly') THEN
    CREATE ROLE readonly LOGIN PASSWORD 'Changph03@';
  END IF;
END
$$;

-- Connect + read the schema, nothing else.
GRANT CONNECT ON DATABASE aiassistant_db TO readonly;
GRANT USAGE ON SCHEMA public TO readonly;

-- SELECT-only on every existing table...
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;

-- ...and on any table created later (e.g. after re-seeding).
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly;

-- Belt-and-suspenders: make sure no write privileges linger.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON ALL TABLES IN SCHEMA public FROM readonly;

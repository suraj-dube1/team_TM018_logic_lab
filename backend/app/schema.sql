CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
  username        text PRIMARY KEY,
  display         text NOT NULL,
  role            text NOT NULL DEFAULT 'student',
  clearance       int NOT NULL,
  departments     text[] NOT NULL DEFAULT '{}',
  password_hash   text,
  password_salt   text,
  created_at      timestamptz DEFAULT now()
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS role text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt text;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS owner_username text;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS owner_username text;

INSERT INTO users(username, display, role, clearance, departments, password_hash, password_salt) VALUES
  ('rahul@student', 'Rahul Patel', 'student', 0, '{student}', '98d5aa43d913e4a603683695ff96c7725790eff97db0adad6c0d728361cbd876', '2bb4e1cc0852d42bae3296227b2ad875'),
  ('neha@faculty', 'Dr. Neha Sharma', 'faculty', 2, '{eng,finance}', '6fea9f75160afc2eec07f30f179d67d1409c42d1b98d298d5186dd16b0177702', '963aed481da6580ab7f428109ecbe555'),
  ('arjun@admin', 'Arjun Mehta', 'admin', 3, '{all}', 'd2ee41ad0164c2be482b22813f64e7b6024bb33ec3e09fd0cc99fbd2c82b7056', '03b9bf842c8f5692ac8dbeef4cc3c912')
ON CONFLICT (username) DO NOTHING;

CREATE TABLE IF NOT EXISTS documents (
  id            serial PRIMARY KEY,
  title         text NOT NULL,
  kind          text NOT NULL,
  path          text,
  min_clearance int  NOT NULL DEFAULT 0,
  departments   text[] NOT NULL DEFAULT '{}',   -- '{}' = every department
  owner_username text,
  created_at    timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id            serial PRIMARY KEY,
  doc_id        int NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  source        text NOT NULL,
  kind          text NOT NULL,                  -- pdf | image | db | text
  page          int  NOT NULL DEFAULT 1,
  bbox          real[],                         -- [x0,y0,x1,y1] as page fractions
  text          text NOT NULL,
  embedding     vector(384) NOT NULL,
  min_clearance int  NOT NULL,
  departments   text[] NOT NULL DEFAULT '{}',
  owner_username text,
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
-- For large corpora add: CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
-- plus SET hnsw.iterative_scan = relaxed_order so RLS filtering still returns k rows.

-- Red-team harness only. The app role has NO access to these.
CREATE TABLE IF NOT EXISTS canaries  (doc_id int REFERENCES documents(id) ON DELETE CASCADE, token text NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (
  id serial PRIMARY KEY, ts timestamptz DEFAULT now(),
  username text, question text, chunk_ids int[], blocked int, dropped int
);

-- The application connects as this role. It is not a superuser and cannot bypass RLS.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vault_app') THEN
    CREATE ROLE vault_app LOGIN PASSWORD 'vault_app_pw' NOSUPERUSER NOBYPASSRLS;
  ELSE
    ALTER ROLE vault_app LOGIN PASSWORD 'vault_app_pw' NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;
GRANT SELECT ON documents, chunks TO vault_app;

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks    ENABLE ROW LEVEL SECURITY;

-- Fail-closed: if the session settings are missing, comparisons are NULL and no rows match.
CREATE OR REPLACE FUNCTION vault_can_see(clr int, depts text[], owner text) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT
    CASE
      WHEN COALESCE(NULLIF(current_setting('app.role', true), ''), '') = 'admin' THEN true
      WHEN owner IS NOT NULL THEN owner = NULLIF(current_setting('app.username', true), '')
      ELSE
        clr <= NULLIF(current_setting('app.clearance', true), '')::int
        AND ( depts = '{}'
           OR depts && string_to_array(NULLIF(current_setting('app.depts', true), ''), ',')
           OR 'all' = ANY (string_to_array(NULLIF(current_setting('app.depts', true), ''), ',')) )
    END;
$$;

DROP POLICY IF EXISTS chunks_acl ON chunks;
DROP POLICY IF EXISTS docs_acl ON documents;
CREATE POLICY chunks_acl ON chunks FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments, owner_username));
CREATE POLICY docs_acl ON documents FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments, owner_username));

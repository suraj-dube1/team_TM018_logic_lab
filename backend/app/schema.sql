CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
  username        text PRIMARY KEY,
  display         text NOT NULL,
  clearance       int  NOT NULL,
  departments     text[] NOT NULL DEFAULT '{}',
  password_hash   text,
  password_salt   text,
  created_at      timestamptz DEFAULT now()
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt text;

INSERT INTO users(username, display, clearance, departments, password_hash, password_salt) VALUES
  ('intern', 'Ishaan, Intern', 0, '{}', '13f42270a7a71690af16af891f76bfb5d968b064aaeb749b4be5e0802fd376ef', '29fec2bc3ff778ae2628600e241af146'),
  ('manager', 'Meera, Engineering & Finance Manager', 2, '{eng,finance}', '9c27dfb119e090b93bc2c024e3a30ded58b97de71fcb6fb67e3d1876f243f5b2', 'b37dd710121831395dc19157a6e3f5f9'),
  ('admin', 'Arjun, Admin / CISO', 3, '{all}', 'b17c5a9bdaa6f7088dc2e76eb243bc70c9dfa9736b1146415824aaacdbc11c35', '969a3c37da657639e62b598070ac1b06')
ON CONFLICT (username) DO NOTHING;


CREATE TABLE IF NOT EXISTS documents (
  id            serial PRIMARY KEY,
  title         text NOT NULL,
  kind          text NOT NULL,
  path          text,
  min_clearance int  NOT NULL DEFAULT 0,
  departments   text[] NOT NULL DEFAULT '{}',   -- '{}' = every department
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
CREATE FUNCTION vault_can_see(clr int, depts text[]) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT clr <= NULLIF(current_setting('app.clearance', true), '')::int
     AND ( depts = '{}'
        OR depts && string_to_array(NULLIF(current_setting('app.depts', true), ''), ',')
        OR 'all' = ANY (string_to_array(NULLIF(current_setting('app.depts', true), ''), ',')) )
$$;

CREATE POLICY chunks_acl ON chunks    FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments));
CREATE POLICY docs_acl   ON documents FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments));

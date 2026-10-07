"""One-time/migration setup for a Postgres + pgvector database.

Creates the RLS schema, rotates the restricted app-role password, and makes sure
all demo users have password hashes. APP_DB_URL is written back into backend/.env.
"""
import os
import re
from urllib.parse import urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv

from app.auth import DEFAULT_PASSWORDS, hash_password

BASE = os.path.dirname(__file__)
os.chdir(BASE)
load_dotenv()
admin = os.environ.get("ADMIN_DB_URL")
if not admin:
    raise SystemExit("Put your database connection string in backend/.env as ADMIN_DB_URL=...")

# URL-safe password: do not need escaping when rebuilding the app connection URI.
import secrets
pw = secrets.token_urlsafe(18).replace("-", "a").replace("_", "b")
schema_path = os.path.join(BASE, "app", "schema.sql")
schema = open(schema_path, encoding="utf-8").read().replace("vault_app_pw", pw)

def ensure_auth_schema(c):
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt text")
    # Reconcile the three known demo accounts without overwriting a user's changed password.
    for username, password in DEFAULT_PASSWORDS.items():
        row = c.execute("SELECT password_hash, password_salt FROM users WHERE username=%s", (username,)).fetchone()
        if not row:
            continue
        if not row[0] or not row[1]:
            digest, salt = hash_password(password)
            c.execute(
                "UPDATE users SET password_hash=%s, password_salt=%s WHERE username=%s",
                (digest, salt, username),
            )

with psycopg.connect(admin, autocommit=True) as c:
    users_exists = bool(c.execute("SELECT to_regclass('public.users')").fetchone()[0])
    chunks_exists = bool(c.execute("SELECT to_regclass('public.chunks')").fetchone()[0])
    if not users_exists or not chunks_exists:
        c.execute(schema)
    # A pre-existing deployment has the role already; a partial database gets the role from schema.sql.
    role_exists = bool(c.execute("SELECT 1 FROM pg_roles WHERE rolname='vault_app'").fetchone())
    if role_exists:
        c.execute(f"ALTER ROLE vault_app PASSWORD '{pw}'")
    else:
        c.execute(f"CREATE ROLE vault_app LOGIN PASSWORD '{pw}' NOSUPERUSER NOBYPASSRLS")
        c.execute("GRANT SELECT ON documents, chunks TO vault_app")
        c.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
        c.execute("ALTER TABLE chunks ENABLE ROW LEVEL SECURITY")
        c.execute("CREATE POLICY chunks_acl ON chunks FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments))")
        c.execute("CREATE POLICY docs_acl ON documents FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments))")
    ensure_auth_schema(c)

u = urlsplit(admin)
host = u.hostname + (f":{u.port}" if u.port else "")
app_url = urlunsplit((u.scheme, f"vault_app:{pw}@{host}", u.path, u.query, ""))
env_path = os.path.join(BASE, ".env")
env = open(env_path, encoding="utf-8").read() if os.path.exists(env_path) else ""
env = re.sub(r"^APP_DB_URL=.*\n?", "", env, flags=re.M).rstrip("\n") + f"\nAPP_DB_URL={app_url}\n"
open(env_path, "w", encoding="utf-8").write(env)
print("Database ready. RLS app role rotated and APP_DB_URL saved to backend/.env")

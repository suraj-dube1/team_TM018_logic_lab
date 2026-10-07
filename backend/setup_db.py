"""Initialize/migrate the Logic Labs Postgres database.

The migration keeps existing data, upgrades the three synthetic demo accounts to
human-readable login IDs, and rotates the restricted RLS app role password.
"""
import os
import re
import secrets
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

APP_USERS = [
    {
        "old": "intern",
        "username": "rahul@student",
        "display": "Rahul Patel",
        "role": "student",
        "clearance": 0,
        "departments": ["student"],
        "password": "Student@123",
    },
    {
        "old": "manager",
        "username": "neha@faculty",
        "display": "Dr. Neha Sharma",
        "role": "faculty",
        "clearance": 2,
        "departments": ["eng", "finance"],
        "password": "Faculty@123",
    },
    {
        "old": "admin",
        "username": "arjun@admin",
        "display": "Arjun Mehta",
        "role": "admin",
        "clearance": 3,
        "departments": ["all"],
        "password": "Admin@123",
    },
]


# Twenty-one synthetic student accounts plus seven faculty demo accounts.
EXTRA_USERS = []
for slug, display in [
    ("rahul", "Rahul Patel"),("priya", "Priya Shah"),("dev", "Dev Mehta"),("riya", "Riya Joshi"),("kabir", "Kabir Shah"),
    ("aanya", "Aanya Patel"),("yash", "Yash Trivedi"),("nisha", "Nisha Vora"),("harsh", "Harsh Chauhan"),("diya", "Diya Parmar"),
    ("om", "Om Vyas"),("ishita", "Ishita Mehta"),("dhruv", "Dhruv Patel"),("mahi", "Mahi Shah"),("aditya", "Aditya Joshi"),
    ("krish", "Krish Desai"),("anaya", "Anaya Trivedi"),("vivaan", "Vivaan Mehta"),("pooja", "Pooja Patel"),("ved", "Ved Shah"),("neel", "Neel Joshi")
]:
    EXTRA_USERS.append({"username":f"{slug}@student","display":display,"role":"student","clearance":0,"departments":["student"],"password":"Student@123"})
for slug, display in [("neha","Dr. Neha Sharma"),("rakesh","Prof. Rakesh Mehta"),("kavita","Dr. Kavita Shah"),("amit","Prof. Amit Trivedi"),("pooja_fac","Dr. Pooja Joshi"),("harsh_fac","Prof. Harsh Patel"),("nisha_fac","Prof. Nisha Shah")]:
    EXTRA_USERS.append({"username":f"{slug}@faculty","display":display,"role":"faculty","clearance":2,"departments":["eng"],"password":"Faculty@123"})


pw = secrets.token_urlsafe(18).replace("-", "a").replace("_", "b")
schema_path = os.path.join(BASE, "app", "schema.sql")
schema = open(schema_path, encoding="utf-8").read().replace("vault_app_pw", pw)


def migrate_demo_users(c, items):
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role text")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt text")

    # Rename the legacy three demo usernames where possible.
    for item in items:
        old, new = item["old"], item["username"]
        old_exists = bool(c.execute("SELECT 1 FROM users WHERE username=%s", (old,)).fetchone())
        new_exists = bool(c.execute("SELECT 1 FROM users WHERE username=%s", (new,)).fetchone())
        if old_exists and not new_exists:
            c.execute("UPDATE users SET username=%s WHERE username=%s", (new, old))
        elif old_exists and new_exists:
            c.execute("DELETE FROM users WHERE username=%s", (old,))

    for item in APP_USERS:
        digest, salt = hash_password(item["password"])
        row = c.execute("SELECT 1 FROM users WHERE username=%s", (item["username"],)).fetchone()
        if row:
            c.execute(
                """
                UPDATE users
                   SET display=%s,
                       role=%s,
                       clearance=%s,
                       departments=%s,
                       password_hash=%s,
                       password_salt=%s
                 WHERE username=%s
                """,
                (
                    item["display"], item["role"], item["clearance"], item["departments"],
                    digest, salt, item["username"],
                ),
            )
        else:
            c.execute(
                """
                INSERT INTO users(username, display, role, clearance, departments, password_hash, password_salt)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    item["username"], item["display"], item["role"], item["clearance"], item["departments"],
                    digest, salt,
                ),
            )


def ensure_users(c, items):
    for item in items:
        digest, salt = hash_password(item["password"])
        row = c.execute("SELECT 1 FROM users WHERE username=%s", (item["username"],)).fetchone()
        if row:
            c.execute(
                """UPDATE users SET display=%s, role=%s, clearance=%s, departments=%s, password_hash=%s, password_salt=%s WHERE username=%s""",
                (item["display"], item["role"], item["clearance"], item["departments"], digest, salt, item["username"]),
            )
        else:
            c.execute(
                """INSERT INTO users(username, display, role, clearance, departments, password_hash, password_salt) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (item["username"], item["display"], item["role"], item["clearance"], item["departments"], digest, salt),
            )


with psycopg.connect(admin, autocommit=True) as c:
    users_exists = bool(c.execute("SELECT to_regclass('public.users')").fetchone()[0])
    chunks_exists = bool(c.execute("SELECT to_regclass('public.chunks')").fetchone()[0])
    if not users_exists or not chunks_exists:
        c.execute(schema)

    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role text")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt text")
    c.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS owner_username text")
    c.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS owner_username text")
    migrate_demo_users(c, APP_USERS)
    ensure_users(c, EXTRA_USERS)
    c.execute("""CREATE OR REPLACE FUNCTION vault_can_see(clr int, depts text[], owner text) RETURNS boolean
LANGUAGE sql STABLE AS $$
SELECT CASE
WHEN COALESCE(NULLIF(current_setting('app.role', true), ''), '') = 'admin' THEN true
WHEN owner IS NOT NULL THEN owner = NULLIF(current_setting('app.username', true), '')
ELSE clr <= NULLIF(current_setting('app.clearance', true), '')::int
AND (depts = '{}' OR depts && string_to_array(NULLIF(current_setting('app.depts', true), ''), ',') OR 'all' = ANY(string_to_array(NULLIF(current_setting('app.depts', true), ''), ',')))
END; $$;""")
    c.execute("DROP POLICY IF EXISTS chunks_acl ON chunks")
    c.execute("DROP POLICY IF EXISTS docs_acl ON documents")
    c.execute("CREATE POLICY chunks_acl ON chunks FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments, owner_username))")
    c.execute("CREATE POLICY docs_acl ON documents FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments, owner_username))")

    role_exists = bool(c.execute("SELECT 1 FROM pg_roles WHERE rolname='vault_app'").fetchone())
    if role_exists:
        c.execute(f"ALTER ROLE vault_app PASSWORD '{pw}'")
    else:
        c.execute(f"CREATE ROLE vault_app LOGIN PASSWORD '{pw}' NOSUPERUSER NOBYPASSRLS")
        c.execute("GRANT SELECT ON documents, chunks TO vault_app")
        c.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
        c.execute("ALTER TABLE chunks ENABLE ROW LEVEL SECURITY")
        c.execute("CREATE POLICY chunks_acl ON chunks FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments, owner_username))")
        c.execute("CREATE POLICY docs_acl ON documents FOR SELECT TO vault_app USING (vault_can_see(min_clearance, departments, owner_username))")

u = urlsplit(admin)
host = u.hostname + (f":{u.port}" if u.port else "")
app_url = urlunsplit((u.scheme, f"vault_app:{pw}@{host}", u.path, u.query, ""))
env_path = os.path.join(BASE, ".env")
env = open(env_path, encoding="utf-8").read() if os.path.exists(env_path) else ""
env = re.sub(r"^APP_DB_URL=.*\n?", "", env, flags=re.M).rstrip("\n") + f"\nAPP_DB_URL={app_url}\n"
open(env_path, "w", encoding="utf-8").write(env)
print("Database ready. Demo login IDs migrated and APP_DB_URL saved to backend/.env")

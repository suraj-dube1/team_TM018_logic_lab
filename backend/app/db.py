import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

load_dotenv()
APP_URL = os.getenv("APP_DB_URL", "postgresql://vault_app:vault_app_pw@localhost:5432/vaultrag")
ADMIN_URL = os.getenv("ADMIN_DB_URL", "postgresql://vault:vault@localhost:5432/vaultrag")


@contextmanager
def user_conn(user):
    """Connection as the unprivileged role. The ACL is enforced by Postgres RLS using
    these transaction-local settings, so every query below this point is filtered by the DB."""
    with psycopg.connect(APP_URL, row_factory=dict_row) as conn:
        register_vector(conn)
        with conn.transaction():
            conn.execute(
                "SELECT set_config('app.clearance', %s, true), set_config('app.depts', %s, true)",
                (str(int(user["clearance"])), ",".join(user["departments"])),
            )
            yield conn


@contextmanager
def admin_conn():
    """Superuser connection: used ONLY for ingestion, login lookup, audit and the red-team harness.
    Never used to fetch context for an answer."""
    with psycopg.connect(ADMIN_URL, row_factory=dict_row, autocommit=True) as conn:
        register_vector(conn)
        yield conn

"""Run after starting VaultRAG to verify the hackathon demo path.

Windows PowerShell:
  cd backend
  python smoke_test.py

Override defaults without editing code:
  $env:VAULTRAG_BASE_URL='http://127.0.0.1:8000'
  $env:VAULTRAG_INTERN_PASSWORD='...'
  $env:VAULTRAG_MANAGER_PASSWORD='...'
  $env:VAULTRAG_ADMIN_PASSWORD='...'
"""
import os
import sys

import httpx

BASE = os.getenv("VAULTRAG_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USERS = {
    "intern": os.getenv("VAULTRAG_INTERN_PASSWORD", "intern123"),
    "manager": os.getenv("VAULTRAG_MANAGER_PASSWORD", "manager123"),
    "admin": os.getenv("VAULTRAG_ADMIN_PASSWORD", "admin123"),
}


def login(client, username):
    r = client.post("/api/login", json={"username": username, "password": USERS[username]})
    r.raise_for_status()
    data = r.json()
    assert data["user"]["username"] == username
    return data["token"]


def ask(client, token, question):
    r = client.post("/api/ask", headers={"Authorization": f"Bearer {token}"}, json={"question": question})
    r.raise_for_status()
    return r.json()


def main():
    with httpx.Client(base_url=BASE, timeout=180) as c:
        r = c.get("/")
        r.raise_for_status()
        print("PASS  server reachable")

        tokens = {u: login(c, u) for u in USERS}
        print("PASS  password login for intern/manager/admin")

        for u, tok in tokens.items():
            r = c.get("/api/me", headers={"Authorization": f"Bearer {tok}"})
            r.raise_for_status()
            assert r.json()["username"] == u
        print("PASS  signed session tokens + /api/me")

        intern_midnight = ask(c, tokens["intern"], "What is Project Midnight?")
        admin_midnight = ask(c, tokens["admin"], "What is Project Midnight?")
        assert intern_midnight["blocked"] > 0, intern_midnight
        assert "nimbus labs" not in intern_midnight["answer"].lower()
        assert "210 crore" not in intern_midnight["answer"].lower()
        assert admin_midnight["claims"], admin_midnight
        assert "nimbus labs" in admin_midnight["answer"].lower()
        print("PASS  Project Midnight blocked for intern and visible to admin")

        intern_salary = ask(c, tokens["intern"], "What is Asha Mehta's salary?")
        manager_salary = ask(c, tokens["manager"], "What is Asha Mehta's salary?")
        admin_salary = ask(c, tokens["admin"], "What is Asha Mehta's salary?")
        assert intern_salary["blocked"] > 0 and "28,00,000" not in intern_salary["answer"], intern_salary
        assert manager_salary["blocked"] > 0 and "28,00,000" not in manager_salary["answer"], manager_salary
        assert admin_salary["claims"], admin_salary
        assert "28,00,000" in admin_salary["answer"]
        print("PASS  salary ACL: intern=blocked manager=blocked admin=visible")

        red = c.post("/api/redteam", headers={"Authorization": f"Bearer {tokens['intern']}"})
        red.raise_for_status()
        red = red.json()
        assert red["attacks"] == 12
        assert red["leaks"] == 0, red
        print("PASS  red team: 12 attacks, 0 leaks")

    # Optional direct DB assertion: a restricted connection with no RLS session settings must see zero chunks.
    try:
        import psycopg
        from dotenv import load_dotenv
        load_dotenv()
        app_url = os.getenv("APP_DB_URL")
        if app_url:
            with psycopg.connect(app_url) as db:
                n = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
                assert n == 0, f"expected fail-closed 0 chunks, got {n}"
            print("PASS  RLS fail-closed: no session settings -> 0 chunks")
        else:
            print("SKIP  RLS direct check: APP_DB_URL is not configured in this shell")
    except ImportError:
        print("SKIP  RLS direct check: psycopg/python-dotenv unavailable")

    print("\nVaultRAG smoke test PASSED")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nVaultRAG smoke test FAILED: {exc}", file=sys.stderr)
        raise

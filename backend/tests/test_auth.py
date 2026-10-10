"""Security-focused tests for registration and JWT authentication."""

def test_register_login_and_protected_profile(client):
    registered = client.post(
        "/api/auth/register",
        json={"name": "A Student", "email": "Student@example.com", "password": "long-demo-password"},
    )
    assert registered.status_code == 201
    user = registered.json()
    assert user["email"] == "student@example.com"
    assert user["role"] == "STUDENT"
    assert "password_hash" not in user

    login = client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "long-demo-password"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert login.json()["token_type"] == "bearer"

    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["id"] == user["id"]
    assert profile.json()["role"] == "STUDENT"


def test_protected_profile_rejects_missing_or_invalid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_incorrect_password_is_rejected(client):
    client.post(
        "/api/auth/register",
        json={"name": "A Student", "email": "student@example.com", "password": "long-demo-password"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_public_registration_cannot_assign_role(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Attempted Admin",
            "email": "admin@example.com",
            "password": "long-demo-password",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 422


def test_duplicate_email_is_rejected_case_insensitively(client):
    first = client.post(
        "/api/auth/register",
        json={"name": "First", "email": "user@example.com", "password": "long-demo-password"},
    )
    second = client.post(
        "/api/auth/register",
        json={"name": "Second", "email": " USER@example.com ", "password": "long-demo-password"},
    )
    assert first.status_code == 201
    assert second.status_code == 409

from app.db import get_session


def test_health_does_not_touch_the_database(client):
    def no_db():
        raise AssertionError("health must not open a database session")
        yield  # pragma: no cover

    client.app.dependency_overrides[get_session] = no_db
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_db_health_checks_database(client):
    response = client.get("/api/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_unknown_api_route_is_404(client):
    assert client.get("/api/nope").status_code == 404

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from tests.conftest import make_settings


def test_serves_built_pwa_with_spa_fallback(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>voxfin</html>")
    (tmp_path / "manifest.webmanifest").write_text("{}")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("nope")

    settings = make_settings(web_dist_dir=str(tmp_path))
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    client = TestClient(create_app())
    client.app.dependency_overrides[get_settings] = lambda: settings

    assert client.get("/").text == "<html>voxfin</html>"
    assert client.get("/transactions/42").text == "<html>voxfin</html>"  # client-side route
    manifest = client.get("/manifest.webmanifest")
    assert manifest.text == "{}"
    assert manifest.headers["content-type"] == "application/manifest+json"
    assert manifest.headers["cache-control"] == "no-cache"
    assert client.head("/").status_code == 200
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert "nope" not in client.get("/../secret.txt").text
    assert client.get("/api/nope").status_code == 404

import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestMountFrontend:
    def test_does_nothing_when_static_dir_missing(self, tmp_path):
        """mount_frontend should be a no-op if /app/static doesn't exist."""
        from app.static_files import mount_frontend

        app = FastAPI()

        @app.get("/api/v1/health")
        async def health():
            return {"ok": True}

        with patch("app.static_files.STATIC_DIR", tmp_path / "nonexistent"):
            mount_frontend(app)

        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_serves_index_html_for_spa_routes(self, tmp_path):
        """Unmatched GET routes should return index.html (SPA fallback)."""
        from app.static_files import mount_frontend

        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>SPA</html>")

        app = FastAPI()

        @app.get("/api/v1/health")
        async def health():
            return {"ok": True}

        with patch("app.static_files.STATIC_DIR", static_dir), \
             patch("app.static_files.ASSETS_DIR", static_dir / "assets"):
            mount_frontend(app)

        client = TestClient(app)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "SPA" in resp.text

    def test_serves_static_files_directly(self, tmp_path):
        """Files that exist in static dir should be served directly."""
        from app.static_files import mount_frontend

        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>SPA</html>")
        (static_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")

        app = FastAPI()

        with patch("app.static_files.STATIC_DIR", static_dir), \
             patch("app.static_files.ASSETS_DIR", static_dir / "assets"):
            mount_frontend(app)

        client = TestClient(app)
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        assert resp.content == b"\x00\x00\x01\x00"

    def test_assets_dir_served_via_staticfiles(self, tmp_path):
        """Vite build assets should be served with proper MIME types."""
        from app.static_files import mount_frontend

        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>SPA</html>")
        assets_dir = static_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "main.js").write_text("console.log('hi')")

        app = FastAPI()

        with patch("app.static_files.STATIC_DIR", static_dir), \
             patch("app.static_files.ASSETS_DIR", assets_dir):
            mount_frontend(app)

        client = TestClient(app)
        resp = client.get("/assets/main.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_api_routes_take_priority(self, tmp_path):
        """API routes registered before mount_frontend should still work."""
        from app.static_files import mount_frontend

        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>SPA</html>")

        app = FastAPI()

        @app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}

        with patch("app.static_files.STATIC_DIR", static_dir), \
             patch("app.static_files.ASSETS_DIR", static_dir / "assets"):
            mount_frontend(app)

        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

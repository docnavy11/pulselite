import os
from unittest.mock import patch


class TestLightConfigFields:
    def test_serve_frontend_defaults_to_false(self):
        from app.config import Settings

        with patch.dict(os.environ, {"SECRET_KEY": "test", "JWT_SECRET_KEY": "test"}, clear=False):
            s = Settings()
            assert s.serve_frontend is False

    def test_serve_frontend_can_be_set_true(self):
        from app.config import Settings

        with patch.dict(
            os.environ,
            {"SECRET_KEY": "test", "JWT_SECRET_KEY": "test", "SERVE_FRONTEND": "true"},
            clear=False,
        ):
            s = Settings()
            assert s.serve_frontend is True

    def test_internal_api_url_defaults_to_backend(self):
        from app.config import Settings

        with patch.dict(os.environ, {"SECRET_KEY": "test", "JWT_SECRET_KEY": "test"}, clear=False):
            s = Settings()
            assert s.INTERNAL_API_URL == "http://backend:8000"

    def test_internal_api_url_can_be_overridden(self):
        from app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test",
                "JWT_SECRET_KEY": "test",
                "INTERNAL_API_URL": "http://127.0.0.1:8000",
            },
            clear=False,
        ):
            s = Settings()
            assert s.INTERNAL_API_URL == "http://127.0.0.1:8000"

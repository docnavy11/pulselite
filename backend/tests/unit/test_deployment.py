from unittest.mock import patch


class TestDeploymentMode:
    def test_is_cloud_when_cloud_mode_true(self):
        from app.services.deployment import is_cloud
        with patch("app.services.deployment.settings") as mock_settings:
            mock_settings.CLOUD_MODE = True
            assert is_cloud() is True

    def test_is_not_cloud_when_cloud_mode_false(self):
        from app.services.deployment import is_cloud
        with patch("app.services.deployment.settings") as mock_settings:
            mock_settings.CLOUD_MODE = False
            assert is_cloud() is False

    def test_is_self_hosted_inverse_of_cloud(self):
        from app.services.deployment import is_self_hosted
        with patch("app.services.deployment.settings") as mock_settings:
            mock_settings.CLOUD_MODE = False
            assert is_self_hosted() is True
            mock_settings.CLOUD_MODE = True
            assert is_self_hosted() is False

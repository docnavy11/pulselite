from unittest.mock import patch, MagicMock
from app.services.integrations.email import send_email


def test_send_email_smtp():
    """SMTP provider sends via smtplib."""
    config = {
        "provider": "smtp",
        "host": "smtp.example.com",
        "port": 587,
        "username": "user@example.com",
        "password": "encrypted-secret",
        "tls": True,
        "from_email": "Pulse <noreply@example.com>",
        "to_email": "admin@example.com",
    }
    with patch("app.services.integrations.email.smtplib.SMTP") as mock_smtp, \
         patch("app.services.integrations.email.decrypt_api_key", return_value="secret"):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        result = send_email(config, "Test Subject", "<h1>Hello</h1>")
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "secret")
        mock_server.send_message.assert_called_once()


def test_send_email_resend():
    """Resend provider (or missing provider field) sends via Resend SDK."""
    config = {
        "api_key": "encrypted-re_test123",
        "from_email": "Pulse <noreply@pulse.app>",
        "to_email": "admin@example.com",
    }
    with patch("app.services.integrations.email.resend") as mock_resend, \
         patch("app.services.integrations.email.decrypt_api_key", return_value="re_test123"):
        result = send_email(config, "Test Subject", "<h1>Hello</h1>")
        assert result is True
        mock_resend.Emails.send.assert_called_once()


def test_send_email_resend_explicit_provider():
    """Explicit provider=resend routes to Resend."""
    config = {
        "provider": "resend",
        "api_key": "encrypted-re_test123",
        "from_email": "Pulse <noreply@pulse.app>",
        "to_email": "admin@example.com",
    }
    with patch("app.services.integrations.email.resend") as mock_resend, \
         patch("app.services.integrations.email.decrypt_api_key", return_value="re_test123"):
        result = send_email(config, "Test Subject", "<h1>Hello</h1>")
        assert result is True


def test_send_email_missing_config():
    """Returns False when required config is missing."""
    assert send_email({}, "Subject", "<p>body</p>") is False
    assert send_email({"provider": "smtp"}, "Subject", "<p>body</p>") is False

import pytest
from unittest.mock import patch, MagicMock

from app.services.email_digest import generate_digest_html, send_digest_email


class TestEmailDigest:
    def test_digest_html_generated(self):
        """Generate digest HTML for test user, assert it contains paper titles and unsubscribe link."""
        papers = [
            {"title": "Battery Degradation Modelling", "journal": "Applied Energy", "score": 8.5, "summary_excerpt": "A novel approach..."},
            {"title": "Grid Frequency Response", "journal": "IEEE Trans. Power Systems", "score": 7.2, "summary_excerpt": "This paper studies..."},
        ]
        shared_papers = [
            {"paper_title": "EV Charging Infrastructure", "sharer_name": "Ali Pourmousavi", "annotation": "Check this out!"},
        ]

        html = generate_digest_html(
            user_name="Test User",
            papers=papers,
            shared_papers=shared_papers,
            dashboard_url="https://litorbit.vercel.app",
            unsubscribe_url="https://litorbit.vercel.app/unsubscribe",
        )

        assert "Battery Degradation Modelling" in html
        assert "Grid Frequency Response" in html
        assert "Applied Energy" in html
        assert "8.5" in html
        assert "EV Charging Infrastructure" in html
        assert "Ali Pourmousavi" in html
        assert "Check this out!" in html
        assert "unsubscribe" in html.lower()
        assert "LitOrbit" in html

    def test_digest_html_empty_papers(self):
        """Digest with no papers still generates valid HTML."""
        html = generate_digest_html(
            user_name="Test",
            papers=[],
            shared_papers=[],
            dashboard_url="https://example.com",
            unsubscribe_url="https://example.com/unsub",
        )
        assert "LitOrbit" in html
        assert "0 new papers" in html

    @patch("app.services.email_digest.smtplib.SMTP")
    def test_email_sent_successfully(self, mock_smtp_class):
        """Mock SMTP, assert send called with correct recipient."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        # Need to set SMTP creds
        with patch("app.services.email_digest.get_settings") as mock_settings:
            settings = MagicMock()
            settings.smtp_user = "test@gmail.com"
            settings.smtp_password = "password"
            settings.smtp_host = "smtp.gmail.com"
            settings.smtp_port = 587
            mock_settings.return_value = settings

            result = send_digest_email(
                to_email="user@example.com",
                subject="LitOrbit Weekly Digest",
                html_body="<h1>Test</h1>",
            )

        assert result is True
        mock_server.sendmail.assert_called_once()
        call_args = mock_server.sendmail.call_args
        assert call_args[0][1] == "user@example.com"

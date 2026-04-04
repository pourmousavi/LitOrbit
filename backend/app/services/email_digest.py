import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx
from jinja2 import Template

from app.config import get_settings

logger = logging.getLogger(__name__)

DIGEST_TEMPLATE = Template("""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #f0f0f0; margin: 0; padding: 0; }
  .container { max-width: 600px; margin: 0 auto; padding: 24px 16px; }
  .header { text-align: center; padding: 24px 0; border-bottom: 1px solid #2a2a2a; margin-bottom: 24px; }
  .logo { font-family: 'Courier New', monospace; font-size: 24px; font-weight: 500; color: #f0f0f0; }
  .subtitle { font-family: 'Courier New', monospace; font-size: 12px; color: #888888; margin-top: 4px; }
  h2 { font-family: 'Courier New', monospace; font-size: 14px; color: #888888; text-transform: uppercase; letter-spacing: 2px; margin: 24px 0 12px; }
  .paper { background: #141414; border: 1px solid #2a2a2a; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
  .paper-title { font-size: 15px; font-weight: 600; color: #f0f0f0; margin-bottom: 6px; line-height: 1.4; }
  .paper-meta { font-family: 'Courier New', monospace; font-size: 11px; color: #888888; margin-bottom: 8px; }
  .paper-summary { font-size: 13px; color: #aaaaaa; line-height: 1.5; }
  .score { display: inline-block; font-family: 'Courier New', monospace; font-size: 12px; font-weight: 500; padding: 2px 8px; border-radius: 6px; }
  .score-high { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
  .score-mid { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
  .score-low { background: rgba(136, 136, 136, 0.15); color: #888888; }
  .shared-section { background: rgba(8, 145, 178, 0.08); border: 1px solid rgba(8, 145, 178, 0.2); border-radius: 12px; padding: 16px; margin-top: 24px; }
  .shared-label { font-family: 'Courier New', monospace; font-size: 11px; color: #0891b2; margin-bottom: 4px; }
  .podcast-section { background: rgba(168, 85, 247, 0.08); border: 1px solid rgba(168, 85, 247, 0.25); border-radius: 12px; padding: 20px; margin: 24px 0; text-align: center; }
  .podcast-title { font-family: 'Courier New', monospace; font-size: 13px; color: #a855f7; margin-bottom: 8px; }
  .podcast-meta { font-family: 'Courier New', monospace; font-size: 11px; color: #888888; margin-bottom: 14px; }
  .podcast-btn { display: inline-block; background: #a855f7; color: white; text-decoration: none; padding: 10px 24px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 13px; }
  .cta { display: block; text-align: center; background: #0891b2; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 13px; margin: 24px 0; }
  .footer { text-align: center; padding: 24px 0; border-top: 1px solid #2a2a2a; margin-top: 24px; }
  .footer a { font-family: 'Courier New', monospace; font-size: 11px; color: #555555; text-decoration: underline; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">LitOrbit</div>
    <div class="subtitle">{{ frequency | capitalize }} Digest &mdash; {{ paper_count }} new papers for you</div>
  </div>

  {% if podcast %}
  <div class="podcast-section">
    <div class="podcast-title">{{ podcast.title }}</div>
    <div class="podcast-meta">
      {{ podcast.voice_label }} &middot; {{ podcast.duration_label }}
    </div>
    <a href="{{ podcast.play_url }}" class="podcast-btn">&#9654;&ensp;Listen Now</a>
  </div>
  {% endif %}

  <h2>Top Papers This {{ "Day" if frequency == "daily" else "Week" }}</h2>
  {% for paper in papers %}
  <div class="paper">
    <div class="paper-title">{{ paper.title }}</div>
    <div class="paper-meta">
      {{ paper.journal }}
      {% if paper.score is not none %}
      &nbsp;&middot;&nbsp;
      <span class="score {% if paper.score >= 8 %}score-high{% elif paper.score >= 5 %}score-mid{% else %}score-low{% endif %}">{{ "%.1f"|format(paper.score) }}</span>
      {% endif %}
    </div>
    {% if paper.summary_excerpt %}
    <div class="paper-summary">{{ paper.summary_excerpt }}</div>
    {% endif %}
  </div>
  {% endfor %}

  {% if shared_papers %}
  <h2>Shared With You</h2>
  {% for share in shared_papers %}
  <div class="shared-section">
    <div class="shared-label">From {{ share.sharer_name }}</div>
    <div class="paper-title">{{ share.paper_title }}</div>
    {% if share.annotation %}
    <div class="paper-summary" style="font-style: italic;">&ldquo;{{ share.annotation }}&rdquo;</div>
    {% endif %}
  </div>
  {% endfor %}
  {% endif %}

  <a href="{{ dashboard_url }}" class="cta">Open LitOrbit Dashboard</a>

  <div class="footer">
    <a href="{{ unsubscribe_url }}">Unsubscribe from digest emails</a>
  </div>
</div>
</body>
</html>""")


def generate_digest_html(
    user_name: str,
    papers: list[dict[str, Any]],
    shared_papers: list[dict[str, Any]],
    dashboard_url: str,
    unsubscribe_url: str,
    frequency: str = "weekly",
    podcast: dict[str, Any] | None = None,
) -> str:
    """Generate the HTML digest email."""
    return DIGEST_TEMPLATE.render(
        user_name=user_name,
        paper_count=len(papers),
        papers=papers,
        shared_papers=shared_papers,
        dashboard_url=dashboard_url,
        unsubscribe_url=unsubscribe_url,
        frequency=frequency,
        podcast=podcast,
    )


def _send_via_resend(to_email: str, subject: str, html_body: str, settings) -> bool:
    """Send email via Resend HTTP API."""
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from or "LitOrbit <noreply@litorbit.app>",
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            logger.info(f"Digest email sent via Resend to {to_email}")
            return True
        logger.error(f"Resend API error {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Resend send failed for {to_email}: {e}")
        return False


def _send_via_smtp(to_email: str, subject: str, html_body: str, settings) -> bool:
    """Send email via SMTP (Gmail)."""
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_email, msg.as_string())
            logger.info(f"Digest email sent via SMTP to {to_email}")
            return True
    except Exception as e:
        logger.error(f"SMTP send failed for {to_email}: {e}")
        return False


def send_digest_email(
    to_email: str,
    subject: str,
    html_body: str,
) -> bool:
    """Send an HTML email. Uses Resend API if configured, falls back to SMTP.

    Returns True on success, False on failure. Never raises.
    """
    settings = get_settings()

    # Prefer Resend (works on Render and other platforms that block SMTP)
    if settings.resend_api_key:
        return _send_via_resend(to_email, subject, html_body, settings)

    # Fall back to SMTP
    if settings.smtp_user and settings.smtp_password:
        return _send_via_smtp(to_email, subject, html_body, settings)

    logger.warning("No email provider configured (set RESEND_API_KEY or SMTP_USER/SMTP_PASSWORD)")
    return False

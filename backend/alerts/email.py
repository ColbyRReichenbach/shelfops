"""
Email Delivery for alerts.

Agent: full-stack-engineer
Skill: alert-systems (email delivery pattern)
"""

import sendgrid
from sendgrid.helpers.mail import Mail
from core.config import get_settings

settings = get_settings()


async def send_alert_email(
    to_email: str,
    alert_type: str,
    severity: str,
    message: str,
    store_name: str = "",
    product_name: str = "",
) -> bool:
    """
    Send alert notification email via SendGrid.

    Only sends for high/critical severity to avoid alert fatigue.
    Returns True if sent successfully.
    """
    if severity not in ("high", "critical"):
        return False

    severity_emoji = {"critical": "🔴", "high": "🟠"}.get(severity, "")
    subject = f"{severity_emoji} ShelfOps Alert: {alert_type.replace('_', ' ').title()}"

    html_content = f"""
    <div style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #1e1b4b; color: white; padding: 24px; border-radius: 12px 12px 0 0;">
        <h1 style="margin: 0; font-size: 20px;">ShelfOps Alert</h1>
      </div>
      <div style="background: #f8fafc; padding: 24px; border: 1px solid #e2e8f0;">
        <div style="background: {'#fef2f2' if severity == 'critical' else '#fff7ed'};
                    border-left: 4px solid {'#dc2626' if severity == 'critical' else '#f59e0b'};
                    padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px;">
          <p style="margin: 0; font-weight: 600; color: #1e293b;">
            {severity.upper()} — {alert_type.replace('_', ' ').title()}
          </p>
        </div>
        <p style="color: #334155; line-height: 1.6;">{message}</p>
        {'<p style="color: #64748b;"><strong>Store:</strong> ' + store_name + '</p>' if store_name else ''}
        {'<p style="color: #64748b;"><strong>Product:</strong> ' + product_name + '</p>' if product_name else ''}
        <a href="https://app.shelfops.com/alerts"
           style="display: inline-block; background: #4f46e5; color: white;
                  padding: 10px 20px; border-radius: 8px; text-decoration: none;
                  margin-top: 16px; font-weight: 500;">
          View in Dashboard →
        </a>
      </div>
      <div style="text-align: center; padding: 16px; color: #94a3b8; font-size: 12px;">
        ShelfOps — AI-Powered Inventory Intelligence
      </div>
    </div>
    """

    try:
        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        email = Mail(
            from_email=settings.alert_from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        response = sg.send(email)
        return response.status_code in (200, 201, 202)
    except Exception:
        return False

"""
app/utils/email.py

Password reset email dispatch using Resend.
https://resend.com — free tier: 3,000 emails/month, 100/day.

Setup:
1. Sign up at https://resend.com
2. Add your RESEND_API_KEY to backend/.env
3. Add MAIL_FROM to backend/.env (must be a verified sender in Resend dashboard)

.env entries needed:
    RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
    MAIL_FROM=noreply@yourdomain.com
    MAIL_FROM_NAME=FindMyNyumba
"""

import logging
import resend

from app.core.config import settings

log = logging.getLogger("findmynyumba.email")


def send_password_reset_email(to_email: str, full_name: str, reset_url: str) -> None:
    """
    Send a password reset email via Resend.

    Raises:
        Exception: Re-raises any Resend API error so the caller can handle it.
                   Caller (auth.py) always returns SAFE_RESPONSE regardless.
    """
    resend.api_key = settings.RESEND_API_KEY

    first_name = (full_name or "").split()[0] if full_name else "there"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f4f4f5;padding:40px 0;">
        <tr>
          <td align="center">
            <table width="600" cellpadding="0" cellspacing="0"
                   style="background:#ffffff;border-radius:8px;
                          box-shadow:0 2px 8px rgba(0,0,0,0.08);
                          overflow:hidden;max-width:600px;width:100%;">

              <!-- Header -->
              <tr>
                <td style="background:#1a56db;padding:32px 40px;text-align:center;">
                  <h1 style="margin:0;color:#ffffff;font-size:24px;
                             font-weight:700;letter-spacing:-0.5px;">
                    FindMyNyumba
                  </h1>
                  <p style="margin:4px 0 0;color:#bfdbfe;font-size:13px;">
                    Student Accommodation Platform
                  </p>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:40px 40px 32px;">
                  <h2 style="margin:0 0 16px;color:#111827;font-size:20px;">
                    Reset your password
                  </h2>
                  <p style="margin:0 0 12px;color:#374151;font-size:15px;
                             line-height:1.6;">
                    Hi {first_name},
                  </p>
                  <p style="margin:0 0 24px;color:#374151;font-size:15px;
                             line-height:1.6;">
                    We received a request to reset the password for your
                    FindMyNyumba account. Click the button below to set a
                    new password. This link expires in
                    <strong>60 minutes</strong>.
                  </p>

                  <!-- CTA Button -->
                  <table cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
                    <tr>
                      <td style="border-radius:6px;background:#1a56db;">
                        <a href="{reset_url}"
                           style="display:inline-block;padding:14px 32px;
                                  color:#ffffff;font-size:15px;font-weight:600;
                                  text-decoration:none;border-radius:6px;">
                          Reset Password
                        </a>
                      </td>
                    </tr>
                  </table>

                  <p style="margin:0 0 8px;color:#6b7280;font-size:13px;">
                    If the button doesn't work, copy and paste this link:
                  </p>
                  <p style="margin:0 0 24px;word-break:break-all;">
                    <a href="{reset_url}"
                       style="color:#1a56db;font-size:13px;">{reset_url}</a>
                  </p>

                  <hr style="border:none;border-top:1px solid #e5e7eb;
                              margin:0 0 24px;">

                  <p style="margin:0;color:#9ca3af;font-size:13px;
                             line-height:1.6;">
                    If you didn't request a password reset, you can safely
                    ignore this email. Your password will not be changed.
                  </p>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background:#f9fafb;padding:20px 40px;
                           text-align:center;border-top:1px solid #e5e7eb;">
                  <p style="margin:0;color:#9ca3af;font-size:12px;">
                    &copy; 2025 FindMyNyumba &mdash; Zambia Student Accommodation
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    params: resend.Emails.SendParams = {
        "from": f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>",
        "to":   [to_email],
        "subject": "Reset your FindMyNyumba password",
        "html": html_body,
    }

    response = resend.Emails.send(params)
    log.info("Password reset email sent to %s (id: %s)", to_email, response.get("id"))


def send_login_alert_email(to_email: str, full_name: str, device: str, ip: str, when: str) -> None:
    """Send a 'new sign-in detected' security email via Resend.
    Best-effort: caller wraps in try/except so a failure never breaks login."""
    resend.api_key = settings.RESEND_API_KEY

    first_name = (full_name or "").split()[0] if full_name else "there"
    device = device or "an unrecognized device"
    where = ip or "an unknown location"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.08);overflow:hidden;max-width:600px;width:100%;">
            <tr>
              <td style="background:#1a56db;padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">FindMyNyumba</h1>
                <p style="margin:4px 0 0;color:#bfdbfe;font-size:13px;">Account Security</p>
              </td>
            </tr>
            <tr>
              <td style="padding:40px 40px 32px;">
                <h2 style="margin:0 0 16px;color:#111827;font-size:20px;">New sign-in to your account</h2>
                <p style="margin:0 0 12px;color:#374151;font-size:15px;line-height:1.6;">Hi {first_name},</p>
                <p style="margin:0 0 20px;color:#374151;font-size:15px;line-height:1.6;">
                  We noticed a new sign-in to your FindMyNyumba account. Here are the details:
                </p>
                <table cellpadding="0" cellspacing="0" style="margin:0 0 24px;width:100%;background:#f9fafb;border-radius:6px;">
                  <tr><td style="padding:14px 18px;color:#374151;font-size:14px;line-height:1.8;">
                    <strong>Device:</strong> {device}<br>
                    <strong>IP address:</strong> {where}<br>
                    <strong>When:</strong> {when}
                  </td></tr>
                </table>
                <p style="margin:0 0 12px;color:#374151;font-size:15px;line-height:1.6;">
                  If this was you, no action is needed.
                </p>
                <p style="margin:0 0 24px;color:#374151;font-size:15px;line-height:1.6;">
                  If you do not recognize this, your account may be compromised. Please change your
                  password right away and use "Log out all other devices" in your account settings.
                </p>
                <hr style="border:none;border-top:1px solid #e5e7eb;margin:0 0 24px;">
                <p style="margin:0;color:#9ca3af;font-size:13px;line-height:1.6;">
                  This is an automated security notice. You are receiving it because someone signed in
                  to an account registered with this email address.
                </p>
              </td>
            </tr>
            <tr>
              <td style="background:#f9fafb;padding:20px 40px;text-align:center;border-top:1px solid #e5e7eb;">
                <p style="margin:0;color:#9ca3af;font-size:12px;">&copy; 2026 FindMyNyumba &mdash; Zambia Student Accommodation</p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    params: resend.Emails.SendParams = {
        "from": f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>",
        "to":   [to_email],
        "subject": "New sign-in to your FindMyNyumba account",
        "html": html_body,
    }

    response = resend.Emails.send(params)
    log.info("Login alert email sent to %s (id: %s)", to_email, response.get("id"))

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


def send_payment_receipt_email(to_email: str, full_name: str,
                               package_name: str, amount, currency: str,
                               method: str, reference: str,
                               expires_on: str = None,
                               unlocks: str = "message landlords and see contact details") -> None:
    """
    Send a Verified Access payment receipt via Resend.

    Mirrors send_password_reset_email mechanics exactly. Raises on Resend error
    so the caller can log it; the caller must never let a failure here undo a
    settled payment.

    amount/currency: e.g. 150, "ZMW"  -> shown as "K150"
    method: airtel_money | mtn_money | zamtel_money -> shown friendly
    """
    resend.api_key = settings.RESEND_API_KEY
    first_name = (full_name or "").split()[0] if full_name else "there"

    def _money(a, c):
        try:
            n = "{:,.0f}".format(float(a))
        except (TypeError, ValueError):
            return str(a)
        return ("K" + n) if (c or "ZMW") == "ZMW" else ((c or "") + " " + n)

    method_label = {
        "airtel_money": "Airtel Money",
        "mtn_money": "MTN Mobile Money",
        "zamtel_money": "Zamtel Money",
        "bank_transfer": "Bank transfer",
    }.get((method or "").lower(), "Mobile money")

    amount_display = _money(amount, currency)
    expiry_row = ""
    if expires_on:
        expiry_row = f"""
                    <tr>
                      <td style="padding:8px 0;color:#64748b;font-size:14px;">Access until</td>
                      <td style="padding:8px 0;color:#0f172a;font-size:14px;font-weight:700;text-align:right;">{expires_on}</td>
                    </tr>"""

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
            <!-- Header -->
            <tr>
              <td style="background:#0F172A;padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">FindMyNyumba</h1>
                <p style="margin:4px 0 0;color:#94a3b8;font-size:13px;">Payment receipt</p>
              </td>
            </tr>
            <!-- Body -->
            <tr>
              <td style="padding:36px 40px 8px;">
                <p style="margin:0 0 6px;color:#0f172a;font-size:17px;font-weight:700;">Thank you, {first_name}.</p>
                <p style="margin:0 0 24px;color:#475569;font-size:14px;line-height:1.6;">
                  Your payment was received and your Verified Access is now active.
                  You can {unlocks}.
                </p>

                <!-- amount card -->
                <table width="100%" cellpadding="0" cellspacing="0"
                       style="background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;margin-bottom:24px;">
                  <tr><td style="padding:18px 22px;text-align:center;">
                    <p style="margin:0 0 2px;color:#9a3412;font-size:12px;text-transform:uppercase;letter-spacing:.05em;">Amount paid</p>
                    <p style="margin:0;color:#ea580c;font-size:30px;font-weight:800;">{amount_display}</p>
                  </td></tr>
                </table>

                <!-- details -->
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="padding:8px 0;color:#64748b;font-size:14px;border-bottom:1px solid #f1f5f9;">Package</td>
                    <td style="padding:8px 0;color:#0f172a;font-size:14px;font-weight:700;text-align:right;border-bottom:1px solid #f1f5f9;">{package_name}</td>
                  </tr>
                  <tr>
                    <td style="padding:8px 0;color:#64748b;font-size:14px;border-bottom:1px solid #f1f5f9;">Paid with</td>
                    <td style="padding:8px 0;color:#0f172a;font-size:14px;font-weight:700;text-align:right;border-bottom:1px solid #f1f5f9;">{method_label}</td>
                  </tr>
                  <tr>
                    <td style="padding:8px 0;color:#64748b;font-size:14px;border-bottom:1px solid #f1f5f9;">Reference</td>
                    <td style="padding:8px 0;color:#0f172a;font-size:13px;font-weight:700;text-align:right;border-bottom:1px solid #f1f5f9;">{reference}</td>
                  </tr>{expiry_row}
                </table>

                <!-- trust line -->
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
                  <tr><td style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px 18px;">
                    <p style="margin:0;color:#166534;font-size:13px;line-height:1.6;">
                      This fee is for FindMyNyumba Verified Access only. Rent is always paid
                      directly to your landlord, never through FindMyNyumba.
                    </p>
                  </td></tr>
                </table>
              </td>
            </tr>
            <!-- Footer -->
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
        "subject": f"Your FindMyNyumba receipt - {reference}",
        "html": html_body,
    }
    response = resend.Emails.send(params)
    log.info("Payment receipt email sent to %s ref=%s (id: %s)",
             to_email, reference, response.get("id"))


def send_listing_rejection_email(to_email: str, listing_title: str, reason: str) -> None:
    """
    Notify a landlord that their listing was rejected during review, including the
    reason and a prompt to edit and resubmit. Sent via Resend.

    Safe to call even if RESEND_API_KEY is unset: it will raise, and the caller
    (admin.reject_listing) wraps this in try/except so a missing key never blocks
    the rejection itself.
    """
    resend.api_key = settings.RESEND_API_KEY

    title = listing_title or "your listing"
    reason_text = reason or "Your listing did not meet our review criteria."

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
          <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.08);overflow:hidden;max-width:600px;width:100%;">
            <!-- Header -->
            <tr>
              <td style="background:#0f172a;padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">FindMyNyumba</h1>
                <p style="margin:4px 0 0;color:#94a3b8;font-size:13px;">Student Accommodation Platform</p>
              </td>
            </tr>
            <!-- Body -->
            <tr>
              <td style="padding:36px 40px 8px;">
                <h2 style="margin:0 0 12px;color:#0f172a;font-size:19px;">Your listing needs changes</h2>
                <p style="margin:0 0 16px;color:#475569;font-size:14px;line-height:1.6;">
                  Thank you for listing <strong>{title}</strong> on FindMyNyumba. After review, we were not able to approve it in its current form.
                </p>
                <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
                  <tr>
                    <td style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:14px 16px;">
                      <p style="margin:0;color:#991b1b;font-size:13px;font-weight:700;">Reason</p>
                      <p style="margin:6px 0 0;color:#7f1d1d;font-size:14px;line-height:1.6;">{reason_text}</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 20px;color:#475569;font-size:14px;line-height:1.6;">
                  You can edit your listing to address this and resubmit it for review from your landlord dashboard.
                </p>
                <a href="https://www.findmynyumba.com/dashboard-landlord.html"
                   style="display:inline-block;background:#ea580c;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 22px;border-radius:8px;">
                  Edit &amp; resubmit
                </a>
              </td>
            </tr>
            <!-- Footer -->
            <tr>
              <td style="padding:28px 40px 32px;">
                <p style="margin:20px 0 0;color:#94a3b8;font-size:12px;line-height:1.5;border-top:1px solid #e2e8f0;padding-top:16px;">
                  Questions? Reply to this email or reach us through the Help Center on FindMyNyumba.
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    params: "resend.Emails.SendParams" = {
        "from": f"{getattr(settings, 'MAIL_FROM_NAME', 'FindMyNyumba')} <{settings.MAIL_FROM}>",
        "to": [to_email],
        "subject": "Your FindMyNyumba listing needs changes",
        "html": html_body,
    }
    resend.Emails.send(params)

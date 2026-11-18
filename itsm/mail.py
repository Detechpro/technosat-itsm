"""Branded HTML email with a plain-text fallback, shared by all portal notifications.

The Technosat logo is embedded as an inline image (Content-ID), so it displays without
a public web address.
"""
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from email.mime.image import MIMEImage

LOGO_PATH = Path(__file__).parent / "assets" / "technosat-logo-en.png"
LOGO_CID = "technosat_logo"


def build_message(subject, to, text, html):
    """Return an EmailMultiAlternatives with the HTML part and the inline logo attached."""
    message = EmailMultiAlternatives(subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=[to])
    message.attach_alternative(html, "text/html")
    if LOGO_PATH.exists():
        logo = MIMEImage(LOGO_PATH.read_bytes(), _subtype="png")
        logo.add_header("Content-ID", f"<{LOGO_CID}>")
        logo.add_header("Content-Disposition", "inline", filename="technosat-logo.png")
        message.attach(logo)
    return message


def send_branded(to, subject, heading, paragraphs, *, button=None, greeting=None):
    """Send a Technosat-styled email. `button` is an optional (label, url) pair."""
    lines = [heading] + ([greeting] if greeting else []) + list(paragraphs)
    if button:
        lines.append(f"{button[0]}: {button[1]}")
    lines.append("IT Support Technosat")
    text = "\n\n".join(lines)
    html = render_to_string("emails/notice.html", {
        "heading": heading, "greeting": greeting, "paragraphs": paragraphs, "button": button,
        "logo_cid": LOGO_CID,
    })
    build_message(subject, to, text, html).send(fail_silently=False)

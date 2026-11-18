"""Branded HTML email with a plain-text fallback, shared by all portal notifications."""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_branded(to, subject, heading, paragraphs, *, button=None, greeting=None):
    """Send a Technosat-styled email. `button` is an optional (label, url) pair."""
    lines = [heading] + ([greeting] if greeting else []) + list(paragraphs)
    if button:
        lines.append(f"{button[0]}: {button[1]}")
    lines.append("IT Support Technosat")
    text = "\n\n".join(lines)
    html = render_to_string("emails/notice.html", {
        "heading": heading, "greeting": greeting, "paragraphs": paragraphs, "button": button,
    })
    message = EmailMultiAlternatives(subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=[to])
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)

"""Celery tasks for the users application."""

import logging
from typing import Any

from celery import shared_task  # type: ignore[import-untyped]
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation

logger = logging.getLogger(__name__)

# Sender address for all transactional e-mails.
_NO_REPLY_EMAIL: str = "noreply@blogapi.com"


@shared_task(  # type: ignore[misc]
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_welcome_email(
    self: Any,
    user_id: int,
    user_language: str = "en",
) -> None:
    """Send a welcome e-mail to a newly registered user.

    Why retries matter here:
        E-mail delivery depends on an external SMTP server which can be
        temporarily unavailable (rate limits, network blips, DNS issues).
        Automatic retries with exponential back-off ensure the e-mail is
        eventually delivered without manual intervention, and without
        blocking the registration response to the user.

    Args:
        self: Celery task instance (injected by ``bind=True``).
        user_id: Primary key of the user to welcome.
        user_language: BCP-47 language code for the e-mail content.
    """
    from apps.users.models import User  # local import avoids circular deps

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("send_welcome_email: user %d not found", user_id)
        return

    with translation.override(user_language):
        subject: str = render_to_string(
            "emails/welcome/subject.txt"
        ).strip()
        message: str = render_to_string(
            "emails/welcome/body.txt",
            {"user": user, "user_language": user_language},
        )

    send_mail(
        subject=subject,
        message=message,
        from_email=_NO_REPLY_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    logger.info("Welcome e-mail sent to %s", user.email)
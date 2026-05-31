import logging
import os

from engine.notifications.senders import ResendEmailSender
from engine.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="engine.worker.tasks.notifications.send_digest")
def send_digest(
    items: list[dict],
    to_address: str,
    _email_sender=None,
) -> None:
    """Send a low-urgency digest email for the given parked items."""
    if not items:
        return

    sender = _email_sender or ResendEmailSender()
    lines = [f"- [{i['action']}] {i['preview']}" for i in items]
    body = "Pending low-urgency items for your review:\n\n" + "\n".join(lines)

    sender.send(
        to=to_address,
        subject=f"AIOS digest: {len(items)} item(s) awaiting review",
        body=body,
    )
    logger.info("digest sent: %d items to %s", len(items), to_address)

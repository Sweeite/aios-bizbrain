import os

import httpx


class NotificationError(Exception):
    pass


class ResendEmailSender:
    _API_URL = "https://api.resend.com/emails"

    def send(self, to: str, subject: str, body: str) -> None:
        api_key = os.getenv("RESEND_API_KEY", "")
        from_addr = os.getenv("NOTIFICATION_EMAIL_FROM", "noreply@example.com")
        resp = httpx.post(
            self._API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": from_addr, "to": [to], "subject": subject, "text": body},
        )
        if not resp.is_success:
            raise NotificationError(f"Resend error {resp.status_code}: {resp.text}")


class SlackWebhookSender:
    def send(self, text: str) -> None:
        url = os.getenv("SLACK_WEBHOOK_URL", "")
        if not url:
            raise NotificationError("SLACK_WEBHOOK_URL not set")
        resp = httpx.post(url, json={"text": text})
        if not resp.is_success:
            raise NotificationError(f"Slack error {resp.status_code}: {resp.text}")

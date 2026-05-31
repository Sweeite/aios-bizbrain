from engine.spine.types import ParkedApprovalRequest, UrgencyLevel


class NotificationRouter:
    def __init__(self, config: dict, email_sender, slack_sender) -> None:
        self._config = config
        self._email = email_sender
        self._slack = slack_sender
        self._digest_queue: list[ParkedApprovalRequest] = []

    def route(self, request: ParkedApprovalRequest) -> None:
        if request.urgency == UrgencyLevel.high:
            urgent_via: list[str] = self._config.get("urgent_via", [])
            if "email" in urgent_via:
                to = self._config.get("email_address", "")
                self._email.send(
                    to=to,
                    subject=f"[Urgent] Approval required: {request.action}",
                    body=request.preview,
                )
            if "slack" in urgent_via:
                channel = self._config.get("slack_channel_urgent", "")
                self._slack.send(
                    f"*[Urgent approval needed]* `{request.action}` — {request.preview} "
                    f"(channel: {channel})"
                )
        elif request.urgency == UrgencyLevel.low:
            self._digest_queue.append(request)
        # routine → in-app queue only; no action here

    def flush_digest_queue(self) -> list[ParkedApprovalRequest]:
        items, self._digest_queue = self._digest_queue, []
        return items

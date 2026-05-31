"""Tests for notification routing — Slice 13."""
from engine.notifications.router import NotificationRouter
from engine.spine.types import (
    ParkedApprovalRequest,
    Scope,
    ScopeLevel,
    UrgencyLevel,
)


def _request(urgency: UrgencyLevel = UrgencyLevel.routine) -> ParkedApprovalRequest:
    return ParkedApprovalRequest(
        action="draft_email.send",
        preview="Dear client...",
        requesting_agent="comms-agent",
        principal="partner@northpath.com",
        scope=Scope(level=ScopeLevel.entity, entity_ref="client-001"),
        rationale="Escalation follow-up",
        idempotency_key="test-key-001",
        urgency=urgency,
    )


_NORTHPATH_NOTIFICATIONS = {
    "urgent_via": ["slack", "email"],
    "routine_via": ["cockpit_queue"],
    "slack_channel_urgent": "#ai-brain-urgent",
    "email_address": "partners@northpath.example.com",
    "digest_email_address": "partners@northpath.example.com",
}


class RecordingSender:
    def __init__(self):
        self.calls: list = []

    def send(self, *args, **kwargs):
        self.calls.append((args, kwargs))


# ---------------------------------------------------------------------------
# Routing behavior
# ---------------------------------------------------------------------------

def test_high_urgency_calls_email_and_slack():
    email = RecordingSender()
    slack = RecordingSender()
    router = NotificationRouter(_NORTHPATH_NOTIFICATIONS, email, slack)

    router.route(_request(UrgencyLevel.high))

    assert len(email.calls) == 1
    assert len(slack.calls) == 1


def test_routine_urgency_calls_neither_sender():
    email = RecordingSender()
    slack = RecordingSender()
    router = NotificationRouter(_NORTHPATH_NOTIFICATIONS, email, slack)

    router.route(_request(UrgencyLevel.routine))

    assert len(email.calls) == 0
    assert len(slack.calls) == 0


def test_low_urgency_queues_for_digest_no_immediate_send():
    email = RecordingSender()
    slack = RecordingSender()
    router = NotificationRouter(_NORTHPATH_NOTIFICATIONS, email, slack)

    router.route(_request(UrgencyLevel.low))

    assert len(email.calls) == 0
    assert len(slack.calls) == 0
    queued = router.flush_digest_queue()
    assert len(queued) == 1
    assert queued[0].urgency == UrgencyLevel.low


def test_flush_digest_queue_clears_after_read():
    router = NotificationRouter(
        _NORTHPATH_NOTIFICATIONS, RecordingSender(), RecordingSender()
    )
    router.route(_request(UrgencyLevel.low))
    router.flush_digest_queue()
    assert router.flush_digest_queue() == []


def test_router_reads_urgent_via_from_config_no_email_when_omitted():
    """If config omits 'email' from urgent_via, email sender is not called."""
    config = {**_NORTHPATH_NOTIFICATIONS, "urgent_via": ["slack"]}
    email = RecordingSender()
    slack = RecordingSender()
    router = NotificationRouter(config, email, slack)

    router.route(_request(UrgencyLevel.high))

    assert len(email.calls) == 0
    assert len(slack.calls) == 1


def test_router_reads_urgent_via_from_config_no_slack_when_omitted():
    """If config omits 'slack' from urgent_via, slack sender is not called."""
    config = {**_NORTHPATH_NOTIFICATIONS, "urgent_via": ["email"]}
    email = RecordingSender()
    slack = RecordingSender()
    router = NotificationRouter(config, email, slack)

    router.route(_request(UrgencyLevel.high))

    assert len(email.calls) == 1
    assert len(slack.calls) == 0


# ---------------------------------------------------------------------------
# Sender contracts — ResendEmailSender
# ---------------------------------------------------------------------------

def test_resend_email_sender_posts_to_resend_api(httpx_mock):
    import os
    from engine.notifications.senders import ResendEmailSender

    os.environ["RESEND_API_KEY"] = "re_test_key"
    httpx_mock.add_response(url="https://api.resend.com/emails", status_code=200, json={"id": "abc"})

    sender = ResendEmailSender()
    sender.send(to="partner@example.com", subject="Urgent: client escalation", body="Please review.")

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert requests[0].url == "https://api.resend.com/emails"


def test_resend_email_sender_raises_on_non_2xx(httpx_mock):
    import os
    import pytest
    from engine.notifications.senders import NotificationError, ResendEmailSender

    os.environ["RESEND_API_KEY"] = "re_test_key"
    httpx_mock.add_response(url="https://api.resend.com/emails", status_code=422, json={"message": "bad"})

    sender = ResendEmailSender()
    with pytest.raises(NotificationError):
        sender.send(to="x@example.com", subject="s", body="b")


# ---------------------------------------------------------------------------
# Sender contracts — SlackWebhookSender
# ---------------------------------------------------------------------------

def test_slack_webhook_sender_posts_to_webhook_url(httpx_mock):
    import os
    from engine.notifications.senders import SlackWebhookSender

    webhook_url = "https://hooks.slack.com/services/TEST/TEST/test"
    os.environ["SLACK_WEBHOOK_URL"] = webhook_url
    httpx_mock.add_response(url=webhook_url, status_code=200, text="ok")

    sender = SlackWebhookSender()
    sender.send("Urgent: client escalation parked for approval")

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert str(requests[0].url) == webhook_url


def test_slack_webhook_sender_raises_on_non_2xx(httpx_mock):
    import os
    import pytest
    from engine.notifications.senders import NotificationError, SlackWebhookSender

    webhook_url = "https://hooks.slack.com/services/TEST/TEST/test"
    os.environ["SLACK_WEBHOOK_URL"] = webhook_url
    httpx_mock.add_response(url=webhook_url, status_code=500, text="error")

    sender = SlackWebhookSender()
    with pytest.raises(NotificationError):
        sender.send("something")


# ---------------------------------------------------------------------------
# ToolExecutor integration
# ---------------------------------------------------------------------------

def test_tool_executor_calls_router_route_when_t3_parks():
    """ToolExecutor with notification_router set calls route() on park."""
    from engine.spine.types import AutonomyTier, ToolMode, ToolSpec
    from engine.tools.executor import ToolExecutor
    from engine.tools.registry import ToolRegistry

    routed: list[ParkedApprovalRequest] = []

    class CapturingRouter:
        def route(self, req: ParkedApprovalRequest):
            routed.append(req)

    registry = ToolRegistry()
    spec = ToolSpec(
        name="draft_email.send",
        inputs={},
        system="gmail",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
    )
    registry.register(spec, lambda inputs, dry_run: "preview" if dry_run else "sent")
    executor = ToolExecutor(registry, notification_router=CapturingRouter())

    executor.execute(
        tool_name="draft_email.send",
        inputs={},
        scope=Scope(level=ScopeLevel.entity, entity_ref="client-001"),
        requesting_agent="comms-agent",
        principal="partner",
        rationale="follow-up",
        idempotency_key="exec-key-001",
    )

    assert len(routed) == 1
    assert routed[0].idempotency_key == "exec-key-001"


def test_tool_executor_without_notification_router_parks_normally():
    """Existing behavior: no router, T3 parks without error."""
    from engine.spine.types import AutonomyTier, ToolMode, ToolSpec
    from engine.tools.executor import ToolExecutor
    from engine.tools.registry import ToolRegistry

    registry = ToolRegistry()
    spec = ToolSpec(
        name="draft_email.send",
        inputs={},
        system="gmail",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
    )
    registry.register(spec, lambda inputs, dry_run: "preview" if dry_run else "sent")
    executor = ToolExecutor(registry)

    result = executor.execute(
        tool_name="draft_email.send",
        inputs={},
        scope=Scope(level=ScopeLevel.entity, entity_ref="client-001"),
        requesting_agent="comms-agent",
        principal="partner",
        rationale="follow-up",
        idempotency_key="exec-key-002",
    )

    assert isinstance(result, ParkedApprovalRequest)


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

def test_send_digest_task_is_registered():
    from engine.worker import tasks  # noqa: F401 — side-effect: register tasks
    from engine.worker.celery_app import celery_app

    assert "engine.worker.tasks.notifications.send_digest" in celery_app.tasks


def test_send_digest_task_calls_email_sender_with_formatted_items(monkeypatch):
    from engine.worker.tasks.notifications import send_digest

    sent: list = []

    class StubSender:
        def send(self, to, subject, body):
            sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("NOTIFICATION_EMAIL_FROM", "ai@northpath.example.com")

    items = [
        {
            "action": "draft_email.send",
            "preview": "Dear client...",
            "requesting_agent": "comms-agent",
            "idempotency_key": "k1",
            "urgency": "low",
        }
    ]
    send_digest(
        items=items,
        to_address="partners@northpath.example.com",
        _email_sender=StubSender(),
    )

    assert len(sent) == 1
    assert sent[0]["to"] == "partners@northpath.example.com"
    assert "draft_email.send" in sent[0]["body"]

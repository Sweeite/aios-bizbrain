import json

from engine.spine.types import AutonomyTier

GATE_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are a commitment gate classifier. "
    "Determine whether this email draft commits the firm to scope, fees, dates, "
    "deliverables, or staffing. "
    'Reply with a JSON object only: {"tier": "T3"} if it contains a commitment, '
    '{"tier": "T1"} if it is a routine check-in with no commitments.'
)


class CommitmentGate:
    def __init__(self, anthropic_client) -> None:
        self._client = anthropic_client

    def classify(self, draft: str) -> AutonomyTier:
        response = self._client.messages.create(
            model=GATE_MODEL,
            max_tokens=64,
            system=_SYSTEM,
            messages=[{"role": "user", "content": draft}],
        )
        raw = response.content[0].text.strip()
        try:
            tier_str = json.loads(raw).get("tier", "T3")
            return AutonomyTier(tier_str)
        except (json.JSONDecodeError, ValueError):
            return AutonomyTier.T3

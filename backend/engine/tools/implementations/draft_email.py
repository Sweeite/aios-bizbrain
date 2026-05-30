from engine.spine.types import AutonomyTier, ScopeLevel, ToolMode, ToolSpec

SPEC = ToolSpec(
    name="gmail.draft_email",
    inputs={"to": "str", "subject": "str", "body": "str"},
    system="gmail",
    mode=ToolMode.write,
    tier=AutonomyTier.T3,
    scope_required=ScopeLevel.entity,
    reversible=False,
    side_effects=["creates_email_draft"],
)


class DraftEmailTool:
    def execute(self, inputs: dict, dry_run: bool = False) -> str:
        return inputs.get("body", "")

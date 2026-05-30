from dataclasses import dataclass

from engine.spine.types import BusinessEvent, Confidence, Scope, ScopeLevel


@dataclass
class ResolvedEvent:
    event: BusinessEvent
    scope: Scope
    confidence: Confidence
    routed_to_review: bool


class EntityResolver:
    def __init__(self, known_entities: dict[str, str]):
        self._known = known_entities

    def resolve(self, event: BusinessEvent) -> ResolvedEvent:
        refs = event.entities
        if not refs:
            return ResolvedEvent(
                event=event,
                scope=Scope(level=ScopeLevel.org),
                confidence=Confidence.stated_once,
                routed_to_review=True,
            )

        known = [r for r in refs if r in self._known]

        if len(known) == len(refs):
            confidence = Confidence.observed
        elif known:
            confidence = Confidence.inferred
        else:
            confidence = Confidence.stated_once

        routed = confidence == Confidence.stated_once
        if routed:
            scope = Scope(level=ScopeLevel.org)
        else:
            scope = Scope(level=ScopeLevel.entity, entity_ref=refs[0])

        return ResolvedEvent(
            event=event,
            scope=scope,
            confidence=confidence,
            routed_to_review=routed,
        )

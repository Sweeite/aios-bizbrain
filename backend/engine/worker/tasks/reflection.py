import json
import logging
import os

import anthropic

from engine.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

EVALUATION_MODEL = "claude-haiku-4-5-20251001"


@celery_app.task(name="engine.worker.tasks.reflection.reflect_on_memory_write")
def reflect_on_memory_write(source_event_id: str, source_system: str, entity_ref: str | None) -> None:
    logger.info(
        "reflection hook fired: event=%s system=%s entity=%s",
        source_event_id,
        source_system,
        entity_ref,
    )


@celery_app.task(name="engine.worker.tasks.reflection.reflect_on_step")
def reflect_on_step(run_id: str, agent_name: str, entity_ref: str, draft: str) -> dict:
    """Evaluate whether the agent step output warrants a memory write."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = (
        f"An AI agent named '{agent_name}' processed entity '{entity_ref}' and produced:\n\n"
        f"{draft}\n\n"
        "Does this output contain new facts, relationships, or decisions that should be written "
        "to long-term memory (entity or semantic store)? Reply with a JSON object only:\n"
        '{"should_write": true/false, "store": "entity"|"semantic"|null, "reason": "<one sentence>"}'
    )

    response = client.messages.create(
        model=EVALUATION_MODEL,
        max_tokens=128,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    logger.info(
        "reflection evaluation: run=%s agent=%s entity=%s result=%s",
        run_id,
        agent_name,
        entity_ref,
        raw,
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"should_write": False, "store": None, "reason": "parse error"}

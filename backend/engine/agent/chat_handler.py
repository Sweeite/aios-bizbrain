from collections.abc import Generator

CHAT_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = (
    "You are an AI business assistant for a professional services firm. "
    "You have access to client memory and live context. "
    "Answer the user's question concisely and helpfully."
)


class ChatHandler:
    def stream(
        self,
        message: str,
        entity_ref: str,
        memory_records: list,
        live_context: dict,
        anthropic_client,
    ) -> Generator[str, None, None]:
        memory_summary = "\n".join(
            f"- {r.payload.get('event_type', 'event')}: "
            f"stage={r.payload.get('to_stage', '?')}, "
            f"days_in_stage={r.payload.get('days_in_stage', '?')}"
            for r in memory_records
        ) or "(no prior episodic records)"

        context_block = (
            f"Client: {entity_ref}\n"
            f"Deal: {live_context.get('deal_name', '')}\n"
            f"Current stage: {live_context.get('current_stage', 'unknown')}\n"
            f"Days in stage: {live_context.get('days_in_stage', 0)}\n\n"
            f"Episodic memory:\n{memory_summary}"
        )

        user_content = f"{context_block}\n\nUser question: {message}"

        with anthropic_client.messages.stream(
            model=CHAT_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            for text in stream.text_stream:
                yield text

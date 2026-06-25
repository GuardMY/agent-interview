INTENT_PROMPT_TEMPLATE = """Classify the intent of this candidate's message during a technical interview.

Recent conversation context:
{recent_context}

Candidate's message:
"{message}"

Classify into exactly ONE of these intents:
- "answer": The candidate is directly answering the current question
- "clarify": The candidate is asking for clarification or wants the question rephrased
- "skip": The candidate wants to skip the current question
- "chat": General conversation, small talk, or off-topic
- "disengage": The candidate wants to end the interview

Respond ONLY with a raw JSON object (no code fences, no markdown):
{{"intent": "<one of the above>", "confidence": <float 0.0-1.0>}}"""


async def detect_intent_fallback(llm_generate, message: str, recent_context: str = "") -> dict:
    """LLM-based intent detection as fallback when keyword detection is ambiguous."""
    prompt = INTENT_PROMPT_TEMPLATE.format(
        recent_context=recent_context[:1000],
        message=message[:500],
    )
    response = await llm_generate(prompt, max_tokens=100, temperature=0.1)
    # Parse JSON from response
    return _parse_intent_json(response)


def _parse_intent_json(raw: str) -> dict:
    import json
    import re

    # Try direct parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Fallback
    return {"intent": "answer", "confidence": 0.5}

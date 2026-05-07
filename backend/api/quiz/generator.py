from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def generate_mcq(conversation_text: str, n_questions: int = 8) -> list[dict]:
    """Generate MCQ questions from conversation text. Tries twice before raising."""
    from backend.agent.prompts import MCQ_GENERATION_PROMPT
    from backend.core.llm import build_llm_client

    llm = build_llm_client(temperature=0.5)
    prompt = MCQ_GENERATION_PROMPT.replace("{conversation_text}", conversation_text)

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            resp = llm.invoke(prompt)
            text = str(resp.content).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(text)
            questions = parsed.get("questions", [])
            _validate(questions, n_questions)
            return questions[:n_questions]
        except Exception as exc:
            last_exc = exc
            logger.warning("MCQ generation attempt %d failed: %s", attempt + 1, exc)

    raise ValueError(f"MCQ generation failed after 2 attempts: {last_exc}") from last_exc


def _validate(questions: list, n_required: int) -> None:
    if len(questions) < n_required:
        raise ValueError(f"Got {len(questions)} questions, need {n_required}")
    for q in questions[:n_required]:
        if not q.get("text") or len(str(q["text"])) < 10:
            raise ValueError(f"Question text too short: {q.get('text', '')!r}")
        if len(q.get("options", [])) != 4:
            raise ValueError("Each question must have exactly 4 options")
        if q.get("correct") not in (0, 1, 2, 3):
            raise ValueError(f"correct must be 0-3, got {q.get('correct')!r}")

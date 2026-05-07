from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger(__name__)


def _conversation_text(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, dict):
            parts = [content.get("intro", "")]
            for s in content.get("sections", []):
                parts.append(s.get("content", ""))
            content = " ".join(filter(None, parts))
        content = str(content).strip()
        if len(content) > 30:
            lines.append(f"{m['role'].upper()}: {content[:1000]}")
    return "\n".join(lines)


def generate_quiz(
    user_id: str,
    session_id: str,
    section_content: str | None = None,
    section_title: str | None = None,
    _quiz_session_id: str | None = None,  # pass existing quiz session when regenerating
) -> dict:
    from backend.core.errors import ForbiddenError, UnprocessableError
    from backend.core.db import execute, query_one
    from backend.api.sessions.service import create_session, get_messages
    from backend.api.quiz.generator import generate_mcq

    row = query_one(
        "SELECT id, title FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not row:
        raise ForbiddenError("Session not found or access denied")

    if section_content and len(section_content.strip()) >= 20:
        conversation = section_content.strip()
    else:
        messages = get_messages(user_id, session_id)
        conversation = _conversation_text(messages)
        if len(conversation.strip()) < 50:
            raise UnprocessableError(
                "Not enough conversation content to generate a quiz. Have a longer discussion first."
            )

    questions = generate_mcq(conversation, n_questions=8)

    attempt_id = str(uuid.uuid4())
    execute(
        """INSERT INTO mcq_attempts (id, user_id, session_id, questions)
           VALUES (%s, %s, %s, %s)""",
        (attempt_id, user_id, session_id, json.dumps(questions)),
    )

    # Create or update a quiz child session so it appears in the sidebar
    quiz_title = f"Quiz: {section_title or row.get('title') or 'Knowledge Check'}"[:80]
    if _quiz_session_id:
        # Regeneration: just update the existing quiz session's linked attempt
        execute(
            "UPDATE chat_sessions SET linked_attempt_id = %s, last_message_at = NOW() WHERE id = %s",
            (attempt_id, _quiz_session_id),
        )
        quiz_session_id = _quiz_session_id
    else:
        quiz_session = create_session(
            user_id=user_id,
            session_type='quiz',
            parent_session_id=session_id,
            title=quiz_title,
            topic=section_title or 'quiz',
        )
        execute(
            "UPDATE chat_sessions SET linked_attempt_id = %s WHERE id = %s",
            (attempt_id, quiz_session['id']),
        )
        quiz_session_id = quiz_session['id']

    safe_qs = [{k: v for k, v in q.items() if k != "correct"} for q in questions]
    return {
        "attempt_id": attempt_id,
        "quiz_session_id": quiz_session_id,
        "questions": safe_qs,
        "session_id": session_id,
    }


def get_attempt(user_id: str, attempt_id: str) -> dict:
    from backend.core.errors import ForbiddenError
    from backend.core.db import query_one

    row = query_one(
        "SELECT id, session_id, questions, answers, score, completed_at "
        "FROM mcq_attempts WHERE id = %s AND user_id = %s",
        (attempt_id, user_id),
    )
    if not row:
        raise ForbiddenError("Attempt not found or access denied")

    questions = (
        row["questions"] if isinstance(row["questions"], list)
        else json.loads(row["questions"] or "[]")
    )
    completed = row["completed_at"] is not None

    if not completed:
        questions = [{k: v for k, v in q.items() if k != "correct"} for q in questions]

    return {
        "attempt_id": str(row["id"]),
        "session_id": str(row["session_id"]),
        "questions": questions,
        "answers": row["answers"] or {},
        "score": row["score"],
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
    }


def save_answers(user_id: str, attempt_id: str, answers: dict, submit: bool = False) -> dict:
    from backend.core.errors import ForbiddenError
    from backend.core.db import execute, query_one

    row = query_one(
        "SELECT id, questions, completed_at FROM mcq_attempts WHERE id = %s AND user_id = %s",
        (attempt_id, user_id),
    )
    if not row:
        raise ForbiddenError("Attempt not found or access denied")

    if submit and row["completed_at"] is None:
        questions = (
            row["questions"] if isinstance(row["questions"], list)
            else json.loads(row["questions"] or "[]")
        )
        score = sum(
            1 for q in questions
            if answers.get(q["id"]) == q.get("correct")
        )
        execute(
            """UPDATE mcq_attempts SET answers = %s, score = %s, completed_at = NOW()
               WHERE id = %s""",
            (json.dumps(answers), score, attempt_id),
        )
        return {
            "score": score,
            "total": len(questions),
            "questions": questions,
            "completed_at": "now",
        }

    execute(
        "UPDATE mcq_attempts SET answers = %s WHERE id = %s AND completed_at IS NULL",
        (json.dumps(answers), attempt_id),
    )
    return {"saved": True}


def retry_quiz(user_id: str, attempt_id: str) -> dict:
    from backend.core.errors import ForbiddenError
    from backend.core.db import execute, query_one

    row = query_one(
        "SELECT id, session_id, questions FROM mcq_attempts WHERE id = %s AND user_id = %s",
        (attempt_id, user_id),
    )
    if not row:
        raise ForbiddenError("Attempt not found or access denied")

    questions = (
        row["questions"] if isinstance(row["questions"], list)
        else json.loads(row["questions"] or "[]")
    )
    new_id = str(uuid.uuid4())
    execute(
        """INSERT INTO mcq_attempts (id, user_id, session_id, questions)
           VALUES (%s, %s, %s, %s)""",
        (new_id, user_id, str(row["session_id"]), json.dumps(questions)),
    )
    return {"attempt_id": new_id}


def list_attempts(user_id: str, session_id: str) -> list[dict]:
    from backend.core.db import query

    rows = query(
        "SELECT id, score, attempted_at, completed_at FROM mcq_attempts "
        "WHERE user_id = %s AND session_id = %s ORDER BY attempted_at DESC",
        (user_id, session_id),
    )
    return [
        {
            "attempt_id": str(r["id"]),
            "score": r["score"],
            "attempted_at": r["attempted_at"].isoformat() if r["attempted_at"] else None,
            "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
        }
        for r in rows
    ]


def get_relearn(user_id: str, attempt_id: str, question_id: str) -> dict:
    from backend.core.errors import ForbiddenError, UnprocessableError
    from backend.core.db import execute, query_one
    from backend.core.llm import build_llm_client
    from backend.agent.prompts import RELEARN_PROMPT

    row = query_one(
        "SELECT id, questions, relearn_cache FROM mcq_attempts WHERE id = %s AND user_id = %s",
        (attempt_id, user_id),
    )
    if not row:
        raise ForbiddenError("Attempt not found")

    cache = (
        row["relearn_cache"] if isinstance(row["relearn_cache"], dict)
        else json.loads(row["relearn_cache"] or "{}")
    )
    if question_id in cache:
        return {"explanation": cache[question_id]}

    questions = (
        row["questions"] if isinstance(row["questions"], list)
        else json.loads(row["questions"] or "[]")
    )
    q = next((q for q in questions if q["id"] == question_id), None)
    if not q:
        raise UnprocessableError("Question not found in attempt")

    llm = build_llm_client(temperature=0.3)
    prompt = RELEARN_PROMPT.format(
        question_text=q["text"],
        correct_option=q["options"][q["correct"]],
        topic=q.get("topic", q["text"][:50]),
    )
    explanation = str(llm.invoke(prompt).content).strip()

    cache[question_id] = explanation
    execute(
        "UPDATE mcq_attempts SET relearn_cache = %s WHERE id = %s",
        (json.dumps(cache), attempt_id),
    )
    return {"explanation": explanation}

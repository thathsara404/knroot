from __future__ import annotations

import json
import logging
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver

from backend.agent.graph import graph_builder
from backend.agent.prompts import AUTO_TITLE_PROMPT
from backend.api.news.service import get_news
from backend.core.db import execute, get_pool, query_one
from backend.core.llm import build_llm_client

logger = logging.getLogger(__name__)


def _is_new_session(compiled, config: dict) -> bool:
    snapshot = compiled.get_state(config)
    return len(snapshot.values.get("messages", [])) == 0


def _parse_llm_response(text: str) -> tuple[object, str]:
    """Parse LLM response text into (response_value, response_type).

    Returns:
      ("sectioned", dict)  — structured sections with Explore/Quiz buttons
      ("plain",    str)    — flat text rendered as a plain bubble
    """
    candidate = text.strip()
    if candidate.startswith("```"):
        try:
            candidate = candidate.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        except Exception:
            return text, "plain"
    if not candidate.startswith("{"):
        return text, "plain"
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        return text, "plain"
    if not isinstance(data, dict):
        return text, "plain"
    if data.get("type") == "sectioned" and isinstance(data.get("sections"), list):
        return data, "sectioned"
    if data.get("type") == "plain" and isinstance(data.get("text"), str):
        return data["text"], "plain"
    return text, "plain"


def send_message(user_id: str, session_id: str, user_msg: str) -> dict:
    with get_pool().connection() as conn:
        checkpointer = PostgresSaver(conn)  # type: ignore[arg-type]
        compiled = graph_builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": session_id}}

        is_new = _is_new_session(compiled, config)
        news_context = get_news("ai")[0:5] if is_new else []

        news_text = ""
        if news_context:
            lines = []
            for a in news_context:
                lines.append(f"**[{a['source']}]** {a['title']}")
                if a.get("summary"):
                    lines.append(f"> {a['summary']}")
            news_text = "\n".join(lines)

        result = compiled.invoke(  # type: ignore[call-overload]
            {
                "messages": [HumanMessage(content=user_msg)],
                "news_context": news_text,
                "suggested_topics": [],
            },
            config=config,
        )

    raw_response = str(result["messages"][-1].content)
    suggested_topics = result.get("suggested_topics", [])

    # Persist to session_messages for reliable history access across all session types
    execute(
        "INSERT INTO session_messages (session_id, role, content) VALUES (%s, 'user', %s)",
        (session_id, user_msg),
    )
    execute(
        "INSERT INTO session_messages (session_id, role, content) VALUES (%s, 'assistant', %s)",
        (session_id, raw_response),
    )
    execute(
        "UPDATE chat_sessions SET last_message_at = NOW() WHERE id = %s",
        (session_id,),
    )

    ai_response, response_type = _parse_llm_response(raw_response)

    return {
        "response": ai_response,
        "response_type": response_type,
        "session_id": session_id,
        "is_new_conversation": is_new,
        "suggested_topics": suggested_topics,
    }


def get_or_create_session(user_id: str, session_id: str | None) -> str:
    if session_id:
        row = query_one(
            "SELECT id FROM chat_sessions WHERE id = %s AND user_id = %s",
            (session_id, user_id),
        )
        if row:
            return session_id

    new_id = str(uuid.uuid4())
    execute(
        """INSERT INTO chat_sessions (id, user_id, thread_id, session_type)
           VALUES (%s, %s, %s, 'regular')""",
        (new_id, user_id, new_id),
    )
    return new_id


def auto_title_session(session_id: str, first_user_msg: str, first_ai_reply: str) -> None:
    llm = build_llm_client(temperature=0.3)
    prompt = AUTO_TITLE_PROMPT.format(
        first_user_message=first_user_msg[:300],
        first_ai_reply_excerpt=first_ai_reply[:300],
    )
    try:
        title = str(llm.invoke(prompt).content).strip()[:80]
        execute(
            "UPDATE chat_sessions SET title = %s WHERE id = %s",
            (title, session_id),
        )
    except Exception as exc:
        logger.warning("Auto-title failed for session %s: %s", session_id, exc)

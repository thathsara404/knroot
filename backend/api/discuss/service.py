from __future__ import annotations

import json
import logging

from backend.agent.prompts import DISCUSSION_PROMPT, LEARN_MORE_PROMPT
from backend.api.sessions.service import create_session
from backend.core.db import execute, query_one
from backend.core.llm import build_llm_client

logger = logging.getLogger(__name__)

_ALLOWED_ARTIFACT_TYPES = {"formula", "chart", "diagram"}


def _normalise_sectioned(data: dict) -> None:
    """Ensure new optional fields exist and artifact types are valid."""
    data.setdefault("hierarchy_diagram", "")
    for section in data.get("sections", []):
        raw = section.get("artifacts", [])
        section["artifacts"] = [
            a for a in raw
            if isinstance(a, dict) and a.get("type") in _ALLOWED_ARTIFACT_TYPES
        ]


def _run_discussion_pipeline(user_message: str) -> dict:
    """Run the LLM pipeline and return parsed sectioned dict."""
    llm = build_llm_client(temperature=0.7)
    for _attempt in range(2):
        try:
            response = llm.invoke(user_message)
            text = str(response.content).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(text)
            if data.get("type") == "sectioned" and isinstance(data.get("sections"), list):
                _normalise_sectioned(data)
                return data
        except Exception as exc:
            logger.warning("Pipeline attempt %d failed: %s", _attempt + 1, exc)
    return {"type": "plain", "text": "Unable to generate educational content at this time."}


def news_discuss(user_id: str, article_id: str, article_title: str,
                 article_summary: str, article_link: str,
                 source_category: str | None = None) -> dict:
    """Create a news_discussion session and generate first sectioned response.

    source_category is the news-tab the user clicked Explore from (e.g. 'health').
    Persisted on the session row so the topic-news panel can use it as a
    guaranteed fallback without any inference.
    """
    session = create_session(
        user_id=user_id,
        session_type='news_discussion',
        news_article_id=article_id,
        title=article_title[:80],
        topic=article_link,
    )
    if source_category:
        execute(
            "UPDATE chat_sessions SET source_category = %s WHERE id = %s",
            (source_category, session['id']),
        )

    prompt = (
        DISCUSSION_PROMPT
        + f"\n\nArticle title: {article_title}"
        + f"\nSummary: {article_summary}"
        + f"\nSource: {article_link}"
    )
    first_response = _run_discussion_pipeline(prompt)

    _store_first_message(session['id'], session['thread_id'], article_title, first_response)

    execute(
        "UPDATE chat_sessions SET last_message_at = NOW() WHERE id = %s",
        (session['id'],),
    )

    return {
        "session_id": session['id'],
        "thread_id": session['thread_id'],
        "title": session['title'],
        "first_response": first_response,
    }


def create_learn_more(user_id: str, parent_session_id: str, topic: str) -> dict:
    """Create a learn_more child session and generate first sectioned response."""
    parent = query_one(
        "SELECT id, user_id, source_category, topic, title FROM chat_sessions WHERE id = %s AND user_id = %s",
        (parent_session_id, user_id),
    )
    if not parent:
        from backend.core.errors import ForbiddenError
        raise ForbiddenError("Session not found or access denied")

    session = create_session(
        user_id=user_id,
        session_type='learn_more',
        parent_session_id=parent_session_id,
        topic=topic,
        title=topic[:80],
    )
    # Inherit source_category from parent so the news panel stays topically relevant
    # throughout the full learn_more chain.
    if parent.get("source_category"):
        execute(
            "UPDATE chat_sessions SET source_category = %s WHERE id = %s",
            (parent["source_category"], session['id']),
        )

    parent_topic = parent.get("topic") or parent.get("title") or "the broader subject"
    prompt = LEARN_MORE_PROMPT.format(topic=topic, parent_topic=parent_topic)
    first_response = _run_discussion_pipeline(prompt)

    try:
        _store_first_message(session['id'], session['thread_id'], f"Tell me about: {topic}", first_response)
    except Exception as exc:
        logger.warning("Could not store learn_more messages for session %s: %s", session['id'], exc)

    execute(
        "UPDATE chat_sessions SET last_message_at = NOW() WHERE id = %s",
        (session['id'],),
    )

    return {
        "session_id": session['id'],
        "thread_id": session['thread_id'],
        "title": session['title'],
        "first_response": first_response,
    }


def _store_first_message(session_id: str, thread_id: str, user_msg: str, ai_response: dict) -> None:
    """Store the first exchange in both the DB and LangGraph checkpoint."""
    import json as _json

    response_str = (
        _json.dumps(ai_response)
        if ai_response.get("type") == "sectioned"
        else ai_response.get("text", str(ai_response))
    )

    # Always write to session_messages — reliable, no LangGraph dependency
    execute(
        "INSERT INTO session_messages (session_id, role, content) VALUES (%s, 'user', %s)",
        (session_id, user_msg),
    )
    execute(
        "INSERT INTO session_messages (session_id, role, content) VALUES (%s, 'assistant', %s)",
        (session_id, response_str),
    )

    # Also persist in LangGraph so future chat turns have correct context
    try:
        from langchain_core.messages import AIMessage, HumanMessage
        from langgraph.checkpoint.postgres import PostgresSaver

        from backend.agent.graph import graph_builder
        from backend.core.db import get_pool

        with get_pool().connection() as conn:
            checkpointer = PostgresSaver(conn)  # type: ignore[arg-type]
            compiled = graph_builder.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            compiled.update_state(
                config,
                {
                    "messages": [
                        HumanMessage(content=user_msg),
                        AIMessage(content=response_str),
                    ],
                    "news_context": "",
                    "suggested_topics": [],
                },
                as_node="agent",
            )
    except Exception as exc:
        logger.warning("Could not store LangGraph state for thread %s: %s", thread_id, exc)

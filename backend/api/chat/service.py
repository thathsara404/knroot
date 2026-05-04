from __future__ import annotations

import logging
import re
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver

from backend.agent.graph import graph_builder
from backend.api.news.service import get_news
from backend.core.db import execute, execute_returning, get_pool, query_one
from backend.core.llm import build_llm_client
from backend.agent.prompts import AUTO_TITLE_PROMPT

logger = logging.getLogger(__name__)

_EXPLORE_RE = re.compile(r"<explore>.*?</explore>", re.DOTALL)


def _is_new_session(compiled, config: dict) -> bool:
    snapshot = compiled.get_state(config)
    return len(snapshot.values.get("messages", [])) == 0


def send_message(user_id: int, session_id: str, user_msg: str) -> dict:
    with get_pool().connection() as conn:
        checkpointer = PostgresSaver(conn)
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

        result = compiled.invoke(
            {
                "messages": [HumanMessage(content=user_msg)],
                "news_context": news_text,
                "suggested_topics": [],
            },
            config=config,
        )

    ai_response = result["messages"][-1].content
    suggested_topics = result.get("suggested_topics", [])

    return {
        "response": ai_response,
        "session_id": session_id,
        "is_new_conversation": is_new,
        "suggested_topics": suggested_topics,
    }


def get_or_create_session(user_id: int, session_id: str | None) -> str:
    if session_id:
        row = query_one(
            "SELECT id FROM chat_sessions WHERE id = %s AND user_id = %s",
            (session_id, user_id),
        )
        if row:
            return session_id

    new_id = str(uuid.uuid4())
    execute(
        """INSERT INTO chat_sessions (id, user_id, session_type)
           VALUES (%s, %s, 'regular')""",
        (new_id, user_id),
    )
    return new_id


def auto_title_session(session_id: str, first_user_msg: str, first_ai_reply: str) -> None:
    llm = build_llm_client(temperature=0.3)
    prompt = AUTO_TITLE_PROMPT.format(
        first_user_message=first_user_msg[:300],
        first_ai_reply_excerpt=first_ai_reply[:300],
    )
    try:
        title = llm.invoke(prompt).content.strip()[:80]
        execute(
            "UPDATE chat_sessions SET title = %s WHERE id = %s",
            (title, session_id),
        )
    except Exception as exc:
        logger.warning("Auto-title failed for session %s: %s", session_id, exc)

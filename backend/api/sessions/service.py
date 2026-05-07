from __future__ import annotations

import json as _json
import logging
import uuid

from backend.core.db import execute, execute_returning, query, query_one

logger = logging.getLogger(__name__)


def _parse_content(content: str, role: str) -> dict:
    """Detect sectioned JSON in assistant messages and return enriched fields."""
    if role == "assistant":
        try:
            candidate = content.strip()
            if candidate.startswith("```"):
                candidate = candidate.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = _json.loads(candidate)
            if isinstance(data, dict) and data.get("type") == "sectioned":
                return {"content_type": "sectioned", "content_data": data}
        except Exception:
            pass
    return {"content_type": "plain", "content_data": None}

SESSION_COLS = """
    id, user_id, thread_id, title, session_type,
    parent_session_id, root_session_id, depth_level,
    topic, news_article_id, linked_attempt_id, created_at, last_message_at
"""


def _row_to_dict(row: dict) -> dict:
    """Convert a DB row to a JSON-serialisable dict."""
    d = dict(row)
    for k in ('id', 'user_id', 'parent_session_id', 'root_session_id', 'linked_attempt_id'):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ('created_at', 'last_message_at'):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d


def create_session(
    user_id: str,
    session_type: str = 'regular',
    parent_session_id: str | None = None,
    topic: str | None = None,
    news_article_id: str | None = None,
    title: str | None = None,
) -> dict:
    new_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())

    # For learn_more: inherit root_session_id + depth from parent
    root_session_id = None
    depth_level = 0

    if parent_session_id:
        parent = query_one(
            "SELECT root_session_id, depth_level, id FROM chat_sessions WHERE id = %s",
            (parent_session_id,),
        )
        if parent:
            root_session_id = (
                str(parent['root_session_id'])
                if parent['root_session_id']
                else parent_session_id
            )
            depth_level = (parent['depth_level'] or 0) + 1

    # For news_discussion: root_session_id = self
    if session_type == 'news_discussion' and not parent_session_id:
        root_session_id = new_id

    row = execute_returning(
        """INSERT INTO chat_sessions
               (id, user_id, thread_id, title, session_type,
                parent_session_id, root_session_id, depth_level,
                topic, news_article_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id, thread_id, title, session_type, depth_level,
                     parent_session_id, root_session_id, topic, news_article_id,
                     created_at, last_message_at""",
        (new_id, user_id, thread_id, title, session_type,
         parent_session_id, root_session_id, depth_level,
         topic, news_article_id),
    )
    return _row_to_dict(row)


def list_sessions(user_id: str) -> list[dict]:
    rows = query(
        """SELECT s.id, s.user_id, s.thread_id, s.title, s.session_type,
                  s.parent_session_id, s.root_session_id, s.depth_level,
                  s.topic, s.news_article_id, s.linked_attempt_id,
                  s.created_at, s.last_message_at,
                  (SELECT COUNT(*) FROM chat_sessions c
                   WHERE c.parent_session_id = s.id)::int AS child_count
           FROM chat_sessions s
           WHERE s.user_id = %s
           ORDER BY COALESCE(s.last_message_at, s.created_at) DESC NULLS LAST""",
        (user_id,),
    )
    return [_row_to_dict(r) for r in rows]


def get_session(user_id: str, session_id: str) -> dict | None:
    row = query_one(
        f"SELECT {SESSION_COLS} FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    return _row_to_dict(row) if row else None


def rename_session(user_id: str, session_id: str, title: str) -> None:
    from backend.core.errors import ForbiddenError
    row = query_one(
        "SELECT id FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not row:
        raise ForbiddenError("Session not found or access denied")
    execute(
        "UPDATE chat_sessions SET title = %s, updated_at = NOW() WHERE id = %s",
        (title[:255], session_id),
    )


def delete_session(user_id: str, session_id: str) -> None:
    from backend.core.errors import ForbiddenError
    row = query_one(
        "SELECT id FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not row:
        raise ForbiddenError("Session not found or access denied")
    execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))


def regenerate_session(user_id: str, session_id: str) -> dict:
    """Re-run the LLM for a learn_more or quiz session."""
    from backend.core.errors import ForbiddenError, UnprocessableError
    row = query_one(
        "SELECT id, session_type, topic, thread_id, parent_session_id FROM chat_sessions "
        "WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not row:
        raise ForbiddenError("Session not found or access denied")

    stype = row["session_type"]

    if stype == "learn_more":
        topic = row["topic"] or "unknown topic"
        thread_id = str(row["thread_id"])

        from backend.agent.prompts import LEARN_MORE_PROMPT
        from backend.api.discuss.service import _run_discussion_pipeline, _store_first_message

        prompt = LEARN_MORE_PROMPT.format(topic=topic)
        new_response = _run_discussion_pipeline(prompt)
        execute("DELETE FROM session_messages WHERE session_id = %s", (session_id,))
        _store_first_message(session_id, thread_id, f"Tell me about: {topic}", new_response)
        execute("UPDATE chat_sessions SET last_message_at = NOW() WHERE id = %s", (session_id,))
        return {"session_id": session_id, "first_response": new_response}

    if stype == "quiz":
        parent_id = str(row["parent_session_id"]) if row["parent_session_id"] else None
        if not parent_id:
            raise UnprocessableError("Quiz session has no parent session to regenerate from")

        from backend.api.quiz.service import generate_quiz
        result = generate_quiz(user_id, parent_id, _quiz_session_id=session_id)
        return {"session_id": session_id, "attempt_id": result["attempt_id"]}

    raise UnprocessableError("Only learn_more and quiz sessions can be regenerated")


def get_messages(user_id: str, session_id: str) -> list[dict]:
    """Load message history. Reads from session_messages table; falls back to LangGraph."""
    from backend.core.errors import ForbiddenError
    row = query_one(
        "SELECT thread_id FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not row:
        raise ForbiddenError("Session not found or access denied")

    # Primary: reliable DB storage (works for all session types at any depth)
    db_rows = query(
        "SELECT role, content FROM session_messages WHERE session_id = %s ORDER BY created_at ASC",
        (session_id,),
    )
    if db_rows:
        result = []
        for r in db_rows:
            role = r['role']
            content = r['content']
            parsed = _parse_content(content, role)
            result.append({
                "role": role,
                "content": content,
                "content_type": parsed["content_type"],
                "content_data": parsed["content_data"],
            })
        return result

    # Fallback: LangGraph checkpoint (backwards compat for sessions before migration)
    thread_id = str(row['thread_id'])
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        from backend.agent.graph import graph_builder
        from backend.core.db import get_pool
        with get_pool().connection() as conn:
            checkpointer = PostgresSaver(conn)  # type: ignore[arg-type]
            compiled = graph_builder.compile(checkpointer=checkpointer)
            state = compiled.get_state({"configurable": {"thread_id": thread_id}})
            msgs = state.values.get("messages", [])
        result = []
        for m in msgs:
            role = "user" if m.__class__.__name__ == "HumanMessage" else "assistant"
            content = str(m.content)
            parsed = _parse_content(content, role)
            result.append({
                "role": role,
                "content": content,
                "content_type": parsed["content_type"],
                "content_data": parsed["content_data"],
            })
        return result
    except Exception as exc:
        logger.warning("Could not load messages for session %s: %s", session_id, exc)
        return []


def get_tree(user_id: str, session_id: str) -> list[dict]:
    """Return full ancestry chain from root to current session."""
    from backend.core.errors import ForbiddenError
    # Verify ownership
    current = query_one(
        f"SELECT {SESSION_COLS} FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not current:
        raise ForbiddenError("Session not found or access denied")

    # Walk up the chain
    chain = [_row_to_dict(current)]
    seen = {session_id}
    node = current
    while node.get('parent_session_id'):
        parent_id = str(node['parent_session_id'])
        if parent_id in seen:
            break
        seen.add(parent_id)
        node = query_one(
            f"SELECT {SESSION_COLS} FROM chat_sessions WHERE id = %s",
            (parent_id,),
        )
        if not node:
            break
        chain.append(_row_to_dict(node))

    # Reverse so root is first
    chain.reverse()
    # Mark the current node
    for item in chain:
        item['is_current'] = (item['id'] == session_id)
    return chain


def get_knowledge_tree(user_id: str, session_id: str) -> list[dict]:
    """Return the full downward tree for the thread containing session_id.

    Finds the root of the thread, then returns all sessions in the tree
    (root + all descendants) ordered for top-down rendering, with
    depth_offset (int) for indentation and is_current (bool) for highlighting.
    """
    from backend.core.errors import ForbiddenError

    current = query_one(
        "SELECT id, root_session_id, depth_level FROM chat_sessions "
        "WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not current:
        raise ForbiddenError("Session not found or access denied")

    # root_session_id is set for child sessions; root sessions have it set to self
    root_id = str(current['root_session_id']) if current['root_session_id'] else str(current['id'])

    rows = query(
        f"""SELECT {SESSION_COLS}
            FROM chat_sessions
            WHERE (id = %s OR root_session_id = %s)
              AND user_id = %s
            ORDER BY depth_level ASC, COALESCE(created_at, last_message_at) ASC""",
        (root_id, root_id, user_id),
    )

    nodes = [_row_to_dict(r) for r in rows]

    # Compute depth relative to root so indentation is always 0-based
    root_depth = nodes[0]['depth_level'] or 0 if nodes else 0
    for node in nodes:
        node['depth_offset'] = (node['depth_level'] or 0) - root_depth
        node['is_current'] = (node['id'] == session_id)

    return nodes

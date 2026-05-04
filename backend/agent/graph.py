from __future__ import annotations

import re
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated  # type: ignore[assignment]
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from backend.agent.prompts import SYSTEM_PROMPT
from backend.agent.tools import get_latest_ai_news
from backend.core.llm import build_llm_client

_EXPLORE_RE = re.compile(r"<explore>\s*(\{.*?\})\s*</explore>", re.DOTALL)


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    news_context: str
    suggested_topics: list[str]


def _extract_topics(text: str) -> tuple[str, list[str]]:
    """Strip <explore> block from response text; return (clean_text, topics)."""
    import json
    match = _EXPLORE_RE.search(text)
    if not match:
        return text, []
    try:
        data = json.loads(match.group(1))
        topics = data.get("topics", [])
    except (ValueError, KeyError):
        topics = []
    clean = _EXPLORE_RE.sub("", text).strip()
    return clean, topics


def build_graph() -> StateGraph:
    tools = [get_latest_ai_news]
    llm = build_llm_client(temperature=0.7).bind_tools(tools)

    def call_model(state: State) -> dict:
        system_content = SYSTEM_PROMPT
        if state.get("news_context"):
            system_content += f"\n\n--- Today's AI News ---\n{state['news_context']}\n---"

        messages = [SystemMessage(content=system_content)] + list(state["messages"])
        response = llm.invoke(messages)

        clean_text, topics = _extract_topics(response.content)
        response.content = clean_text

        return {
            "messages": [response],
            "news_context": "",
            "suggested_topics": topics,
        }

    graph = StateGraph(State)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph


graph_builder = build_graph()

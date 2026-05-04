from __future__ import annotations

import os
from langchain_openai import ChatOpenAI


def build_llm_client(temperature: float = 0.7) -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat"),
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:5000"),
            "X-Title": "Knowledge Root",
        },
        temperature=temperature,
    )

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)

# Lazy-initialised globals — built on first call to run_fact_check()
_runner = None
_session_service = None

SEARCH_AGENT_PROMPT = """\
You are a fact-checking research agent. You receive a news article title and summary.

Your task:
1. Identify 3-4 key factual claims in the article that can be independently verified.
2. For each claim, use the google_search tool to search for corroborating or contradicting \
evidence from credible sources.
3. After searching all claims, summarise what you found: supporting evidence, contradicting \
evidence, or absence of sources.

Focus on verifiable facts only — not opinions, predictions, or editorial language."""

VERDICT_AGENT_PROMPT = """\
You are a fact-checking verdict agent. The previous research agent has searched Google for \
evidence on the key claims from a news article. Based on those findings:

1. Rate each claim: "verified", "disputed", or "unverifiable"
   - verified: multiple credible sources confirm it
   - disputed: credible sources contradict each other or contradict the claim
   - unverifiable: no credible sources found either way
2. Extract the most relevant source URLs the search agent found.
3. Give an overall verdict for the article.

Return ONLY valid JSON — no prose outside the JSON:
{
  "overall_verdict": "verified|mostly_verified|disputed|unverifiable",
  "claims": [
    {
      "claim": "<the specific factual claim>",
      "verdict": "verified|disputed|unverifiable",
      "evidence": "<one concise sentence summarising the evidence found>",
      "sources": ["<url1>", "<url2>"]
    }
  ],
  "summary": "<2-3 sentence overall assessment of the article's accuracy>"
}"""


def _build_fact_check_pipeline():
    global _runner, _session_service
    if _runner is not None:
        return

    from google.adk.agents import LlmAgent, SequentialAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools import google_search

    # Gemini model for native Google Search grounding.
    # Configurable via FACT_CHECK_MODEL; defaults to gemini-2.0-flash.
    model = os.getenv("FACT_CHECK_MODEL", "gemini-2.0-flash")

    search_agent = LlmAgent(
        name="search_agent",
        model=model,
        instruction=SEARCH_AGENT_PROMPT,
        tools=[google_search],
    )
    verdict_agent = LlmAgent(
        name="verdict_agent",
        model=model,
        instruction=VERDICT_AGENT_PROMPT,
    )

    pipeline = SequentialAgent(
        name="fact_check_pipeline",
        sub_agents=[search_agent, verdict_agent],
    )

    _session_service = InMemorySessionService()
    _runner = Runner(
        agent=pipeline,
        app_name="knroot_factcheck",
        session_service=_session_service,
    )


def run_fact_check(article_title: str, article_summary: str, article_link: str) -> dict:
    """Run the Google Search → Verdict fact-check pipeline for a news article.

    Requires GOOGLE_API_KEY to be set. Returns a structured fact-check report
    or an error fallback dict if the pipeline is unavailable.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        logger.warning("GOOGLE_API_KEY not set — fact-check pipeline unavailable")
        return _fallback_fact_check(article_title, reason="GOOGLE_API_KEY not configured")

    try:
        _build_fact_check_pipeline()
    except Exception as exc:
        logger.error("Fact-check pipeline build failed: %s", exc)
        return _fallback_fact_check(article_title)

    user_message = (
        f"Article title: {article_title}\n"
        f"Summary: {article_summary or 'No summary available.'}\n"
        f"Source URL: {article_link}"
    )
    pipeline_session_id = str(uuid.uuid4())

    async def _run() -> str:
        from google.genai.types import Content, Part

        await _session_service.create_session(
            app_name="knroot_factcheck",
            user_id="factcheck",
            session_id=pipeline_session_id,
        )
        async for event in _runner.run_async(
            user_id="factcheck",
            session_id=pipeline_session_id,
            new_message=Content(role="user", parts=[Part(text=user_message)]),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                return event.content.parts[0].text or ""
        return ""

    try:
        loop = asyncio.new_event_loop()
        try:
            raw = loop.run_until_complete(_run())
        finally:
            loop.close()

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if not text:
            raise ValueError("Empty pipeline response")
        data = json.loads(text)
        if "claims" in data and "overall_verdict" in data:
            return data
        raise ValueError(f"Unexpected response structure: {list(data.keys())}")
    except Exception as exc:
        logger.error("Fact-check pipeline execution failed: %s", exc)
        return _fallback_fact_check(article_title)


def _fallback_fact_check(article_title: str, reason: str = "") -> dict:
    summary = f"Fact-check could not be completed for '{article_title}'."
    if reason:
        summary += f" {reason}."
    else:
        summary += " The verification service is temporarily unavailable."
    return {
        "overall_verdict": "unverifiable",
        "claims": [],
        "summary": summary,
        "error": True,
    }

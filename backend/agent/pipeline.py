from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# Sources that publish research papers/preprints, not verifiable news claims.
# The fact-check pipeline should not be invoked for these sources.
RESEARCH_SOURCES = frozenset({
    "ArXiv AI", "ArXiv ML",
    "HuggingFace Blog", "GitHub Blog",
    "bioRxiv", "PLOS Biology", "eLife",
})

FACT_CHECK_PROMPT = """\
You are a fact-checking agent with Google Search access. Verify the key claims in this article.

Article title: {title}
Summary: {summary}
URL: {link}

Steps:
1. Identify 3-4 key factual claims that can be independently verified via web search.
2. For each claim, search Google to find corroborating or contradicting evidence from credible sources.
3. Rate each claim: "verified", "disputed", or "unverifiable"
   - verified: multiple credible sources confirm it
   - disputed: credible sources contradict the claim
   - unverifiable: no credible sources found either way
4. Give an overall verdict for the article.

Focus only on verifiable facts — skip opinions, predictions, and editorial language.

Return ONLY valid JSON, no prose outside the JSON:
{{
  "overall_verdict": "verified|mostly_verified|disputed|unverifiable",
  "claims": [
    {{
      "claim": "<specific factual claim>",
      "verdict": "verified|disputed|unverifiable",
      "evidence": "<one sentence summarising the evidence found>",
      "sources": ["<url1>", "<url2>"]
    }}
  ],
  "summary": "<2-3 sentence overall assessment of the article's accuracy>"
}}"""


def run_fact_check(article_title: str, article_summary: str, article_link: str) -> dict:
    """Verify claims in a news article using Gemini with Google Search grounding.

    Requires GOOGLE_API_KEY. Returns a structured fact-check report dict or
    a graceful fallback if the API is unavailable.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return _fallback(article_title, "GOOGLE_API_KEY not configured")

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
    except Exception as exc:
        logger.error("google-genai initialisation failed: %s", exc)
        return _fallback(article_title, "google-genai package unavailable")

    model_name = os.getenv("FACT_CHECK_MODEL", "gemini-2.0-flash")
    prompt = FACT_CHECK_PROMPT.format(
        title=article_title,
        summary=article_summary or "No summary available.",
        link=article_link or "",
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if not text:
            raise ValueError("Empty response from Gemini")

        # Strip inline citation markers that grounding sometimes injects (e.g. [1], [2])
        text = _strip_citations(text)

        data = json.loads(text)
        if "claims" not in data or "overall_verdict" not in data:
            raise ValueError(f"Unexpected response keys: {list(data.keys())}")

        _merge_grounding_sources(data, response)
        return data

    except Exception as exc:
        reason = _classify_error(exc)
        logger.error("Fact-check failed for '%s' (%s): %s", article_title, reason, exc)
        return _fallback(article_title, reason)


def _classify_error(exc: Exception) -> str:
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
        return "Gemini API quota exceeded — please try again later or upgrade your Google AI plan"
    if "403" in msg or "API_KEY_INVALID" in msg or "permission" in msg.lower():
        return "GOOGLE_API_KEY is invalid or lacks Gemini API access"
    if "404" in msg or "not found" in msg.lower():
        return f"Model not found — check FACT_CHECK_MODEL env var"
    return ""


def _strip_citations(text: str) -> str:
    """Remove inline citation markers like [1] or [1, 2] that grounding may inject."""
    import re
    return re.sub(r"\[\d+(?:,\s*\d+)*\]", "", text)


def _merge_grounding_sources(data: dict, response) -> None:
    """Pull real source URLs from grounding metadata into claims that have none."""
    try:
        gm = response.candidates[0].grounding_metadata
        urls = [
            chunk.web.uri
            for chunk in (gm.grounding_chunks or [])
            if getattr(chunk, "web", None) and chunk.web.uri
        ]
        if not urls:
            return
        for i, claim in enumerate(data.get("claims", [])):
            if not claim.get("sources"):
                start = (i * 2) % len(urls)
                claim["sources"] = urls[start: start + 2] or urls[:2]
    except (AttributeError, IndexError, TypeError):
        pass


def _fallback(article_title: str, reason: str = "") -> dict:
    msg = f"Fact-check could not be completed for '{article_title}'."
    if reason:
        msg += f" {reason}."
    else:
        msg += " The verification service is temporarily unavailable."
    return {
        "overall_verdict": "unverifiable",
        "claims": [],
        "summary": msg,
        "error": True,
    }

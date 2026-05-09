from __future__ import annotations

import logging
import re

from langchain_core.tools import tool

from backend.api.news.service import get_news

logger = logging.getLogger(__name__)


@tool
def get_latest_ai_news() -> str:
    """Fetch the latest AI news, research papers, and technical announcements."""
    articles = get_news("ai")
    if not articles:
        return "No AI news available at the moment."
    lines = []
    for a in articles[:12]:
        lines.append(f"**[{a['source']}]** {a['title']}")
        if a.get("summary"):
            lines.append(f"> {a['summary']}")
        if a.get("link"):
            lines.append(f"  {a['link']}")
        lines.append("")
    return "\n".join(lines)


@tool
def fetch_url(url: str) -> str:
    """Fetch and return the main text content of a publicly accessible URL.

    Call this whenever the user provides a URL and asks to explain, summarise,
    or discuss its content. Returns up to 4000 characters of extracted page
    text. Returns a descriptive error string if the page is unreachable,
    paywalled, or JS-rendered with insufficient static content — use that
    information to explain the limitation to the user rather than guessing.
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        response = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; KnowledgeRoot/1.0; "
                    "educational content reader)"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove boilerplate
        for tag in soup(["script", "style", "nav", "footer",
                         "header", "aside", "form", "iframe"]):
            tag.decompose()

        # Prefer semantic content containers
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id=re.compile(r"content|article|main|body", re.I))
            or soup.find(class_=re.compile(r"content|article|post|entry|body", re.I))
            or soup.body
        )

        if not main:
            return "Could not extract any content from this page."

        text = main.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)  # collapse blank lines

        if len(text) < 100:
            return (
                f"Very little text was extracted from {url} "
                "(fewer than 100 characters). The page may require "
                "JavaScript to render, or a login to access."
            )

        logger.info("fetch_url: extracted %d chars from %s", len(text), url)
        return text[:4000]

    except requests.exceptions.Timeout:
        return f"Request timed out fetching {url} — the server took too long to respond."
    except requests.exceptions.HTTPError as exc:
        return f"HTTP {exc.response.status_code} error fetching {url}."
    except Exception as exc:
        logger.warning("fetch_url failed for %s: %s", url, exc)
        return f"Could not fetch {url}: {exc}"

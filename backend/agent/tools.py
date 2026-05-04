from langchain_core.tools import tool

from backend.api.news.service import get_news


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

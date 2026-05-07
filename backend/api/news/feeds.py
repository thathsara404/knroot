from __future__ import annotations

NEWS_FEEDS: dict[str, list[tuple[str, str]]] = {
    "ai": [
        ("TechCrunch AI",    "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("VentureBeat AI",   "https://venturebeat.com/ai/feed/"),
        ("The Verge AI",     "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
        ("ArXiv AI",         "https://arxiv.org/rss/cs.AI"),
        ("HuggingFace Blog", "https://huggingface.co/blog/feed.xml"),
        ("Reuters Tech",     "https://feeds.reuters.com/reuters/technologyNews"),
        ("BBC Technology",   "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ],
    "tech": [
        ("TechCrunch",       "https://techcrunch.com/feed/"),
        ("Reuters Tech",     "https://feeds.reuters.com/reuters/technologyNews"),
        ("BBC Technology",   "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("The Verge",        "https://www.theverge.com/rss/index.xml"),
        ("Wired",            "https://www.wired.com/feed/rss"),
        ("Ars Technica",     "https://feeds.arstechnica.com/arstechnica/index"),
        ("CNET",             "https://www.cnet.com/rss/news/"),
    ],
    "programming": [
        ("Hacker News",      "https://hnrss.org/frontpage"),
        ("Dev.to",           "https://dev.to/feed"),
        ("Stack Overflow",   "https://stackoverflow.blog/feed/"),
        ("InfoQ",            "https://feed.infoq.com/"),
        ("GitHub Blog",      "https://github.blog/feed/"),
    ],
    "political": [
        ("Reuters World",    "https://feeds.reuters.com/Reuters/worldNews"),
        ("BBC World",        "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("CNN",              "http://rss.cnn.com/rss/edition.rss"),
        ("AP News",          "https://rsshub.app/apnews/topics/ap-top-news"),
        ("Al Jazeera",       "https://www.aljazeera.com/xml/rss/all.xml"),
        ("NPR News",         "https://feeds.npr.org/1001/rss.xml"),
    ],
}

# All feeds combined — used for topic-specific news search
ALL_FEEDS: list[tuple[str, str]] = []
_seen_urls: set[str] = set()
for _feeds in NEWS_FEEDS.values():
    for _name, _url in _feeds:
        if _url not in _seen_urls:
            ALL_FEEDS.append((_name, _url))
            _seen_urls.add(_url)

ITEMS_PER_FEED = 5

NEWS_FEEDS: dict[str, list[tuple[str, str]]] = {
    "ai": [
        ("ArXiv AI",         "https://arxiv.org/rss/cs.AI"),
        ("ArXiv ML",         "https://arxiv.org/rss/cs.LG"),
        ("HuggingFace Blog", "https://huggingface.co/blog/feed.xml"),
        ("VentureBeat AI",   "https://venturebeat.com/ai/feed/"),
        ("The Verge AI",     "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ],
    "programming": [
        ("Hacker News",      "https://hnrss.org/frontpage"),
        ("Dev.to",           "https://dev.to/feed"),
        ("Stack Overflow",   "https://stackoverflow.blog/feed/"),
        ("InfoQ",            "https://feed.infoq.com/"),
        ("GitHub Blog",      "https://github.blog/feed/"),
    ],
    "political": [
        ("Reuters",          "https://feeds.reuters.com/Reuters/worldNews"),
        ("BBC World",        "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("AP News",          "https://rsshub.app/apnews/topics/ap-top-news"),
        ("Al Jazeera",       "https://www.aljazeera.com/xml/rss/all.xml"),
        ("NPR News",         "https://feeds.npr.org/1001/rss.xml"),
    ],
}

ITEMS_PER_FEED = 3

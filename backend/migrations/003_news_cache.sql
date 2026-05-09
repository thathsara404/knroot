CREATE TABLE IF NOT EXISTS news_cache (
    cache_key  VARCHAR(50) PRIMARY KEY,
    articles   JSONB       NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

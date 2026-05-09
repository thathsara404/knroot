-- Migration 008 — Add source_category to chat_sessions
-- Stores the news-tab category a news_discussion session originated from
-- (e.g. 'health', 'economy', 'ai'). Used as a guaranteed fallback when
-- topic-news semantic search returns no results — no inference needed.
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS source_category VARCHAR(20);

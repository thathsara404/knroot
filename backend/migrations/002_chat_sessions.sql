CREATE TABLE IF NOT EXISTS chat_sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
    thread_id         VARCHAR(255) UNIQUE NOT NULL DEFAULT gen_random_uuid()::text,
    title             VARCHAR(255),
    session_type      VARCHAR(20) NOT NULL DEFAULT 'regular',
    parent_session_id UUID REFERENCES chat_sessions(id),
    root_session_id   UUID REFERENCES chat_sessions(id),
    depth_level       INTEGER NOT NULL DEFAULT 0,
    topic             VARCHAR(500),
    news_article_id   VARCHAR(20),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    last_message_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_last ON chat_sessions(user_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_parent    ON chat_sessions(parent_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_root      ON chat_sessions(root_session_id);

CREATE TABLE IF NOT EXISTS session_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_messages_session_created
    ON session_messages (session_id, created_at ASC);

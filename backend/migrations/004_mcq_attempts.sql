CREATE TABLE IF NOT EXISTS mcq_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    section_id      VARCHAR(10),
    questions       JSONB NOT NULL,
    answers         JSONB,
    score           SMALLINT,
    scope_sessions  JSONB,
    relearn_cache   JSONB DEFAULT '{}',
    attempted_at    TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mcq_session ON mcq_attempts(session_id);

ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS imported_from_share_id UUID REFERENCES shares(id) ON DELETE SET NULL;

ALTER TABLE shares
    ADD COLUMN IF NOT EXISTS source_share_id UUID REFERENCES shares(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_imported ON chat_sessions(imported_from_share_id)
    WHERE imported_from_share_id IS NOT NULL;

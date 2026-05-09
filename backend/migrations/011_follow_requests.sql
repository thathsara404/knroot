-- Migration 011: follow request approval flow
-- Adds status column to user_follows so follows require approval.
-- Existing rows receive DEFAULT 'accepted' (backward-compatible — they were direct follows).

ALTER TABLE user_follows
    ADD COLUMN IF NOT EXISTS status       VARCHAR(10)  NOT NULL DEFAULT 'accepted',
    ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ           DEFAULT NOW();

-- Fast lookup: all pending requests directed at a given user
CREATE INDEX IF NOT EXISTS idx_follows_pending
    ON user_follows(followed_id, status)
    WHERE status = 'pending';

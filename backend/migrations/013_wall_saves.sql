-- Migration 013: wall_saves — lightweight bookmark linking a user to a public share.
-- Workflow: user clicks "Save to my wall" on public wall → share appears in their
-- private wall; from there they can Import the session tree into their Root section.

CREATE TABLE IF NOT EXISTS wall_saves (
    user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    share_id UUID NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, share_id)
);

CREATE INDEX IF NOT EXISTS idx_wall_saves_user ON wall_saves(user_id, saved_at DESC);

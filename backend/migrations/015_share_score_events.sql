-- Share-triggered score events: reshare bonus & toxic-post penalty.
-- Points are snapshotted at the moment of sharing so future vote changes
-- do not retroactively alter previously awarded/deducted points.
CREATE TABLE IF NOT EXISTS share_score_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    share_id            UUID NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    source_share_id     UUID          REFERENCES shares(id) ON DELETE SET NULL,
    points              INT  NOT NULL,
    reason              VARCHAR(40) NOT NULL,   -- 'reshare_bonus' | 'toxic_penalty'
    snapshot_upvotes    INT,
    snapshot_downvotes  INT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Prevents awarding the reshare bonus more than once per (user, source post).
-- Toxic-penalty rows are intentionally not covered so each reshare can incur
-- the penalty independently.
CREATE UNIQUE INDEX IF NOT EXISTS uq_reshare_bonus_once
    ON share_score_events (user_id, source_share_id)
    WHERE reason = 'reshare_bonus';

CREATE INDEX IF NOT EXISTS idx_score_events_user
    ON share_score_events (user_id);

CREATE INDEX IF NOT EXISTS idx_score_events_share
    ON share_score_events (share_id);

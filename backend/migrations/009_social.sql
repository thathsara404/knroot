CREATE TABLE IF NOT EXISTS shares (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id    UUID        NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    visibility    VARCHAR(20) NOT NULL DEFAULT 'public',   -- 'public' | 'friends'
    description   TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_shares_public   ON shares(visibility, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shares_user     ON shares(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS share_votes (
    id         UUID     PRIMARY KEY DEFAULT gen_random_uuid(),
    share_id   UUID     NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    user_id    UUID     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote       SMALLINT NOT NULL CHECK (vote IN (-1, 1)),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(share_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_votes_share ON share_votes(share_id);

CREATE TABLE IF NOT EXISTS share_comments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_id   UUID NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comments_share ON share_comments(share_id, created_at ASC);

CREATE TABLE IF NOT EXISTS user_follows (
    follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followed_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY(follower_id, followed_id)
);
CREATE INDEX IF NOT EXISTS idx_follows_follower ON user_follows(follower_id);
CREATE INDEX IF NOT EXISTS idx_follows_followed ON user_follows(followed_id);

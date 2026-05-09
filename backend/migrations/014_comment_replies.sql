ALTER TABLE share_comments
    ADD COLUMN IF NOT EXISTS parent_comment_id UUID REFERENCES share_comments(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_comments_parent
    ON share_comments(parent_comment_id)
    WHERE parent_comment_id IS NOT NULL;

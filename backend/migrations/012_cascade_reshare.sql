-- Migration 012: cascade-delete derivative re-shares when the original share is deleted.
-- Changes source_share_id FK from ON DELETE SET NULL to ON DELETE CASCADE.
-- When User A deletes their share, any re-shares by other users that directly reference
-- that share (source_share_id = A's share id) are also deleted, removing them from all walls.
-- chat_sessions.imported_from_share_id remains ON DELETE SET NULL (imports are independent copies).

ALTER TABLE shares
    DROP CONSTRAINT IF EXISTS shares_source_share_id_fkey;

ALTER TABLE shares
    ADD CONSTRAINT shares_source_share_id_fkey
    FOREIGN KEY (source_share_id) REFERENCES shares(id) ON DELETE CASCADE;

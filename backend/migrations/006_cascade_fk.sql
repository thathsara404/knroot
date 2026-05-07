-- Add ON DELETE CASCADE to chat_sessions self-referential FKs so that
-- deleting any session automatically removes all descendants at any depth.

ALTER TABLE chat_sessions
  DROP CONSTRAINT IF EXISTS chat_sessions_parent_session_id_fkey;

ALTER TABLE chat_sessions
  ADD CONSTRAINT chat_sessions_parent_session_id_fkey
    FOREIGN KEY (parent_session_id) REFERENCES chat_sessions(id)
    ON DELETE CASCADE;

-- root_session_id points to the tree root; if root is deleted the cascade
-- via parent_session_id already cleans up children, but we still need to
-- handle the FK itself — SET NULL so rows deleted by cascade don't fail.
ALTER TABLE chat_sessions
  DROP CONSTRAINT IF EXISTS chat_sessions_root_session_id_fkey;

ALTER TABLE chat_sessions
  ADD CONSTRAINT chat_sessions_root_session_id_fkey
    FOREIGN KEY (root_session_id) REFERENCES chat_sessions(id)
    ON DELETE SET NULL;

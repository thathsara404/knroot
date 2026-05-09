-- Add linked_attempt_id to chat_sessions so quiz-type sessions can point
-- directly to their mcq_attempts row for sidebar navigation.
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS linked_attempt_id UUID;

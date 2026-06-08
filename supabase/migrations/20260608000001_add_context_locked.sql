-- context_locked = true means the 4 context fields (situation, approach, technical_work,
-- lessons_learned) were hand-curated and must not be overwritten by rebuild-experiences.
ALTER TABLE experiences
  ADD COLUMN IF NOT EXISTS context_locked BOOLEAN NOT NULL DEFAULT false;

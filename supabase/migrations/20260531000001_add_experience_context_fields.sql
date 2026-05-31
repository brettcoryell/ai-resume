-- Add structured AI context fields to experiences table.
-- Populated by rebuild-experiences edge function from blob content.
-- Displayed in the "View Context" expandable panel on each experience card.

ALTER TABLE experiences
  ADD COLUMN IF NOT EXISTS situation      TEXT,
  ADD COLUMN IF NOT EXISTS approach       TEXT,
  ADD COLUMN IF NOT EXISTS technical_work TEXT,
  ADD COLUMN IF NOT EXISTS lessons_learned TEXT;

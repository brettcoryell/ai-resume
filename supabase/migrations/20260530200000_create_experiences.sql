-- Create experiences table for the public-facing career timeline.
-- Populated automatically by the rebuild-experiences edge function,
-- which is triggered by rebuild-blob after every blob update.
-- Do not edit rows manually — they will be overwritten on next blob rebuild.

CREATE TABLE IF NOT EXISTS experiences (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name    TEXT NOT NULL,
  title           TEXT NOT NULL,
  title_progression TEXT,
  start_date      DATE,
  end_date        DATE,
  is_current      BOOLEAN NOT NULL DEFAULT false,
  bullet_points   TEXT[] NOT NULL DEFAULT '{}',
  display_order   INTEGER NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- RLS: public can read, only service role can write
ALTER TABLE experiences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_experiences"
  ON experiences FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "service_role_all_experiences"
  ON experiences FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

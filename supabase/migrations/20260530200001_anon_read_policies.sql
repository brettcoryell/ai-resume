-- Allow anonymous (public) users to read the public-facing career data.
-- These tables had RLS enabled with no policies, blocking the frontend entirely.
-- The chat edge function uses service_role and is unaffected by these policies.

CREATE POLICY IF NOT EXISTS "anon_read_candidate_profile"
  ON candidate_profile FOR SELECT
  TO anon
  USING (true);

CREATE POLICY IF NOT EXISTS "anon_read_skills"
  ON skills FOR SELECT
  TO anon
  USING (true);

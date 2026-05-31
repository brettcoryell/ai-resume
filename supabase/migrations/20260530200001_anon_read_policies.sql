-- Allow anonymous (public) users to read the public-facing career data.
-- Two layers required: PostgreSQL GRANT (table-level) AND RLS policy (row-level).
-- The chat edge function uses service_role and is unaffected by these policies.

-- Layer 1: PostgreSQL grants
GRANT SELECT ON candidate_profile TO anon;
GRANT SELECT ON skills TO anon;
GRANT SELECT ON experiences TO anon;

-- Layer 2: RLS policies
CREATE POLICY IF NOT EXISTS "anon_read_candidate_profile"
  ON candidate_profile FOR SELECT
  TO anon
  USING (true);

CREATE POLICY IF NOT EXISTS "anon_read_skills"
  ON skills FOR SELECT
  TO anon
  USING (true);

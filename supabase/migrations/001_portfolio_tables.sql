-- ============================================================
-- AI Resume Portfolio Tables
-- Sits alongside the existing `thoughts` and `intent` tables
-- in the exploration Supabase project. Do NOT modify those tables.
--
-- ob_thought_id columns enable traceability back to OB thoughts
-- captured via the Interview Agent. The sync pipeline
-- (scripts/sync_career_from_ob.py) populates these via upsert.
-- ============================================================

-- ──────────────────────────────────────────────
-- 1. Candidate profile (single row — YOUR site)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candidate_profile (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Display
  name                  TEXT NOT NULL,
  email                 TEXT,
  title                 TEXT,
  target_titles         TEXT[],
  target_company_stages TEXT[],
  elevator_pitch        TEXT,
  career_narrative      TEXT,
  looking_for           TEXT,
  not_looking_for       TEXT,
  -- Logistics
  salary_min            INTEGER,
  salary_max            INTEGER,
  availability_status   TEXT,
  availability_date     DATE,
  location              TEXT,
  remote_preference     TEXT,
  -- Social
  github_url            TEXT,
  linkedin_url          TEXT,
  -- OB traceability
  ob_thought_id         UUID,   -- source thought for profile narrative
  -- Timestamps
  created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- 2. Work experiences
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS experiences (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id          UUID REFERENCES candidate_profile(id) ON DELETE CASCADE,
  company_name          TEXT NOT NULL,
  title                 TEXT NOT NULL,
  title_progression     TEXT,
  start_date            DATE,
  end_date              DATE,
  is_current            BOOLEAN DEFAULT FALSE,
  -- Public (shown on site)
  bullet_points         TEXT[],
  -- Private (AI context only — never sent to browser)
  why_joined            TEXT,
  why_left              TEXT,
  actual_contributions  TEXT,
  proudest_achievement  TEXT,
  would_do_differently  TEXT,
  challenges_faced      TEXT,
  lessons_learned       TEXT,
  manager_would_say     TEXT,
  reports_would_say     TEXT,
  quantified_impact     JSONB,
  -- OB traceability
  ob_thought_id         UUID,   -- source thought for this role's deep-dive
  -- Ordering
  display_order         INTEGER,
  created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- 3. Skills with honest self-assessment
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS skills (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id      UUID REFERENCES candidate_profile(id) ON DELETE CASCADE,
  skill_name        TEXT NOT NULL,
  category          TEXT CHECK (category IN ('strong', 'moderate', 'gap')),
  self_rating       INTEGER CHECK (self_rating BETWEEN 1 AND 5),
  evidence          TEXT,
  honest_notes      TEXT,
  years_experience  DECIMAL,
  last_used         DATE,
  -- OB traceability
  ob_thought_id     UUID,
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- 4. Explicit gaps and weaknesses
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gaps_weaknesses (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id          UUID REFERENCES candidate_profile(id) ON DELETE CASCADE,
  gap_type              TEXT CHECK (gap_type IN ('skill', 'experience', 'environment', 'role_type')),
  description           TEXT NOT NULL,
  why_its_a_gap         TEXT,
  interest_in_learning  BOOLEAN DEFAULT FALSE,
  -- OB traceability
  ob_thought_id         UUID,
  created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- 5. Pre-written FAQ responses
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS faq_responses (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id        UUID REFERENCES candidate_profile(id) ON DELETE CASCADE,
  question            TEXT NOT NULL,
  answer              TEXT NOT NULL,
  is_common_question  BOOLEAN DEFAULT FALSE,
  -- OB traceability
  ob_thought_id       UUID,
  created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- 6. AI behavior instructions
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_instructions (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id     UUID REFERENCES candidate_profile(id) ON DELETE CASCADE,
  instruction_type TEXT CHECK (instruction_type IN ('honesty', 'tone', 'boundaries', 'other')),
  instruction      TEXT NOT NULL,
  priority         INTEGER DEFAULT 0,
  created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- 7. Chat history (session context for AI)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_history (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,
  role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content    TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id, created_at);

-- ──────────────────────────────────────────────
-- Row-Level Security
-- ──────────────────────────────────────────────

ALTER TABLE candidate_profile  ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiences        ENABLE ROW LEVEL SECURITY;
ALTER TABLE skills             ENABLE ROW LEVEL SECURITY;
ALTER TABLE gaps_weaknesses    ENABLE ROW LEVEL SECURITY;
ALTER TABLE faq_responses      ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_instructions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history       ENABLE ROW LEVEL SECURITY;

-- Public can read display fields (edge functions use service role key, bypass RLS)
CREATE POLICY "Public read candidate_profile"
  ON candidate_profile FOR SELECT USING (true);

CREATE POLICY "Public read experiences"
  ON experiences FOR SELECT USING (true);

CREATE POLICY "Public read skills"
  ON skills FOR SELECT USING (true);

-- gaps_weaknesses, faq_responses, ai_instructions: admin only for write;
-- edge functions read via service role key (bypasses RLS)
CREATE POLICY "Admin full access candidate_profile"
  ON candidate_profile FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Admin full access experiences"
  ON experiences FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Admin full access skills"
  ON skills FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Admin full access gaps_weaknesses"
  ON gaps_weaknesses FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Admin full access faq_responses"
  ON faq_responses FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Admin full access ai_instructions"
  ON ai_instructions FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Admin full access chat_history"
  ON chat_history FOR ALL
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

-- Auto-update updated_at on candidate_profile
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_candidate_profile_updated_at
  BEFORE UPDATE ON candidate_profile
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

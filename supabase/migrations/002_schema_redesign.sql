-- ============================================================
-- Schema Redesign v2 — ai-resume
-- Replaces flat `experiences` table with a normalized structure:
--   employers → roles → accomplishments
--   people + people_engagements (many-to-many people ↔ employers/roles)
--   stories + story_roles (many-to-many stories ↔ roles, with link_type)
--
-- Also adds ob_thought_id to ai_instructions (was missing, causing warnings)
-- and display_order to faq_responses.
-- ============================================================

-- ── Wipe all existing career data (rebuild from OB via --extract) ─────────────
TRUNCATE TABLE experiences     CASCADE;
TRUNCATE TABLE skills          CASCADE;
TRUNCATE TABLE gaps_weaknesses CASCADE;
TRUNCATE TABLE faq_responses   CASCADE;
TRUNCATE TABLE ai_instructions CASCADE;

-- ── Drop the flat experiences table ──────────────────────────────────────────
DROP TABLE IF EXISTS experiences CASCADE;

-- ── Patch existing tables ─────────────────────────────────────────────────────
ALTER TABLE ai_instructions ADD COLUMN IF NOT EXISTS ob_thought_id UUID;
ALTER TABLE faq_responses   ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 99;

-- ── employers ─────────────────────────────────────────────────────────────────
-- One row per company per stint (stint_index handles "worked there twice")
CREATE TABLE IF NOT EXISTS employers (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID NOT NULL REFERENCES candidate_profile(id) ON DELETE CASCADE,
  company_name  TEXT NOT NULL,
  stint_index   INTEGER NOT NULL DEFAULT 1,
  industry      TEXT,
  display_order INTEGER,
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE (candidate_id, company_name, stint_index)
);

-- ── roles ─────────────────────────────────────────────────────────────────────
-- One row per distinct title/tenure, hangs off an employer
CREATE TABLE IF NOT EXISTS roles (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employer_id          UUID NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
  ob_thought_id        UUID,
  title                TEXT NOT NULL,
  title_progression    TEXT,
  start_date           DATE,
  end_date             DATE,
  is_current           BOOLEAN DEFAULT FALSE,
  why_joined           TEXT,
  why_left             TEXT,
  actual_contributions TEXT,
  proudest_achievement TEXT,
  manager_would_say    TEXT,
  reports_would_say    TEXT,
  display_order        INTEGER,
  created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE (employer_id, title)
);

-- ── accomplishments ───────────────────────────────────────────────────────────
-- Discrete resume bullet points; replaced wholesale on each --extract
CREATE TABLE IF NOT EXISTS accomplishments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id       UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  ob_thought_id UUID,
  content       TEXT NOT NULL,
  has_metric    BOOLEAN DEFAULT FALSE,
  display_order INTEGER,
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── people ────────────────────────────────────────────────────────────────────
-- One row per named person; engagements capture per-employer context
CREATE TABLE IF NOT EXISTS people (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id  UUID NOT NULL REFERENCES candidate_profile(id) ON DELETE CASCADE,
  ob_thought_id UUID,
  name          TEXT NOT NULL,
  general_note  TEXT,
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE (candidate_id, name)
);

-- ── people_engagements ────────────────────────────────────────────────────────
-- One row per person × employer/role context
CREATE TABLE IF NOT EXISTS people_engagements (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id     UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  employer_id   UUID REFERENCES employers(id) ON DELETE SET NULL,
  role_id       UUID REFERENCES roles(id) ON DELETE SET NULL,
  ob_thought_id UUID,
  relationship  TEXT CHECK (relationship IN ('manager', 'report', 'peer', 'mentor', 'client', 'other')),
  note          TEXT,
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── stories ───────────────────────────────────────────────────────────────────
-- STAR-format narratives; cross-career linkages via story_roles
CREATE TABLE IF NOT EXISTS stories (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id        UUID NOT NULL REFERENCES candidate_profile(id) ON DELETE CASCADE,
  ob_thought_id       UUID,
  title               TEXT NOT NULL,
  situation           TEXT,
  task                TEXT,
  action              TEXT,
  result              TEXT,
  tags                TEXT[],
  primary_employer_id UUID REFERENCES employers(id) ON DELETE SET NULL,
  primary_role_id     UUID REFERENCES roles(id) ON DELETE SET NULL,
  created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE (candidate_id, title)
);

-- ── story_roles ───────────────────────────────────────────────────────────────
-- Many-to-many: story ↔ roles, with link_type describing the relationship
CREATE TABLE IF NOT EXISTS story_roles (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  story_id    UUID NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
  role_id     UUID REFERENCES roles(id) ON DELETE CASCADE,
  employer_id UUID REFERENCES employers(id) ON DELETE CASCADE,
  link_type   TEXT CHECK (link_type IN ('origin', 'application', 'taught', 'reference')),
  created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── Row-Level Security ────────────────────────────────────────────────────────

ALTER TABLE employers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles              ENABLE ROW LEVEL SECURITY;
ALTER TABLE accomplishments    ENABLE ROW LEVEL SECURITY;
ALTER TABLE people             ENABLE ROW LEVEL SECURITY;
ALTER TABLE people_engagements ENABLE ROW LEVEL SECURITY;
ALTER TABLE stories            ENABLE ROW LEVEL SECURITY;
ALTER TABLE story_roles        ENABLE ROW LEVEL SECURITY;

-- Public read for display tables
CREATE POLICY "Public read employers"       ON employers       FOR SELECT USING (true);
CREATE POLICY "Public read roles"           ON roles           FOR SELECT USING (true);
CREATE POLICY "Public read accomplishments" ON accomplishments FOR SELECT USING (true);

-- Admin full access (edge functions use service role key, bypass RLS)
CREATE POLICY "Admin full access employers"
  ON employers FOR ALL USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Admin full access roles"
  ON roles FOR ALL USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Admin full access accomplishments"
  ON accomplishments FOR ALL USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Admin full access people"
  ON people FOR ALL USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Admin full access people_engagements"
  ON people_engagements FOR ALL USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Admin full access stories"
  ON stories FOR ALL USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Admin full access story_roles"
  ON story_roles FOR ALL USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');

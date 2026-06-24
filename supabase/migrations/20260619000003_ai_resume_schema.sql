-- Move all ai-resume tables from public to ai_resume schema.
-- The trigger on public.thoughts (notify_blob_rebuild) stays in public —
-- it only calls an HTTP endpoint and doesn't touch ai-resume tables directly.
-- The update_updated_at_column() helper stays in public; triggers follow tables.

CREATE SCHEMA IF NOT EXISTS ai_resume;
GRANT USAGE ON SCHEMA ai_resume TO anon, authenticated, service_role;

-- ── Move tables ───────────────────────────────────────────────────────────────

ALTER TABLE public.candidate_profile    SET SCHEMA ai_resume;
ALTER TABLE public.skills               SET SCHEMA ai_resume;
ALTER TABLE public.gaps_weaknesses      SET SCHEMA ai_resume;
ALTER TABLE public.ai_instructions      SET SCHEMA ai_resume;
ALTER TABLE public.chat_history         SET SCHEMA ai_resume;
ALTER TABLE public.employers            SET SCHEMA ai_resume;
ALTER TABLE public.roles                SET SCHEMA ai_resume;
ALTER TABLE public.accomplishments      SET SCHEMA ai_resume;
ALTER TABLE public.people               SET SCHEMA ai_resume;
ALTER TABLE public.people_engagements   SET SCHEMA ai_resume;
ALTER TABLE public.stories              SET SCHEMA ai_resume;
ALTER TABLE public.story_roles          SET SCHEMA ai_resume;
ALTER TABLE public.career_blob          SET SCHEMA ai_resume;
ALTER TABLE public.experiences          SET SCHEMA ai_resume;

-- ── Re-apply grants ───────────────────────────────────────────────────────────

-- Public read access (matches anon_read policies from 20260530200001)
GRANT SELECT ON ai_resume.candidate_profile  TO anon;
GRANT SELECT ON ai_resume.skills             TO anon;
GRANT SELECT ON ai_resume.experiences        TO anon;

-- Service role full access
GRANT ALL ON ai_resume.candidate_profile    TO service_role;
GRANT ALL ON ai_resume.experiences          TO service_role;
GRANT ALL ON ai_resume.skills               TO service_role;
GRANT ALL ON ai_resume.gaps_weaknesses      TO service_role;
GRANT ALL ON ai_resume.ai_instructions      TO service_role;
GRANT ALL ON ai_resume.chat_history         TO service_role;
GRANT ALL ON ai_resume.employers            TO service_role;
GRANT ALL ON ai_resume.roles                TO service_role;
GRANT ALL ON ai_resume.accomplishments      TO service_role;
GRANT ALL ON ai_resume.people               TO service_role;
GRANT ALL ON ai_resume.people_engagements   TO service_role;
GRANT ALL ON ai_resume.stories              TO service_role;
GRANT ALL ON ai_resume.story_roles          TO service_role;
GRANT ALL ON ai_resume.career_blob          TO service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ai_resume TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ai_resume TO anon;

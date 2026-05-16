# CLAUDE.md — Session Bootstrap + Project Context

You are **Coda** (Claude Code, he/him). The Claude Chat assistant is **Ariel** (she/her).

---

## Session Start — Required

At the start of every session, before responding to Brett:

1. Call `list_context` with `permanent=true` to load all architectural context:
   ```
   list_context(permanent=true)
   ```
2. Call `list_context` with `since` set to 7 days ago to load recent session notes:
   ```
   list_context(since="<ISO date 7 days ago>", limit=15)
   ```
3. Read all returned entries and proceed informed. Do not ask Brett for context you
   can retrieve from the table.

## Session End — Required

Call `capture_context` summarizing what was done, decisions made, and anything pending.
- `source`: `"claude-code"`
- `session_ref`: descriptive string (e.g. `"coda-2026-05-08-topic"`)
- `topics`: kebab-case tags + one priority bucket tag: `"now"`, `"soon"`, or `"later"`
- Omit `expires_at` for permanent entries; use ISO timestamp for time-limited ones.

---

# Project Context for Brett's AI Resume

This file is read automatically by Claude Code at the start of every session.
It contains the full architectural context needed to work on this project intelligently.
Do not delete or substantially shorten this file — it is the project's institutional memory.

---

## What This Project Is

`ai-resume` is Brett Coryell's AI-powered career website — a professional portfolio that
lets hiring managers and recruiters interact with an AI that knows Brett's full career
history, skills, gaps, and preferences. Instead of a static resume, visitors can ask
questions and get direct, honest answers drawn from Brett's actual experience.

**Live site:** https://ai-resume-mu-seven.vercel.app
**Admin panel:** https://ai-resume-mu-seven.vercel.app/admin/login
**GitHub:** private repo under Brett's account

**Inspiration and original source:** Nate Jones's `sample-ai-resume` repo
(https://github.com/komodo170845/sample-ai-resume), a Lovable-generated scaffold
with fictional "Marcus Chen" as the candidate. Brett's project keeps the visual
design entirely intact and replaces all data with real content from his OpenBrain
knowledge system.

---

## Repo Location and Structure

```
~/Code/AI/ai-resume/          ← this repo (one of three under ~/Code/AI/)
  src/
    components/               ← React UI components (Tailwind + shadcn/ui)
    hooks/
      useCandidateData.ts     ← React Query hooks: useCandidateProfile, useExperiences, useSkills
    lib/
      supabase.ts             ← Supabase client + EDGE_FN_URL export
    pages/
      Index.tsx               ← main public page
      admin/
        Login.tsx             ← email/password auth form
        Dashboard.tsx         ← admin sidebar navigation
        ProfileForm.tsx       ← edit candidate_profile
        ExperienceForm.tsx    ← list/add/edit/delete experiences
  supabase/
    functions/
      chat/index.ts           ← AI chat edge function (Claude)
      analyze-jd/index.ts     ← JD fit analysis edge function (Claude)
    migrations/
      001_portfolio_tables.sql ← all 7 career tables
  scripts/
    sync_career_from_ob.py    ← OB→career tables sync pipeline (THE KEY SCRIPT)
  .env.local                  ← VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY (gitignored)
  vercel.json                 ← SPA rewrite rule (all routes → index.html)
  CLAUDE.md                   ← this file
```

The other two projects under `~/Code/AI/`:
- `open_brain/` — OpenBrain knowledge system (ingestion, synthesis, temporal agents)
- `wiki/` — Obsidian vault output

---

## Supabase Project

All three projects (open_brain, wiki, ai-resume) share **one Supabase project**:
- Project name: `open-brain`
- Project ref: `zybttfjewunokevxwtqc`
- URL: `https://zybttfjewunokevxwtqc.supabase.co`

The career tables sit alongside the existing `thoughts` and `intent` tables.
**Never touch `thoughts` or `intent` from this repo.**

### Career Tables (created in migration 001)

| Table | Purpose |
|---|---|
| `candidate_profile` | Single row: name, title, email, LinkedIn, elevator pitch, narrative, looking_for, not_looking_for, target_titles[], target_company_stages[] |
| `experiences` | One row per role: company, title, dates, bullet_points[], private AI context fields |
| `skills` | skill_name, category (strong/moderate/gap), honest_notes |
| `gaps_weaknesses` | Acknowledged weaknesses: description, why_its_a_gap, gap_type |
| `faq_responses` | Pre-written Q&As (not yet populated) |
| `ai_instructions` | Behavior instructions for the AI chat |
| `chat_history` | Session-scoped chat logs |

All career tables (except `chat_history`) have an `ob_thought_id UUID` column for
traceability back to the OB thought that sourced each row.

### Row-Level Security
- `candidate_profile`, `experiences`, `skills`: public SELECT
- All other tables: authenticated (admin) only for write; edge functions bypass RLS
  via service role key

### Edge Functions (deployed)
- `chat` — takes `{message, sessionId}`, fetches full candidate context via service
  role key (including private fields), calls Claude, saves to chat_history, returns reply
- `analyze-jd` — takes `{jobDescription}`, returns structured fit assessment JSON:
  `{verdict, headline, opening, gaps[], transfers, recommendation}`

Both functions use `claude-sonnet-4-6` (updated 2026-05-07 from deprecated claude-sonnet-4-20250514).

### Auth
- Admin user: brettcoryell@yahoo.com (password set in Supabase Auth dashboard)
- Auth method: email + password via `supabase.auth.signInWithPassword()`

---

## Environment Variables

### For the browser app (`.env.local`, gitignored via `*.local`):
```
VITE_SUPABASE_URL=https://zybttfjewunokevxwtqc.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_FxeFC6fREKhFpb2J06iHvg_4U1AzksA
```

### For the sync script (loaded from `~/Code/AI/open_brain/.env`):
```
SUPABASE_URL=https://zybttfjewunokevxwtqc.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<in open_brain/.env>
ANTHROPIC_API_KEY=<in open_brain/.env>
```

### Supabase secrets (edge functions):
```
ANTHROPIC_API_KEY=<set via: supabase secrets set ANTHROPIC_API_KEY=...>
```

---

## The OB → Career Pipeline

The central innovation: Brett's career data lives in OpenBrain (OB) as biographical
thoughts captured via Interview Agent sessions. The sync script extracts that data
and populates the career tables.

### `scripts/sync_career_from_ob.py`

**Mode 1 — Extract (one-time bootstrap or refresh):**
```bash
python3 scripts/sync_career_from_ob.py --extract
```
Fetches all biographical OB thoughts mentioning Brett / tagged with career topics,
sends them to Claude (claude-sonnet-4-20250514) for structured extraction, then
upserts results to all career tables. Idempotent — safe to re-run.

**Mode 2 — Structured sync (ongoing):**
```bash
python3 scripts/sync_career_from_ob.py
```
Reads OB thoughts with `metadata.type` starting with `career-` and syncs them to
the appropriate table. For future use once Interview Agent sessions write typed thoughts.

**Other flags:**
```bash
python3 scripts/sync_career_from_ob.py --dry-run --extract  # preview only
python3 scripts/sync_career_from_ob.py --stats              # show table counts
python3 scripts/sync_career_from_ob.py --type skill         # sync one type only
```

### Current data state (as of 2026-05-05)
- candidate_profile: 1 row (name, title, email, LinkedIn, location, elevator pitch,
  career narrative, looking_for, not_looking_for, target_titles, target_company_stages)
- experiences: 8 roles (Sprint, Purdue, Emory, NIU, Neighborly, Rennes/ACUTE,
  Elementum, plus one duplicate variant from re-run)
- skills: 49 entries (24 strong, 23 moderate, 2 gap)
- gaps_weaknesses: 9 entries
- ai_instructions: 9 entries

**Note on data quality:** The AI's JD analysis sometimes claims Brett lacks experience
he actually has. This is an OB data gap — the specific experiences aren't in OB thoughts
yet. Fix: capture the missing context as OB thoughts via Interview Agent or
`capture_thought` MCP tool, then re-run `--extract`.

---

## Deployment

- **Hosting:** Vercel (hobby account), connected via CLI
- **Deploy command:** `vercel --prod` from `~/Code/AI/ai-resume/`
- **SPA routing:** `vercel.json` rewrites all paths to `index.html` — required for
  React Router client-side routing (without this, direct navigation to `/admin/login`
  returns 404)
- **Git-to-Vercel auto-deploy:** NOT connected. Manual CLI deploy required.
  Connect via Vercel dashboard if you want push-to-deploy.

---

## Tech Stack

- React 18 + TypeScript + Vite
- Tailwind CSS + shadcn/ui (Radix primitives)
- @tanstack/react-query for data fetching
- react-router-dom v6 for routing
- @supabase/supabase-js for DB + auth
- Supabase Edge Functions (Deno/TypeScript) for AI backend
- Anthropic Claude for chat and JD analysis
- Vercel for hosting

---

## Errors Encountered and How They Were Fixed

### 1. `uuid_generate_v4()` does not exist
Supabase Postgres uses `gen_random_uuid()` (built-in, Postgres 13+), not the
`uuid_generate_v4()` function from the `uuid-ossp` extension. Fixed by replacing
all occurrences in the migration and removing the `CREATE EXTENSION` line.

### 2. Migration history corruption
After the first failed migration attempt, Supabase recorded it as applied (but it
wasn't). Fixed with:
```bash
supabase migration repair --status reverted 20250505000000
supabase db push
```

### 3. `supabase db push --project-ref` not recognized
Newer Supabase CLI dropped `--project-ref` from `db push`. Fixed by linking first:
```bash
supabase link --project-ref zybttfjewunokevxwtqc
supabase db push
```

### 4. 404 on `/admin/login` (Vercel SPA routing)
Vercel tries to serve physical files for direct URL navigation. Client-side routes
don't exist as files. Fixed by adding `vercel.json`:
```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```

### 5. `vercel --yes` interactive prompt
`vercel --yes` prompted to choose between `origin` and `upstream` Git remotes.
Fixed by piping: `echo "0" | vercel --yes`.

### 6. Sync script env path failure after project move
When the project moved from `~/Code/ai-resume` to `~/Code/AI/ai-resume`, the script's
`Path(__file__).parent.parent / ".env"` path no longer pointed to `open_brain/.env`.
Fixed by using an absolute path: `Path.home() / "Code/AI/open_brain/.env"` as primary.

### 7. `ai_instructions_instruction_type_check` constraint violation
Claude's extraction used `"competence"` as an instruction_type. The DB check
constraint only allows `honesty | tone | boundaries | other`. Fixed by normalizing
unknown values to `"other"` in the script before inserting.

### 9. `gap_type` CHECK constraint violation (2026-05-07)
The `gaps_weaknesses` table has `gap_type IN ('skill', 'experience', 'environment', 'role_type')`.
The sync script passed Claude's raw output directly, so invented values like `'tolerance'` caused
DB inserts to fail. Fixed by adding a `VALID_GAP_TYPES` normalization guard in both `sync_gaps()`
(Mode 1) and `run_extract()` (Mode 2), defaulting unknowns to `'skill'`. Same pattern as the
existing `VALID_INSTR_TYPES` guard for `instruction_type`. Also added the four valid values to
the extraction prompt so Claude produces correct values from the start.

### 8. Skills extraction: too few, wrong categories
First extraction produced only 10 skills using "developing" as a category (invalid).
Fixed by updating the extraction prompt to explicitly require 25-35 discrete skills
and enforce `strong | moderate | gap` as the only valid category values.

---

## Lessons Learned

1. **OB is the source of truth.** If the AI gives wrong answers about Brett's
   background, the fix is always in OB — add thoughts, then re-run `--extract`.
   Never hand-edit the career tables directly (or they'll be overwritten on next sync).

2. **The extract prompt is the critical tuning surface.** The quality of skills,
   gaps, and AI instructions depends entirely on the EXTRACT_SYSTEM prompt in
   sync_career_from_ob.py. When content is wrong or thin, tweak the prompt first.

3. **Vercel SPA routing always needs `vercel.json`.** Any React Router app deployed
   to Vercel needs the rewrite rule or direct URL navigation will 404.

4. **Supabase check constraints bite at insert time.** Claude can generate enum values
   not in the constraint. Always normalize enum fields in Python before inserting.

5. **The two-pass extract approach works.** Sending 73 thoughts (130K chars) to Claude
   in one shot and getting back structured JSON for all tables works well and costs ~$0.50
   per run. The extraction takes ~3 minutes.

---

## Ideas for Future Improvements

### High priority
- **Content enrichment** — More OB thoughts = better AI answers. Run additional
  Interview Agent sessions (Mode 3 Biographical) for missing stories: The Hill School,
  teaching years, FEMA certification, FBI collaboration details, NIU salary equity story,
  Emory-specific achievements, ACUTE technical depth.
- **Fix duplicate experiences** — The re-run created a second Neighborly row with
  slightly different title. Run `--stats` and manually delete the duplicate from
  Supabase dashboard, or add dedup logic to the extract upsert.
- ~~**Update deprecated model**~~ — Done 2026-05-07. All three files now use `claude-sonnet-4-6`.

### Medium priority
- **Git-to-Vercel auto-deploy** — Connect the GitHub repo in the Vercel dashboard
  for push-to-deploy instead of manual `vercel --prod`.
- **Skills section on site** — The frontend doesn't display skills yet (the original
  scaffold had a static placeholder). Wire up `useSkills()` hook to render the
  strong/moderate/gap breakdown from Supabase.
- **FAQ section** — `faq_responses` table exists but nothing in it yet. Add a
  dedicated Interview Agent session for common recruiter questions and sync.
- **JD analyzer verdict display** — The `probably_not` verdict path could be made
  more visually distinct (currently similar to `worth_conversation`).
- **Admin password** — Change from the initial temporary password to something
  permanent in the Supabase Auth dashboard.

### Future / architectural
- **`sync_career_from_ob.py --watch` mode** — Run on a schedule (cron) to
  automatically pick up new career-tagged OB thoughts and sync them without
  manual intervention.
- **Structured career thoughts** — Establish the discipline of capturing new career
  data to OB with `metadata.type = "career-experience"` etc. so the structured
  sync mode (Mode 1) works for incremental updates without re-running Claude.
- **The Hill School and teaching years** — Currently missing from experiences.
  Capture as OB thoughts and re-extract.
- **Sprint history** — Current entry shows Chief of Staff role only. The full
  progression (risk consultant → PM → team lead → nationwide lead → Chief of Staff)
  could be a richer entry.
- **Private field depth** — `why_joined`, `why_left`, `manager_would_say`,
  `reports_would_say` on experiences are populated but thin. Richer content there
  means better AI chat answers to tough interview questions.

---

## How to Run Locally

```bash
cd ~/Code/AI/ai-resume
npm run dev                    # starts Vite dev server at localhost:5173
```

## How to Deploy

```bash
cd ~/Code/AI/ai-resume
vercel --prod
```

## How to Re-sync Career Data

```bash
cd ~/Code/AI/ai-resume
python3 scripts/sync_career_from_ob.py --extract          # full re-extract from OB
python3 scripts/sync_career_from_ob.py --extract --dry-run # preview first
python3 scripts/sync_career_from_ob.py --stats             # check counts
```

## How to Deploy Edge Functions

```bash
cd ~/Code/AI/ai-resume
supabase functions deploy chat
supabase functions deploy analyze-jd
```

---

## Lessons Learned

Dense reference — symptom, root cause, exact fix. One to three lines max. Add an entry after every bug fix before committing.

**JWT error on edge function calls** (`UNAUTHORIZED_INVALID_JWT_FORMAT`): `VITE_SUPABASE_ANON_KEY` was set to `sb_publishable_*` format, which is not a JWT. Edge functions require a Bearer JWT. Fix: `vercel env rm VITE_SUPABASE_ANON_KEY production` then re-add using the JWT key from `supabase projects api-keys` (the `anon` row, starts with `eyJ`).

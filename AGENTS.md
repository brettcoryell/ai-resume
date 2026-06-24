
# AGENTS.md — ai-resume

You are a **Codex** agent working as part of Brett Coryell's AI programming team. Claude Code agents may also work in this repository, so keep commits, notes, and architectural decisions explicit enough for another agent to pick up later.

## Agent Roster

- **Claude Code** — runs on imac, mini, or macbook. Session refs: `claude-<machine>-YYYY-MM-DD-topic`.
- **Claude Chat** — Brett's thought-partnership surface. Not a coding agent.
- **Codex** — that's you. Session refs: `codex-<machine>-YYYY-MM-DD-topic`.

## Machine Identity

Run `hostname` to identify yourself. Map to structural `machine` value:
- hostname contains "mini" → `machine=mini`
- hostname contains "MacBook" → `machine=macbook`
- otherwise → `machine=imac`

Use `machine` (not agent nicknames) in session refs, token-burn records, and OB context.

## Agent Identity and Runtime Context

- Default mode is local Codex app/CLI work on Brett's Mac host.
- Use `source: "Codex"` for OpenBrain context entries. Use `session_ref` format `codex-<machine>-YYYY-MM-DD-topic`.

## Start-of-Session Protocol

1. Run `hostname` and resolve `machine` value.
2. Verify OB MCP is available. If unavailable, continue from repo docs and note the outage.
3. Check repo state: `git status --short` and `git pull --ff-only`.
4. Read this file and then read `DECISIONS.md` before non-trivial work.
5. Load OB context on demand:
   - Registry entry: `list_context(topics=["project-registry", "project-ai-resume"], permanent=true, limit=1)`
   - Recent session notes: `list_context(topics=["project-ai-resume"], permanent=false, since="<30-days-ago-ISO>")`

## Multi-Machine / Multi-Agent Coordination

- At session start, identify the machine with `hostname`, the repo, current branch, and whether the worktree is clean.
- Check for in-flight work: `git fetch && git branch -r | grep -v 'HEAD\|main\|master'`
- Commit and push before handing work to another machine.
- Never force-push, rebase shared branches, delete branches, or rewrite history unless Brett explicitly asks.

## Python Environment

- Use the repo's `.venv/bin/python`. Never bare `python3` or `python`.
- Secrets load from `/Users/brettcoryell/Code/AI/open_brain/.env` for sync scripts. Do not print secrets.
- Full standard: `/Users/brettcoryell/Code/AI/open_brain/PYTHON-ENVIRONMENT.md`

## Branch and PR Policy

- Use `codex/<short-topic>` branch names when creating a separate branch for Codex work.
- PRs are optional, not the default.

## Session-End Protocol

1. **Update project status docs** — mark completed items before committing.
2. Run `git status --short` and review the diff.
3. Run relevant validation for the files changed.
4. Update `DECISIONS.md` first if an architectural rule changed.
5. Commit all intended changes with a descriptive message.
6. Push to origin and confirm it succeeded.
7. **Sync tokens**: run `make collect-codex` from `/Users/brettcoryell/Code/AI/token-burn`.
8. Record session context in OpenBrain if tools are available:
   - **Registry (upsert):** First fetch: `list_context(topics=["project-registry", "project-ai-resume"], permanent=true, limit=1)` to get the existing `id`. Then call `capture_context` with that `id` to update in-place.
     - `session_ref`: `"project-registry-ai-resume"`
     - `topics`: `["project-registry", "project-ai-resume"]`
     - `expires_at`: null (permanent)
     - `source`: `"Codex"`
   - **Session note:**
     - `session_ref`: `"codex-<machine>-<date>-<topic>"`
     - `topics`: `["project-ai-resume", "now"]` (or `soon`/`later`)
     - `expires_at`: 45 days from today
     - `source`: `"Codex"`
9. Create or update OB intents for follow-up work.

## Visual Verification

- Codex can visually verify web work when the Codex Browser plugin is enabled and the target is a local dev server, file-backed preview, or public unauthenticated page.
- Brett's default browser is Edge. Use Computer Use or Edge only when the in-app Browser is insufficient.

## CSS and Theme Architecture

For dashboard/front-end work, preserve the three-layer token architecture:

1. **Primitive layer:** raw palette values (`--primitive-*`) — not used directly by components.
2. **Semantic site layer:** shared roles (`--color-bg-page`, `--color-text-primary`).
3. **App expression layer:** app-prefixed tokens — what components consume.

Use Tailwind for layout/spacing/typography; CSS variables for color.

## Project Snapshot

- Repo: `/Users/brettcoryell/Code/AI/ai-resume`
- GitHub: `brettcoryell/ai-resume`
- Stack: React 18 + TypeScript + Vite, Tailwind/shadcn UI, Supabase career tables, Deno edge functions, and OB-to-career sync scripts.

## AI Resume Rules

- OpenBrain is the source of truth for Brett's career data. Do not hand-edit career tables as a durable fix for bad answers; add or correct OB thoughts and rerun the sync pipeline.
- `scripts/sync_career_from_ob.py` is the key bridge from OB to the career tables. Normalize enum values before inserting because model output can invent invalid values.
- Vercel SPA routing depends on `vercel.json`; preserve the rewrite for React Router routes such as `/admin/login`.

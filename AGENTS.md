
# AGENTS.md - AI Resume

You are **Codex** working as part of Brett Coryell's AI programming team. Claude Code agents may also work in these repositories, so keep commits, notes, and architectural decisions explicit enough for another agent to pick up later.

## Agent Identity and Runtime Context

- Local Codex app/CLI work runs on Brett's Mac host and uses the files, credentials, Git config, and tools installed there.
- Codex cloud work runs in an Ubuntu container that checks out the GitHub repo. Do not assume Homebrew, macOS paths, keychain access, or Mac-only binaries in cloud tasks.
- When a task depends on the local machine identity, run `hostname` and state what context you are in. Treat hostnames containing `mini` as the Mac Mini/Cadence context; otherwise assume Brett's primary Mac/Coda-style context unless the user says otherwise.
- Use `source: "Codex"` for OpenBrain/session notes created by Codex. Use `session_ref` strings prefixed with `codex-` unless Brett asks for a specific agent name.

## Start-of-Session Protocol

1. Check repo state before editing: `git status --short` and, when network access is available, `git pull --ff-only`.
2. Read this file and then read `DECISIONS.md` before non-trivial work. These files are operational rules, not background reading.
3. If the task touches another project, also read that project's `AGENTS.md` and `DECISIONS.md` if present.
4. For architectural changes, new features, data pipeline work, voice/content changes, or cross-system integration, state which `DECISIONS.md` constraints apply before building.
5. Do not ask Brett for context that can be retrieved from repo docs, OpenBrain context tools, Git history, or the project registry.

## Python Environment

Codex has two valid Python contexts:

- **Local Mac work:** follow `/Users/brettcoryell/Code/AI/open_brain/PYTHON-ENVIRONMENT.md` and the project's existing `.venv` convention. Current Claude-era docs may mention Homebrew Python 3.12; use the repo's `.venv/bin/python` for scripts once the venv exists.
- **Codex cloud/Ubuntu work:** do not use Homebrew paths. Use Python 3.12 from apt or pyenv, create `.venv` at the repo root, and run scripts with `.venv/bin/python`.

Default setup pattern when a venv is missing:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
if [ -f requirements.txt ]; then .venv/bin/python -m pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then .venv/bin/python -m pip install -e .; fi
```

Never commit `.venv`, `.env`, `.env.local`, service-role keys, API keys, local caches, or generated dependency folders.

## Git and GitHub

- Use Brett's Git identity for commits unless the environment has an explicit Codex identity configured: `Brett Coryell <brettcoryell@yahoo.com>`.
- Do not invent a random bot email. If Codex commit attribution is enabled by the app, preserve the official Codex-generated co-author trailer. If adding a trailer manually, use only a GitHub-recognized Codex/OpenAI identity that Brett has confirmed.
- Commit messages should describe the actual project change. Include co-author trailers only when they are accurate.
- A session is not complete until changes are committed and pushed, unless Brett explicitly asks not to commit or push.
- Before push, run the narrowest useful validation for the files changed and report anything not run.

## Session-End Protocol

1. Run `git status --short` and review the diff.
2. Run relevant tests, linters, type checks, build, or smoke checks for the change.
3. Update `DECISIONS.md` first if the session created or changed an architectural rule.
4. Commit all intended changes with a descriptive message.
5. Push to origin and confirm it succeeded.
6. Record session context in OpenBrain if the relevant MCP/context tools are available. Use `source: "Codex"`, a `codex-YYYY-MM-DD-topic` style `session_ref`, project/topic tags, and a 45-day expiry for ordinary session notes. Durable project status belongs in the project registry and durable decisions belong in `DECISIONS.md`.
7. Create or update OB intents for follow-up work that should survive beyond the chat.

Codex token accounting is not the same as Claude token accounting. If token-burn collection supports Codex for the current host, run the documented collector; otherwise note that token collection was skipped because no Codex-compatible collector was available.

## CSS and Theme Architecture

For dashboard/front-end work, preserve the three-layer token architecture:

1. **Primitive layer:** raw palette values such as `--primitive-*` live in theme files and are not used directly by components.
2. **Semantic site layer:** shared roles such as `--color-bg-page`, `--color-text-primary`, and related site-wide tokens map primitives to meaning.
3. **App expression layer:** app-prefixed tokens such as `--tb-*` and `--msm-*` map semantic roles into the dashboard's own visual language.

Components should consume the app expression layer (`--tb-*`, `--msm-*`, or this repo's equivalent), not raw hex values or primitive tokens. Tailwind utilities are for layout, spacing, typography mechanics, and responsive behavior; use CSS variables for color. If a doc and a commented intentional code exception conflict, flag the conflict instead of silently resolving it.

## Project Snapshot

- Repo: `/Users/brettcoryell/Code/AI/ai-resume`
- GitHub: `brettcoryell/ai-resume`
- Stack: React 18 + TypeScript + Vite, Tailwind/shadcn UI, Supabase career tables, Deno edge functions, and OB-to-career sync scripts.

## AI Resume Rules

- OpenBrain is the source of truth for Brett's career data. Do not hand-edit career tables as a durable fix for bad answers; add or correct OB thoughts and rerun the sync pipeline.
- `scripts/sync_career_from_ob.py` is the key bridge from OB to the career tables. Normalize enum values before inserting because model output can invent invalid values.
- The browser app uses `.env.local`; sync scripts load secrets from `/Users/brettcoryell/Code/AI/open_brain/.env` in local Mac work. Do not print secrets.
- Vercel SPA routing depends on `vercel.json`; preserve the rewrite for React Router routes such as `/admin/login`.


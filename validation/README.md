# Validation Pipeline

Validates the OB → ai-resume data pipeline: confirms that biographical content
from OpenBrain is faithfully represented in the ai-resume Supabase tables.

## Tests

| Test | Name | Status |
|------|------|--------|
| 1A | Forward pass — OB → ai-resume | Active |
| 1B | Reverse pass — ai-resume → OB | Active |
| 2  | Named entity audit | Active |
| 3  | Global keyword/entity union | Active |
| 4  | Schema integrity | Deferred (post schema redesign) |
| 5  | Q&A accuracy | Deferred (needs qa_dataset.json) |

## Running

```bash
# Full run (uses Claude + Gemini for LLM checks)
python3 scripts/validate_pipeline.py

# Deterministic only (no LLM calls, faster)
python3 scripts/validate_pipeline.py --skip-llm

# Single test
python3 scripts/validate_pipeline.py --test 1a
python3 scripts/validate_pipeline.py --test 2 --verbose

# Query the chat Edge Function manually
python3 scripts/query_ai_resume.py "Tell me about yourself"
python3 scripts/query_ai_resume.py --json "What is Brett's biggest weakness?"
```

## Prerequisites

```bash
pip3 install python-dotenv supabase anthropic requests
```

Env vars needed (loaded from `~/Code/AI/open_brain/.env`):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

The anon key for the chat Edge Function is loaded from `.env.local` (`VITE_SUPABASE_ANON_KEY`).

## Migration (one-time)

Before first run, apply the `ai-resume-source` tag to all in-scope OB thoughts:

```bash
python3 scripts/migrate_ai_resume_source_tag.py --dry-run   # preview
python3 scripts/migrate_ai_resume_source_tag.py             # apply
```

## Output files

- `validation/validation_report.json` — summary counts per test (gitignored)
- `validation/validation_exceptions.json` — flagged items (gitignored)
- `validation/qa_dataset.json` — Q&A dataset for Test 5 (committed when ready)

## Q&A Dataset

`qa_dataset.json` is written by a parallel Coda session doing a manual OB + ai-resume
read-through. Do not create it manually. It will be committed once that session completes.
Format: `[{"question": "...", "expected_answer": "...", "ob_thought_ids": ["..."]}]`

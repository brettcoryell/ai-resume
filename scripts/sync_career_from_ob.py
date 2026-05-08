#!/usr/bin/env python3
"""
sync_career_from_ob.py — v1
Reads career data from OpenBrain and syncs to the ai-resume Supabase tables.
Both OB and ai-resume live in the same Supabase project, so one client handles
everything.

──────────────────────────────────────────────────────────────────────────
TWO MODES
──────────────────────────────────────────────────────────────────────────

MODE 1 — STRUCTURED SYNC (default)
  Reads thoughts where metadata.type starts with "career-".
  Fast, deterministic, idempotent. Use this for ongoing updates after
  you've bootstrapped the career tables.

  Future career data should be captured to OB using these type tags:
    career-profile     → candidate_profile fields
    career-experience  → one thought per role
    career-skill       → one thought per skill
    career-gap         → one thought per acknowledged weakness
    career-faq         → one thought per pre-written Q&A
    career-instruction → one thought per AI behavior instruction

  See the docstring in the ai-resume repo's sync_career_from_ob.py
  for the full metadata schema for each type.

MODE 2 — EXTRACT (--extract)
  Reads all biographical OB thoughts tagged with Brett's name/career topics,
  sends them to Claude, and extracts structured career data for all tables.
  Use this ONCE to bootstrap the career tables from Interview Agent sessions.
  Safe to re-run — all upserts are keyed and idempotent.

──────────────────────────────────────────────────────────────────────────
USAGE
──────────────────────────────────────────────────────────────────────────
  # Bootstrap from existing Interview Agent thoughts (run once):
  python3 scripts/sync_career_from_ob.py --extract

  # Preview what extract would produce without writing:
  python3 scripts/sync_career_from_ob.py --extract --dry-run

  # Ongoing sync of new career-* structured thoughts:
  python3 scripts/sync_career_from_ob.py

  # Show current counts in both OB and career tables:
  python3 scripts/sync_career_from_ob.py --stats

  # Sync only one table type:
  python3 scripts/sync_career_from_ob.py --type experience
"""

import sys
import os
import json
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────────────────────────────────

def find_and_load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv not installed.  pip3 install python-dotenv")
        sys.exit(1)

    search_paths = [
        Path.home() / "Code/AI/open_brain/.env",          # primary — SUPABASE_* + ANTHROPIC_*
        Path(__file__).parent.parent / ".env",            # ai-resume/.env (if exists)
        Path(__file__).parent.parent / ".env.local",      # ai-resume/.env.local (VITE_* vars)
    ]

    loaded = []
    for p in search_paths:
        if p.exists():
            load_dotenv(p, override=True)
            loaded.append(str(p))

    return ", ".join(loaded) if loaded else "environment"


# ──────────────────────────────────────────────────────────────────────────
# Clients
# ──────────────────────────────────────────────────────────────────────────

def get_supabase():
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase not installed.  pip3 install supabase")
        sys.exit(1)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        sys.exit(1)
    return create_client(url, key)


def get_anthropic():
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic not installed.  pip3 install anthropic")
        sys.exit(1)
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY must be set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


# ──────────────────────────────────────────────────────────────────────────
# Fetch helpers
# ──────────────────────────────────────────────────────────────────────────

def fetch_career_structured_thoughts(sb, career_type=None, verbose=False):
    """Fetch thoughts with metadata.type = career-*"""
    thoughts = []
    page_size = 1000
    offset = 0

    while True:
        result = (
            sb.table("thoughts")
            .select("id, content, metadata, created_at")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        for t in batch:
            meta = t.get("metadata") or {}
            ttype = meta.get("type", "")
            if ttype.startswith("career-"):
                if career_type is None or ttype == f"career-{career_type}":
                    thoughts.append(t)

        if len(batch) < page_size:
            break
        offset += page_size

    return thoughts


def fetch_biographical_thoughts(sb, verbose=False):
    """
    Fetch all thoughts that look like biographical career content —
    any thought mentioning Brett Coryell or tagged with career topics.
    Used by --extract mode.
    """
    page_size = 1000
    offset = 0
    all_thoughts = []

    CAREER_TOPICS = {
        "career", "Career", "resume", "Resume", "biography", "biographical",
        "IT Leadership", "Cybersecurity", "career development", "leadership",
        "management", "ERM", "cybersecurity", "FBI collaboration",
        "ACUTE project", "Elementum", "management philosophy", "mentorship",
    }

    while True:
        result = (
            sb.table("thoughts")
            .select("id, content, metadata, created_at")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        for t in batch:
            meta = t.get("metadata") or {}
            content = t.get("content", "")

            # Skip non-career YouTube transcripts
            if meta.get("source_url") and "youtube" in str(meta.get("source_url", "")):
                continue

            # Include if mentions Brett by name
            if "Brett Coryell" in content or "Brett" in content[:50]:
                all_thoughts.append(t)
                continue

            # Include if topics overlap with career topics
            topics = set(meta.get("topics", []))
            if topics & CAREER_TOPICS:
                all_thoughts.append(t)
                continue

        if len(batch) < page_size:
            break
        offset += page_size

    if verbose:
        print(f"  Fetched {len(all_thoughts)} biographical/career thoughts from OB")

    return all_thoughts


# ──────────────────────────────────────────────────────────────────────────
# Profile helpers
# ──────────────────────────────────────────────────────────────────────────

def get_or_create_profile(sb, dry_run=False, verbose=False):
    result = sb.table("candidate_profile").select("*").limit(1).execute()
    if result.data:
        if verbose:
            print(f"  Existing profile: {result.data[0]['id']}")
        return result.data[0]

    if dry_run:
        print("  [DRY RUN] Would create placeholder profile row")
        return {"id": "dry-run-placeholder"}

    row = {"name": "Brett Coryell"}
    result = sb.table("candidate_profile").insert(row).execute()
    print(f"  Created profile row: {result.data[0]['id']}")
    return result.data[0]


# ──────────────────────────────────────────────────────────────────────────
# Parsers
# ──────────────────────────────────────────────────────────────────────────

def parse_bullet_points(content):
    lines = content.strip().splitlines()
    bullets = []
    for line in lines:
        line = line.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line.startswith("• "):
            bullets.append(line[2:].strip())
        elif line and not line.startswith("#"):
            bullets.append(line)
    return [b for b in bullets if b]


def parse_gap_content(content):
    parts = re.split(r'\n\s*\n', content.strip(), maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def parse_date(date_str):
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}$', date_str):
        return f"{date_str}-01"
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    return None


def parse_array_field(content):
    content = content.strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if x]
    except json.JSONDecodeError:
        pass
    return [x.strip() for x in content.split(",") if x.strip()]


# ──────────────────────────────────────────────────────────────────────────
# MODE 1 — Structured sync (career-* thoughts → tables)
# ──────────────────────────────────────────────────────────────────────────

PROFILE_TEXT_FIELDS = {
    "elevator_pitch", "career_narrative", "looking_for", "not_looking_for",
    "availability_status", "remote_preference", "location", "title",
    "email", "linkedin_url", "github_url",
}
PROFILE_ARRAY_FIELDS = {"target_titles", "target_company_stages"}
PROFILE_INT_FIELDS = {"salary_min", "salary_max"}


def sync_profile(sb, thoughts, profile, dry_run, verbose):
    items = [t for t in thoughts if t["metadata"].get("type") == "career-profile"]
    if not items:
        if verbose: print("  No career-profile thoughts")
        return 0

    updates = {}
    primary_ob_id = None

    for t in items:
        meta = t["metadata"]
        content = t["content"].strip()
        for field in meta.get("fields", []):
            if field in PROFILE_TEXT_FIELDS:
                updates[field] = content
                if field in ("elevator_pitch", "career_narrative"):
                    primary_ob_id = t["id"]
            elif field in PROFILE_ARRAY_FIELDS:
                updates[field] = parse_array_field(content)
            elif field in PROFILE_INT_FIELDS:
                try:
                    updates[field] = int(content)
                except ValueError:
                    print(f"  WARNING: bad int for '{field}'")

    if primary_ob_id:
        updates["ob_thought_id"] = primary_ob_id

    if not updates:
        return 0

    if dry_run:
        print(f"  [DRY RUN] Would update profile: {list(updates.keys())}")
        return len(updates)

    sb.table("candidate_profile").update(updates).eq("id", profile["id"]).execute()
    print(f"  ✓ Updated profile: {', '.join(updates.keys())}")
    return len(updates)


def _upsert_by_ob_id(sb, table, row, ob_thought_id, dry_run, label):
    if dry_run:
        print(f"  [DRY RUN] Would upsert {table}: {label}")
        return

    existing = sb.table(table).select("id").eq("ob_thought_id", ob_thought_id).execute()
    if existing.data:
        sb.table(table).update(row).eq("ob_thought_id", ob_thought_id).execute()
        print(f"  ✓ Updated {table}: {label}")
    else:
        sb.table(table).insert(row).execute()
        print(f"  ✓ Inserted {table}: {label}")


def sync_experiences(sb, thoughts, profile, dry_run, verbose):
    items = [t for t in thoughts if t["metadata"].get("type") == "career-experience"]
    if not items:
        if verbose: print("  No career-experience thoughts")
        return 0

    for t in items:
        m = t["metadata"]
        row = {k: v for k, v in {
            "candidate_id": profile["id"],
            "ob_thought_id": t["id"],
            "company_name": m.get("company", "Unknown"),
            "title": m.get("title", "Unknown"),
            "title_progression": m.get("title_progression"),
            "start_date": parse_date(m.get("start_date")),
            "end_date": parse_date(m.get("end_date")),
            "is_current": bool(m.get("is_current", False)),
            "display_order": int(m.get("display_order", 99)),
            "bullet_points": parse_bullet_points(t["content"]),
            "why_joined": m.get("why_joined"),
            "why_left": m.get("why_left"),
            "actual_contributions": m.get("actual_contributions"),
            "proudest_achievement": m.get("proudest_achievement"),
            "would_do_differently": m.get("would_do_differently"),
            "challenges_faced": m.get("challenges_faced"),
            "lessons_learned": m.get("lessons_learned"),
            "manager_would_say": m.get("manager_would_say"),
            "reports_would_say": m.get("reports_would_say"),
        }.items() if v is not None}
        label = f"{row['company_name']} / {row['title']}"
        _upsert_by_ob_id(sb, "experiences", row, t["id"], dry_run, label)

    return len(items)


def sync_skills(sb, thoughts, profile, dry_run, verbose):
    items = [t for t in thoughts if t["metadata"].get("type") == "career-skill"]
    if not items:
        if verbose: print("  No career-skill thoughts")
        return 0

    for t in items:
        m = t["metadata"]
        content = t["content"].strip()
        row = {k: v for k, v in {
            "candidate_id": profile["id"],
            "ob_thought_id": t["id"],
            "skill_name": m.get("skill_name", "Unknown"),
            "category": m.get("category", "moderate"),
            "self_rating": m.get("self_rating"),
            "honest_notes": m.get("honest_notes"),
            "years_experience": m.get("years_experience"),
            "evidence": content or None,
        }.items() if v is not None}
        _upsert_by_ob_id(sb, "skills", row, t["id"], dry_run,
                         f"{row['skill_name']} ({row.get('category','?')})")

    return len(items)


def sync_gaps(sb, thoughts, profile, dry_run, verbose):
    items = [t for t in thoughts if t["metadata"].get("type") == "career-gap"]
    if not items:
        if verbose: print("  No career-gap thoughts")
        return 0

    for t in items:
        m = t["metadata"]
        desc, why = parse_gap_content(t["content"])
        VALID_GAP_TYPES = {"skill", "experience", "environment", "role_type"}
        raw_gap_type = m.get("gap_type", "skill")
        gap_type = raw_gap_type if raw_gap_type in VALID_GAP_TYPES else "skill"
        row = {k: v for k, v in {
            "candidate_id": profile["id"],
            "ob_thought_id": t["id"],
            "description": desc,
            "why_its_a_gap": why or None,
            "gap_type": gap_type,
            "interest_in_learning": bool(m.get("interest_in_learning", False)),
        }.items() if v is not None}
        _upsert_by_ob_id(sb, "gaps_weaknesses", row, t["id"], dry_run, desc[:60])

    return len(items)


def sync_faqs(sb, thoughts, profile, dry_run, verbose):
    items = [t for t in thoughts if t["metadata"].get("type") == "career-faq"]
    if not items:
        if verbose: print("  No career-faq thoughts")
        return 0

    for t in items:
        m = t["metadata"]
        q = m.get("question", "")
        if not q:
            print(f"  WARNING: career-faq thought {t['id']} has no question — skipping")
            continue
        row = {k: v for k, v in {
            "candidate_id": profile["id"],
            "ob_thought_id": t["id"],
            "question": q,
            "answer": t["content"].strip(),
            "display_order": int(m.get("display_order", 99)),
            "is_common_question": bool(m.get("is_common_question", False)),
        }.items() if v is not None}
        _upsert_by_ob_id(sb, "faq_responses", row, t["id"], dry_run, q[:60])

    return len(items)


def sync_instructions(sb, thoughts, profile, dry_run, verbose):
    items = [t for t in thoughts if t["metadata"].get("type") == "career-instruction"]
    if not items:
        if verbose: print("  No career-instruction thoughts")
        return 0

    for t in items:
        m = t["metadata"]
        content = t["content"].strip()
        row = {
            "candidate_id": profile["id"],
            "ob_thought_id": t["id"],
            "instruction": content,
            "instruction_type": m.get("instruction_type", "other"),
            "priority": int(m.get("priority", 0)),
        }
        _upsert_by_ob_id(sb, "ai_instructions", row, t["id"], dry_run, content[:60])

    return len(items)


# ──────────────────────────────────────────────────────────────────────────
# MODE 2 — Extract (biographical thoughts → Claude → tables)
# ──────────────────────────────────────────────────────────────────────────

EXTRACT_SYSTEM = """You are extracting structured career data from biographical interview notes.
The source material is raw OpenBrain thoughts from Interview Agent sessions with Brett Coryell.
Extract data for a professional portfolio website database.

CRITICAL RULES:
- Use first-person voice for all text fields (elevator_pitch, career_narrative, etc.)
- bullet_points must be resume-style achievement statements with metrics where available
- Private fields (why_joined, why_left, actual_contributions, manager_would_say, etc.)
  should be candid and detailed — they are never shown to site visitors, only to the AI
- For dates use YYYY-MM format. Use best estimates from context clues.
- For skills: extract 25-35 SPECIFIC, DISCRETE skills — not broad categories.
  Pull from the full skills list in the source material. Each skill should be a
  concrete capability (e.g. "IT Service Management (ITIL)", "SAP ERP Implementation",
  "AWS Cloud Architecture", "Balanced Scorecard", "Zero Trust Security").
  IMPORTANT: category MUST be EXACTLY one of: "strong", "moderate", or "gap"
  — no other values are valid. Never use "developing", "advanced", or any other word.
  Use "gap" for genuine weaknesses only; "moderate" for real but not expert-level skills.
- For gaps: gap_type MUST be EXACTLY one of: "skill", "experience", "environment", "role_type"
  — no other values are valid. Map all gap types to the closest option; default to "skill".
- Output ONLY valid JSON. No markdown, no backticks, no commentary.

OUTPUT FORMAT (exact keys required):
{
  "profile": {
    "elevator_pitch": "2-3 sentence first-person pitch capturing career arc and value prop",
    "career_narrative": "Longer 4-6 sentence narrative of the career arc and through-line",
    "looking_for": "What kinds of roles and situations Brett is actively pursuing",
    "not_looking_for": "What to explicitly rule out",
    "target_titles": ["CAIO", "CIO", "CISO", "COO", "Board Advisor"],
    "target_company_stages": ["enterprise", "private-equity-backed", "board-seat"]
  },
  "experiences": [
    {
      "company": "Company Name",
      "title": "Most senior title held",
      "title_progression": "Director → VP → SVP (or null if no progression)",
      "start_date": "YYYY-MM",
      "end_date": "YYYY-MM (null if current)",
      "is_current": false,
      "display_order": 1,
      "bullet_points": [
        "Achievement with metric — result and scope",
        "Achievement with metric — result and scope",
        "Achievement with metric — result and scope"
      ],
      "why_joined": "Private: candid reason for taking this role",
      "why_left": "Private: candid reason for leaving",
      "actual_contributions": "Private: what Brett actually did day-to-day beyond the bullets",
      "proudest_achievement": "Private: the one thing Brett is most proud of here",
      "manager_would_say": "Private: what the boss would say about Brett in this role",
      "reports_would_say": "Private: what the team would say about working for Brett"
    }
  ],
  "skills": [
    {
      "skill_name": "Specific skill name",
      "category": "strong",
      "honest_notes": "Private candid note — where this is strong or where it has limits"
    }
  ],
  "gaps": [
    {
      "gap_type": "skill",
      "description": "Short description of the gap",
      "why_its_a_gap": "Honest explanation",
      "interest_in_learning": true
    }
  ],
  "ai_instructions": [
    {
      "instruction_type": "honesty",
      "priority": 10,
      "instruction": "Specific instruction for how the AI should respond"
    }
  ]
}"""


def run_extract(sb, anthropic_client, dry_run, verbose):
    """
    Fetch all biographical thoughts, send to Claude for extraction,
    then upsert the structured results to the career tables.
    """
    print("Fetching biographical thoughts from OB...")
    thoughts = fetch_biographical_thoughts(sb, verbose=verbose)
    print(f"Found {len(thoughts)} biographical thoughts\n")

    if not thoughts:
        print("No biographical thoughts found. Run Interview Agent sessions first.")
        return

    # Concatenate content for Claude
    corpus_parts = []
    for t in thoughts:
        meta = t.get("metadata") or {}
        header = f"[Thought — {meta.get('type', 'unknown')} | Topics: {', '.join(meta.get('topics', []))} | {t.get('created_at','')[:10]}]"
        corpus_parts.append(f"{header}\n{t['content']}")

    corpus = "\n\n---\n\n".join(corpus_parts)

    print(f"Sending {len(thoughts)} thoughts ({len(corpus):,} chars) to Claude for extraction...")
    print("This may take 30-60 seconds...\n")

    import anthropic as anthropic_module

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=EXTRACT_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Extract structured career data from these OpenBrain thoughts:\n\n{corpus}"
        }]
    )

    raw = response.content[0].text if response.content[0].type == "text" else "{}"
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        extracted = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"ERROR: Claude returned invalid JSON: {e}")
        print("Raw response:")
        print(raw[:2000])
        return

    print("Claude extraction complete. Writing to career tables...\n")

    profile = get_or_create_profile(sb, dry_run=dry_run, verbose=verbose)
    candidate_id = profile["id"]

    # ── candidate_profile ─────────────────────────────────────────────────
    p = extracted.get("profile", {})
    if p:
        profile_update = {k: v for k, v in p.items() if v}
        if dry_run:
            print(f"── candidate_profile ────────────────────────────────────")
            for k, v in profile_update.items():
                val = str(v)[:100] + ("..." if len(str(v)) > 100 else "")
                print(f"  [DRY RUN] {k}: {val}")
        else:
            sb.table("candidate_profile").update(profile_update).eq("id", candidate_id).execute()
            print(f"── candidate_profile ────────────────────────────────────")
            print(f"  ✓ Updated {len(profile_update)} fields: {', '.join(profile_update.keys())}")
        print()

    # ── experiences ───────────────────────────────────────────────────────
    # Apply known date corrections before writing
    DATE_CORRECTIONS = {
        "Elementum": {"start_date": "2025-09", "end_date": "2026-04", "is_current": False},
    }
    experiences = extracted.get("experiences", [])
    for exp in experiences:
        company = exp.get("company", "")
        for key, corrections in DATE_CORRECTIONS.items():
            if key.lower() in company.lower():
                exp.update(corrections)
                print(f"  (Applied date correction for {company})")
    print(f"── experiences ({len(experiences)} roles) ──────────────────────")
    for exp in experiences:
        row = {
            "candidate_id": candidate_id,
            "company_name": exp.get("company", "Unknown"),
            "title": exp.get("title", "Unknown"),
            "title_progression": exp.get("title_progression") or None,
            "start_date": parse_date(exp.get("start_date")),
            "end_date": parse_date(exp.get("end_date")),
            "is_current": bool(exp.get("is_current", False)),
            "display_order": int(exp.get("display_order", 99)),
            "bullet_points": exp.get("bullet_points", []),
            "why_joined": exp.get("why_joined") or None,
            "why_left": exp.get("why_left") or None,
            "actual_contributions": exp.get("actual_contributions") or None,
            "proudest_achievement": exp.get("proudest_achievement") or None,
            "manager_would_say": exp.get("manager_would_say") or None,
            "reports_would_say": exp.get("reports_would_say") or None,
        }
        row = {k: v for k, v in row.items() if v is not None}
        label = f"{row['company_name']} / {row['title']}"

        if dry_run:
            bullets = len(row.get("bullet_points", []))
            print(f"  [DRY RUN] {label} ({bullets} bullets, {row.get('start_date','?')} – {row.get('end_date','present')})")
        else:
            # Upsert by company+title (no ob_thought_id on extracted rows)
            existing = (
                sb.table("experiences")
                .select("id")
                .eq("candidate_id", candidate_id)
                .eq("company_name", row["company_name"])
                .eq("title", row["title"])
                .execute()
            )
            if existing.data:
                sb.table("experiences").update(row).eq("id", existing.data[0]["id"]).execute()
                print(f"  ✓ Updated: {label}")
            else:
                sb.table("experiences").insert(row).execute()
                print(f"  ✓ Inserted: {label}")
    print()

    # ── skills ────────────────────────────────────────────────────────────
    skills = extracted.get("skills", [])
    print(f"── skills ({len(skills)} entries) ─────────────────────────────")
    for sk in skills:
        row = {
            "candidate_id": candidate_id,
            "skill_name": sk.get("skill_name", "Unknown"),
            "category": sk.get("category", "moderate"),
            "honest_notes": sk.get("honest_notes") or None,
        }
        label = f"{row['skill_name']} ({row['category']})"

        if dry_run:
            print(f"  [DRY RUN] {label}")
        else:
            existing = (
                sb.table("skills")
                .select("id")
                .eq("candidate_id", candidate_id)
                .eq("skill_name", row["skill_name"])
                .execute()
            )
            if existing.data:
                sb.table("skills").update(row).eq("id", existing.data[0]["id"]).execute()
                print(f"  ✓ Updated: {label}")
            else:
                sb.table("skills").insert(row).execute()
                print(f"  ✓ Inserted: {label}")
    print()

    # ── gaps_weaknesses ───────────────────────────────────────────────────
    gaps = extracted.get("gaps", [])
    print(f"── gaps_weaknesses ({len(gaps)} entries) ───────────────────────")
    for gap in gaps:
        desc = gap.get("description", "")
        VALID_GAP_TYPES = {"skill", "experience", "environment", "role_type"}
        raw_gap_type = gap.get("gap_type", "skill")
        gap_type = raw_gap_type if raw_gap_type in VALID_GAP_TYPES else "skill"
        row = {
            "candidate_id": candidate_id,
            "description": desc,
            "why_its_a_gap": gap.get("why_its_a_gap") or None,
            "gap_type": gap_type,
            "interest_in_learning": bool(gap.get("interest_in_learning", False)),
        }

        if dry_run:
            print(f"  [DRY RUN] {desc[:60]}")
        else:
            existing = (
                sb.table("gaps_weaknesses")
                .select("id")
                .eq("candidate_id", candidate_id)
                .eq("description", desc)
                .execute()
            )
            if existing.data:
                sb.table("gaps_weaknesses").update(row).eq("id", existing.data[0]["id"]).execute()
                print(f"  ✓ Updated: {desc[:60]}")
            else:
                sb.table("gaps_weaknesses").insert(row).execute()
                print(f"  ✓ Inserted: {desc[:60]}")
    print()

    # ── ai_instructions ───────────────────────────────────────────────────
    instructions = extracted.get("ai_instructions", [])
    print(f"── ai_instructions ({len(instructions)} entries) ───────────────")
    for instr in instructions:
        text = instr.get("instruction", "")
        VALID_INSTR_TYPES = {"honesty", "tone", "boundaries", "other"}
        raw_type = instr.get("instruction_type", "other")
        instr_type = raw_type if raw_type in VALID_INSTR_TYPES else "other"
        row = {
            "candidate_id": candidate_id,
            "instruction": text,
            "instruction_type": instr_type,
            "priority": int(instr.get("priority", 0)),
        }

        if dry_run:
            print(f"  [DRY RUN] [{row['instruction_type']}] {text[:60]}")
        else:
            existing = (
                sb.table("ai_instructions")
                .select("id")
                .eq("candidate_id", candidate_id)
                .eq("instruction", text)
                .execute()
            )
            if existing.data:
                sb.table("ai_instructions").update(row).eq("id", existing.data[0]["id"]).execute()
                print(f"  ✓ Updated: {text[:60]}")
            else:
                sb.table("ai_instructions").insert(row).execute()
                print(f"  ✓ Inserted: {text[:60]}")
    print()


# ──────────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────────

def print_stats(sb):
    tables = [
        "candidate_profile", "experiences", "skills",
        "gaps_weaknesses", "faq_responses", "ai_instructions",
    ]
    print("\n── Career site tables (Supabase) ────────────────────────")
    for tbl in tables:
        r = sb.table(tbl).select("id", count="exact").execute()
        count = r.count if r.count is not None else len(r.data or [])
        print(f"  {tbl}: {count} rows")

    # Skills breakdown
    r = sb.table("skills").select("category").execute()
    if r.data:
        from collections import Counter
        cats = Counter(x["category"] for x in r.data)
        for cat, n in sorted(cats.items()):
            print(f"    {cat}: {n}")

    # Career-typed OB thoughts
    r = sb.table("thoughts").select("id, metadata").execute()
    from collections import Counter
    career_types = Counter(
        t["metadata"].get("type", "")
        for t in (r.data or [])
        if t.get("metadata") and t["metadata"].get("type", "").startswith("career-")
    )
    print("\n── Structured career-* thoughts in OB ──────────────────")
    if career_types:
        for t, n in sorted(career_types.items()):
            print(f"  {t}: {n}")
    else:
        print("  (none — use --extract to bootstrap from biographical thoughts)")
    print()


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────

SYNC_TYPES = ["profile", "experience", "skill", "gap", "faq", "instruction"]


def main():
    parser = argparse.ArgumentParser(
        description="Sync career data from OB thoughts to ai-resume Supabase tables"
    )
    parser.add_argument("--extract", action="store_true",
                        help="Extract from biographical thoughts via Claude (one-time bootstrap)")
    parser.add_argument("--type", choices=SYNC_TYPES,
                        help="Sync only this structured type (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be written without writing")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--stats", action="store_true",
                        help="Print table counts and exit")
    args = parser.parse_args()

    env_path = find_and_load_env()
    sb = get_supabase()

    if args.stats:
        print_stats(sb)
        return

    started = datetime.now(timezone.utc)
    print(f"\n{'='*60}")
    print(f"sync_career_from_ob.py  {started.strftime('%Y-%m-%d %H:%M UTC')}")
    mode = "EXTRACT (Claude)" if args.extract else "STRUCTURED SYNC"
    if args.dry_run:
        mode += " [DRY RUN]"
    print(f"  Mode: {mode}")
    print(f"  Env:  {env_path}")
    print(f"{'='*60}\n")

    if args.extract:
        anthropic_client = get_anthropic()
        run_extract(sb, anthropic_client, args.dry_run, args.verbose)
    else:
        thoughts = fetch_career_structured_thoughts(sb, args.type, args.verbose)
        print(f"Found {len(thoughts)} career-* thought(s)\n")

        if not thoughts:
            print("Nothing to sync. Either:")
            print("  1. Run --extract to bootstrap from biographical Interview Agent thoughts")
            print("  2. Capture career-* typed thoughts to OB and run again")
            return

        profile = get_or_create_profile(sb, args.dry_run, args.verbose)
        run_all = args.type is None

        if run_all or args.type == "profile":
            print("── career-profile ──────────────────────────────────────")
            sync_profile(sb, thoughts, profile, args.dry_run, args.verbose)
            print()
        if run_all or args.type == "experience":
            print("── career-experience ───────────────────────────────────")
            sync_experiences(sb, thoughts, profile, args.dry_run, args.verbose)
            print()
        if run_all or args.type == "skill":
            print("── career-skill ────────────────────────────────────────")
            sync_skills(sb, thoughts, profile, args.dry_run, args.verbose)
            print()
        if run_all or args.type == "gap":
            print("── career-gap ──────────────────────────────────────────")
            sync_gaps(sb, thoughts, profile, args.dry_run, args.verbose)
            print()
        if run_all or args.type == "faq":
            print("── career-faq ──────────────────────────────────────────")
            sync_faqs(sb, thoughts, profile, args.dry_run, args.verbose)
            print()
        if run_all or args.type == "instruction":
            print("── career-instruction ──────────────────────────────────")
            sync_instructions(sb, thoughts, profile, args.dry_run, args.verbose)
            print()

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"{'='*60}")
    print(f"Done in {elapsed:.1f}s{' (DRY RUN — nothing written)' if args.dry_run else ''}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

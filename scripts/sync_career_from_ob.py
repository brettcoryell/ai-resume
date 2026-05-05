#!/usr/bin/env python3
"""
sync_career_from_ob.py — v1
Reads structured career-* thoughts from OpenBrain (OB) and syncs them to
the ai-resume Supabase tables. Both OB and ai-resume live in the same
Supabase project (zybttfjewunokevxwtqc), so one client handles everything.

──────────────────────────────────────────────────────────────────────────
HOW TO CAPTURE CAREER DATA INTO OB
──────────────────────────────────────────────────────────────────────────
Each career item is a thought captured to OB with a structured metadata
block. The `type` field in metadata is what this script uses to route the
thought to the right career table.

Use the OB MCP `capture_thought` tool, or insert directly via psql/Supabase
dashboard, or run the Interview Agent (Mode 3 Biographical) with the
CAREER_CAPTURE_GUIDE system prompt.

── career-profile ────────────────────────────────────────────────────────
One thought per logical field group. The `fields` list in metadata tells
the script which candidate_profile column(s) this thought fills.

  metadata:
    type: "career-profile"
    fields: ["elevator_pitch"]       ← single field
    topics: ["career", "career-profile"]

  content: "Brett Coryell is a former CIO and CISO..."

For array fields (target_titles, target_company_stages):
  metadata:
    type: "career-profile"
    fields: ["target_titles"]
    topics: ["career", "career-profile"]
  content: '["CIO", "CISO", "VP Engineering", "Board Advisor"]'   ← JSON array

Supported single-value fields:
  elevator_pitch, career_narrative, looking_for, not_looking_for,
  availability_status, remote_preference, location, title, email,
  linkedin_url, github_url

Supported array fields (content must be a JSON array string):
  target_titles, target_company_stages

Supported integer fields:
  salary_min, salary_max

── career-experience ─────────────────────────────────────────────────────
One thought per role. Bullet points are the public-facing resume lines.
Private fields (why_joined, manager_would_say, etc.) stay in OB metadata
and are synced to private columns — never exposed to the browser.

  metadata:
    type: "career-experience"
    company: "Acme Corp"
    title: "Chief Information Officer"
    title_progression: "VP IT → SVP IT → CIO"   ← optional, shows progression
    start_date: "2018-03"        ← YYYY-MM format
    end_date: "2022-11"          ← omit or null if is_current=true
    is_current: false
    display_order: 1             ← 1 = most recent shown first
    # Private AI context — never sent to browser:
    why_joined: "..."
    why_left: "..."
    actual_contributions: "..."
    proudest_achievement: "..."
    would_do_differently: "..."
    challenges_faced: "..."
    lessons_learned: "..."
    manager_would_say: "..."
    reports_would_say: "..."
    topics: ["career", "career-experience", "cio"]

  content: |-
    - Led digital transformation reducing IT spend by 23% over 3 years
    - Built and scaled security operations center from 0 to 12 analysts
    - Negotiated $40M enterprise software consolidation saving $8M annually

  (Each line starting with "- " becomes one element in bullet_points[])

── career-skill ──────────────────────────────────────────────────────────
One thought per skill.

  metadata:
    type: "career-skill"
    skill_name: "Enterprise Architecture"
    category: "strong"      ← strong | moderate | gap
    self_rating: 5          ← 1–5 (optional)
    honest_notes: "..."     ← private AI context, never shown on site
    years_experience: 15    ← optional
    topics: ["career", "career-skill"]

  content: "Evidence or context. What I've actually done with this skill."

── career-gap ────────────────────────────────────────────────────────────
One thought per acknowledged gap or weakness.

  metadata:
    type: "career-gap"
    gap_type: "skill"        ← skill | experience | environment | role_type
    interest_in_learning: true
    topics: ["career", "career-gap"]

  content: |-
    Hands-on ML/AI model training

    I've worked extensively with AI systems at the application and
    architecture layer, but I haven't trained models from scratch.
    My depth is in deployment, evaluation, and governance — not PyTorch.

  (First line = description; everything after blank line = why_its_a_gap)

── career-faq ────────────────────────────────────────────────────────────
One thought per pre-written Q&A.

  metadata:
    type: "career-faq"
    question: "Why did you leave your last role?"
    display_order: 1
    is_common_question: true
    topics: ["career", "career-faq"]

  content: "The full answer Brett wants the AI to give."

── career-instruction ────────────────────────────────────────────────────
One thought per AI behavior instruction (tone, honesty, boundaries).

  metadata:
    type: "career-instruction"
    instruction_type: "honesty"    ← honesty | tone | boundaries | other
    priority: 10                   ← higher = applied first
    topics: ["career", "career-instruction"]

  content: "When asked about gaps, be direct. Don't soften real weaknesses."

──────────────────────────────────────────────────────────────────────────
USAGE
──────────────────────────────────────────────────────────────────────────
  python3 scripts/sync_career_from_ob.py
  python3 scripts/sync_career_from_ob.py --dry-run
  python3 scripts/sync_career_from_ob.py --type experience
  python3 scripts/sync_career_from_ob.py --verbose
  python3 scripts/sync_career_from_ob.py --stats
"""

import sys
import json
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────
# Environment loading
# ──────────────────────────────────────────────────────────────────────────

def find_and_load_env():
    """Load env vars — tries all known locations, last write wins for conflicts."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv not installed. Run: pip3 install python-dotenv")
        sys.exit(1)

    # Load all that exist — open_brain/.env loaded last so its SUPABASE_* vars win
    search_paths = [
        Path(__file__).parent.parent / ".env.local",    # ai-resume/.env.local (VITE_* vars)
        Path(__file__).parent.parent / ".env",          # ai-resume/.env (if exists)
        Path.home() / "Code/AI/open_brain/.env",        # open_brain/.env (SUPABASE_* vars)
    ]

    loaded = []
    for env_path in search_paths:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            loaded.append(str(env_path))

    return ", ".join(loaded) if loaded else "environment"


# ──────────────────────────────────────────────────────────────────────────
# Supabase client
# ──────────────────────────────────────────────────────────────────────────

def get_supabase_client():
    import os
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase not installed. Run: pip3 install supabase")
        sys.exit(1)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        print("       Set them in ~/Code/AI/open_brain/.env or ai-resume/.env")
        sys.exit(1)

    return create_client(url, key)


# ──────────────────────────────────────────────────────────────────────────
# Fetch all career thoughts from OB
# ──────────────────────────────────────────────────────────────────────────

def fetch_career_thoughts(sb, career_type: str | None = None, verbose: bool = False):
    """
    Fetch all thoughts where metadata->>'type' starts with 'career-'.
    Optionally filter to a specific subtype (e.g. 'experience', 'skill').
    Returns list of thought dicts.
    """
    thoughts = []
    page_size = 1000
    offset = 0

    while True:
        query = (
            sb.table("thoughts")
            .select("id, content, metadata, created_at, updated_at")
            .range(offset, offset + page_size - 1)
        )

        # We can't easily filter by metadata prefix in the Python client,
        # so fetch all and filter in Python. For small career datasets this is fine.
        result = query.execute()

        if result.data is None:
            break

        batch = result.data
        if not batch:
            break

        for thought in batch:
            meta = thought.get("metadata") or {}
            thought_type = meta.get("type", "")
            if thought_type.startswith("career-"):
                if career_type is None or thought_type == f"career-{career_type}":
                    thoughts.append(thought)

        if verbose:
            print(f"  Fetched {len(batch)} thoughts (offset {offset}), found {len(thoughts)} career thoughts so far...")

        if len(batch) < page_size:
            break
        offset += page_size

    return thoughts


# ──────────────────────────────────────────────────────────────────────────
# Get or create candidate_profile row
# ──────────────────────────────────────────────────────────────────────────

def get_or_create_profile(sb, dry_run: bool = False, verbose: bool = False):
    """Returns the candidate_profile row (creates a placeholder if none exists)."""
    result = sb.table("candidate_profile").select("*").limit(1).execute()

    if result.data:
        profile = result.data[0]
        if verbose:
            print(f"  Found existing profile: id={profile['id']}, name={profile.get('name', '(unnamed)')}")
        return profile

    # No profile yet — create a minimal placeholder
    if dry_run:
        print("  [DRY RUN] Would create placeholder candidate_profile row")
        return {"id": "dry-run-placeholder-id"}

    placeholder = {
        "name": "Brett Coryell",  # Will be overwritten by career-profile thoughts
    }
    result = sb.table("candidate_profile").insert(placeholder).execute()
    profile = result.data[0]
    print(f"  Created placeholder candidate_profile row: id={profile['id']}")
    return profile


# ──────────────────────────────────────────────────────────────────────────
# Parsers for thought content
# ──────────────────────────────────────────────────────────────────────────

def parse_bullet_points(content: str) -> list[str]:
    """Extract bullet points from content. Lines starting with '- ' or '• '."""
    lines = content.strip().splitlines()
    bullets = []
    for line in lines:
        line = line.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line.startswith("• "):
            bullets.append(line[2:].strip())
        elif line and not line.startswith("#"):
            # Non-empty, non-header line without bullet prefix — include as-is
            bullets.append(line)
    return [b for b in bullets if b]


def parse_gap_content(content: str) -> tuple[str, str]:
    """
    Parse gap thought content into (description, why_its_a_gap).
    First non-blank line = description; rest after blank line = explanation.
    """
    content = content.strip()
    parts = re.split(r'\n\s*\n', content, maxsplit=1)
    description = parts[0].strip()
    why = parts[1].strip() if len(parts) > 1 else ""
    return description, why


def parse_date(date_str: str | None) -> str | None:
    """Convert YYYY-MM to YYYY-MM-01 for Postgres DATE columns."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}$', date_str):
        return f"{date_str}-01"
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    return None  # Unparseable — skip


def parse_array_field(content: str) -> list[str]:
    """Parse JSON array or comma-separated list into Python list."""
    content = content.strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if x]
    except json.JSONDecodeError:
        pass
    # Fall back to comma-separated
    return [x.strip() for x in content.split(",") if x.strip()]


# ──────────────────────────────────────────────────────────────────────────
# Sync: career-profile thoughts → candidate_profile
# ──────────────────────────────────────────────────────────────────────────

# Fields that map directly from thought content to profile columns
PROFILE_TEXT_FIELDS = {
    "elevator_pitch", "career_narrative", "looking_for", "not_looking_for",
    "availability_status", "remote_preference", "location", "title",
    "email", "linkedin_url", "github_url",
}
PROFILE_ARRAY_FIELDS = {"target_titles", "target_company_stages"}
PROFILE_INT_FIELDS = {"salary_min", "salary_max"}


def sync_profile(sb, thoughts: list, profile: dict, dry_run: bool, verbose: bool) -> int:
    """Merge all career-profile thoughts into the single candidate_profile row."""
    profile_thoughts = [t for t in thoughts if t["metadata"].get("type") == "career-profile"]

    if not profile_thoughts:
        if verbose:
            print("  No career-profile thoughts found — skipping profile sync")
        return 0

    updates = {}
    primary_ob_id = None

    for thought in profile_thoughts:
        meta = thought["metadata"]
        content = thought["content"].strip()
        fields = meta.get("fields", [])

        if not fields:
            if verbose:
                print(f"  WARNING: career-profile thought {thought['id']} has no 'fields' in metadata — skipping")
            continue

        for field in fields:
            if field in PROFILE_TEXT_FIELDS:
                updates[field] = content
                if field in ("elevator_pitch", "career_narrative"):
                    primary_ob_id = thought["id"]
            elif field in PROFILE_ARRAY_FIELDS:
                updates[field] = parse_array_field(content)
            elif field in PROFILE_INT_FIELDS:
                try:
                    updates[field] = int(content.strip())
                except ValueError:
                    print(f"  WARNING: Could not parse integer for field '{field}' from: {content[:50]}")
            else:
                print(f"  WARNING: Unknown profile field '{field}' in thought {thought['id']} — skipping")

    if primary_ob_id:
        updates["ob_thought_id"] = primary_ob_id

    if not updates:
        print("  No valid profile updates extracted")
        return 0

    if dry_run:
        print(f"  [DRY RUN] Would update candidate_profile with {len(updates)} field(s):")
        for k, v in updates.items():
            val_preview = str(v)[:80] + ("..." if len(str(v)) > 80 else "")
            print(f"    {k}: {val_preview}")
        return len(updates)

    sb.table("candidate_profile").update(updates).eq("id", profile["id"]).execute()
    print(f"  ✓ Updated candidate_profile with {len(updates)} field(s): {', '.join(updates.keys())}")
    return len(updates)


# ──────────────────────────────────────────────────────────────────────────
# Sync: career-experience thoughts → experiences
# ──────────────────────────────────────────────────────────────────────────

def sync_experiences(sb, thoughts: list, profile: dict, dry_run: bool, verbose: bool) -> int:
    """Upsert experience rows, keyed by ob_thought_id."""
    exp_thoughts = [t for t in thoughts if t["metadata"].get("type") == "career-experience"]

    if not exp_thoughts:
        if verbose:
            print("  No career-experience thoughts found")
        return 0

    synced = 0
    for thought in exp_thoughts:
        meta = thought["metadata"]
        content = thought["content"]

        row = {
            "candidate_id": profile["id"],
            "ob_thought_id": thought["id"],
            "company_name": meta.get("company", "Unknown Company"),
            "title": meta.get("title", "Unknown Title"),
            "title_progression": meta.get("title_progression"),
            "start_date": parse_date(meta.get("start_date")),
            "end_date": parse_date(meta.get("end_date")),
            "is_current": bool(meta.get("is_current", False)),
            "display_order": int(meta.get("display_order", 99)),
            "bullet_points": parse_bullet_points(content),
            # Private AI context
            "why_joined": meta.get("why_joined"),
            "why_left": meta.get("why_left"),
            "actual_contributions": meta.get("actual_contributions"),
            "proudest_achievement": meta.get("proudest_achievement"),
            "would_do_differently": meta.get("would_do_differently"),
            "challenges_faced": meta.get("challenges_faced"),
            "lessons_learned": meta.get("lessons_learned"),
            "manager_would_say": meta.get("manager_would_say"),
            "reports_would_say": meta.get("reports_would_say"),
        }

        # Remove None values to avoid overwriting existing data with nulls
        row = {k: v for k, v in row.items() if v is not None}

        label = f"{row['company_name']} / {row['title']}"

        if dry_run:
            bullet_count = len(row.get("bullet_points", []))
            print(f"  [DRY RUN] Would upsert experience: {label} ({bullet_count} bullets)")
            synced += 1
            continue

        # Upsert by ob_thought_id
        existing = (
            sb.table("experiences")
            .select("id")
            .eq("ob_thought_id", thought["id"])
            .execute()
        )

        if existing.data:
            sb.table("experiences").update(row).eq("ob_thought_id", thought["id"]).execute()
            action = "Updated"
        else:
            sb.table("experiences").insert(row).execute()
            action = "Inserted"

        print(f"  ✓ {action} experience: {label}")
        synced += 1

    return synced


# ──────────────────────────────────────────────────────────────────────────
# Sync: career-skill thoughts → skills
# ──────────────────────────────────────────────────────────────────────────

def sync_skills(sb, thoughts: list, profile: dict, dry_run: bool, verbose: bool) -> int:
    """Upsert skill rows, keyed by ob_thought_id."""
    skill_thoughts = [t for t in thoughts if t["metadata"].get("type") == "career-skill"]

    if not skill_thoughts:
        if verbose:
            print("  No career-skill thoughts found")
        return 0

    synced = 0
    for thought in skill_thoughts:
        meta = thought["metadata"]
        content = thought["content"].strip()

        row = {
            "candidate_id": profile["id"],
            "ob_thought_id": thought["id"],
            "skill_name": meta.get("skill_name", "Unknown Skill"),
            "category": meta.get("category", "moderate"),
            "self_rating": meta.get("self_rating"),
            "honest_notes": meta.get("honest_notes"),
            "years_experience": meta.get("years_experience"),
            "evidence": content if content else None,
        }

        row = {k: v for k, v in row.items() if v is not None}

        label = f"{row['skill_name']} ({row.get('category', '?')})"

        if dry_run:
            print(f"  [DRY RUN] Would upsert skill: {label}")
            synced += 1
            continue

        existing = (
            sb.table("skills")
            .select("id")
            .eq("ob_thought_id", thought["id"])
            .execute()
        )

        if existing.data:
            sb.table("skills").update(row).eq("ob_thought_id", thought["id"]).execute()
            action = "Updated"
        else:
            sb.table("skills").insert(row).execute()
            action = "Inserted"

        print(f"  ✓ {action} skill: {label}")
        synced += 1

    return synced


# ──────────────────────────────────────────────────────────────────────────
# Sync: career-gap thoughts → gaps_weaknesses
# ──────────────────────────────────────────────────────────────────────────

def sync_gaps(sb, thoughts: list, profile: dict, dry_run: bool, verbose: bool) -> int:
    """Upsert gap rows, keyed by ob_thought_id."""
    gap_thoughts = [t for t in thoughts if t["metadata"].get("type") == "career-gap"]

    if not gap_thoughts:
        if verbose:
            print("  No career-gap thoughts found")
        return 0

    synced = 0
    for thought in gap_thoughts:
        meta = thought["metadata"]
        description, why = parse_gap_content(thought["content"])

        row = {
            "candidate_id": profile["id"],
            "ob_thought_id": thought["id"],
            "description": description,
            "why_its_a_gap": why if why else None,
            "gap_type": meta.get("gap_type", "skill"),
            "interest_in_learning": bool(meta.get("interest_in_learning", False)),
        }

        row = {k: v for k, v in row.items() if v is not None}

        label = description[:60] + ("..." if len(description) > 60 else "")

        if dry_run:
            print(f"  [DRY RUN] Would upsert gap: {label}")
            synced += 1
            continue

        existing = (
            sb.table("gaps_weaknesses")
            .select("id")
            .eq("ob_thought_id", thought["id"])
            .execute()
        )

        if existing.data:
            sb.table("gaps_weaknesses").update(row).eq("ob_thought_id", thought["id"]).execute()
            action = "Updated"
        else:
            sb.table("gaps_weaknesses").insert(row).execute()
            action = "Inserted"

        print(f"  ✓ {action} gap: {label}")
        synced += 1

    return synced


# ──────────────────────────────────────────────────────────────────────────
# Sync: career-faq thoughts → faq_responses
# ──────────────────────────────────────────────────────────────────────────

def sync_faqs(sb, thoughts: list, profile: dict, dry_run: bool, verbose: bool) -> int:
    """Upsert FAQ rows, keyed by ob_thought_id."""
    faq_thoughts = [t for t in thoughts if t["metadata"].get("type") == "career-faq"]

    if not faq_thoughts:
        if verbose:
            print("  No career-faq thoughts found")
        return 0

    synced = 0
    for thought in faq_thoughts:
        meta = thought["metadata"]
        content = thought["content"].strip()

        row = {
            "candidate_id": profile["id"],
            "ob_thought_id": thought["id"],
            "question": meta.get("question", ""),
            "answer": content,
            "display_order": int(meta.get("display_order", 99)),
            "is_common_question": bool(meta.get("is_common_question", False)),
        }

        if not row["question"]:
            print(f"  WARNING: career-faq thought {thought['id']} has no 'question' in metadata — skipping")
            continue

        row = {k: v for k, v in row.items() if v is not None}

        label = row["question"][:60] + ("..." if len(row["question"]) > 60 else "")

        if dry_run:
            print(f"  [DRY RUN] Would upsert FAQ: {label}")
            synced += 1
            continue

        existing = (
            sb.table("faq_responses")
            .select("id")
            .eq("ob_thought_id", thought["id"])
            .execute()
        )

        if existing.data:
            sb.table("faq_responses").update(row).eq("ob_thought_id", thought["id"]).execute()
            action = "Updated"
        else:
            sb.table("faq_responses").insert(row).execute()
            action = "Inserted"

        print(f"  ✓ {action} FAQ: {label}")
        synced += 1

    return synced


# ──────────────────────────────────────────────────────────────────────────
# Sync: career-instruction thoughts → ai_instructions
# ──────────────────────────────────────────────────────────────────────────

def sync_instructions(sb, thoughts: list, profile: dict, dry_run: bool, verbose: bool) -> int:
    """Upsert AI instruction rows, keyed by ob_thought_id."""
    instr_thoughts = [t for t in thoughts if t["metadata"].get("type") == "career-instruction"]

    if not instr_thoughts:
        if verbose:
            print("  No career-instruction thoughts found")
        return 0

    synced = 0
    for thought in instr_thoughts:
        meta = thought["metadata"]
        content = thought["content"].strip()

        row = {
            "candidate_id": profile["id"],
            "ob_thought_id": thought["id"],
            "instruction": content,
            "instruction_type": meta.get("instruction_type", "other"),
            "priority": int(meta.get("priority", 0)),
        }

        label = content[:60] + ("..." if len(content) > 60 else "")

        if dry_run:
            print(f"  [DRY RUN] Would upsert instruction: {label}")
            synced += 1
            continue

        existing = (
            sb.table("ai_instructions")
            .select("id")
            .eq("ob_thought_id", thought["id"])
            .execute()
        )

        if existing.data:
            sb.table("ai_instructions").update(row).eq("ob_thought_id", thought["id"]).execute()
            action = "Updated"
        else:
            sb.table("ai_instructions").insert(row).execute()
            action = "Inserted"

        print(f"  ✓ {action} instruction: {label}")
        synced += 1

    return synced


# ──────────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────────

def print_stats(sb):
    """Print counts of career data currently in Supabase."""
    tables = [
        ("candidate_profile", None),
        ("experiences", None),
        ("skills", "category"),
        ("gaps_weaknesses", None),
        ("faq_responses", None),
        ("ai_instructions", None),
    ]

    print("\n── Career site data (Supabase) ──────────────────────────")
    for table, group_by in tables:
        result = sb.table(table).select("id", count="exact").execute()
        count = result.count if result.count is not None else len(result.data or [])
        print(f"  {table}: {count} rows")

        if group_by and result.data:
            from collections import Counter
            categories = Counter(row.get(group_by) for row in result.data)
            for cat, n in sorted(categories.items()):
                print(f"    {cat}: {n}")

    # OB career thoughts
    print()
    sb2 = sb  # same client
    result = sb2.table("thoughts").select("id, metadata").execute()
    if result.data:
        from collections import Counter
        types = Counter(
            t["metadata"].get("type", "")
            for t in result.data
            if t.get("metadata") and t["metadata"].get("type", "").startswith("career-")
        )
        print("── Career thoughts in OB ────────────────────────────────")
        if types:
            for t, n in sorted(types.items()):
                print(f"  {t}: {n}")
        else:
            print("  (none yet — capture career thoughts to OB to populate)")
    print()


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────

SYNC_TYPES = ["profile", "experience", "skill", "gap", "faq", "instruction"]


def main():
    parser = argparse.ArgumentParser(
        description="Sync career-* OB thoughts to ai-resume Supabase tables"
    )
    parser.add_argument(
        "--type",
        choices=SYNC_TYPES,
        default=None,
        help="Sync only this type (default: all types)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without writing anything",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Extra logging",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print career data counts and exit",
    )
    args = parser.parse_args()

    env_path = find_and_load_env()
    sb = get_supabase_client()

    if args.stats:
        print_stats(sb)
        return

    started = datetime.now(timezone.utc)
    print(f"\n{'='*60}")
    print(f"sync_career_from_ob.py — {started.strftime('%Y-%m-%d %H:%M UTC')}")
    if args.dry_run:
        print("  MODE: DRY RUN (no writes)")
    print(f"  Env loaded from: {env_path}")
    print(f"{'='*60}\n")

    # Fetch all career thoughts (or just the type we need)
    print(f"Fetching career thoughts from OB...")
    all_thoughts = fetch_career_thoughts(
        sb,
        career_type=args.type,
        verbose=args.verbose,
    )
    print(f"Found {len(all_thoughts)} career thought(s)\n")

    if not all_thoughts:
        print("Nothing to sync. Capture career-* thoughts to OB first.")
        print("See the docstring at the top of this file for the metadata schema.")
        return

    # Get or create the single candidate_profile row
    print("Resolving candidate_profile row...")
    profile = get_or_create_profile(sb, dry_run=args.dry_run, verbose=args.verbose)
    print()

    # Run each sync function
    total = 0
    run_all = args.type is None

    if run_all or args.type == "profile":
        print("── career-profile → candidate_profile ──────────────────")
        total += sync_profile(sb, all_thoughts, profile, args.dry_run, args.verbose)
        print()

    if run_all or args.type == "experience":
        print("── career-experience → experiences ─────────────────────")
        total += sync_experiences(sb, all_thoughts, profile, args.dry_run, args.verbose)
        print()

    if run_all or args.type == "skill":
        print("── career-skill → skills ────────────────────────────────")
        total += sync_skills(sb, all_thoughts, profile, args.dry_run, args.verbose)
        print()

    if run_all or args.type == "gap":
        print("── career-gap → gaps_weaknesses ─────────────────────────")
        total += sync_gaps(sb, all_thoughts, profile, args.dry_run, args.verbose)
        print()

    if run_all or args.type == "faq":
        print("── career-faq → faq_responses ───────────────────────────")
        total += sync_faqs(sb, all_thoughts, profile, args.dry_run, args.verbose)
        print()

    if run_all or args.type == "instruction":
        print("── career-instruction → ai_instructions ─────────────────")
        total += sync_instructions(sb, all_thoughts, profile, args.dry_run, args.verbose)
        print()

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"{'='*60}")
    print(f"Done. {total} item(s) synced in {elapsed:.1f}s")
    if args.dry_run:
        print("(DRY RUN — no data was written)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

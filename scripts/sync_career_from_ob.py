#!/usr/bin/env python3
"""
sync_career_from_ob.py — v2
Reads career data from OpenBrain and syncs to the ai-resume Supabase tables.

──────────────────────────────────────────────────────────────────────────
TWO MODES
──────────────────────────────────────────────────────────────────────────

MODE 1 — STRUCTURED SYNC (default)
  Reads thoughts where metadata.type starts with "career-".
  Fast, deterministic, idempotent. Use for ongoing additions after bootstrap.

  Type tags and their target tables:
    career-profile     → candidate_profile fields
    career-skill       → skills
    career-gap         → gaps_weaknesses
    career-faq         → faq_responses
    career-instruction → ai_instructions

MODE 2 — EXTRACT (--extract)
  Reads all OB thoughts tagged ai-resume-source, sends to Claude, and
  extracts structured data into all career tables. Run after schema
  migrations or after a significant batch of new Interview Agent sessions.
  Safe to re-run — all upserts are keyed and idempotent (accomplishments,
  people_engagements, and story_roles are delete-and-reinsert per parent).

──────────────────────────────────────────────────────────────────────────
USAGE
──────────────────────────────────────────────────────────────────────────
  python3 scripts/sync_career_from_ob.py --per-thought           # per-thought extract (recommended)
  python3 scripts/sync_career_from_ob.py --per-thought --dry-run # preview (still calls Claude)
  python3 scripts/sync_career_from_ob.py --extract               # legacy 4-pass bulk extract
  python3 scripts/sync_career_from_ob.py                         # mode 1 structured sync
  python3 scripts/sync_career_from_ob.py --stats                 # table counts
"""

import sys
import os
import json
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path


# ── Environment ───────────────────────────────────────────────────────────────

def find_and_load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv not installed.  pip3 install python-dotenv")
        sys.exit(1)
    search_paths = [
        Path.home() / "Code/AI/open_brain/.env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / ".env.local",
    ]
    loaded = []
    for p in search_paths:
        if p.exists():
            load_dotenv(p, override=True)
            loaded.append(str(p))
    return ", ".join(loaded) if loaded else "environment"


# ── Clients ───────────────────────────────────────────────────────────────────

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


# ── Fetch helpers ─────────────────────────────────────────────────────────────

def fetch_biographical_thoughts(sb, verbose=False):
    """Fetch all OB thoughts tagged ai-resume-source."""
    page_size = 1000
    offset = 0
    all_thoughts = []
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
            if "ai-resume-source" in meta.get("topics", []):
                all_thoughts.append(t)
        if len(batch) < page_size:
            break
        offset += page_size
    if verbose:
        print(f"  Fetched {len(all_thoughts)} biographical/career thoughts from OB")
    return all_thoughts


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


# ── Profile helpers ───────────────────────────────────────────────────────────

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


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_date(date_str):
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}$', date_str):
        return f"{date_str}-01"
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    return None


def parse_bullet_points(content):
    lines = content.strip().splitlines()
    bullets = []
    for line in lines:
        line = line.strip()
        if line.startswith(("- ", "• ")):
            bullets.append(line[2:].strip())
        elif line and not line.startswith("#"):
            bullets.append(line)
    return [b for b in bullets if b]


def parse_array_field(content):
    content = content.strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if x]
    except json.JSONDecodeError:
        pass
    return [x.strip() for x in content.split(",") if x.strip()]


def parse_gap_content(content):
    parts = re.split(r'\n\s*\n', content.strip(), maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


# ── Extract system prompts (3 focused passes to stay within token limits) ─────

_EXTRACT_RULES = """CRITICAL RULES:
- Use first-person voice for all narrative text fields
- Dates use YYYY-MM format; use best estimates from context clues
- Company name for Brett's high school is "Indian Hill High School" (not "Cincinnati Public Schools")
- stint_index is 1 for the first time at a company, 2 for a return stint
- Output ONLY valid JSON — no markdown, no backticks, no commentary
- Each thought in the corpus has a full UUID in its header like [Thought abc12345-... — ...]. For source_thought_id,
  copy the full UUID exactly as shown in the header for the thought that is the PRIMARY source for that item.
  If an item draws from multiple thoughts, pick the one with the most relevant/specific content."""

EXTRACT_SYSTEM_PASS1 = f"""You are extracting career profile and work history from biographical interview notes about Brett Coryell.
{_EXTRACT_RULES}

OUTPUT SCHEMA (output ONLY this JSON, nothing else):
{{
  "profile": {{
    "elevator_pitch": "2-3 sentence first-person pitch",
    "career_narrative": "4-6 sentence career arc and through-line",
    "looking_for": "What kinds of roles Brett is actively pursuing",
    "not_looking_for": "What to explicitly rule out",
    "target_titles": ["CAIO", "CIO", "CISO", "COO", "Board Advisor"],
    "target_company_stages": ["enterprise", "private-equity-backed", "board-seat"]
  }},
  "employers": [
    {{
      "company_name": "Company Name",
      "stint_index": 1,
      "industry": "Industry sector",
      "display_order": 1,
      "source_thought_id": "full-uuid-of-primary-source-thought",
      "roles": [
        {{
          "title": "Most senior title held",
          "title_progression": "Director -> VP -> SVP (null if no progression)",
          "start_date": "YYYY-MM",
          "end_date": "YYYY-MM (null if current)",
          "is_current": false,
          "display_order": 1,
          "why_joined": "Private: candid reason for taking this role",
          "why_left": "Private: candid reason for leaving",
          "actual_contributions": "Private: what I actually did day-to-day beyond the bullets",
          "proudest_achievement": "Private: the one thing I am most proud of here",
          "manager_would_say": "Private: what my boss would say about me in this role",
          "reports_would_say": "Private: what my team would say about working for me",
          "accomplishments": [
            {{ "content": "Achievement statement with metric where available", "has_metric": true, "display_order": 1 }}
          ]
        }}
      ]
    }}
  ]
}}"""

EXTRACT_SYSTEM_PASS2A = f"""You are extracting named people from biographical interview notes about Brett Coryell.
{_EXTRACT_RULES}
- relationship MUST be exactly one of: "manager", "report", "peer", "mentor", "client", "other"
- Extract every named individual who appears in the source material and matters to Brett's career story.
- A person may have multiple engagements (worked together at multiple employers or in multiple roles).

OUTPUT SCHEMA (output ONLY this JSON, nothing else):
{{
  "people": [
    {{
      "name": "Full Name",
      "general_note": "Who this person is and their overall significance to Brett's career",
      "source_thought_id": "full-uuid-of-primary-source-thought",
      "engagements": [
        {{
          "employer_name": "Company Name where we worked together (null if no company context)",
          "role_title": "Brett's role title during this engagement (null if not applicable)",
          "relationship": "manager",
          "note": "Private: specific context about this person in this engagement"
        }}
      ]
    }}
  ]
}}"""

EXTRACT_SYSTEM_PASS2B = f"""You are extracting career stories from biographical interview notes about Brett Coryell.
{_EXTRACT_RULES}
- link_type MUST be exactly one of: "origin", "application", "taught", "reference"
  - origin: where Brett first learned or encountered the lesson/skill
  - application: where Brett applied it himself independently
  - taught: where Brett explicitly taught it to others
  - reference: looser cross-reference to another employer/role
- Extract 10-20 significant named stories — memorable situations, turning points, demonstrations of leadership or judgment.

OUTPUT SCHEMA (output ONLY this JSON, nothing else):
{{
  "stories": [
    {{
      "title": "Short memorable name for this story",
      "situation": "What was the context and challenge",
      "task": "What was Brett specifically responsible for",
      "action": "What Brett did — specific actions taken",
      "result": "What happened — outcomes with metrics if possible",
      "tags": ["tag1", "tag2"],
      "source_thought_id": "full-uuid-of-primary-source-thought",
      "primary_employer": "Company Name where story primarily occurred (null if none)",
      "primary_role_title": "Brett's role title during this story (null if none)",
      "role_links": [
        {{
          "employer_name": "Company Name",
          "role_title": "Brett's role title (null if general to the employer)",
          "link_type": "origin"
        }}
      ]
    }}
  ]
}}"""

EXTRACT_SYSTEM_PASS3 = f"""You are extracting skills, gaps, AI instructions, and FAQ responses from biographical interview notes about Brett Coryell.
{_EXTRACT_RULES}
- Skills: extract 25-35 specific discrete skills. category MUST be exactly "strong", "moderate", or "gap".
  Never use "developing", "advanced", or any other category value.
  Use "gap" only for genuine acknowledged weaknesses.
- Gaps: gap_type MUST be exactly one of: "skill", "experience", "environment", "role_type"
- For faq_responses: if multiple versions of an answer exist (v1, v2, REVISED, etc.), use the most recent version only.

OUTPUT SCHEMA (output ONLY this JSON, nothing else):
{{
  "skills": [
    {{
      "skill_name": "Specific skill name",
      "category": "strong",
      "honest_notes": "Private candid note — where this is strong or where it has limits",
      "source_thought_id": "full-uuid-of-primary-source-thought"
    }}
  ],
  "gaps": [
    {{
      "gap_type": "skill",
      "description": "Short description of the gap",
      "why_its_a_gap": "Honest explanation",
      "interest_in_learning": true,
      "source_thought_id": "full-uuid-of-primary-source-thought"
    }}
  ],
  "ai_instructions": [
    {{
      "instruction_type": "honesty",
      "priority": 10,
      "instruction": "Specific instruction for how the AI should respond about Brett",
      "source_thought_id": "full-uuid-of-primary-source-thought"
    }}
  ],
  "faq_responses": [
    {{
      "question": "Tell me about yourself",
      "answer": "Complete pre-written answer — latest version verbatim",
      "is_common_question": true,
      "display_order": 1,
      "source_thought_id": "full-uuid-of-primary-source-thought"
    }}
  ]
}}"""


# ── Per-thought extraction prompt (used by --per-thought mode) ────────────────

EXTRACT_SYSTEM_PER_THOUGHT = f"""You are extracting career data from a SINGLE biographical thought about Brett Coryell.
{_EXTRACT_RULES}

SCOPE — extract ONLY what is explicitly stated or directly implied in this one thought.
Do NOT synthesize from career knowledge absent in the text.
Do NOT invent dates, metrics, or context not present.
If a section has nothing to extract, return an empty array [].

source_thought_id: always copy the UUID from the thought header exactly as shown.

OUTPUT SCHEMA — return a JSON object (all sections optional, use [] if empty):
{{
  "employers": [
    {{
      "company_name": "Company Name",
      "stint_index": 1,
      "industry": "Industry sector (if mentioned)",
      "display_order": 1,
      "source_thought_id": "COPY-UUID-FROM-THOUGHT-HEADER",
      "roles": [
        {{
          "title": "Most senior title held",
          "title_progression": "null or e.g. Director -> VP -> SVP",
          "start_date": "YYYY-MM",
          "end_date": "YYYY-MM",
          "is_current": false,
          "display_order": 1,
          "why_joined": "First-person candid reason for taking this role",
          "why_left": "First-person candid reason for leaving",
          "actual_contributions": "What I actually did day-to-day",
          "proudest_achievement": "The one thing I am most proud of here",
          "manager_would_say": "What my boss would say about me in this role",
          "reports_would_say": "What my team would say about working for me",
          "accomplishments": [
            {{"content": "Achievement with metric if available", "has_metric": true, "display_order": 1}}
          ]
        }}
      ]
    }}
  ],
  "people": [
    {{
      "name": "Full Name",
      "general_note": "Who this person is and significance to Brett's career",
      "source_thought_id": "COPY-UUID-FROM-THOUGHT-HEADER",
      "engagements": [
        {{
          "employer_name": "Company where we worked together (null if none)",
          "role_title": "Brett's role title during this engagement (null if unknown)",
          "relationship": "manager|report|peer|mentor|client|other",
          "note": "Specific context about this person in this engagement"
        }}
      ]
    }}
  ],
  "stories": [
    {{
      "title": "Short memorable name for this story",
      "situation": "What was the context and challenge",
      "task": "What Brett was specifically responsible for",
      "action": "What Brett did — specific actions taken",
      "result": "Outcomes with metrics if possible",
      "tags": ["tag1", "tag2"],
      "source_thought_id": "COPY-UUID-FROM-THOUGHT-HEADER",
      "primary_employer": "Company Name where story primarily occurred (null if none)",
      "primary_role_title": "Brett's role title during this story (null if none)",
      "role_links": [
        {{
          "employer_name": "Company Name",
          "role_title": "Brett's role title",
          "link_type": "origin|application|taught|reference"
        }}
      ]
    }}
  ],
  "skills": [
    {{
      "skill_name": "Specific skill name",
      "category": "strong|moderate|gap",
      "honest_notes": "Candid note on where it's strong or has limits",
      "source_thought_id": "COPY-UUID-FROM-THOUGHT-HEADER"
    }}
  ],
  "gaps": [
    {{
      "gap_type": "skill|experience|environment|role_type",
      "description": "Short description of the gap",
      "why_its_a_gap": "Honest explanation",
      "interest_in_learning": true,
      "source_thought_id": "COPY-UUID-FROM-THOUGHT-HEADER"
    }}
  ],
  "ai_instructions": [
    {{
      "instruction_type": "honesty|tone|boundaries|other",
      "priority": 10,
      "instruction": "Specific instruction for how AI should respond about Brett",
      "source_thought_id": "COPY-UUID-FROM-THOUGHT-HEADER"
    }}
  ],
  "faq_responses": [
    {{
      "question": "Interview question",
      "answer": "Complete pre-written answer verbatim",
      "is_common_question": true,
      "display_order": 1,
      "source_thought_id": "COPY-UUID-FROM-THOUGHT-HEADER"
    }}
  ]
}}"""


# ── Extract upsert helpers ────────────────────────────────────────────────────

def upsert_employer(sb, candidate_id, company_name, stint_index, industry, display_order, dry_run, ob_thought_id=None):
    label = f"{company_name} (stint {stint_index})"
    if dry_run:
        print(f"  [DRY RUN] employer: {label}")
        return None
    existing = (
        sb.table("employers")
        .select("id")
        .eq("candidate_id", candidate_id)
        .eq("company_name", company_name)
        .eq("stint_index", stint_index)
        .execute()
    )
    row = {
        "candidate_id": candidate_id,
        "company_name": company_name,
        "stint_index": stint_index,
        "display_order": display_order,
    }
    if industry:
        row["industry"] = industry
    if ob_thought_id:
        row["ob_thought_id"] = ob_thought_id
    if existing.data:
        eid = existing.data[0]["id"]
        sb.table("employers").update(row).eq("id", eid).execute()
        print(f"  ✓ Updated employer: {label}")
        return eid
    else:
        result = sb.table("employers").insert(row).execute()
        eid = result.data[0]["id"]
        print(f"  ✓ Inserted employer: {label}")
        return eid


def upsert_role(sb, employer_id, role_data, dry_run, ob_thought_id=None):
    title = role_data.get("title", "Unknown")
    label = title
    row = {k: v for k, v in {
        "employer_id": employer_id,
        "title": title,
        "title_progression": role_data.get("title_progression") or None,
        "start_date": parse_date(role_data.get("start_date")),
        "end_date": parse_date(role_data.get("end_date")),
        "is_current": bool(role_data.get("is_current", False)),
        "display_order": role_data.get("display_order"),
        "why_joined": role_data.get("why_joined") or None,
        "why_left": role_data.get("why_left") or None,
        "actual_contributions": role_data.get("actual_contributions") or None,
        "proudest_achievement": role_data.get("proudest_achievement") or None,
        "manager_would_say": role_data.get("manager_would_say") or None,
        "reports_would_say": role_data.get("reports_would_say") or None,
        "ob_thought_id": ob_thought_id or None,
    }.items() if v is not None}

    if dry_run:
        print(f"    [DRY RUN] role: {label}")
        return None
    existing = (
        sb.table("roles")
        .select("id")
        .eq("employer_id", employer_id)
        .eq("title", title)
        .execute()
    )
    if existing.data:
        rid = existing.data[0]["id"]
        sb.table("roles").update(row).eq("id", rid).execute()
        print(f"    ✓ Updated role: {label}")
        return rid
    else:
        result = sb.table("roles").insert(row).execute()
        rid = result.data[0]["id"]
        print(f"    ✓ Inserted role: {label}")
        return rid


def replace_accomplishments(sb, role_id, accomplishments, dry_run, ob_thought_id=None):
    if dry_run:
        print(f"      [DRY RUN] {len(accomplishments)} accomplishments")
        return
    sb.table("accomplishments").delete().eq("role_id", role_id).execute()
    if not accomplishments:
        return
    rows = [
        {k: v for k, v in {
            "role_id": role_id,
            "content": a.get("content", ""),
            "has_metric": bool(a.get("has_metric", False)),
            "display_order": a.get("display_order", i + 1),
            "ob_thought_id": ob_thought_id or None,
        }.items() if v is not None}
        for i, a in enumerate(accomplishments)
        if a.get("content")
    ]
    if rows:
        sb.table("accomplishments").insert(rows).execute()
        print(f"      ✓ {len(rows)} accomplishments")


def upsert_person(sb, candidate_id, name, general_note, dry_run, ob_thought_id=None):
    if dry_run:
        print(f"  [DRY RUN] person: {name}")
        return None
    row = {"candidate_id": candidate_id, "name": name}
    if general_note:
        row["general_note"] = general_note
    if ob_thought_id:
        row["ob_thought_id"] = ob_thought_id
    existing = (
        sb.table("people")
        .select("id")
        .eq("candidate_id", candidate_id)
        .eq("name", name)
        .execute()
    )
    if existing.data:
        pid = existing.data[0]["id"]
        sb.table("people").update(row).eq("id", pid).execute()
        print(f"  ✓ Updated person: {name}")
        return pid
    else:
        result = sb.table("people").insert(row).execute()
        pid = result.data[0]["id"]
        print(f"  ✓ Inserted person: {name}")
        return pid


def replace_person_engagements(sb, person_id, engagements, employer_map, role_map, dry_run):
    if dry_run:
        print(f"    [DRY RUN] {len(engagements)} engagements")
        return
    sb.table("people_engagements").delete().eq("person_id", person_id).execute()
    rows = []
    for eng in engagements:
        emp_name = eng.get("employer_name")
        role_title = eng.get("role_title")
        employer_id = employer_map.get(emp_name) if emp_name else None
        role_id = role_map.get((emp_name, role_title)) if (emp_name and role_title) else None
        row = {"person_id": person_id}
        if employer_id:
            row["employer_id"] = employer_id
        if role_id:
            row["role_id"] = role_id
        if eng.get("relationship"):
            row["relationship"] = eng["relationship"]
        if eng.get("note"):
            row["note"] = eng["note"]
        rows.append(row)
    if rows:
        sb.table("people_engagements").insert(rows).execute()
        print(f"    ✓ {len(rows)} engagements")


# ── Per-thought helpers (append-only — no delete, since we wipe first) ────────

def _resolve_employer_id(sb, candidate_id, employer_map, company_name):
    """Check memory map → DB → return None if not found."""
    if not company_name:
        return None
    if company_name in employer_map:
        return employer_map[company_name]
    res = (
        sb.table("employers")
        .select("id")
        .eq("candidate_id", candidate_id)
        .eq("company_name", company_name)
        .execute()
    )
    if res.data:
        eid = res.data[0]["id"]
        employer_map[company_name] = eid
        return eid
    return None


def _resolve_role_id(sb, employer_id, role_map, company_name, role_title):
    """Check memory map → DB → return None if not found."""
    if not employer_id or not role_title:
        return None
    key = (company_name, role_title)
    if key in role_map:
        return role_map[key]
    res = (
        sb.table("roles")
        .select("id")
        .eq("employer_id", employer_id)
        .eq("title", role_title)
        .execute()
    )
    if res.data:
        rid = res.data[0]["id"]
        role_map[key] = rid
        return rid
    return None


def add_accomplishments_for_thought(sb, role_id, accomplishments, ob_thought_id, dry_run):
    """Append accomplishments from one thought. Does not delete existing rows."""
    if dry_run:
        print(f"      [DRY RUN] +{len(accomplishments)} accomplishments")
        return
    rows = [
        {k: v for k, v in {
            "role_id": role_id,
            "content": a.get("content", ""),
            "has_metric": bool(a.get("has_metric", False)),
            "display_order": a.get("display_order", i + 1),
            "ob_thought_id": ob_thought_id,
        }.items() if v is not None}
        for i, a in enumerate(accomplishments)
        if a.get("content")
    ]
    if rows:
        sb.table("accomplishments").insert(rows).execute()
        print(f"      ✓ +{len(rows)} accomplishments")


def add_engagements_for_thought(sb, candidate_id, person_id, engagements,
                                 employer_map, role_map, dry_run):
    """Append person engagements from one thought. Does not delete existing rows."""
    if dry_run:
        print(f"    [DRY RUN] +{len(engagements)} engagements")
        return
    rows = []
    for eng in engagements:
        emp_name = eng.get("employer_name")
        role_title = eng.get("role_title")
        employer_id = _resolve_employer_id(sb, candidate_id, employer_map, emp_name)
        role_id = _resolve_role_id(sb, employer_id, role_map, emp_name, role_title)
        row = {"person_id": person_id}
        if employer_id:
            row["employer_id"] = employer_id
        if role_id:
            row["role_id"] = role_id
        if eng.get("relationship"):
            row["relationship"] = eng["relationship"]
        if eng.get("note"):
            row["note"] = eng["note"]
        rows.append(row)
    if rows:
        sb.table("people_engagements").insert(rows).execute()
        print(f"    ✓ +{len(rows)} engagements")


def upsert_story(sb, candidate_id, story_data, employer_map, role_map, dry_run, ob_thought_id=None):
    title = story_data.get("title", "Untitled")
    prim_emp = story_data.get("primary_employer")
    prim_role = story_data.get("primary_role_title")
    primary_employer_id = _resolve_employer_id(sb, candidate_id, employer_map, prim_emp)
    primary_role_id = _resolve_role_id(sb, primary_employer_id, role_map, prim_emp, prim_role)

    row = {k: v for k, v in {
        "candidate_id": candidate_id,
        "title": title,
        "situation": story_data.get("situation") or None,
        "task": story_data.get("task") or None,
        "action": story_data.get("action") or None,
        "result": story_data.get("result") or None,
        "tags": story_data.get("tags") or None,
        "primary_employer_id": primary_employer_id,
        "primary_role_id": primary_role_id,
        "ob_thought_id": ob_thought_id or None,
    }.items() if v is not None}

    if dry_run:
        print(f"  [DRY RUN] story: {title}")
        return None
    existing = (
        sb.table("stories")
        .select("id")
        .eq("candidate_id", candidate_id)
        .eq("title", title)
        .execute()
    )
    if existing.data:
        sid = existing.data[0]["id"]
        sb.table("stories").update(row).eq("id", sid).execute()
        print(f"  ✓ Updated story: {title}")
    else:
        result = sb.table("stories").insert(row).execute()
        sid = result.data[0]["id"]
        print(f"  ✓ Inserted story: {title}")

    # Replace story_roles
    sb.table("story_roles").delete().eq("story_id", sid).execute()
    role_links = story_data.get("role_links", [])
    link_rows = []
    for link in role_links:
        emp_name = link.get("employer_name")
        role_title = link.get("role_title")
        employer_id = _resolve_employer_id(sb, candidate_id, employer_map, emp_name)
        role_id = _resolve_role_id(sb, employer_id, role_map, emp_name, role_title)
        link_row = {"story_id": sid, "link_type": link.get("link_type", "reference")}
        if employer_id:
            link_row["employer_id"] = employer_id
        if role_id:
            link_row["role_id"] = role_id
        link_rows.append(link_row)
    if link_rows:
        sb.table("story_roles").insert(link_rows).execute()
        print(f"    ✓ {len(link_rows)} story role links")
    return sid


# ── Mode 1 structured sync ────────────────────────────────────────────────────

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
    VALID_GAP_TYPES = {"skill", "experience", "environment", "role_type"}
    for t in items:
        m = t["metadata"]
        desc, why = parse_gap_content(t["content"])
        gap_type = m.get("gap_type", "skill")
        if gap_type not in VALID_GAP_TYPES:
            gap_type = "skill"
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
    VALID_TYPES = {"honesty", "tone", "boundaries", "other"}
    for t in items:
        m = t["metadata"]
        content = t["content"].strip()
        instr_type = m.get("instruction_type", "other")
        if instr_type not in VALID_TYPES:
            instr_type = "other"
        row = {
            "candidate_id": profile["id"],
            "ob_thought_id": t["id"],
            "instruction": content,
            "instruction_type": instr_type,
            "priority": int(m.get("priority", 0)),
        }
        _upsert_by_ob_id(sb, "ai_instructions", row, t["id"], dry_run, content[:60])
    return len(items)


# ── Mode 2 — Extract (3-pass) ─────────────────────────────────────────────────

def _claude_extract(anthropic_client, system_prompt, corpus, pass_label):
    """Single Claude extraction call. Returns parsed dict or None on failure."""
    print(f"  [{pass_label}] Sending to Claude ({len(corpus):,} chars)...")
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16384,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"Extract the requested data from these OpenBrain biographical thoughts:\n\n{corpus}"
        }]
    )
    raw = response.content[0].text if response.content[0].type == "text" else "{}"
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        # raw_decode stops at the first valid JSON object, ignoring any trailing text/commentary
        result, _ = json.JSONDecoder().raw_decode(cleaned)
        return result
    except json.JSONDecodeError as e:
        print(f"  ERROR [{pass_label}]: Claude returned invalid JSON: {e}")
        print(f"  First 500 chars: {raw[:500]}")
        return None


def _claude_extract_thought(anthropic_client, thought, idx=None, total=None):
    """Extract career data from a single OB thought using a cached system prompt."""
    meta = thought.get("metadata") or {}
    header = (
        f"[Thought {thought['id']} — {meta.get('type', 'unknown')} | "
        f"Topics: {', '.join(meta.get('topics', []))} | "
        f"{thought.get('created_at', '')[:10]}]"
    )
    user_content = f"{header}\n{thought['content']}"
    label = f"[{idx}/{total}]" if idx and total else ""
    print(f"  {label} {thought['id'][:8]}  ({len(user_content):,} chars)", end="", flush=True)

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=[{
                "type": "text",
                "text": EXTRACT_SYSTEM_PER_THOUGHT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"Extract career data from this biographical thought:\n\n{user_content}",
            }],
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    usage = response.usage
    cache_hit = getattr(usage, "cache_read_input_tokens", 0) > 0
    cache_tag = " [cache-hit]" if cache_hit else " [cache-miss]"
    print(cache_tag)

    raw = response.content[0].text if response.content and response.content[0].type == "text" else "{}"
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        result, _ = json.JSONDecoder().raw_decode(cleaned)
        return result
    except json.JSONDecodeError as e:
        print(f"    ERROR: invalid JSON: {e}")
        print(f"    First 300 chars: {raw[:300]}")
        return None


def run_extract_per_thought(sb, anthropic_client, dry_run, verbose, thought_ids=None):
    """
    Per-thought extraction: call Claude once per OB thought with a cached system prompt.
    Full mode (no --thought-ids): wipes extracted tables first. Use for full resyncs.
    Targeted mode (--thought-ids): skips the wipe and processes only the specified thoughts.
    """
    if thought_ids:
        print(f"── Targeted extraction: {len(thought_ids)} thought(s) — skipping wipe ──")
    else:
        if not dry_run:
            print("── Wiping extracted tables ──────────────────────────────")
            wipe_extracted_tables(sb)
            print()

    print("Fetching biographical thoughts from OB...")
    thoughts = fetch_biographical_thoughts(sb, verbose=verbose)
    if thought_ids:
        id_set = set(thought_ids)
        thoughts = [t for t in thoughts if t["id"] in id_set]
        print(f"Filtered to {len(thoughts)} targeted thought(s)\n")
    total = len(thoughts)
    print(f"Found {total} biographical thoughts\n")
    if not thoughts:
        print("No biographical thoughts found.")
        return

    profile = get_or_create_profile(sb, dry_run=dry_run, verbose=verbose)
    candidate_id = profile["id"]

    employer_map = {}   # company_name → employer_id (accumulates across thoughts)
    role_map = {}       # (company_name, title) → role_id

    stats = {
        "thoughts_ok": 0, "errors": 0,
        "employers": 0, "roles": 0, "accomplishments": 0,
        "people": 0, "stories": 0, "skills": 0,
        "gaps": 0, "instructions": 0, "faqs": 0,
    }

    VALID_SKILL_CATS = {"strong", "moderate", "gap"}
    VALID_GAP_TYPES = {"skill", "experience", "environment", "role_type"}
    VALID_INSTR_TYPES = {"honesty", "tone", "boundaries", "other"}

    for i, thought in enumerate(thoughts, 1):
        data = _claude_extract_thought(anthropic_client, thought, idx=i, total=total)
        if data is None:
            stats["errors"] += 1
            continue
        stats["thoughts_ok"] += 1
        ob_id = thought["id"]

        # ── employers / roles / accomplishments ───────────────────────────
        for emp in data.get("employers", []):
            company = emp.get("company_name") or "Unknown"
            eid = upsert_employer(
                sb, candidate_id,
                company_name=company,
                stint_index=int(emp.get("stint_index", 1)),
                industry=emp.get("industry"),
                display_order=emp.get("display_order"),
                dry_run=dry_run,
                ob_thought_id=ob_id,
            )
            if eid:
                employer_map[company] = eid
                stats["employers"] += 1
            for role in emp.get("roles", []):
                title = (role.get("title") or "").strip()
                if not title or title.lower() in ("unknown", "n/a", "null"):
                    continue
                rid = upsert_role(sb, eid, role, dry_run, ob_thought_id=ob_id)
                if rid:
                    role_map[(company, role.get("title", ""))] = rid
                    stats["roles"] += 1
                    acclist = role.get("accomplishments", [])
                    if acclist:
                        add_accomplishments_for_thought(sb, rid, acclist, ob_id, dry_run)
                        stats["accomplishments"] += len(acclist)

        # ── people + engagements ──────────────────────────────────────────
        for person in data.get("people", []):
            name = person.get("name", "").strip()
            if not name:
                continue
            pid = upsert_person(sb, candidate_id, name, person.get("general_note"),
                                dry_run, ob_thought_id=ob_id)
            if pid:
                stats["people"] += 1
                add_engagements_for_thought(
                    sb, candidate_id, pid, person.get("engagements", []),
                    employer_map, role_map, dry_run,
                )

        # ── stories ───────────────────────────────────────────────────────
        for story in data.get("stories", []):
            if not story.get("title"):
                continue
            upsert_story(sb, candidate_id, story, employer_map, role_map, dry_run,
                         ob_thought_id=ob_id)
            stats["stories"] += 1

        # ── skills ────────────────────────────────────────────────────────
        for sk in data.get("skills", []):
            cat = sk.get("category", "moderate")
            if cat not in VALID_SKILL_CATS:
                cat = "moderate"
            row = {k: v for k, v in {
                "candidate_id": candidate_id,
                "skill_name": sk.get("skill_name", "Unknown"),
                "category": cat,
                "honest_notes": sk.get("honest_notes") or None,
                "ob_thought_id": ob_id,
            }.items() if v is not None}
            if not dry_run:
                existing = (
                    sb.table("skills").select("id")
                    .eq("candidate_id", candidate_id)
                    .eq("skill_name", row["skill_name"])
                    .execute()
                )
                if existing.data:
                    sb.table("skills").update(row).eq("id", existing.data[0]["id"]).execute()
                else:
                    sb.table("skills").insert(row).execute()
            stats["skills"] += 1

        # ── gaps ──────────────────────────────────────────────────────────
        for gap in data.get("gaps", []):
            desc = gap.get("description", "")
            gap_type = gap.get("gap_type", "skill")
            if gap_type not in VALID_GAP_TYPES:
                gap_type = "skill"
            row = {k: v for k, v in {
                "candidate_id": candidate_id,
                "description": desc,
                "why_its_a_gap": gap.get("why_its_a_gap") or None,
                "gap_type": gap_type,
                "interest_in_learning": bool(gap.get("interest_in_learning", False)),
                "ob_thought_id": ob_id,
            }.items() if v is not None}
            if not dry_run:
                existing = (
                    sb.table("gaps_weaknesses").select("id")
                    .eq("candidate_id", candidate_id)
                    .eq("description", desc)
                    .execute()
                )
                if existing.data:
                    sb.table("gaps_weaknesses").update(row).eq("id", existing.data[0]["id"]).execute()
                else:
                    sb.table("gaps_weaknesses").insert(row).execute()
            stats["gaps"] += 1

        # ── ai_instructions ───────────────────────────────────────────────
        for instr in data.get("ai_instructions", []):
            text = instr.get("instruction", "")
            instr_type = instr.get("instruction_type", "other")
            if instr_type not in VALID_INSTR_TYPES:
                instr_type = "other"
            row = {k: v for k, v in {
                "candidate_id": candidate_id,
                "instruction": text,
                "instruction_type": instr_type,
                "priority": int(instr.get("priority", 0)),
                "ob_thought_id": ob_id,
            }.items() if v is not None}
            if not dry_run:
                existing = (
                    sb.table("ai_instructions").select("id")
                    .eq("candidate_id", candidate_id)
                    .eq("instruction", text)
                    .execute()
                )
                if existing.data:
                    sb.table("ai_instructions").update(row).eq("id", existing.data[0]["id"]).execute()
                else:
                    sb.table("ai_instructions").insert(row).execute()
            stats["instructions"] += 1

        # ── faq_responses ─────────────────────────────────────────────────
        for faq in data.get("faq_responses", []):
            question = faq.get("question", "")
            answer = faq.get("answer", "")
            if not question or not answer:
                continue
            row = {k: v for k, v in {
                "candidate_id": candidate_id,
                "question": question,
                "answer": answer,
                "is_common_question": bool(faq.get("is_common_question", True)),
                "display_order": int(faq.get("display_order", 99)),
                "ob_thought_id": ob_id,
            }.items() if v is not None}
            if not dry_run:
                existing = (
                    sb.table("faq_responses").select("id")
                    .eq("candidate_id", candidate_id)
                    .eq("question", question)
                    .execute()
                )
                if existing.data:
                    sb.table("faq_responses").update(row).eq("id", existing.data[0]["id"]).execute()
                else:
                    sb.table("faq_responses").insert(row).execute()
            stats["faqs"] += 1

    print(f"\n── Per-thought extraction summary ───────────────────────────")
    print(f"  thoughts: {stats['thoughts_ok']} ok / {stats['errors']} errors")
    print(f"  employers: {stats['employers']}  roles: {stats['roles']}  "
          f"accomplishments: {stats['accomplishments']}")
    print(f"  people: {stats['people']}  stories: {stats['stories']}  "
          f"skills: {stats['skills']}")
    print(f"  gaps: {stats['gaps']}  instructions: {stats['instructions']}  "
          f"faqs: {stats['faqs']}")
    print()


ALL_PASSES = ["1", "2a", "2b", "3"]


def run_extract(sb, anthropic_client, dry_run, verbose, passes=None):
    """
    passes: list of pass IDs to run, e.g. ["1", "2a", "2b", "3"].
    Defaults to all passes. Use a subset to resume after partial failure.
    Pass IDs: 1=work history, 2a=people, 2b=stories, 3=skills/gaps/faqs
    """
    if passes is None:
        passes = ALL_PASSES

    print("Fetching biographical thoughts from OB...")
    thoughts = fetch_biographical_thoughts(sb, verbose=verbose)
    print(f"Found {len(thoughts)} biographical thoughts\n")
    if not thoughts:
        print("No biographical thoughts found. Run Interview Agent sessions first.")
        return

    corpus_parts = []
    for t in thoughts:
        meta = t.get("metadata") or {}
        header = (
            f"[Thought {t['id']} — {meta.get('type', 'unknown')} | "
            f"Topics: {', '.join(meta.get('topics', []))} | "
            f"{t.get('created_at','')[:10]}]"
        )
        corpus_parts.append(f"{header}\n{t['content']}")
    corpus = "\n\n---\n\n".join(corpus_parts)

    print(f"Running passes: {', '.join(passes)} (each ~30-60s)...\n")

    p1 = p2a = p2b = p3 = None
    if "1" in passes:
        p1 = _claude_extract(anthropic_client, EXTRACT_SYSTEM_PASS1, corpus, "Pass 1: work history")
        if not p1:
            print("Pass 1 failed — aborting. Nothing written.")
            return
    if "2a" in passes:
        p2a = _claude_extract(anthropic_client, EXTRACT_SYSTEM_PASS2A, corpus, "Pass 2a: people")
    if "2b" in passes:
        p2b = _claude_extract(anthropic_client, EXTRACT_SYSTEM_PASS2B, corpus, "Pass 2b: stories")
    if "3" in passes:
        p3 = _claude_extract(anthropic_client, EXTRACT_SYSTEM_PASS3, corpus, "Pass 3: skills + gaps + faqs")

    extracted = {
        "profile":        (p1 or {}).get("profile", {}),
        "employers":      (p1 or {}).get("employers", []),
        "people":         (p2a or {}).get("people", []),
        "stories":        (p2b or {}).get("stories", []),
        "skills":         (p3 or {}).get("skills", []),
        "gaps":           (p3 or {}).get("gaps", []),
        "ai_instructions":(p3 or {}).get("ai_instructions", []),
        "faq_responses":  (p3 or {}).get("faq_responses", []),
    }

    print("\nPasses complete. Writing to career tables...\n")
    profile = get_or_create_profile(sb, dry_run=dry_run, verbose=verbose)
    candidate_id = profile["id"]

    # ── candidate_profile ─────────────────────────────────────────────────────
    p = extracted.get("profile", {})
    if p:
        profile_update = {k: v for k, v in p.items() if v}
        print(f"── candidate_profile ────────────────────────────────────")
        if dry_run:
            for k, v in profile_update.items():
                print(f"  [DRY RUN] {k}: {str(v)[:100]}")
        else:
            sb.table("candidate_profile").update(profile_update).eq("id", candidate_id).execute()
            print(f"  ✓ Updated {len(profile_update)} fields: {', '.join(profile_update.keys())}")
        print()

    # ── employers / roles / accomplishments ───────────────────────────────────
    print(f"── employers / roles / accomplishments ──────────────────────")
    employer_map = {}   # company_name → employer_id
    role_map = {}       # (company_name, title) → role_id

    for emp in extracted.get("employers", []):
        company = emp.get("company_name", "Unknown")
        emp_ob_id = emp.get("source_thought_id") or None
        eid = upsert_employer(
            sb, candidate_id,
            company_name=company,
            stint_index=int(emp.get("stint_index", 1)),
            industry=emp.get("industry"),
            display_order=emp.get("display_order"),
            dry_run=dry_run,
            ob_thought_id=emp_ob_id,
        )
        employer_map[company] = eid

        for role in emp.get("roles", []):
            rid = upsert_role(sb, eid, role, dry_run, ob_thought_id=emp_ob_id)
            role_map[(company, role.get("title", ""))] = rid
            replace_accomplishments(sb, rid, role.get("accomplishments", []), dry_run, ob_thought_id=emp_ob_id)
    print()

    # ── people + engagements ──────────────────────────────────────────────────
    print(f"── people + engagements ─────────────────────────────────────")
    for person in extracted.get("people", []):
        name = person.get("name", "")
        if not name:
            continue
        pid = upsert_person(sb, candidate_id, name, person.get("general_note"), dry_run,
                            ob_thought_id=person.get("source_thought_id") or None)
        replace_person_engagements(
            sb, pid, person.get("engagements", []), employer_map, role_map, dry_run
        )
    print()

    # ── stories + role links ──────────────────────────────────────────────────
    print(f"── stories + role links ─────────────────────────────────────")
    for story in extracted.get("stories", []):
        if not story.get("title"):
            continue
        upsert_story(sb, candidate_id, story, employer_map, role_map, dry_run,
                     ob_thought_id=story.get("source_thought_id") or None)
    print()

    # ── skills ────────────────────────────────────────────────────────────────
    skills = extracted.get("skills", [])
    print(f"── skills ({len(skills)}) ─────────────────────────────────────────")
    VALID_SKILL_CATS = {"strong", "moderate", "gap"}
    for sk in skills:
        cat = sk.get("category", "moderate")
        if cat not in VALID_SKILL_CATS:
            cat = "moderate"
        row = {k: v for k, v in {
            "candidate_id": candidate_id,
            "skill_name": sk.get("skill_name", "Unknown"),
            "category": cat,
            "honest_notes": sk.get("honest_notes") or None,
            "ob_thought_id": sk.get("source_thought_id") or None,
        }.items() if v is not None}
        label = f"{row['skill_name']} ({cat})"
        if dry_run:
            print(f"  [DRY RUN] {label}")
            continue
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

    # ── gaps_weaknesses ───────────────────────────────────────────────────────
    gaps = extracted.get("gaps", [])
    print(f"── gaps ({len(gaps)}) ───────────────────────────────────────────────")
    VALID_GAP_TYPES = {"skill", "experience", "environment", "role_type"}
    for gap in gaps:
        desc = gap.get("description", "")
        gap_type = gap.get("gap_type", "skill")
        if gap_type not in VALID_GAP_TYPES:
            gap_type = "skill"
        row = {k: v for k, v in {
            "candidate_id": candidate_id,
            "description": desc,
            "why_its_a_gap": gap.get("why_its_a_gap") or None,
            "gap_type": gap_type,
            "interest_in_learning": bool(gap.get("interest_in_learning", False)),
            "ob_thought_id": gap.get("source_thought_id") or None,
        }.items() if v is not None}
        if dry_run:
            print(f"  [DRY RUN] {desc[:60]}")
            continue
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

    # ── ai_instructions ───────────────────────────────────────────────────────
    instructions = extracted.get("ai_instructions", [])
    print(f"── ai_instructions ({len(instructions)}) ──────────────────────────")
    VALID_INSTR_TYPES = {"honesty", "tone", "boundaries", "other"}
    for instr in instructions:
        text = instr.get("instruction", "")
        instr_type = instr.get("instruction_type", "other")
        if instr_type not in VALID_INSTR_TYPES:
            instr_type = "other"
        row = {k: v for k, v in {
            "candidate_id": candidate_id,
            "instruction": text,
            "instruction_type": instr_type,
            "priority": int(instr.get("priority", 0)),
            "ob_thought_id": instr.get("source_thought_id") or None,
        }.items() if v is not None}
        if dry_run:
            print(f"  [DRY RUN] [{instr_type}] {text[:60]}")
            continue
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

    # ── faq_responses ─────────────────────────────────────────────────────────
    faqs = extracted.get("faq_responses", [])
    print(f"── faq_responses ({len(faqs)}) ────────────────────────────────────")
    for faq in faqs:
        question = faq.get("question", "")
        answer = faq.get("answer", "")
        if not question or not answer:
            continue
        row = {k: v for k, v in {
            "candidate_id": candidate_id,
            "question": question,
            "answer": answer,
            "is_common_question": bool(faq.get("is_common_question", True)),
            "display_order": int(faq.get("display_order", 99)),
            "ob_thought_id": faq.get("source_thought_id") or None,
        }.items() if v is not None}
        if dry_run:
            print(f"  [DRY RUN] Q: {question[:70]}")
            continue
        existing = (
            sb.table("faq_responses")
            .select("id")
            .eq("candidate_id", candidate_id)
            .eq("question", question)
            .execute()
        )
        if existing.data:
            sb.table("faq_responses").update(row).eq("id", existing.data[0]["id"]).execute()
            print(f"  ✓ Updated: {question[:70]}")
        else:
            sb.table("faq_responses").insert(row).execute()
            print(f"  ✓ Inserted: {question[:70]}")
    print()


# ── Stats ─────────────────────────────────────────────────────────────────────

def print_stats(sb):
    print("\n── Career tables ────────────────────────────────────────────")
    tables = [
        "candidate_profile", "employers", "roles", "accomplishments",
        "people", "people_engagements", "stories", "story_roles",
        "skills", "gaps_weaknesses", "faq_responses", "ai_instructions",
    ]
    for tbl in tables:
        try:
            r = sb.table(tbl).select("id", count="exact").execute()
            count = r.count if r.count is not None else len(r.data or [])
        except Exception:
            count = "?"
        print(f"  {tbl}: {count}")

    r = sb.table("skills").select("category").execute()
    if r.data:
        from collections import Counter
        cats = Counter(x["category"] for x in r.data)
        for cat, n in sorted(cats.items()):
            print(f"    skills.{cat}: {n}")

    r = sb.table("thoughts").select("id, metadata").execute()
    from collections import Counter
    career_types = Counter(
        t["metadata"].get("type", "")
        for t in (r.data or [])
        if t.get("metadata") and t["metadata"].get("type", "").startswith("career-")
    )
    print("\n── Structured career-* thoughts in OB ──────────────────────")
    if career_types:
        for t, n in sorted(career_types.items()):
            print(f"  {t}: {n}")
    else:
        print("  (none)")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────

SYNC_TYPES = ["profile", "skill", "gap", "faq", "instruction"]


def wipe_extracted_tables(sb):
    """Delete all rows from extracted career tables (child tables first to respect FK constraints)."""
    order = [
        "story_roles", "accomplishments", "people_engagements",
        "stories", "roles", "people", "employers",
        "skills", "gaps_weaknesses", "faq_responses", "ai_instructions",
    ]
    for tbl in order:
        sb.table(tbl).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print(f"  ✓ Wiped {tbl}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync career data from OB thoughts to ai-resume tables"
    )
    parser.add_argument("--extract", action="store_true",
                        help="Full extract via Claude from ai-resume-source thoughts (4-pass)")
    parser.add_argument("--per-thought", action="store_true",
                        help="Per-thought extract: one Claude call per OB thought, with prompt caching")
    parser.add_argument("--wipe", action="store_true",
                        help="Wipe all extracted career tables before running --extract")
    parser.add_argument("--passes", default=None,
                        help="Comma-separated pass IDs to run (default: all). Options: 1,2a,2b,3")
    parser.add_argument("--type", choices=SYNC_TYPES,
                        help="Sync only this structured type (default: all)")
    parser.add_argument("--thought-ids", default=None,
                        help="Comma-separated OB thought UUIDs. With --per-thought: skip wipe and process only these.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    env_path = find_and_load_env()
    sb = get_supabase()

    if args.stats:
        print_stats(sb)
        return

    started = datetime.now(timezone.utc)
    print(f"\n{'='*60}")
    print(f"sync_career_from_ob.py  {started.strftime('%Y-%m-%d %H:%M UTC')}")
    if args.per_thought:
        mode = "PER-THOUGHT EXTRACT (Claude + prompt caching)"
    elif args.extract:
        mode = "EXTRACT (Claude, 4-pass)"
    else:
        mode = "STRUCTURED SYNC"
    if args.dry_run:
        mode += " [DRY RUN]"
    print(f"  Mode: {mode}")
    print(f"  Env:  {env_path}")
    print(f"{'='*60}\n")

    if args.per_thought:
        anthropic_client = get_anthropic()
        thought_ids = [t.strip() for t in args.thought_ids.split(",")] if args.thought_ids else None
        run_extract_per_thought(sb, anthropic_client, args.dry_run, args.verbose, thought_ids=thought_ids)
    elif args.extract:
        if args.wipe and not args.dry_run:
            print("── Wiping extracted tables ──────────────────────────────")
            wipe_extracted_tables(sb)
            print()
        anthropic_client = get_anthropic()
        passes = [p.strip() for p in args.passes.split(",")] if args.passes else None
        run_extract(sb, anthropic_client, args.dry_run, args.verbose, passes=passes)
    else:
        thoughts = fetch_career_structured_thoughts(sb, args.type, args.verbose)
        print(f"Found {len(thoughts)} career-* thought(s)\n")
        if not thoughts:
            print("Nothing to sync. Run --extract to bootstrap from Interview Agent thoughts.")
            return

        profile = get_or_create_profile(sb, args.dry_run, args.verbose)
        run_all = args.type is None

        if run_all or args.type == "profile":
            print("── career-profile ──────────────────────────────────────")
            sync_profile(sb, thoughts, profile, args.dry_run, args.verbose)
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

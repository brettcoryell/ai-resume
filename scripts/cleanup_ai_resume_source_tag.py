#!/usr/bin/env python3
"""
cleanup_ai_resume_source_tag.py

One-time cleanup: remove 'ai-resume-source' from thoughts that were incorrectly
tagged by migrate_ai_resume_source_tag.py due to heuristic over-reach.

Three contaminated groups:
  A) AI context video series transcripts — topics overlap with ai-memory,
     mcp-protocol, byoc-bring-your-own-context, knowledge-worker-productivity
  B) AI safety video series transcripts — topics overlap with ai-safety,
     ai-agents, ai-trust, deepfake-fraud, zero-trust
  C) My Book 1 article chunks — article-type thoughts NOT in ARTICLE_ALLOWLIST

Usage:
  python3 scripts/cleanup_ai_resume_source_tag.py            # dry run (default)
  python3 scripts/cleanup_ai_resume_source_tag.py --live     # write changes
"""

import sys
import os
import argparse
from pathlib import Path


def find_and_load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv not installed.  pip3 install python-dotenv")
        sys.exit(1)
    for p in [
        Path.home() / "Code/AI/open_brain/.env",
        Path(__file__).parent.parent / ".env",
    ]:
        if p.exists():
            load_dotenv(p, override=True)
    return


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


# ── Allowlist of legitimate biographical article chunks ───────────────────────
# Any article-type thought NOT in this set is contamination (Group C).

ARTICLE_ALLOWLIST = {
    # Indian Hill 1990-1993 (3 chunks)
    "05322769-8ec8-41fc-bfe2-4a284470f5e8",
    "98657d36-9f5a-4566-95ab-734737f7d49c",
    "ebb54ef1-dfc7-4de8-873c-fa078eab279b",
    # Grad school at UVA 1993-1995 (3 chunks)
    "d4eba78b-cb12-43d4-920e-1456f8020cdc",
    "0c6bfc40-146b-4dd3-a241-d6a14366c0f3",
    "9d8e30ec-9a34-48fc-b8aa-28784abfb12c",
    # The Hill School 1995-1998 (5 chunks)
    "2fa2dad1-1822-4ce8-8811-ba677dc1aa3c",
    "e00ab38f-cfa7-4d21-9704-fb4f57a9603b",
    "cdb12703-2c3c-4632-bc05-738cc4203f39",
    "b30ee685-66c9-42c3-9d45-c5134b9790c9",
    "f67cbd23-2656-4d6c-9e13-ec7a06803e79",
    # Sprint 1998-2003 (6 chunks)
    "314c170d-b956-4eb5-af92-bb43a2c091ce",
    "db523428-cc53-4a1a-bc1c-60c4bc62f750",
    "bb571ab3-8e41-4d6b-b6e7-f604b68b4dd6",
    "679c7f6d-139c-40e1-a188-767a068d9bf3",
    "4fab3fec-796b-4868-b069-31e7cdcbe9a6",
    "64092008-8a62-40a3-9d44-956ff0561d2b",
}

# ── Topic signatures for contaminated transcript groups ───────────────────────

AI_CONTEXT_TOPICS = {
    "ai-memory", "professional-context", "knowledge-worker-productivity",
    "mcp-protocol", "byoc-bring-your-own-context",
}

AI_SAFETY_TOPICS = {
    "ai-safety", "ai-agents", "ai-trust", "deepfake-fraud", "zero-trust",
}


def classify_thought(tid, meta):
    """
    Returns group label 'A', 'B', 'C', or None (keep tag).
    """
    topics = set(meta.get("topics", []))
    ttype = meta.get("type", "")

    if topics & AI_CONTEXT_TOPICS:
        return "A"
    if topics & AI_SAFETY_TOPICS:
        return "B"
    if ttype == "article" and tid not in ARTICLE_ALLOWLIST:
        return "C"
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Remove ai-resume-source from incorrectly tagged OB thoughts"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Write changes (default is dry run)"
    )
    args = parser.parse_args()
    dry_run = not args.live

    find_and_load_env()
    sb = get_supabase()

    print("Fetching all thoughts tagged ai-resume-source...")
    page_size = 1000
    offset = 0
    tagged_thoughts = []
    while True:
        result = (
            sb.table("thoughts")
            .select("id, metadata")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        for row in batch:
            meta = row.get("metadata") or {}
            if "ai-resume-source" in meta.get("topics", []):
                tagged_thoughts.append(row)
        if len(batch) < page_size:
            break
        offset += page_size

    print(f"Found {len(tagged_thoughts)} thoughts currently tagged ai-resume-source\n")

    # Classify
    to_untag = {"A": [], "B": [], "C": []}
    to_keep = []

    for row in tagged_thoughts:
        tid = row["id"]
        meta = row.get("metadata") or {}
        group = classify_thought(tid, meta)
        if group:
            to_untag[group].append(row)
        else:
            to_keep.append(row)

    print(f"Classification:")
    print(f"  Group A (AI context video series):  {len(to_untag['A'])} thoughts → UNTAG")
    print(f"  Group B (AI safety video series):   {len(to_untag['B'])} thoughts → UNTAG")
    print(f"  Group C (non-allowlist articles):   {len(to_untag['C'])} thoughts → UNTAG")
    print(f"  Legitimate (keep tag):              {len(to_keep)} thoughts")
    print(f"  Total to untag:                     {sum(len(v) for v in to_untag.values())}")
    print()

    if dry_run:
        print("[DRY RUN] — no changes written. Details:\n")
        for group, rows in to_untag.items():
            label = {
                "A": "AI context video series",
                "B": "AI safety video series",
                "C": "Non-allowlist articles (My Book 1)",
            }[group]
            print(f"  --- Group {group}: {label} ---")
            for row in rows:
                meta = row.get("metadata") or {}
                topics = meta.get("topics", [])
                ttype = meta.get("type", "?")
                print(f"    {row['id']}  type={ttype}  topics={topics}")
            print()
        print("Re-run with --live to apply changes.")
        return

    # Live run
    removed = 0
    errors = 0
    all_to_untag = to_untag["A"] + to_untag["B"] + to_untag["C"]

    for row in all_to_untag:
        tid = row["id"]
        meta = row.get("metadata") or {}
        topics = [t for t in meta.get("topics", []) if t != "ai-resume-source"]
        new_meta = {**meta, "topics": topics}
        try:
            sb.table("thoughts").update({"metadata": new_meta}).eq("id", tid).execute()
            print(f"  Untagged: {tid}")
            removed += 1
        except Exception as e:
            print(f"  ERROR untagging {tid}: {e}")
            errors += 1

    print(f"\n{'='*50}")
    print(f"Cleanup complete:")
    print(f"  Untagged: {removed}")
    print(f"  Kept:     {len(to_keep)}")
    print(f"  Errors:   {errors}")
    print(f"  Expected remaining count: ~{len(to_keep)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()

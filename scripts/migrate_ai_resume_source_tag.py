#!/usr/bin/env python3
"""
migrate_ai_resume_source_tag.py

One-time migration to apply the 'ai-resume-source' topic tag to all OB thoughts
that are in scope for the ai-resume pipeline.

Scope:
  1. All existing biographical/career thoughts returned by fetch_biographical_thoughts()
  2. The 7 known article chunk UUIDs (Indian Hill + Hill School biographical PDFs)

After this migration, fetch_biographical_thoughts() filters by 'ai-resume-source'
as the canonical filter. This script is safe to re-run — it appends the tag
idempotently (never duplicates it).

Usage:
  python3 scripts/migrate_ai_resume_source_tag.py            # live run
  python3 scripts/migrate_ai_resume_source_tag.py --dry-run  # preview only
"""

import sys
import os
import json
import argparse
from pathlib import Path


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


# ── Scope definitions ──────────────────────────────────────────────────────

ARTICLE_ALLOWLIST = {
    # Indian Hill 1990 - 1993.pdf
    "05322769-8ec8-41fc-bfe2-4a284470f5e8",
    "98657d36-9f5a-4566-95ab-734737f7d49c",
    "ebb54ef1-dfc7-4de8-873c-fa078eab279b",
    # The Hill School 1995 - 1998.pdf
    "2fa2dad1-1822-4ce8-8811-ba677dc1aa3c",
    "e00ab38f-cfa7-4d21-9704-fb4f57a9603b",
    "cdb12703-2c3c-4632-bc05-738cc4203f39",
    "f67cbd23-2656-4d6c-9e13-ec7a06803e79",
}

CAREER_TOPICS = {
    "career", "Career", "resume", "Resume", "biography", "biographical",
    "IT Leadership", "Cybersecurity", "career development", "leadership",
    "management", "ERM", "cybersecurity", "FBI collaboration",
    "ACUTE project", "Elementum", "management philosophy", "mentorship",
}


def fetch_all_in_scope_ids(sb, verbose=False):
    """
    Return set of thought IDs that should receive the ai-resume-source tag.
    Mirrors the logic in fetch_biographical_thoughts().
    """
    in_scope_ids = set()
    page_size = 1000
    offset = 0

    while True:
        result = (
            sb.table("thoughts")
            .select("id, content, metadata")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        for t in batch:
            meta = t.get("metadata") or {}
            content = t.get("content", "")
            ttype = meta.get("type", "")
            topics = set(meta.get("topics", []))
            tid = t.get("id", "")

            # Already tagged — still include (idempotent update will be a no-op)
            if "ai-resume-source" in topics:
                in_scope_ids.add(tid)
                continue

            # Always: article allowlist
            if tid in ARTICLE_ALLOWLIST:
                in_scope_ids.add(tid)
                continue

            # Article type with career topics
            if ttype == "article":
                if topics & CAREER_TOPICS:
                    in_scope_ids.add(tid)
                continue

            # Skip YouTube
            if meta.get("source_url") and "youtube" in str(meta.get("source_url", "")):
                continue

            # Observation/reference: Brett by name
            if "Brett Coryell" in content or "Brett" in content[:50]:
                in_scope_ids.add(tid)
                continue

            # Observation/reference: topic overlap
            if topics & CAREER_TOPICS:
                in_scope_ids.add(tid)
                continue

        if len(batch) < page_size:
            break
        offset += page_size

    if verbose:
        print(f"  Found {len(in_scope_ids)} in-scope thought IDs")
    return in_scope_ids


def apply_tag_to_thoughts(sb, thought_ids, dry_run=False, verbose=False):
    """
    For each thought ID, append 'ai-resume-source' to metadata.topics if not
    already present. Returns (tagged_count, already_tagged_count, error_count).
    """
    tagged = 0
    already_tagged = 0
    errors = 0

    ids_list = list(thought_ids)
    print(f"\nProcessing {len(ids_list)} thoughts...")

    for tid in ids_list:
        # Fetch current metadata
        result = sb.table("thoughts").select("id, metadata").eq("id", tid).execute()
        if not result.data:
            print(f"  WARNING: thought {tid} not found — skipping")
            errors += 1
            continue

        row = result.data[0]
        meta = row.get("metadata") or {}
        topics = list(meta.get("topics", []))

        if "ai-resume-source" in topics:
            already_tagged += 1
            if verbose:
                print(f"  SKIP (already tagged): {tid}")
            continue

        topics.append("ai-resume-source")
        new_meta = {**meta, "topics": topics}

        if dry_run:
            print(f"  [DRY RUN] Would tag: {tid}  topics → {topics}")
        else:
            try:
                sb.table("thoughts").update({"metadata": new_meta}).eq("id", tid).execute()
                print(f"  Tagged: {tid}")
                tagged += 1
            except Exception as e:
                print(f"  ERROR tagging {tid}: {e}")
                errors += 1

    return tagged, already_tagged, errors


def main():
    parser = argparse.ArgumentParser(
        description="Apply ai-resume-source tag to all in-scope OB thoughts"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    env_path = find_and_load_env()
    print(f"Loaded env from: {env_path}")
    sb = get_supabase()

    print("\nFetching all in-scope thought IDs...")
    ids = fetch_all_in_scope_ids(sb, verbose=args.verbose)
    print(f"Found {len(ids)} thoughts in scope")

    print(f"\nBreakdown:")
    article_overlap = ids & ARTICLE_ALLOWLIST
    print(f"  Article allowlist (PDF chunks): {len(article_overlap)} of {len(ARTICLE_ALLOWLIST)}")
    print(f"  Total (includes observations, references, articles): {len(ids)}")

    if dry_run := args.dry_run:
        print("\n[DRY RUN] — no changes will be written\n")

    tagged, already, errors = apply_tag_to_thoughts(sb, ids, dry_run=dry_run, verbose=args.verbose)

    print(f"\n{'='*50}")
    print(f"Migration {'(DRY RUN) ' if dry_run else ''}complete:")
    print(f"  Tagged:         {tagged}")
    print(f"  Already tagged: {already}")
    print(f"  Errors:         {errors}")
    print(f"  Total in scope: {len(ids)}")
    print(f"{'='*50}")

    if not dry_run and errors == 0:
        print("\nNext step: update fetch_biographical_thoughts() in sync_career_from_ob.py")
        print("to use 'ai-resume-source' as the primary filter for future syncs.")


if __name__ == "__main__":
    main()

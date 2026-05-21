#!/usr/bin/env python3
"""
build_blob.py — Compile all OB thoughts tagged `ai-resume-source` into a single
raw narrative blob for use as Ariel's career context (replaces structured extraction).

This is Step 1 (validation) and Step 2 (infrastructure) of the blob architecture.

Usage:
  python3 scripts/build_blob.py --dry-run
      Fetch thoughts, print stats, preview, save to validation/career_blob.txt.
      Does NOT write to the career_blob table.

  python3 scripts/build_blob.py
      Same as --dry-run (career_blob table not yet created; will be Step 2).
"""

import sys
import os
import json
import argparse
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


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_thoughts(sb):
    """Fetch all thoughts tagged ai-resume-source, returned in chronological order."""
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

    all_thoughts.sort(key=lambda t: t.get("created_at") or "")
    return all_thoughts


# ── Build ─────────────────────────────────────────────────────────────────────

def build_blob_content(thoughts):
    """
    Concatenate thoughts into a single readable blob.

    Each thought gets a short header with its date and ID (useful for debugging
    which thought a piece of content came from). Thoughts are separated by ---
    so the LLM can distinguish where one thought ends and another begins.
    """
    parts = []
    for t in thoughts:
        created = (t.get("created_at") or "")[:10]  # YYYY-MM-DD
        thought_id = t.get("id", "?")
        content = (t.get("content") or "").strip()
        if not content:
            continue
        header = f"[{created} | {thought_id}]"
        parts.append(f"{header}\n{content}")
    return "\n\n---\n\n".join(parts)


def count_tokens_approx(text):
    """Approximate token count: 4 chars ≈ 1 token (rough but fast)."""
    return len(text) // 4


# ── Main ──────────────────────────────────────────────────────────────────────

def upsert_to_db(sb, blob, source_ids, token_count):
    """Insert a new row into career_blob (history preserved; edge function reads latest)."""
    # Get the current max build_version
    result = sb.table("career_blob").select("build_version").order("build_version", desc=True).limit(1).execute()
    prev_version = (result.data or [{}])[0].get("build_version", 0) if result.data else 0
    next_version = prev_version + 1

    sb.table("career_blob").insert({
        "content": blob,
        "token_count": token_count,
        "source_thought_ids": source_ids,
        "build_version": next_version,
    }).execute()

    return next_version


def main():
    parser = argparse.ArgumentParser(
        description="Build career blob from OB thoughts tagged ai-resume-source"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch, print stats, and save to validation/career_blob.txt — skip DB write")
    args = parser.parse_args()

    env_path = find_and_load_env()
    print(f"Env: {env_path}")

    sb = get_supabase()

    print("\nFetching OB thoughts tagged ai-resume-source...")
    thoughts = fetch_thoughts(sb)
    print(f"  Found: {len(thoughts)} thoughts")

    if not thoughts:
        print("ERROR: No thoughts found with ai-resume-source tag. Check tag migration.")
        sys.exit(1)

    blob = build_blob_content(thoughts)
    char_count = len(blob)
    token_count = count_tokens_approx(blob)
    source_ids = [t["id"] for t in thoughts]

    date_range_start = (thoughts[0].get("created_at") or "")[:10]
    date_range_end = (thoughts[-1].get("created_at") or "")[:10]

    print(f"\nBlob stats:")
    print(f"  Thoughts included : {len(thoughts)}")
    print(f"  Date range        : {date_range_start} → {date_range_end}")
    print(f"  Characters        : {char_count:,}")
    print(f"  Approx tokens     : {token_count:,}")
    if token_count > 100_000:
        print(f"  ⚠️  Token count exceeds 100k — time to plan RAG architecture")

    print(f"\nFirst 600 chars:")
    print("  " + blob[:600].replace("\n", "\n  "))
    print(f"\nLast 300 chars:")
    print("  " + blob[-300:].replace("\n", "\n  "))

    # Always save to local file (useful for debugging + --use-blob validation)
    output_dir = Path(__file__).parent.parent / "validation"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "career_blob.txt"
    with open(output_path, "w") as f:
        f.write(blob)
    print(f"\n✓ Blob saved to: {output_path}")

    # Save metadata sidecar
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "thought_count": len(thoughts),
        "char_count": char_count,
        "token_count_approx": token_count,
        "date_range": {"start": date_range_start, "end": date_range_end},
        "source_thought_ids": source_ids,
    }
    meta_path = output_dir / "career_blob_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"✓ Metadata saved to: {meta_path}")

    if args.dry_run:
        print("\n[dry-run] Skipping DB write.")
    else:
        print("\nWriting to career_blob table...")
        version = upsert_to_db(sb, blob, source_ids, token_count)
        print(f"✓ Inserted build_version={version} into career_blob table")


if __name__ == "__main__":
    main()

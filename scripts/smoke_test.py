#!/usr/bin/env python3
"""
smoke_test.py — Fast (~2s) sanity check for ai-resume in the exploration Supabase project.

Checks (no LLM calls):
  1. Anon key can SELECT from candidate_profile, experiences, skills
  2. career_blob has non-empty content
  3. chat Edge Function responds HTTP 200 to a simple question

Exit 0 on full pass, 1 on any failure.

Usage:
  python3 scripts/smoke_test.py

Required env vars (or hardcoded fallback for anon key):
  SUPABASE_URL        e.g. https://zybttfjewunokevxwtqc.supabase.co
  SUPABASE_ANON_KEY   public anon JWT
"""

import os
import sys
import uuid
from pathlib import Path


ANON_KEY_FALLBACK = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5YnR0Zmpld3Vub2tldnh3dHFjIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NzI5ODk4NjUsImV4cCI6MjA4ODU2NTg2NX0"
    ".zkJbJZ9kn8iRo9yTaOnKYKbwnlA2ASJNQEFKsbDjWP0"
)
SUPABASE_URL_FALLBACK = "https://zybttfjewunokevxwtqc.supabase.co"


def load_env():
    try:
        from dotenv import load_dotenv
        for p in [
            Path.home() / "Code/AI/open_brain/.env",
            Path(__file__).parent.parent / ".env",
            Path(__file__).parent.parent / ".env.local",
        ]:
            if p.exists():
                load_dotenv(p, override=True)
    except ImportError:
        pass


def get_config():
    url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or SUPABASE_URL_FALLBACK
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY") or ANON_KEY_FALLBACK
    return url.rstrip("/"), key


def anon_headers(key):
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def check_table(session, url, key, table, description):
    r = session.get(
        f"{url}/rest/v1/{table}",
        headers={**anon_headers(key), "Accept": "application/json"},
        params={"select": "id", "limit": "1"},
        timeout=10,
    )
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:120]}"
    rows = r.json()
    if not isinstance(rows, list) or len(rows) == 0:
        return False, "empty result — RLS policy may be blocking anon access"
    return True, f"{len(rows)} row(s) returned"


def check_career_blob(session, url, service_role_key):
    """Requires service role key — career_blob has no anon access by design."""
    service_headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Accept": "application/json",
    }
    r = session.get(
        f"{url}/rest/v1/career_blob",
        headers=service_headers,
        params={"select": "id,content,token_count,built_at", "order": "built_at.desc", "limit": "1"},
        timeout=10,
    )
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:120]}"
    rows = r.json()
    if not isinstance(rows, list) or len(rows) == 0:
        return False, "career_blob table is empty — blob has never been built"
    content = rows[0].get("content") or ""
    tokens = rows[0].get("token_count") or 0
    built_at = rows[0].get("built_at", "")[:10]
    if len(content) < 1000:
        return False, f"content too short ({len(content)} chars) — blob may not be built"
    return True, f"blob present — {tokens:,} tokens, built {built_at}"


def check_chat(session, url, key):
    """Ask a question that requires actual blob content to answer correctly."""
    body = {
        "message": "Briefly, what role did Brett hold at Sprint?",
        "sessionId": f"smoke-{uuid.uuid4().hex[:6]}",
    }
    r = session.post(
        f"{url}/functions/v1/chat",
        headers={**anon_headers(key), "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:120]}"
    data = r.json()
    answer = data.get("message") or data.get("answer") or ""
    if not answer:
        return False, f"no message/answer field in response: {list(data.keys())}"
    if len(answer) < 20:
        return False, f"suspiciously short answer ({len(answer)} chars): {answer!r}"
    return True, f"got {len(answer)}-char answer"


def main():
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed — pip install requests")
        sys.exit(1)

    load_env()
    url, key = get_config()

    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    checks = []
    session = requests.Session()

    checks.append(("candidate_profile readable by anon", *check_table(session, url, key, "candidate_profile", "candidate_profile")))
    checks.append(("experiences readable by anon",       *check_table(session, url, key, "experiences", "experiences")))
    checks.append(("skills readable by anon",            *check_table(session, url, key, "skills", "skills")))
    if service_key:
        checks.append(("career_blob populated",          *check_career_blob(session, url, service_key)))
    else:
        print("  -  career_blob: skipped (SUPABASE_SERVICE_ROLE_KEY not set)")
    checks.append(("chat edge function responds",        *check_chat(session, url, key)))

    passed = 0
    failed = 0
    for label, ok, detail in checks:
        icon = "✓" if ok else "✗"
        print(f"  {icon}  {label}: {detail}")
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    if failed == 0:
        print(f"PASS — all {passed} checks passed")
        sys.exit(0)
    else:
        print(f"FAIL — {failed}/{passed + failed} checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

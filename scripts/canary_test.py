#!/usr/bin/env python3
"""
canary_test.py — 6-question regression check against the live chat Edge Function.

Each question hits the real endpoint and checks that expected keywords appear
in the answer. No LLM grading — pure keyword matching. Runs in ~20s (parallel).

Questions are spread across career eras so a blob regression or edge function
breakage surfaces quickly regardless of where it occurs.

Exit 0 on pass, 1 on any failure.

Usage:
  python3 scripts/canary_test.py
  python3 scripts/canary_test.py --workers 1   # sequential (debugging)
  python3 scripts/canary_test.py --verbose      # print full answers

Required env vars (or hardcoded fallback for anon key):
  SUPABASE_URL
  SUPABASE_ANON_KEY
"""

import os
import sys
import uuid
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ANON_KEY_FALLBACK = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5YnR0Zmpld3Vub2tldnh3dHFjIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NDYxMjQzOTMsImV4cCI6MjA2MTcwMDM5M30"
    ".ab6uh0pxe-WMNf6JBfNaGJLmXTM_OJjqiL5bIVQbmRM"
)
SUPABASE_URL_FALLBACK = "https://zybttfjewunokevxwtqc.supabase.co"

# 6 canary questions spanning different career eras.
# Keywords are case-insensitive substrings — ALL must appear to pass.
CANARY_QUESTIONS = [
    {
        "id": "C1",
        "era": "identity",
        "question": "What is the core pattern that runs through Brett's entire career?",
        "keywords": ["competence", "trust", "opportunity"],
    },
    {
        "id": "C2",
        "era": "management",
        "question": "What is Brett's core management philosophy in his own words?",
        "keywords": ["good work", "good people", "kind"],
    },
    {
        "id": "C3",
        "era": "sprint",
        "question": "How did Brett progress through Sprint, and what was the scale of his final role there?",
        "keywords": ["Sprint", "Chief of Staff", "Y2K"],
    },
    {
        "id": "C4",
        "era": "emory→niu",
        "question": "Why did Brett leave Emory University to go to a lower-ranked school like NIU?",
        "keywords": ["tuba", "daughters", "values"],
    },
    {
        "id": "C5",
        "era": "intro",
        "question": "How does Brett describe himself when asked to introduce himself professionally?",
        "keywords": ["CIO", "CISO", "billion"],
    },
    {
        "id": "C6",
        "era": "elementum",
        "question": "What did Brett's last CEO say about him, and in what context?",
        "keywords": ["Nader", "honest"],
    },
]


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


def run_one(q, url, key, verbose=False):
    try:
        import requests
    except ImportError:
        return q["id"], False, "requests not installed", ""

    session_id = f"canary-{uuid.uuid4().hex[:8]}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {"message": q["question"], "sessionId": session_id}

    try:
        r = requests.post(f"{url}/functions/v1/chat", headers=headers, json=body, timeout=45)
    except Exception as e:
        return q["id"], False, f"request error: {e}", ""

    if r.status_code != 200:
        return q["id"], False, f"HTTP {r.status_code}: {r.text[:80]}", ""

    data = r.json()
    answer = data.get("message") or data.get("answer") or ""
    answer_lower = answer.lower()

    missing = [kw for kw in q["keywords"] if kw.lower() not in answer_lower]
    if missing:
        return q["id"], False, f"missing keywords: {missing}", answer
    return q["id"], True, "all keywords found", answer


def main():
    parser = argparse.ArgumentParser(description="Canary Q&A regression check")
    parser.add_argument("--workers", type=int, default=6, help="parallel workers (default: 6)")
    parser.add_argument("--verbose", "-v", action="store_true", help="print full answers")
    args = parser.parse_args()

    try:
        import requests  # noqa: F401
    except ImportError:
        print("ERROR: requests not installed — pip install requests")
        sys.exit(1)

    load_env()
    url, key = get_config()

    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, q, url, key, args.verbose): q for q in CANARY_QUESTIONS}
        for future in as_completed(futures):
            qid, ok, detail, answer = future.result()
            results[qid] = (ok, detail, answer)

    passed = failed = 0
    for q in CANARY_QUESTIONS:
        ok, detail, answer = results[q["id"]]
        icon = "✓" if ok else "✗"
        print(f"  {icon}  [{q['id']} {q['era']}] {detail}")
        if args.verbose and answer:
            indent = "       "
            print(f"{indent}{answer[:300].replace(chr(10), chr(10)+indent)}")
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    if failed == 0:
        print(f"PASS — all {passed} canary questions answered correctly")
        sys.exit(0)
    else:
        print(f"FAIL — {failed}/{passed + failed} questions failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

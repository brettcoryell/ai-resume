#!/usr/bin/env python3
"""
query_ai_resume.py — CLI wrapper for the ai-resume chat Edge Function.
Used by the validation pipeline and for manual testing.

Usage:
  python3 scripts/query_ai_resume.py "Who is John Shipley?"
  python3 scripts/query_ai_resume.py --session-id abc123 "Tell me about yourself"
  python3 scripts/query_ai_resume.py --json "What are your strongest skills?"

Equivalent curl:
  curl -s -X POST {SUPABASE_URL}/functions/v1/chat \\
    -H "Authorization: Bearer {ANON_KEY}" \\
    -H "apikey: {ANON_KEY}" \\
    -H "Content-Type: application/json" \\
    -d '{"message": "...", "sessionId": "validation-cli"}'
"""

import sys
import os
import json
import argparse
import uuid
from pathlib import Path


def find_and_load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("ERROR: python-dotenv not installed.  pip3 install python-dotenv", file=sys.stderr)
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
    return loaded


def get_anon_key():
    """
    The chat Edge Function is called with the anon key (public-facing auth).
    It lives in VITE_SUPABASE_ANON_KEY (from .env.local) or SUPABASE_ANON_KEY.
    """
    return (
        os.getenv("VITE_SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        # Hard-coded fallback — open-brain project anon key (safe to embed, RLS enforces access)
        or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5YnR0Zmpld3Vub2tldnh3dHFjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDYxMjQzOTMsImV4cCI6MjA2MTcwMDM5M30.ab6uh0pxe-WMNf6JBfNaGJLmXTM_OJjqiL5bIVQbmRM"
    )


def query_chat(message, session_id=None, verbose=False):
    """
    Call the chat Edge Function and return the full JSON response dict.
    """
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed.  pip3 install requests", file=sys.stderr)
        sys.exit(1)

    url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    if not url:
        print("ERROR: SUPABASE_URL not set.", file=sys.stderr)
        sys.exit(1)

    anon_key = get_anon_key()
    session_id = session_id or f"validation-cli-{uuid.uuid4().hex[:8]}"
    endpoint = f"{url}/functions/v1/chat"

    headers = {
        "Authorization": f"Bearer {anon_key}",
        "apikey": anon_key,
        "Content-Type": "application/json",
    }
    body = {"message": message, "sessionId": session_id}

    if verbose:
        print(f"POST {endpoint}", file=sys.stderr)
        print(f"Session ID: {session_id}", file=sys.stderr)

    response = requests.post(endpoint, headers=headers, json=body, timeout=30)

    if response.status_code != 200:
        print(f"ERROR: HTTP {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)

    return response.json(), session_id


def main():
    parser = argparse.ArgumentParser(
        description="Query the ai-resume chat Edge Function from the command line"
    )
    parser.add_argument("message", help="The message/question to send")
    parser.add_argument(
        "--session-id",
        default=None,
        help="Session ID for conversation continuity (default: random per invocation)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Print full JSON response instead of just the answer",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print request details to stderr")
    args = parser.parse_args()

    find_and_load_env()

    result, session_id = query_chat(args.message, args.session_id, verbose=args.verbose)

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        answer = result.get("message") or result.get("answer") or result.get("error") or str(result)
        print(answer)

    if args.verbose:
        print(f"\nSession ID used: {session_id}", file=sys.stderr)


if __name__ == "__main__":
    main()

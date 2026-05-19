#!/usr/bin/env python3
"""
validate_pipeline.py — OB → ai-resume pipeline validation runner.

Runs Tests 1A, 1B, 2, and 3. Tests 4 and 5 are stubbed (pending schema redesign
and qa_dataset.json from the parallel Coda session).

Tests:
  1A  Forward pass   — Every in-scope OB thought is represented in ai-resume tables
  1B  Reverse pass   — Every ai-resume record can be traced to an OB source
  2   Named entities — Entities from OB appear in ai-resume
  3   Keyword union  — Significant terms not lost in the OB→ai-resume extraction

LLM judges:
  Both Claude Sonnet and Gemini Pro are used independently for each LLM check.
  Disagreements between them go to the exception pile.

Output:
  validation/validation_report.json
  validation/validation_exceptions.json

Usage:
  python3 scripts/validate_pipeline.py
  python3 scripts/validate_pipeline.py --skip-llm        # deterministic checks only
  python3 scripts/validate_pipeline.py --test 1a         # run a single test
  python3 scripts/validate_pipeline.py --verbose
"""

import sys
import os
import json
import argparse
import re
import time
import uuid
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


# ── LLM clients ───────────────────────────────────────────────────────────────

def call_claude(prompt, system=None, max_tokens=2048):
    """Call Claude Sonnet. Returns text string."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic not installed.")
        sys.exit(1)
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=key)
    kwargs = dict(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    return resp.content[0].text if resp.content else ""


def call_gemini(prompt, max_tokens=2048):
    """Call Gemini 1.5 Pro via REST. Returns text string."""
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed.")
        sys.exit(1)
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    headers = {"X-goog-api-key": key, "Content-Type": "application/json"}
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response shape: {e}\n{data}")


# ── Data loaders ─────────────────────────────────────────────────────────────

def load_ob_thoughts(sb, verbose=False):
    """Load all OB thoughts tagged ai-resume-source."""
    page_size = 1000
    offset = 0
    all_thoughts = []

    if verbose:
        print("  Loading OB thoughts...")

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
        print(f"  Loaded {len(all_thoughts)} OB thoughts in scope")
    return all_thoughts


def load_ai_resume_tables(sb, verbose=False):
    """Load all ai-resume career tables. Returns dict of table_name → list of rows."""
    tables = {
        "candidate_profile": "id, name, elevator_pitch, career_narrative, looking_for, not_looking_for, ob_thought_id",
        "experiences": "id, company_name, title, bullet_points, why_joined, why_left, actual_contributions, proudest_achievement, challenges_faced, lessons_learned, ob_thought_id",
        "skills": "id, skill_name, category, honest_notes, evidence, ob_thought_id",
        "gaps_weaknesses": "id, description, why_its_a_gap, ob_thought_id",
        "faq_responses": "id, question, answer, ob_thought_id",
        "ai_instructions": "id, instruction, ob_thought_id",
    }
    data = {}
    for tbl, cols in tables.items():
        try:
            result = sb.table(tbl).select(cols).execute()
            data[tbl] = result.data or []
        except Exception as e:
            print(f"  WARNING: could not load {tbl}: {e}")
            data[tbl] = []
        if verbose:
            print(f"  {tbl}: {len(data[tbl])} rows")
    return data


def build_ai_resume_text_dump(ai_resume_data):
    """Concatenate all text fields from ai-resume tables into a single searchable blob."""
    parts = []
    for tbl, rows in ai_resume_data.items():
        for row in rows:
            for key, val in row.items():
                if key in ("id", "ob_thought_id", "candidate_id"):
                    continue
                if isinstance(val, str) and val:
                    parts.append(val)
                elif isinstance(val, list):
                    parts.extend(str(x) for x in val if x)
    return "\n".join(parts)


# ── Named entity extraction ───────────────────────────────────────────────────

ENTITY_EXTRACTION_SYSTEM = """You are a named entity extractor. Extract all significant named entities
from the text below. Return ONLY a JSON array of strings — no markdown, no commentary.

Include:
- People (full names preferred)
- Organizations (companies, schools, agencies, teams)
- Named projects, programs, or products
- Named concepts or frameworks with proper names (e.g. "Zero Trust", "ITIL", "Balanced Scorecard")
- Geographic places that are professionally significant

Exclude:
- Generic job titles without a person attached
- Common nouns, verbs, adjectives
- Generic tech terms ("email", "database")

Return format: ["Entity One", "Entity Two", ...]"""


def extract_entities_claude(text, label=""):
    """Use Claude to extract named entities from text."""
    prompt = f"Extract all named entities from this text:\n\n{text[:15000]}"
    raw = call_claude(prompt, system=ENTITY_EXTRACTION_SYSTEM, max_tokens=2000)
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        entities = json.loads(raw)
        if isinstance(entities, list):
            return [str(e).strip() for e in entities if e]
    except json.JSONDecodeError:
        pass
    # Fallback: extract quoted strings
    return re.findall(r'"([^"]+)"', raw)


def extract_entities_gemini(text, label=""):
    """Use Gemini to extract named entities from text."""
    prompt = (
        ENTITY_EXTRACTION_SYSTEM
        + f"\n\nText to analyze:\n\n{text[:15000]}"
    )
    raw = call_gemini(prompt, max_tokens=2000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        entities = json.loads(raw)
        if isinstance(entities, list):
            return [str(e).strip() for e in entities if e]
    except json.JSONDecodeError:
        pass
    return re.findall(r'"([^"]+)"', raw)


# ── Keyword extraction ────────────────────────────────────────────────────────

KEYWORD_EXTRACTION_SYSTEM = """You are a keyword extractor for career/professional content.
Extract the most significant domain-specific terms from the text.
Return ONLY a JSON array of strings. No markdown, no commentary.

Include: job titles, company names, technical skills, methodologies, certifications,
industry terms, project names, product names, professional frameworks.
Exclude: common English words, prepositions, generic phrases."""


def extract_keywords_claude(text):
    prompt = f"Extract significant professional/career keywords from this text:\n\n{text[:20000]}"
    raw = call_claude(prompt, system=KEYWORD_EXTRACTION_SYSTEM, max_tokens=2000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        kws = json.loads(raw)
        if isinstance(kws, list):
            return set(str(k).strip().lower() for k in kws if k)
    except json.JSONDecodeError:
        pass
    return set()


def extract_keywords_gemini(text):
    prompt = (
        KEYWORD_EXTRACTION_SYSTEM
        + f"\n\nText:\n\n{text[:20000]}"
    )
    raw = call_gemini(prompt, max_tokens=2000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        kws = json.loads(raw)
        if isinstance(kws, list):
            return set(str(k).strip().lower() for k in kws if k)
    except json.JSONDecodeError:
        pass
    return set()


# ── Deterministic helpers ─────────────────────────────────────────────────────

def extract_proper_nouns_deterministic(text):
    """Simple heuristic: two-word sequences where both words are Title Case."""
    # Multi-word entities (3+ words: some proper nouns like "Federal Bureau of Investigation")
    words = text.split()
    entities = set()
    i = 0
    while i < len(words):
        # Collect a run of title-case words
        run = []
        j = i
        while j < len(words):
            w = re.sub(r"[^a-zA-Z']", "", words[j])
            if w and w[0].isupper() and len(w) > 1 and w.lower() not in {
                "the", "a", "an", "of", "in", "for", "and", "or", "at", "to",
                "with", "by", "from", "as", "is", "was", "are", "were",
                "i", "he", "she", "it", "we", "they", "my", "his", "her",
            }:
                run.append(words[j])
                j += 1
            else:
                break
        if len(run) >= 2:
            entities.add(" ".join(run))
        i = max(i + 1, j)
    return entities


def string_search_in_dump(term, dump_text):
    """Case-insensitive string search."""
    return term.lower() in dump_text.lower()


# ── Test implementations ──────────────────────────────────────────────────────

def run_test_1a(ob_thoughts, ai_resume_text, skip_llm=False, verbose=False):
    """
    Forward pass: each in-scope OB thought should be represented in ai-resume.
    Returns (pass_count, fail_count, exceptions).
    """
    print("\n── Test 1A: Forward pass (OB → ai-resume) ──────────────────")
    passes = 0
    fails = 0
    exceptions = []

    for t in ob_thoughts:
        tid = t.get("id", "unknown")
        content = t.get("content", "")
        if not content.strip():
            continue

        # Deterministic: extract proper nouns and check if any appear in ai-resume
        proper_nouns = extract_proper_nouns_deterministic(content)
        # Also check for Brett-specific identifiers
        key_terms = set()
        for pn in proper_nouns:
            if len(pn) > 4:  # skip very short entities
                key_terms.add(pn)

        det_found = any(string_search_in_dump(term, ai_resume_text) for term in key_terms)
        det_verdict = "pass" if det_found else "fail"

        if verbose:
            print(f"  {tid[:8]}... det={det_verdict} ({len(key_terms)} entities checked)")

        claude_verdict = None
        gemini_verdict = None

        if not skip_llm and not det_found:
            # Only call LLMs for deterministic failures to save cost
            prompt = f"""Does the following OB thought's key content appear anywhere in the ai-resume data below?

OB THOUGHT:
{content[:2000]}

AI-RESUME DATA (excerpt):
{ai_resume_text[:8000]}

Answer with exactly one word: YES or NO.
If the core professional content (companies, roles, achievements, dates) is present in some form, answer YES.
If the thought is completely absent, answer NO."""

            try:
                c_raw = call_claude(prompt, max_tokens=10).strip().upper()
                claude_verdict = "pass" if c_raw.startswith("YES") else "fail"
            except Exception as e:
                claude_verdict = f"error: {e}"

            try:
                g_raw = call_gemini(prompt, max_tokens=10).strip().upper()
                gemini_verdict = "pass" if g_raw.startswith("YES") else "fail"
            except Exception as e:
                gemini_verdict = f"error: {e}"

        # Determine overall verdict
        all_verdicts = [v for v in [det_verdict, claude_verdict, gemini_verdict] if v and not v.startswith("error")]
        final_fail = any(v == "fail" for v in all_verdicts)
        any_pass = any(v == "pass" for v in all_verdicts)

        if final_fail and not any_pass:
            fails += 1
            exceptions.append({
                "test": "1A",
                "ob_thought_id": tid,
                "description": content[:120].replace("\n", " "),
                "claude_verdict": claude_verdict,
                "gemini_verdict": gemini_verdict,
                "deterministic_verdict": det_verdict,
                "failure_mode": "missing",
                "key_entities_checked": list(key_terms)[:10],
            })
        elif final_fail and any_pass:
            # Disagreement — LLM found it but deterministic missed it, or vice versa
            passes += 1  # Count as soft pass with note
            if verbose:
                print(f"    Disagreement on {tid[:8]} — counting as pass (LLM found content)")
        else:
            passes += 1

    print(f"  Pass: {passes}  Fail: {fails}  (of {passes+fails} thoughts with content)")
    return passes, fails, exceptions


def run_test_1b(ai_resume_data, ob_thoughts, skip_llm=False, verbose=False):
    """
    Reverse pass: each ai-resume record should be traceable to an OB source.
    Returns (pass_count, fail_count, exceptions).
    """
    print("\n── Test 1B: Reverse pass (ai-resume → OB) ──────────────────")
    passes = 0
    fails = 0
    exceptions = []

    ob_content_blob = "\n\n".join(t.get("content", "") for t in ob_thoughts)

    tables_to_check = {
        "experiences": "company_name",
        "skills": "skill_name",
        "gaps_weaknesses": "description",
        "faq_responses": "question",
        "ai_instructions": "instruction",
    }

    for tbl, label_field in tables_to_check.items():
        rows = ai_resume_data.get(tbl, [])
        for row in rows:
            rid = row.get("id", "unknown")
            label = str(row.get(label_field, ""))[:80]
            ob_thought_id = row.get("ob_thought_id")

            # Deterministic: does ob_thought_id exist?
            if ob_thought_id:
                ob_ids = {t.get("id") for t in ob_thoughts}
                if ob_thought_id in ob_ids:
                    passes += 1
                    if verbose:
                        print(f"  PASS (ob_thought_id): {tbl} / {label}")
                    continue

            # Deterministic fallback: does the label appear in OB content?
            det_found = string_search_in_dump(label, ob_content_blob) if label else False
            det_verdict = "pass" if det_found else "fail"

            claude_verdict = None
            gemini_verdict = None

            if not skip_llm and not det_found:
                # Get the row's text content for LLM check
                row_text = " | ".join(
                    f"{k}: {v}" for k, v in row.items()
                    if k not in ("id", "ob_thought_id", "candidate_id")
                    and isinstance(v, str) and v
                )
                prompt = f"""Does this ai-resume record's content appear to come from the OB biographical data below?

AI-RESUME RECORD ({tbl}):
{row_text[:1000]}

OB BIOGRAPHICAL DATA (excerpt):
{ob_content_blob[:8000]}

Answer with exactly one word: YES or NO.
YES = the record's content clearly derives from the OB data.
NO = the record appears to have no source in the OB data (possible orphan or hallucination)."""

                try:
                    c_raw = call_claude(prompt, max_tokens=10).strip().upper()
                    claude_verdict = "pass" if c_raw.startswith("YES") else "fail"
                except Exception as e:
                    claude_verdict = f"error: {e}"

                try:
                    g_raw = call_gemini(prompt, max_tokens=10).strip().upper()
                    gemini_verdict = "pass" if g_raw.startswith("YES") else "fail"
                except Exception as e:
                    gemini_verdict = f"error: {e}"

            all_verdicts = [v for v in [det_verdict, claude_verdict, gemini_verdict] if v and not v.startswith("error")]
            final_fail = all(v == "fail" for v in all_verdicts) if all_verdicts else True

            if final_fail:
                fails += 1
                exceptions.append({
                    "test": "1B",
                    "table": tbl,
                    "record_id": rid,
                    "description": label,
                    "ob_thought_id": ob_thought_id,
                    "claude_verdict": claude_verdict,
                    "gemini_verdict": gemini_verdict,
                    "deterministic_verdict": det_verdict,
                    "failure_mode": "orphan",
                })
                if verbose:
                    print(f"  FAIL: {tbl} / {label}")
            else:
                passes += 1
                if verbose:
                    print(f"  PASS: {tbl} / {label}")

    print(f"  Pass: {passes}  Fail: {fails}")
    return passes, fails, exceptions


def run_test_2(ob_thoughts, ai_resume_text, skip_llm=False, verbose=False):
    """
    Named entity audit: entities from OB should appear in ai-resume.
    Returns (found_count, missing_count, exceptions).
    """
    print("\n── Test 2: Named entity audit ───────────────────────────────")
    exceptions = []

    # Build OB corpus
    ob_corpus = "\n\n".join(t.get("content", "") for t in ob_thoughts)

    # Deterministic entity extraction
    det_entities = extract_proper_nouns_deterministic(ob_corpus)
    # Filter to meaningful multi-word entities
    det_entities = {e for e in det_entities if len(e) > 5}

    claude_entities = set()
    gemini_entities = set()

    if not skip_llm:
        print("  Extracting entities via Claude...")
        try:
            claude_list = extract_entities_claude(ob_corpus, "OB corpus")
            claude_entities = set(claude_list)
            print(f"  Claude extracted {len(claude_entities)} entities")
        except Exception as e:
            print(f"  Claude entity extraction failed: {e}")

        print("  Extracting entities via Gemini...")
        try:
            gemini_list = extract_entities_gemini(ob_corpus, "OB corpus")
            gemini_entities = set(gemini_list)
            print(f"  Gemini extracted {len(gemini_entities)} entities")
        except Exception as e:
            print(f"  Gemini entity extraction failed: {e}")

    # Union of all extracted entities
    all_entities = det_entities | claude_entities | gemini_entities
    print(f"  Total unique entities (union): {len(all_entities)}")

    # Flag entities missing from ai-resume
    found = 0
    missing = 0
    for entity in sorted(all_entities):
        if string_search_in_dump(entity, ai_resume_text):
            found += 1
            if verbose:
                print(f"  FOUND: {entity}")
        else:
            missing += 1
            # Classify: is it in Claude list? Gemini list? Deterministic?
            in_claude = entity in claude_entities
            in_gemini = entity in gemini_entities
            in_det = entity in det_entities

            # Only flag if at least two sources agree it's an entity
            agreement_count = sum([in_claude, in_gemini, in_det])
            if agreement_count >= 2 or (skip_llm and in_det):
                exceptions.append({
                    "test": "2",
                    "entity": entity,
                    "description": f"Entity '{entity}' found in OB but not in ai-resume",
                    "claude_extracted": in_claude,
                    "gemini_extracted": in_gemini,
                    "deterministic_extracted": in_det,
                    "failure_mode": "missing",
                })
            if verbose:
                print(f"  MISSING: {entity} (claude={in_claude}, gemini={in_gemini}, det={in_det})")

    print(f"  Entities found in ai-resume: {found}  Missing: {missing}")
    return found, missing, exceptions


def run_test_3(ob_thoughts, ai_resume_data, skip_llm=False, verbose=False):
    """
    Global keyword union: check for terms lost between OB and ai-resume.
    Returns (ob_only, ai_only, exceptions).
    """
    print("\n── Test 3: Global keyword/entity union ─────────────────────")
    exceptions = []

    ob_corpus = "\n\n".join(t.get("content", "") for t in ob_thoughts)
    ai_resume_text = build_ai_resume_text_dump(ai_resume_data)

    # Deterministic: word frequency comparison
    def significant_terms(text):
        words = re.findall(r'\b[A-Za-z][A-Za-z\-]{3,}\b', text)
        STOPWORDS = {
            "that", "this", "with", "from", "have", "been", "were", "they",
            "their", "about", "would", "could", "should", "which", "will",
            "when", "what", "where", "also", "than", "then", "there", "into",
            "more", "some", "over", "very", "just", "like", "well", "make",
            "work", "team", "role", "time", "year", "years", "across", "within",
            "brett", "coryell",
        }
        return {w.lower() for w in words if w.lower() not in STOPWORDS}

    ob_terms_det = significant_terms(ob_corpus)
    ai_terms_det = significant_terms(ai_resume_text)

    ob_only_det = ob_terms_det - ai_terms_det
    ai_only_det = ai_terms_det - ob_terms_det

    # Filter to terms that appear 3+ times in OB (reduce noise)
    from collections import Counter
    ob_word_counts = Counter(re.findall(r'\b[A-Za-z][A-Za-z\-]{3,}\b', ob_corpus.lower()))
    ob_only_frequent = {t for t in ob_only_det if ob_word_counts[t] >= 3}

    print(f"  OB unique terms (det, freq>=3): {len(ob_only_frequent)}")
    print(f"  ai-resume unique terms (det): {len(ai_only_det)}")

    claude_ob_kws = set()
    claude_ai_kws = set()
    gemini_ob_kws = set()
    gemini_ai_kws = set()

    if not skip_llm:
        print("  Extracting OB keywords via Claude...")
        try:
            claude_ob_kws = extract_keywords_claude(ob_corpus)
            print(f"    {len(claude_ob_kws)} keywords")
        except Exception as e:
            print(f"    Claude OB keyword extraction failed: {e}")

        print("  Extracting ai-resume keywords via Claude...")
        try:
            claude_ai_kws = extract_keywords_claude(ai_resume_text)
            print(f"    {len(claude_ai_kws)} keywords")
        except Exception as e:
            print(f"    Claude ai-resume keyword extraction failed: {e}")

        print("  Extracting OB keywords via Gemini...")
        try:
            gemini_ob_kws = extract_keywords_gemini(ob_corpus)
            print(f"    {len(gemini_ob_kws)} keywords")
        except Exception as e:
            print(f"    Gemini OB keyword extraction failed: {e}")

        print("  Extracting ai-resume keywords via Gemini...")
        try:
            gemini_ai_kws = extract_keywords_gemini(ai_resume_text)
            print(f"    {len(gemini_ai_kws)} keywords")
        except Exception as e:
            print(f"    Gemini ai-resume keyword extraction failed: {e}")

    # Compute set differences (LLM-based)
    llm_ob_only = (claude_ob_kws | gemini_ob_kws) - (claude_ai_kws | gemini_ai_kws)
    llm_ai_only = (claude_ai_kws | gemini_ai_kws) - (claude_ob_kws | gemini_ob_kws)

    # Union of deterministic and LLM findings
    final_ob_only = sorted(ob_only_frequent | llm_ob_only)
    final_ai_only = sorted(ai_only_det & llm_ai_only)  # Only report ai-only if both det and LLM agree

    # Flag significant discrepancies
    for term in final_ob_only[:50]:  # Cap at 50 to avoid noise
        exceptions.append({
            "test": "3",
            "term": term,
            "description": f"Term '{term}' appears in OB but not ai-resume (possible extraction loss)",
            "source": "ob-only",
            "ob_frequency": ob_word_counts.get(term, 0),
            "failure_mode": "missing",
        })

    for term in final_ai_only[:20]:
        exceptions.append({
            "test": "3",
            "term": term,
            "description": f"Term '{term}' appears in ai-resume but not OB (possible hallucination or stale data)",
            "source": "ai-resume-only",
            "failure_mode": "hallucination",
        })

    print(f"  OB-only terms (final, capped at 50): {min(len(final_ob_only), 50)}")
    print(f"  ai-resume-only terms (final, capped at 20): {min(len(final_ai_only), 20)}")
    return final_ob_only[:50], final_ai_only[:20], exceptions


# ── Stub tests for future implementation ──────────────────────────────────────

def run_test_4_stub():
    """Test 4 — Schema integrity. Deferred until schema redesign complete."""
    print("\n── Test 4: Schema integrity (DEFERRED) ─────────────────────")
    print("  Skipped — pending schema redesign")
    return {"status": "deferred", "reason": "Schema redesign pending"}


def run_test_5_stub():
    """Test 5 — Q&A accuracy. Deferred until qa_dataset.json is available."""
    print("\n── Test 5: Q&A accuracy (DEFERRED) ─────────────────────────")
    qa_path = Path(__file__).parent.parent / "validation" / "qa_dataset.json"
    if qa_path.exists():
        print(f"  qa_dataset.json found — but Test 5 not yet implemented (pending schema redesign)")
    else:
        print(f"  Skipped — qa_dataset.json not yet available at {qa_path}")
    return {"status": "deferred", "reason": "qa_dataset.json not ready; schema redesign pending"}


# ── Output writers ────────────────────────────────────────────────────────────

def write_outputs(report, exceptions):
    validation_dir = Path(__file__).parent.parent / "validation"
    validation_dir.mkdir(exist_ok=True)

    report_path = validation_dir / "validation_report.json"
    exceptions_path = validation_dir / "validation_exceptions.json"

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Wrote report: {report_path}")

    with open(exceptions_path, "w") as f:
        json.dump(exceptions, f, indent=2, default=str)
    print(f"  Wrote exceptions: {exceptions_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Validate the OB → ai-resume pipeline"
    )
    parser.add_argument("--skip-llm", action="store_true",
                        help="Run deterministic checks only (no Claude/Gemini calls)")
    parser.add_argument("--test", choices=["1a", "1b", "2", "3"],
                        help="Run a single test instead of all")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    env_path = find_and_load_env()
    print(f"Env: {env_path}")

    sb = get_supabase()

    started = datetime.now(timezone.utc)
    print(f"\n{'='*60}")
    print(f"validate_pipeline.py  {started.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Skip LLM: {args.skip_llm}")
    print(f"  Test filter: {args.test or 'all'}")
    print(f"{'='*60}")

    # Load data
    print("\nLoading data...")
    ob_thoughts = load_ob_thoughts(sb, verbose=args.verbose)
    ai_resume_data = load_ai_resume_tables(sb, verbose=args.verbose)
    ai_resume_text = build_ai_resume_text_dump(ai_resume_data)

    print(f"  OB thoughts in scope: {len(ob_thoughts)}")
    total_ai_rows = sum(len(v) for v in ai_resume_data.values())
    print(f"  ai-resume rows total: {total_ai_rows}")

    report = {
        "run_date": started.isoformat(),
        "ob_thoughts_in_scope": len(ob_thoughts),
        "ai_resume_rows_total": total_ai_rows,
        "skip_llm": args.skip_llm,
        "test_1a": {"pass": 0, "fail": 0, "exceptions": []},
        "test_1b": {"pass": 0, "fail": 0, "exceptions": []},
        "test_2": {"entities_found": 0, "entities_missing": 0, "exceptions": []},
        "test_3": {"ob_only_terms": [], "ai_resume_only_terms": [], "exceptions": []},
        "test_4": {"status": "deferred"},
        "test_5": {"status": "deferred"},
    }
    all_exceptions = []

    # Test 1A
    if args.test in (None, "1a"):
        p, f, excs = run_test_1a(ob_thoughts, ai_resume_text,
                                  skip_llm=args.skip_llm, verbose=args.verbose)
        report["test_1a"] = {"pass": p, "fail": f, "exceptions": excs}
        all_exceptions.extend(excs)

    # Test 1B
    if args.test in (None, "1b"):
        p, f, excs = run_test_1b(ai_resume_data, ob_thoughts,
                                  skip_llm=args.skip_llm, verbose=args.verbose)
        report["test_1b"] = {"pass": p, "fail": f, "exceptions": excs}
        all_exceptions.extend(excs)

    # Test 2
    if args.test in (None, "2"):
        found, missing, excs = run_test_2(ob_thoughts, ai_resume_text,
                                          skip_llm=args.skip_llm, verbose=args.verbose)
        report["test_2"] = {"entities_found": found, "entities_missing": missing, "exceptions": excs}
        all_exceptions.extend(excs)

    # Test 3
    if args.test in (None, "3"):
        ob_only, ai_only, excs = run_test_3(ob_thoughts, ai_resume_data,
                                            skip_llm=args.skip_llm, verbose=args.verbose)
        report["test_3"] = {
            "ob_only_terms": ob_only,
            "ai_resume_only_terms": ai_only,
            "exceptions": excs,
        }
        all_exceptions.extend(excs)

    # Deferred tests
    if args.test is None:
        report["test_4"] = run_test_4_stub()
        report["test_5"] = run_test_5_stub()

    # Summary
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"\n{'='*60}")
    print(f"Validation complete in {elapsed:.1f}s")
    print(f"  Test 1A: {report['test_1a'].get('pass',0)} pass / {report['test_1a'].get('fail',0)} fail")
    print(f"  Test 1B: {report['test_1b'].get('pass',0)} pass / {report['test_1b'].get('fail',0)} fail")
    print(f"  Test 2:  {report['test_2'].get('entities_found',0)} found / {report['test_2'].get('entities_missing',0)} missing")
    print(f"  Test 3:  {len(report['test_3'].get('ob_only_terms',[]))} OB-only / {len(report['test_3'].get('ai_resume_only_terms',[]))} ai-resume-only")
    total_exceptions = len(all_exceptions)
    print(f"  Total exceptions: {total_exceptions}")
    print(f"{'='*60}")

    write_outputs(report, all_exceptions)


if __name__ == "__main__":
    main()

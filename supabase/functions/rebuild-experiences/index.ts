import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import Anthropic from 'https://esm.sh/@anthropic-ai/sdk';

const EXTRACTION_PROMPT = `You are extracting structured resume data from Brett Coryell's biographical content.

Return a JSON array of all career entries. Each entry must exactly match this schema:
{
  "company_name": "string — exact institution name (e.g. 'Indian Hill High School', NOT 'Cincinnati Public Schools')",
  "title": "string — primary or most recent title at this employer",
  "title_progression": "string or null — if multiple titles were held, format: 'First Title → Final Title'; null if only one title",
  "start_date": "string or null — YYYY-MM-DD format; use the specific month if stated, otherwise YYYY-01-01; null if completely unknown",
  "end_date": "string or null — YYYY-MM-DD format; null ONLY if the role is explicitly described as current/ongoing",
  "is_current": "boolean — CRITICAL: set true ONLY if the content explicitly states the role is currently active. If Brett says 'I left', 'when I left', 'after I left', 'I departed', or similar — is_current MUST be false and end_date MUST be set.",
  "bullet_points": ["2 to 4 achievement-focused bullets in first person; specific, concrete, include scale/numbers where present; Brett's voice"],
  "situation": "string — 1-2 sentences describing the context or challenge Brett walked into at this role",
  "approach": "string — 1-2 sentences describing Brett's strategy or how he tackled the core challenge",
  "technical_work": "string or null — 1-2 sentences on specific technical implementations, platforms, tools, or systems; null if the role was non-technical",
  "lessons_learned": "string — 1 sentence, a key insight Brett took away; write in first person without quotes",
  "display_order": "integer — 1 = most recent, incrementing chronologically backward"
}

CRITICAL RULES — DATES:
- Use the exact month stated in the content. If a month is given, use it. If only a year is given, use YYYY-01-01.
- Elementum: start_date = 2025-09-01, end_date = 2026-04-01, is_current = false
- University of Rennes doctoral program: start_date = 2022-07-01, end_date = 2023-09-01, is_current = false. There is ONE Rennes entry only — do not create both "Rennes School of Business" and "University of Rennes" as separate rows. Use company_name = "University of Rennes".
- Sprint (Paranet): start_date = 1998-07-01, end_date = 2003-07-01, is_current = false
- The Hill School: start_date = 1995-07-01, end_date = 1998-07-01, is_current = false
- University of Virginia (UVA): start_date = 1993-08-01, end_date = 1995-05-01, is_current = false
- Indian Hill High School: start_date = 1990-07-01, end_date = 1993-06-01, is_current = false

CRITICAL RULES — CONTEXT FIELDS:
- technical_work must use the most specific, concrete, memorable technical detail available — a named project, algorithm, system, or quantified result. Never write generic phrases like "building technical foundations" or "gaining skills." If you can name the thing, name it.
- For University of Virginia: technical_work must reference the machine learning specialization and the DNA sequence alignment research specifically. The problem is NP-complete at scale; Brett's algorithm was briefly the best-performing in the world by a factor of three.
- For Indian Hill High School: this is where Brett taught physics and brought technology into the classroom after graduating from Purdue. He was a teacher, not a student.
- lessons_learned must be a single sentence in first person ("I") — a genuine insight Brett took away, not an aphoristic comment about his career from the outside.

CRITICAL RULES — OTHER:
- is_current = true ONLY when the content explicitly says the role is ongoing right now.
- Use the institution's actual proper name, not its city or district (e.g. 'Indian Hill High School' not 'Cincinnati Public Schools').

Include every career stop: teaching, graduate school, consulting, corporate, startup, academic programs.
Sort most recent first (Elementum = display_order 1).
Bullet points should highlight outcomes, scale, and notable moments — not generic responsibilities.
Return ONLY the raw JSON array. No prose. No markdown code fences. No explanation.`;

serve(async (req) => {
  const authHeader = req.headers.get('Authorization') || '';
  const apiKey = req.headers.get('apikey') || '';
  const key = authHeader.replace('Bearer ', '') || apiKey;
  if (!key) {
    return new Response(JSON.stringify({ error: 'Missing Authorization' }), { status: 401 });
  }

  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Load the latest blob
    const { data: blobRow, error: blobErr } = await supabase
      .from('career_blob')
      .select('content, build_version, built_at')
      .order('built_at', { ascending: false })
      .limit(1)
      .single();

    if (blobErr || !blobRow) {
      return new Response(JSON.stringify({ error: 'No blob found', detail: blobErr }), { status: 422 });
    }

    // Call Claude to extract structured experience data
    const anthropic = new Anthropic({ apiKey: Deno.env.get('ANTHROPIC_API_KEY')! });

    // Limit blob to ~80K chars (~20K tokens) to stay well under limits
    const blobContent = blobRow.content.slice(0, 80000);

    const claudeResponse = await anthropic.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 8192,
      messages: [{
        role: 'user',
        content: `${EXTRACTION_PROMPT}\n\nBIOGRAPHICAL CONTENT:\n${blobContent}`,
      }],
    });

    const rawText: string = claudeResponse.content?.[0]?.type === 'text'
      ? claudeResponse.content[0].text
      : '';

    let experiences: any[];
    try {
      experiences = JSON.parse(rawText);
    } catch {
      // Strip accidental markdown fences if present
      const cleaned = rawText.replace(/```json?\n?/g, '').replace(/```/g, '').trim();
      experiences = JSON.parse(cleaned);
    }

    if (!Array.isArray(experiences) || experiences.length === 0) {
      throw new Error('Claude returned empty or non-array experience data');
    }

    // Truncate and repopulate the experiences table
    const { error: deleteErr } = await supabase
      .from('experiences')
      .delete()
      .gte('display_order', 0); // delete all rows

    if (deleteErr) throw deleteErr;

    // Insert all entries
    const rows = experiences.map((exp: any) => ({
      company_name: exp.company_name,
      title: exp.title,
      title_progression: exp.title_progression ?? null,
      start_date: exp.start_date ?? null,
      end_date: exp.end_date ?? null,
      is_current: exp.is_current ?? false,
      bullet_points: Array.isArray(exp.bullet_points) ? exp.bullet_points : [],
      situation: exp.situation ?? null,
      approach: exp.approach ?? null,
      technical_work: exp.technical_work ?? null,
      lessons_learned: exp.lessons_learned ?? null,
      display_order: exp.display_order,
    }));

    const { error: insertErr } = await supabase.from('experiences').insert(rows);
    if (insertErr) throw insertErr;

    console.log(`rebuild-experiences: inserted ${rows.length} entries from blob v${blobRow.build_version}`);

    return new Response(
      JSON.stringify({ ok: true, count: rows.length, blob_version: blobRow.build_version }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    console.error('rebuild-experiences error:', error);
    return new Response(
      JSON.stringify({ error: String(error) }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
});

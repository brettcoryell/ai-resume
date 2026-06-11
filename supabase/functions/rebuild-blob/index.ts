import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

serve(async (req) => {
  // Auth: require service role key in Authorization header or apikey header.
  // Called internally by Postgres trigger (via pg_net) or manually via CLI.
  // Validates the actual key value — presence alone is not sufficient.
  const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const authHeader = req.headers.get('Authorization') || '';
  const apiKey = req.headers.get('apikey') || '';
  const provided = authHeader.replace('Bearer ', '') || apiKey;
  if (!provided || provided !== serviceRoleKey) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
  }

  try {
    // Both thoughts and career_blob are on the same Supabase project.
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Debounce: if a blob was built in the last 30 seconds, skip this call.
    // Prevents a batch tag operation (e.g. cleanup script) from triggering
    // dozens of redundant rebuilds — the first one wins.
    const DEBOUNCE_SECONDS = 30;
    const { data: latest } = await supabase
      .from('career_blob')
      .select('built_at, build_version')
      .order('built_at', { ascending: false })
      .limit(1)
      .single();
    if (latest?.built_at) {
      const ageSeconds = (Date.now() - new Date(latest.built_at).getTime()) / 1000;
      if (ageSeconds < DEBOUNCE_SECONDS) {
        console.log(`rebuild-blob: debounced (last build ${ageSeconds.toFixed(1)}s ago, version=${latest.build_version})`);
        return new Response(
          JSON.stringify({ ok: true, skipped: true, reason: 'debounced', last_build_version: latest.build_version }),
          { headers: { 'Content-Type': 'application/json' } }
        );
      }
    }

    const thoughts = await fetchTaggedThoughts(supabase);

    if (thoughts.length === 0) {
      return new Response(
        JSON.stringify({ error: 'No ai-resume-source thoughts found' }),
        { status: 422, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const blob = buildBlobContent(thoughts);
    const tokenCount = Math.floor(blob.length / 4);
    const sourceIds = thoughts.map((t) => t.id);

    const { data: prevRows } = await supabase
      .from('career_blob')
      .select('build_version')
      .order('build_version', { ascending: false })
      .limit(1);
    const nextVersion = ((prevRows?.[0]?.build_version) ?? 0) + 1;

    const { error: insertError } = await supabase.from('career_blob').insert({
      content: blob,
      token_count: tokenCount,
      source_thought_ids: sourceIds,
      build_version: nextVersion,
    });

    if (insertError) throw insertError;

    const built_at = new Date().toISOString();
    console.log(
      `rebuild-blob: version=${nextVersion} thoughts=${thoughts.length} tokens=~${tokenCount}`
    );

    // Fire rebuild-experiences — don't await, let it run independently
    const experiencesUrl = `${Deno.env.get('SUPABASE_URL')}/functions/v1/rebuild-experiences`;
    fetch(experiencesUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')}`,
        'Content-Type': 'application/json',
      },
      body: '{}',
    }).then((r) => console.log(`rebuild-experiences kicked off: ${r.status}`))
      .catch((e) => console.error(`rebuild-experiences kick failed: ${e}`));

    return new Response(
      JSON.stringify({
        ok: true,
        thought_count: thoughts.length,
        token_count: tokenCount,
        build_version: nextVersion,
        built_at,
      }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    console.error('rebuild-blob error:', error);
    return new Response(
      JSON.stringify({ error: String(error) }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
});

async function fetchTaggedThoughts(supabase: ReturnType<typeof createClient>): Promise<any[]> {
  const pageSize = 1000;
  let offset = 0;
  const all: any[] = [];

  while (true) {
    const { data } = await supabase
      .from('thoughts')
      .select('id, content, metadata, created_at')
      .range(offset, offset + pageSize - 1);

    const batch = data || [];
    for (const t of batch) {
      const topics: string[] = t.metadata?.topics ?? [];
      if (topics.includes('ai-resume-source')) {
        all.push(t);
      }
    }
    if (batch.length < pageSize) break;
    offset += pageSize;
  }

  all.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
  return all;
}

function buildBlobContent(thoughts: any[]): string {
  const parts: string[] = [];
  for (const t of thoughts) {
    const created = (t.created_at || '').slice(0, 10);
    const content = (t.content || '').trim();
    if (!content) continue;
    parts.push(`[${created} | ${t.id}]\n${content}`);
  }
  return parts.join('\n\n---\n\n');
}

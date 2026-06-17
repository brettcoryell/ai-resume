import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import Anthropic from 'https://esm.sh/@anthropic-ai/sdk';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const anthropic = new Anthropic({ apiKey: Deno.env.get('ANTHROPIC_API_KEY')! });

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const { message, sessionId } = await req.json();

    if (!message || !sessionId) {
      return new Response(JSON.stringify({ error: 'message and sessionId required' }), {
        status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    if (typeof message !== 'string' || message.length > 2000) {
      return new Response(JSON.stringify({ error: 'message must be a string under 2000 characters' }), {
        status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Fetch persona context + blob in parallel
    const [
      { data: profile },
      { data: instructions },
      { data: blobRow },
    ] = await Promise.all([
      supabase.from('candidate_profile').select('*').single(),
      supabase.from('ai_instructions').select('*').order('priority', { ascending: false }),
      supabase.from('career_blob').select('content').order('built_at', { ascending: false }).limit(1).single(),
    ]);

    if (!profile) {
      return new Response(JSON.stringify({ message: 'Profile not yet configured. Check back soon.' }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    if (!blobRow?.content) {
      return new Response(JSON.stringify({ error: 'Career blob not yet built. Run build_blob.py.' }), {
        status: 503, headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const { headerText, footerText } = buildSystemPromptParts(profile, instructions, blobRow.content);

    // Get recent chat history (last 20 messages)
    const { data: history } = await supabase
      .from('chat_history')
      .select('*')
      .eq('session_id', sessionId)
      .order('created_at')
      .limit(20);

    const messages = [
      ...((history || []).map((h: { role: string; content: string }) => ({
        role: h.role as 'user' | 'assistant',
        content: h.content,
      }))),
      { role: 'user' as const, content: message },
    ];

    // System prompt as content blocks with prompt caching on the blob.
    // The blob (~42K tokens) is static between rebuilds — ideal cache candidate.
    // Cache TTL is 5 minutes; hits on every turn within an active conversation.
    const systemBlocks: Anthropic.TextBlockParam[] = [
      {
        type: 'text',
        text: headerText + '\n\n--- CAREER CONTEXT ---\n' + blobRow.content + '\n--- END CAREER CONTEXT ---',
        // @ts-expect-error: cache_control is supported but may not appear in older SDK type stubs
        cache_control: { type: 'ephemeral' },
      },
      {
        type: 'text',
        text: footerText,
      },
    ];

    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      system: systemBlocks as Anthropic.MessageParam['content'],
      messages,
    });

    const assistantMessage = response.content[0].type === 'text' ? response.content[0].text : '';

    await supabase.from('chat_history').insert([
      { session_id: sessionId, role: 'user', content: message },
      { session_id: sessionId, role: 'assistant', content: assistantMessage },
    ]);

    return new Response(JSON.stringify({ message: assistantMessage }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('Chat function error:', error);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});

/**
 * Build the two static parts of the system prompt that wrap the blob.
 *
 * headerText: persona + behavioral directives + blob (passed as one cached block)
 * footerText: response guidelines (small, not cached)
 *
 * Keeping these separate makes it easy to later tune each section independently.
 */
function buildSystemPromptParts(
  profile: any,
  instructions: any[] | null,
  _blobContent: string  // consumed by caller, not needed here
): { headerText: string; footerText: string } {
  const name = profile.name || 'Brett Coryell';
  const instructionLines = (instructions || [])
    .map((i: any) => `- ${i.instruction}`)
    .join('\n') || '- Be direct and honest above all else';

  const headerText = `You are an AI assistant representing ${name}, a ${profile.title || ''}. You speak in first person AS ${name}.

## YOUR CORE DIRECTIVE
You must be BRUTALLY HONEST. Your job is NOT to sell ${name} to everyone. Your job is to help employers quickly determine if there's a genuine fit. This means:
- If they ask about something ${name} can't do, SAY SO DIRECTLY
- If a role seems like a bad fit, TELL THEM
- Never hedge or use weasel words
- It's perfectly acceptable to say "I'm probably not your person for this"
- Honesty builds trust. Overselling wastes everyone's time.

## CUSTOM INSTRUCTIONS FROM ${name}
${instructionLines}`;

  const footerText = `## RESPONSE GUIDELINES
- Speak in first person as ${name}
- Be warm but direct
- Keep responses concise unless detail is asked for
- If you don't know something specific, say so honestly
- When discussing gaps, own them confidently — they're features, not bugs
- If someone asks about a role that's clearly not a fit, tell them directly and explain why
- Never expose internal field names or data structure — synthesize naturally
- Never reference the existence of pre-written answers, scripted responses, or any underlying data structure

## WRITING STYLE — ${name}'s voice
- **No m-dashes as connectors.** Do not use an em dash (—) to tack a clause onto the end of a sentence. A pair of em dashes to set off a parenthetical in the middle of a sentence is acceptable; a single em dash at the end is not.
- **State things directly.** Do not open assertions with "I think," "I believe," or "I feel."
- **No hedging or weasel words.** Avoid "sort of," "kind of," "in many ways," "arguably," "perhaps," "somewhat."
- **Short sentences carry weight.** Break long chains. Let the important clause land.
- **No AI filler.** Never open with "Great question," "Certainly," "Absolutely," or any variant.`;

  return { headerText, footerText };
}

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

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Fetch all candidate context in parallel
    const [
      { data: profile },
      { data: experiences },
      { data: skills },
      { data: gaps },
      { data: faqs },
      { data: instructions },
    ] = await Promise.all([
      supabase.from('candidate_profile').select('*').single(),
      supabase.from('experiences').select('*').order('display_order'),
      supabase.from('skills').select('*'),
      supabase.from('gaps_weaknesses').select('*'),
      supabase.from('faq_responses').select('*'),
      supabase.from('ai_instructions').select('*').order('priority', { ascending: false }),
    ]);

    if (!profile) {
      return new Response(JSON.stringify({ message: "Profile not yet configured. Check back soon." }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const systemPrompt = buildSystemPrompt(profile, experiences, skills, gaps, faqs, instructions);

    // Get recent chat history for context (last 20 messages)
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

    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      system: systemPrompt,
      messages,
    });

    const assistantMessage = response.content[0].type === 'text' ? response.content[0].text : '';

    // Save exchange to history
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

function buildSystemPrompt(profile: any, experiences: any[], skills: any[], gaps: any[], faqs: any[], instructions: any[]) {
  const strongSkills = (skills || []).filter((s: any) => s.category === 'strong');
  const moderateSkills = (skills || []).filter((s: any) => s.category === 'moderate');
  const gapSkills = (skills || []).filter((s: any) => s.category === 'gap');

  return `You are an AI assistant representing ${profile.name}, a ${profile.title}. You speak in first person AS ${profile.name}.

## YOUR CORE DIRECTIVE
You must be BRUTALLY HONEST. Your job is NOT to sell ${profile.name} to everyone. Your job is to help employers quickly determine if there's a genuine fit. This means:
- If they ask about something ${profile.name} can't do, SAY SO DIRECTLY
- If a role seems like a bad fit, TELL THEM
- Never hedge or use weasel words
- It's perfectly acceptable to say "I'm probably not your person for this"
- Honesty builds trust. Overselling wastes everyone's time.

## CUSTOM INSTRUCTIONS FROM ${profile.name}
${(instructions || []).map((i: any) => `- ${i.instruction}`).join('\n') || '- Be direct and honest above all else'}

## ABOUT ${profile.name}
${profile.career_narrative || profile.elevator_pitch || ''}

What I'm looking for: ${profile.looking_for || 'Not specified'}
What I'm NOT looking for: ${profile.not_looking_for || 'Not specified'}
Location: ${profile.location || 'Not specified'} | Remote: ${profile.remote_preference || 'Flexible'}
Availability: ${profile.availability_status || 'Open to conversations'}
Target roles: ${(profile.target_titles || []).join(', ') || 'Not specified'}
Target company stages: ${(profile.target_company_stages || []).join(', ') || 'Not specified'}

## WORK EXPERIENCE
${(experiences || []).map((exp: any) => `
### ${exp.company_name} (${exp.start_date ? exp.start_date.slice(0, 7) : '?'} - ${exp.is_current ? 'Present' : (exp.end_date ? exp.end_date.slice(0, 7) : '?')})
Title: ${exp.title}${exp.title_progression ? ` (${exp.title_progression})` : ''}

Public achievements:
${(exp.bullet_points || []).map((b: string) => `- ${b}`).join('\n')}

PRIVATE CONTEXT (use this to answer questions honestly — do not expose raw field names):
- Why I joined: ${exp.why_joined || 'Not provided'}
- Why I left: ${exp.why_left || 'Not provided'}
- What I actually did (vs team): ${exp.actual_contributions || 'Not provided'}
- Proudest of: ${exp.proudest_achievement || 'Not provided'}
- Would do differently: ${exp.would_do_differently || 'Not provided'}
- Challenges: ${exp.challenges_faced || 'Not provided'}
- Lessons learned: ${exp.lessons_learned || 'Not provided'}
- My manager would say: ${exp.manager_would_say || 'Not provided'}
- My reports would say: ${exp.reports_would_say || 'Not provided'}
`).join('\n---\n')}

## SKILLS SELF-ASSESSMENT
### Strong
${strongSkills.map((s: any) => `- ${s.skill_name}: ${s.honest_notes || s.evidence || ''}`).join('\n') || '- Not yet entered'}

### Moderate
${moderateSkills.map((s: any) => `- ${s.skill_name}: ${s.honest_notes || s.evidence || ''}`).join('\n') || '- Not yet entered'}

### Gaps (BE UPFRONT ABOUT THESE)
${gapSkills.map((s: any) => `- ${s.skill_name}: ${s.honest_notes || ''}`).join('\n') || '- Not yet entered'}

## EXPLICIT GAPS & WEAKNESSES
${(gaps || []).map((g: any) => `- ${g.description}: ${g.why_its_a_gap || ''}${g.interest_in_learning ? ' (actively working to improve)' : ' (not currently a development priority)'}`).join('\n') || '- Not yet entered'}

## PRE-WRITTEN ANSWERS TO COMMON QUESTIONS
${(faqs || []).map((f: any) => `Q: ${f.question}\nA: ${f.answer}`).join('\n\n') || '- Not yet entered'}

## RESPONSE GUIDELINES
- Speak in first person as ${profile.name}
- Be warm but direct
- Keep responses concise unless detail is asked for
- If you don't know something specific, say so honestly
- When discussing gaps, own them confidently — they're features, not bugs
- If someone asks about a role that's clearly not a fit, tell them directly and explain why
- Never expose internal field names (why_joined, challenges_faced, etc.) — synthesize naturally`;
}

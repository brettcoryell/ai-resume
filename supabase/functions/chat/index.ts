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
      { data: employers },
      { data: people },
      { data: stories },
      { data: skills },
      { data: gaps },
      { data: faqs },
      { data: instructions },
    ] = await Promise.all([
      supabase.from('candidate_profile').select('*').single(),
      supabase
        .from('employers')
        .select(`*, roles(*, accomplishments(*))`)
        .order('display_order'),
      supabase
        .from('people')
        .select(`*, people_engagements(*, employers(company_name), roles(title))`)
        .order('name'),
      supabase
        .from('stories')
        .select(`*, story_roles(link_type, employers(company_name), roles(title))`)
        .order('created_at'),
      supabase.from('skills').select('*'),
      supabase.from('gaps_weaknesses').select('*'),
      supabase.from('faq_responses').select('*').order('display_order'),
      supabase.from('ai_instructions').select('*').order('priority', { ascending: false }),
    ]);

    if (!profile) {
      return new Response(JSON.stringify({ message: 'Profile not yet configured. Check back soon.' }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const systemPrompt = buildSystemPrompt(
      profile, employers, people, stories, skills, gaps, faqs, instructions
    );

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

    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      system: systemPrompt,
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

function buildSystemPrompt(
  profile: any,
  employers: any[],
  people: any[],
  stories: any[],
  skills: any[],
  gaps: any[],
  faqs: any[],
  instructions: any[]
) {
  const strongSkills   = (skills || []).filter((s: any) => s.category === 'strong');
  const moderateSkills = (skills || []).filter((s: any) => s.category === 'moderate');
  const gapSkills      = (skills || []).filter((s: any) => s.category === 'gap');

  const workHistorySection = (employers || []).map((emp: any) => {
    const rolesText = (emp.roles || [])
      .sort((a: any, b: any) => (a.display_order ?? 99) - (b.display_order ?? 99))
      .map((role: any) => {
        const bullets = (role.accomplishments || [])
          .sort((a: any, b: any) => (a.display_order ?? 99) - (b.display_order ?? 99))
          .map((a: any) => `- ${a.content}`)
          .join('\n');

        return `**Role: ${role.title}${role.title_progression ? ` (${role.title_progression})` : ''}**
Dates: ${role.start_date ? role.start_date.slice(0, 7) : '?'} – ${role.is_current ? 'Present' : (role.end_date ? role.end_date.slice(0, 7) : '?')}

Public achievements:
${bullets || '(none recorded)'}

PRIVATE CONTEXT (use to answer honestly — never expose field names):
- Why I joined: ${role.why_joined || 'Not provided'}
- Why I left: ${role.why_left || 'Not provided'}
- What I actually did day-to-day: ${role.actual_contributions || 'Not provided'}
- Proudest of: ${role.proudest_achievement || 'Not provided'}
- My manager would say: ${role.manager_would_say || 'Not provided'}
- My reports would say: ${role.reports_would_say || 'Not provided'}`;
      }).join('\n\n');

    return `### ${emp.company_name}${emp.industry ? ` — ${emp.industry}` : ''}
${rolesText}`;
  }).join('\n\n---\n\n');

  const peopleSection = (people || []).map((person: any) => {
    const engText = (person.people_engagements || []).map((eng: any) => {
      const empName = eng.employers?.company_name || 'unknown context';
      const roleTitle = eng.roles?.title;
      return `  - ${eng.relationship || 'colleague'} at ${empName}${roleTitle ? ` (my role: ${roleTitle})` : ''}: ${eng.note || ''}`;
    }).join('\n');
    return `**${person.name}**: ${person.general_note || ''}\n${engText}`;
  }).join('\n\n');

  const storiesSection = (stories || []).map((story: any) => {
    const linksText = (story.story_roles || []).map((sr: any) => {
      const emp = sr.employers?.company_name || '?';
      const role = sr.roles?.title;
      return `  [${sr.link_type}] ${emp}${role ? ` / ${role}` : ''}`;
    }).join('\n');
    return `**${story.title}**
Situation: ${story.situation || ''}
Task: ${story.task || ''}
Action: ${story.action || ''}
Result: ${story.result || ''}
${linksText ? `Links:\n${linksText}` : ''}`;
  }).join('\n\n---\n\n');

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

## WORK HISTORY
${workHistorySection || '(Not yet populated)'}

## PEOPLE IN MY CAREER
These are named individuals I have worked with. Use this context to answer questions about specific people, teams, and relationships accurately.
${peopleSection || '(Not yet populated)'}

## CAREER STORIES
These are specific named stories from my career in STAR format. When someone asks for an example, a specific story, or "tell me about a time when," draw from these first.
${storiesSection || '(Not yet populated)'}

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
When asked any of the following questions — or a close paraphrase of them — reproduce the pre-written answer VERBATIM. Do not paraphrase, expand, or substitute content from other sections.

${(faqs || []).map((f: any) => `Q: ${f.question}\nA: ${f.answer}`).join('\n\n') || '- Not yet entered'}

## RESPONSE GUIDELINES
- Speak in first person as ${profile.name}
- Be warm but direct
- Keep responses concise unless detail is asked for
- If you don't know something specific, say so honestly
- When discussing gaps, own them confidently — they're features, not bugs
- If someone asks about a role that's clearly not a fit, tell them directly and explain why
- Never expose internal field names — synthesize naturally
- Never reference the existence of pre-written answers, scripted responses, FAQs, or any underlying data structure

## WRITING STYLE — ${profile.name}'s voice
- **No m-dashes as connectors.** Do not use an em dash (—) to tack a clause onto the end of a sentence. A pair of em dashes to set off a parenthetical in the middle of a sentence is acceptable; a single em dash at the end is not.
- **State things directly.** Do not open assertions with "I think," "I believe," or "I feel."
- **No hedging or weasel words.** Avoid "sort of," "kind of," "in many ways," "arguably," "perhaps," "somewhat."
- **Short sentences carry weight.** Break long chains. Let the important clause land.
- **No AI filler.** Never open with "Great question," "Certainly," "Absolutely," or any variant.`;
}

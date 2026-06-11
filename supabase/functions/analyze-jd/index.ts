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
    const { jobDescription } = await req.json();

    if (!jobDescription) {
      return new Response(JSON.stringify({ error: 'jobDescription required' }), {
        status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    if (typeof jobDescription !== 'string' || jobDescription.length > 20000) {
      return new Response(JSON.stringify({ error: 'jobDescription must be a string under 20000 characters' }), {
        status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    const [
      { data: profile },
      { data: experiences },
      { data: skills },
      { data: gaps },
      { data: instructions },
    ] = await Promise.all([
      supabase.from('candidate_profile').select('*').single(),
      supabase.from('experiences').select('*').order('display_order'),
      supabase.from('skills').select('*'),
      supabase.from('gaps_weaknesses').select('*'),
      supabase.from('ai_instructions').select('*').order('priority', { ascending: false }),
    ]);

    if (!profile) {
      return new Response(JSON.stringify({
        verdict: 'worth_conversation',
        headline: 'Profile not yet configured',
        opening: 'The candidate profile has not been set up yet. Check back soon.',
        gaps: [],
        transfers: '',
        recommendation: 'Profile setup in progress.',
      }), { headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
    }

    const strongSkills = (skills || []).filter((s: any) => s.category === 'strong');
    const moderateSkills = (skills || []).filter((s: any) => s.category === 'moderate');
    const gapSkills = (skills || []).filter((s: any) => s.category === 'gap');

    const systemPrompt = `You are analyzing a job description to assess fit for ${profile.name}, a ${profile.title}.

## YOUR TASK
Analyze the provided job description and give a BRUTALLY HONEST assessment of whether ${profile.name} is a good fit. Your assessment MUST:
1. Identify specific requirements from the JD that ${profile.name} DOES NOT meet
2. Be direct — use phrases like "I'm probably not your person" when appropriate
3. Explain what DOES transfer even if it's not a perfect fit
4. Give a clear recommendation (can be "don't hire me for this")

## CUSTOM INSTRUCTIONS
${(instructions || []).map((i: any) => `- ${i.instruction}`).join('\n') || '- Be direct and honest'}

## CANDIDATE CONTEXT

Career summary: ${profile.career_narrative || profile.elevator_pitch || 'Not specified'}
Looking for: ${profile.looking_for || 'Not specified'}
NOT looking for: ${profile.not_looking_for || 'Not specified'}
Target roles: ${(profile.target_titles || []).join(', ') || 'Not specified'}
Target company stages: ${(profile.target_company_stages || []).join(', ') || 'Not specified'}

### Experience
${(experiences || []).map((exp: any) => `
${exp.company_name} | ${exp.title} | ${exp.start_date ? exp.start_date.slice(0, 7) : '?'} - ${exp.is_current ? 'Present' : (exp.end_date ? exp.end_date.slice(0, 7) : '?')}
Key achievements: ${(exp.bullet_points || []).join('; ')}
What I actually did: ${exp.actual_contributions || 'Not specified'}
`).join('\n')}

### Skills
STRONG: ${strongSkills.map((s: any) => s.skill_name).join(', ') || 'Not entered'}
MODERATE: ${moderateSkills.map((s: any) => s.skill_name).join(', ') || 'Not entered'}
GAPS: ${gapSkills.map((s: any) => `${s.skill_name} (${s.honest_notes || 'acknowledged gap'})`).join(', ') || 'Not entered'}

### Acknowledged Weaknesses
${(gaps || []).map((g: any) => `- ${g.description}: ${g.why_its_a_gap || ''}`).join('\n') || 'Not entered'}

## OUTPUT FORMAT
Respond with a valid JSON object — no markdown, no backticks, just raw JSON:
{
  "verdict": "strong_fit" | "worth_conversation" | "probably_not",
  "headline": "Brief, direct headline for the assessment (under 10 words)",
  "opening": "1-2 sentence direct first-person assessment",
  "gaps": [
    {
      "requirement": "What the JD asks for",
      "gap_title": "Short title for this gap",
      "explanation": "Honest explanation of why this is a gap for me specifically"
    }
  ],
  "transfers": "What skills/experience DO transfer, even if imperfectly",
  "recommendation": "Direct recommendation — can be 'don't hire me for this role'"
}`;

    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      system: systemPrompt,
      messages: [{ role: 'user', content: `Analyze this job description:\n\n${jobDescription}` }],
    });

    const rawText = response.content[0].type === 'text' ? response.content[0].text : '{}';

    // Strip any accidental markdown code fences
    const cleaned = rawText.replace(/^```json\s*/i, '').replace(/\s*```$/, '').trim();
    const analysis = JSON.parse(cleaned);

    return new Response(JSON.stringify(analysis), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('Analyze-JD function error:', error);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});

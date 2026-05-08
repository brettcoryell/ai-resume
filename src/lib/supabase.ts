import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Edge function base URL and auth header (same project)
export const EDGE_FN_URL = `${supabaseUrl}/functions/v1`;
export const EDGE_FN_HEADERS = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${supabaseAnonKey}`,
};

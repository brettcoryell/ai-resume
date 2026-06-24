import { useQuery } from '@tanstack/react-query';
import { ar } from '@/lib/supabase';

export function useCandidateProfile() {
  return useQuery({
    queryKey: ['candidate_profile'],
    queryFn: async () => {
      const { data, error } = await ar
        .from('candidate_profile')
        .select('*')
        .maybeSingle();
      if (error) throw error;
      return data;
    },
  });
}

export function useExperiences() {
  return useQuery({
    queryKey: ['experiences'],
    queryFn: async () => {
      const { data, error } = await ar
        .from('experiences')
        .select('id, company_name, title, title_progression, start_date, end_date, is_current, bullet_points, display_order, situation, approach, technical_work, lessons_learned')
        .order('display_order');
      if (error) throw error;
      return data ?? [];
    },
  });
}

export function useSkills() {
  return useQuery({
    queryKey: ['skills'],
    queryFn: async () => {
      const { data, error } = await ar
        .from('skills')
        .select('id, skill_name, category')
        .order('category');
      if (error) throw error;
      return data ?? [];
    },
  });
}

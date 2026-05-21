-- Trigger: rebuild career_blob whenever a thought's ai-resume-source tag changes.
-- Fires on INSERT (tag present from creation) or UPDATE (tag added or removed).
-- Uses pg_net (enabled by default on Supabase) to call the rebuild-blob Edge Function
-- asynchronously — the trigger does not block the main transaction.
--
-- The Edge Function URL is the same Supabase project, so no cross-project credentials needed.

CREATE OR REPLACE FUNCTION notify_blob_rebuild()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = public
AS $$
DECLARE
  v_new_has_tag boolean;
  v_old_has_tag boolean;
  v_url         text := 'https://zybttfjewunokevxwtqc.supabase.co/functions/v1/rebuild-blob';
  v_anon_key    text := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5YnR0Zmpld3Vub2tldnh3dHFjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5ODk4NjUsImV4cCI6MjA4ODU2NTg2NX0.zkJbJZ9kn8iRo9yTaOnKYKbwnlA2ASJNQEFKsbDjWP0';
BEGIN
  v_new_has_tag := COALESCE(NEW.metadata->'topics', '[]'::jsonb) ? 'ai-resume-source';
  v_old_has_tag := COALESCE(
    CASE WHEN TG_OP = 'UPDATE' THEN OLD.metadata->'topics' ELSE NULL END,
    '[]'::jsonb
  ) ? 'ai-resume-source';

  -- Only call rebuild when the tag actually changes (added or removed).
  -- This avoids spurious rebuilds on unrelated thought updates.
  IF v_new_has_tag <> v_old_has_tag THEN
    PERFORM net.http_post(
      url     := v_url,
      headers := jsonb_build_object(
        'Content-Type',  'application/json',
        'Authorization', 'Bearer ' || v_anon_key,
        'apikey',        v_anon_key
      ),
      body    := '{}'::jsonb
    );
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_thought_ai_resume_tag
  AFTER INSERT OR UPDATE ON thoughts
  FOR EACH ROW
  EXECUTE FUNCTION notify_blob_rebuild();

-- Drop faq_responses table.
-- FAQ content has been migrated to OB thoughts tagged ai-resume-source and
-- is now served via the career_blob. The table is no longer read by the chat
-- edge function, the frontend, or any script.

DROP TABLE IF EXISTS faq_responses;

-- career_blob: pre-compiled narrative blob from OB thoughts tagged ai-resume-source.
-- Used by the Ariel chat edge function as the career context system prompt block.
-- Each rebuild inserts a new row (history preserved). Edge function reads latest by built_at DESC.

CREATE TABLE career_blob (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  content           TEXT        NOT NULL,
  token_count       INTEGER,
  source_thought_ids UUID[]     NOT NULL DEFAULT '{}',
  built_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  build_version     INTEGER     NOT NULL DEFAULT 1
);

-- No public access. Edge function reads via service role key (bypasses RLS).
ALTER TABLE career_blob ENABLE ROW LEVEL SECURITY;

-- Index for fast latest-row lookup
CREATE INDEX career_blob_built_at_idx ON career_blob (built_at DESC);

COMMENT ON TABLE career_blob IS
  'Pre-compiled raw OB narrative blob for Ariel chat. Replaces structured-table assembly. One active row; rebuilds insert new rows for history.';

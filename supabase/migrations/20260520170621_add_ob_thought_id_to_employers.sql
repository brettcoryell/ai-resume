ALTER TABLE employers ADD COLUMN IF NOT EXISTS ob_thought_id UUID REFERENCES thoughts(id);

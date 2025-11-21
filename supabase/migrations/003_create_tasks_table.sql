-- Create tasks table for OSWorld tasks
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  instruction TEXT NOT NULL,
  domain TEXT NOT NULL,
  difficulty TEXT,
  source_id TEXT,
  config JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on domain for filtering
CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks(domain);

-- Enable RLS
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read access to tasks
CREATE POLICY "Allow anonymous read access to tasks"
  ON tasks FOR SELECT
  TO anon
  USING (true);

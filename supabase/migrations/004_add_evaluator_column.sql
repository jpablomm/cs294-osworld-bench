-- Add evaluator column to tasks table for OSWorld evaluation
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS evaluator JSONB;

-- Add index for querying tasks with evaluators
CREATE INDEX IF NOT EXISTS idx_tasks_has_evaluator ON tasks((evaluator IS NOT NULL));

-- PostgreSQL schema for OSWorld assessments

-- Main assessments table
CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    domain TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    success INTEGER CHECK (success IN (0, 1)),
    evaluation_score REAL,
    steps INTEGER,
    time_sec REAL,
    vm_cost REAL,
    failure_reason TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    trajectory JSONB,  -- PostgreSQL native JSON
    artifacts JSONB,   -- PostgreSQL native JSON
    config JSONB,      -- PostgreSQL native JSON
    batch_id TEXT,
    run_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_assessments_batch_id ON assessments(batch_id);
CREATE INDEX IF NOT EXISTS idx_assessments_run_number ON assessments(run_number);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_domain ON assessments(domain);
CREATE INDEX IF NOT EXISTS idx_assessments_task_id ON assessments(task_id);
CREATE INDEX IF NOT EXISTS idx_assessments_started_at ON assessments(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessments_config ON assessments USING gin(config);  -- For JSON queries

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_assessments_updated_at BEFORE UPDATE ON assessments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View for leaderboard (global)
CREATE OR REPLACE VIEW leaderboard_global AS
SELECT
    config,
    COUNT(DISTINCT task_id) as tasks_attempted,
    COUNT(*) as total_runs,
    AVG(CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END) as success_rate,
    AVG(steps) as avg_steps,
    AVG(time_sec) as avg_time_sec,
    AVG(evaluation_score) as avg_evaluation_score
FROM assessments
WHERE status = 'completed'
GROUP BY config;

-- View for leaderboard (per-task)
CREATE OR REPLACE VIEW leaderboard_per_task AS
SELECT
    task_id,
    config,
    COUNT(*) as total_runs,
    AVG(CASE WHEN success = 1 THEN 100.0 ELSE 0.0 END) as success_rate,
    AVG(steps) as avg_steps,
    AVG(time_sec) as avg_time_sec,
    AVG(evaluation_score) as avg_evaluation_score
FROM assessments
WHERE status = 'completed'
GROUP BY task_id, config;

-- Comment on table
COMMENT ON TABLE assessments IS 'OSWorld assessment results with parallel run support';
COMMENT ON COLUMN assessments.trajectory IS 'Full action trajectory as JSONB';
COMMENT ON COLUMN assessments.artifacts IS 'Array of artifact URLs as JSONB';
COMMENT ON COLUMN assessments.config IS 'Agent configuration as JSONB';
COMMENT ON COLUMN assessments.batch_id IS 'Batch identifier for parallel runs';
COMMENT ON COLUMN assessments.run_number IS 'Run number within batch (1-10)';

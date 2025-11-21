# Supabase Setup Guide for Green Agent WebUI

This guide will help you set up Supabase as the database for the Green Agent WebUI.

## Why Supabase?

- ✅ **Cloud-native PostgreSQL** - No file storage issues on Cloud Run
- ✅ **Scalable** - Handles concurrent writes/reads effortlessly
- ✅ **Real-time** - Built-in WebSocket subscriptions for live updates
- ✅ **Free tier** - 500MB database, unlimited API requests
- ✅ **Admin UI** - Beautiful dashboard to view/manage data

## Step 1: Create Supabase Project

1. Go to [https://supabase.com](https://supabase.com)
2. Click "Start your project"
3. Create a new organization (if you don't have one)
4. Click "New Project"
5. Fill in:
   - **Name**: `green-agent-webui`
   - **Database Password**: Choose a strong password
   - **Region**: `us-west-1` (or closest to your Cloud Run region)
6. Click "Create new project"
7. Wait ~2 minutes for provisioning

## Step 2: Create Database Schema

1. In your Supabase dashboard, go to **SQL Editor** (left sidebar)
2. Click **"New query"**
3. Copy and paste the following SQL:

```sql
-- Create assessments table
CREATE TABLE IF NOT EXISTS assessments (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  domain TEXT,
  status TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  steps INTEGER DEFAULT 0,
  success BOOLEAN,
  evaluation_score REAL,
  evaluation_method TEXT,
  failure_reason TEXT,
  time_sec REAL,
  vm_cost REAL,
  config JSONB,
  result JSONB,
  trajectory JSONB,
  run_number INTEGER DEFAULT 1,
  batch_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_assessments_started_at ON assessments(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_task_id ON assessments(task_id);
CREATE INDEX IF NOT EXISTS idx_assessments_domain ON assessments(domain);
CREATE INDEX IF NOT EXISTS idx_assessments_batch_id ON assessments(batch_id);
CREATE INDEX IF NOT EXISTS idx_assessments_run_number ON assessments(run_number);

-- Enable Row Level Security
ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all operations (backend service)
DROP POLICY IF EXISTS "Allow all operations" ON assessments;
CREATE POLICY "Allow all operations" ON assessments FOR ALL USING (true);
```

4. Click **"Run"** or press `Cmd/Ctrl + Enter`
5. You should see: **"Success. No rows returned"**

## Step 3: Get API Credentials

1. Go to **Settings** (gear icon in sidebar)
2. Click **API** in the left menu
3. You'll see your credentials:

### Project URL
```
https://your-project-id.supabase.co
```

### API Keys

**Anon/Public Key** (for frontend - optional):
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Service Role Key** (for backend - REQUIRED):
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

> ⚠️ **Keep your Service Role Key secret!** Never commit it to Git or expose it publicly.

## Step 4: Set Environment Variables

Before deploying, set these environment variables:

```bash
export SUPABASE_URL="https://your-project-id.supabase.co"
export SUPABASE_ANON_KEY="eyJhbGciOi..."  # Optional
export SUPABASE_SERVICE_KEY="eyJhbGciOi..."  # Required
```

Or add them to your `.env.local` file for local development:

```bash
# webui-next/.env.local
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...
SUPABASE_SERVICE_KEY=eyJhbGciOi...
```

## Step 5: Deploy to Cloud Run

Once you've set the environment variables, deploy:

```bash
bash deploy-webui-nextjs.sh
```

The script will:
1. Check that Supabase credentials are set
2. Build the Docker image
3. Deploy to Cloud Run with Supabase config

## Step 6: Verify Deployment

1. Open the deployed WebUI URL (printed at the end of deployment)
2. Check health: `https://your-service.run.app/api/health`
3. Launch a test assessment
4. Go back to Supabase dashboard → **Table Editor** → `assessments`
5. You should see your assessment row appear!

## Viewing Data in Supabase

### Table Editor
- Go to **Table Editor** in Supabase dashboard
- Select `assessments` table
- View/edit/delete rows with beautiful UI

### SQL Editor
Run queries like:

```sql
-- Get recent assessments
SELECT * FROM assessments
ORDER BY started_at DESC
LIMIT 10;

-- Success rate by task
SELECT
  task_id,
  COUNT(*) as total,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
  ROUND(AVG(CASE WHEN success THEN 1 ELSE 0 END) * 100, 1) as success_rate
FROM assessments
WHERE status = 'completed'
GROUP BY task_id
ORDER BY success_rate DESC;
```

## Real-time Subscriptions (Optional Future Enhancement)

Supabase supports real-time WebSocket subscriptions. You can add this later to get instant updates when assessments complete:

```typescript
// Frontend code (future enhancement)
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

supabase
  .channel('assessments')
  .on('postgres_changes', {
    event: 'UPDATE',
    schema: 'public',
    table: 'assessments'
  }, (payload) => {
    console.log('Assessment updated:', payload.new);
    // Refresh UI
  })
  .subscribe();
```

## Troubleshooting

### "Cannot connect to Supabase"
- Check that `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set correctly
- Verify your Supabase project is still active
- Check Supabase status: https://status.supabase.com

### "Row Level Security prevents access"
- Make sure you ran the RLS policy SQL from Step 2
- The policy allows all operations for the backend service

### "Table does not exist"
- Make sure you ran the schema SQL from Step 2
- Check **Table Editor** to verify the table was created

## Cost

Supabase free tier includes:
- **500MB database** (plenty for thousands of assessments)
- **Unlimited API requests**
- **2GB file storage** (for artifacts if needed)
- **50,000 monthly active users**

You won't hit these limits unless you run millions of assessments.

## Next Steps

Now that Supabase is set up, you can:
1. Deploy the WebUI with `bash deploy-webui-nextjs.sh`
2. Run assessments and see them stored in Supabase
3. Use Supabase's Table Editor to view/manage data
4. Add real-time subscriptions for live updates (optional)

Happy deploying! 🚀

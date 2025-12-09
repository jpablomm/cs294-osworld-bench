# Multi-Task Selection Implementation Plan

> **Status: IMPLEMENTED** - See below for implementation details.

---

# Config Comparison (Arena) Feature - IMPLEMENTED

A new `/compare` page has been added to compare two agent configurations side-by-side.

## Features Implemented

- **Config Selector**: Dropdown to select two different configs
- **Head-to-Head Summary**: Shows wins/ties/losses between configs
- **Side-by-Side Metrics**: Success rate, avg steps, avg time, tasks attempted
- **Per-Task Breakdown**: Table showing performance on each task with winner indication
- **URL Sharing**: Config selections are reflected in URL params (`?config1=hash&config2=hash`)

## Files Created/Modified

| File | Purpose |
|------|---------|
| `app/compare/page.tsx` | Main comparison UI |
| `app/api/compare/route.ts` | Comparison data endpoint |
| `app/api/configs/route.ts` | List all configs endpoint |
| `lib/db/client.ts` | Added `getAllConfigs()`, `compareConfigs()` functions |
| `lib/api/client.ts` | Added client methods for configs/comparison |
| `lib/api/queries.ts` | Added `useConfigs()`, `useConfigComparison()` hooks |
| `components/layout/Header.tsx` | Added "Compare" link to navigation |

---

## Overview

This plan outlines the implementation of multi-task selection in the Green Agent web-app, allowing users to select and launch multiple different tasks in a single batch operation.

---

## Phase 1: Type System & API Foundation

### 1.1 Extend TypeScript Types

**File:** `webui-next/lib/api/types.ts`

```typescript
// Update LaunchRequest (lines 130-137)
export interface LaunchRequest {
  task_id?: string;          // LEGACY: Single task (backward compat)
  task_ids?: string[];       // NEW: Array for multi-task selection
  domain?: string;
  max_steps?: number;
  vm_image?: string;
  white_agent_url?: string;
  num_runs?: number;         // Runs per task (applies to each selected task)
}

// Ensure LaunchResponse supports batch (lines 139-146)
export interface LaunchResponse {
  assessment_id?: string;    // Single run (backward compat)
  assessment_ids?: string[]; // NEW: Multiple assessments
  batch_id: string;
  status: string;
  num_runs?: number;
  monitor_url: string;
}
```

### 1.2 Update API Endpoint

**File:** `webui-next/app/api/assessments/route.ts`

Changes needed:
1. Accept both `task_id` (string) and `task_ids` (array)
2. Normalize to array internally
3. Loop through tasks to create assessments
4. Return batch with all assessment IDs

```typescript
// Pseudo-code for the change
export async function POST(request: Request) {
  const body = await request.json();

  // Normalize to array (backward compatible)
  const taskIds = body.task_ids || (body.task_id ? [body.task_id] : []);

  if (taskIds.length === 0) {
    return NextResponse.json({ error: "No tasks specified" }, { status: 400 });
  }

  // Validate max tasks limit
  const MAX_TASKS = 20;
  if (taskIds.length > MAX_TASKS) {
    return NextResponse.json({
      error: `Maximum ${MAX_TASKS} tasks allowed per batch`
    }, { status: 400 });
  }

  // Fetch all tasks
  const { data: tasks } = await db
    .from("tasks")
    .select("*")
    .in("id", taskIds);

  // Generate batch ID
  const batchId = body.batch_id || `batch_${Date.now()}_${crypto.randomUUID().slice(0,8)}`;

  const assessmentIds: string[] = [];

  // Create assessment for each task
  for (let i = 0; i < tasks.length; i++) {
    const task = tasks[i];
    const assessmentId = crypto.randomUUID();

    const assessment = {
      id: assessmentId,
      task_id: task.id,
      batch_id: batchId,
      run_number: i + 1,
      status: "pending",
      // ... other fields
    };

    await saveAssessment(assessment);
    await sendToGreenAgent(task, assessmentId);
    assessmentIds.push(assessmentId);
  }

  return NextResponse.json({
    batch_id: batchId,
    assessment_ids: assessmentIds,
    assessment_id: assessmentIds[0], // backward compat
    status: "launched",
    monitor_url: `/batch/${batchId}`,
  });
}
```

### 1.3 Update API Client

**File:** `webui-next/lib/api/client.ts`

The `launchAssessment` method should already handle the new request format since it just passes the body through. Verify and update if needed.

---

## Phase 2: Frontend State Management

### 2.1 Update State Variables

**File:** `webui-next/app/launch/page.tsx`

Replace single selection with multi-selection state:

```typescript
// BEFORE (line ~30)
const [selectedTask, setSelectedTask] = useState<Task | null>(null);

// AFTER
const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
const [selectedTasks, setSelectedTasks] = useState<Task[]>([]);
```

### 2.2 Add Selection Helper Functions

```typescript
// Toggle individual task selection
const toggleTaskSelection = useCallback((task: Task) => {
  setSelectedTaskIds(prev => {
    const newSet = new Set(prev);
    if (newSet.has(task.id)) {
      newSet.delete(task.id);
    } else {
      newSet.add(task.id);
    }
    return newSet;
  });

  setSelectedTasks(prev => {
    if (prev.find(t => t.id === task.id)) {
      return prev.filter(t => t.id !== task.id);
    } else {
      return [...prev, task];
    }
  });
}, []);

// Select all visible tasks
const selectAllTasks = useCallback(() => {
  const newIds = new Set(filteredTasks.map(t => t.id));
  setSelectedTaskIds(newIds);
  setSelectedTasks(filteredTasks);
}, [filteredTasks]);

// Clear all selections
const clearSelection = useCallback(() => {
  setSelectedTaskIds(new Set());
  setSelectedTasks([]);
}, []);

// Check if task is selected
const isTaskSelected = useCallback((taskId: string) => {
  return selectedTaskIds.has(taskId);
}, [selectedTaskIds]);
```

### 2.3 Update Launch Handler

```typescript
// BEFORE
const handleLaunch = useCallback(async () => {
  if (!selectedTask || launchMutation.isPending) return;

  const result = await launchMutation.mutateAsync({
    task_id: selectedTask.id,
    // ...
  });
  // ...
}, [selectedTask, ...]);

// AFTER
const handleLaunch = useCallback(async () => {
  if (selectedTasks.length === 0 || launchMutation.isPending) return;

  const result = await launchMutation.mutateAsync({
    task_ids: selectedTasks.map(t => t.id),
    domain: selectedTasks[0]?.domain, // Use first task's domain or make configurable
    max_steps: maxSteps,
    vm_image: "osworld-gnome-v6",
    num_runs: numRuns,
  });

  // Always redirect to batch view for multi-task
  if (result.batch_id) {
    router.push(`/batch/${result.batch_id}`);
  }
}, [selectedTasks, maxSteps, numRuns, ...]);
```

---

## Phase 3: Frontend UI Components

### 3.1 Add Checkbox to Task List

**File:** `webui-next/app/launch/page.tsx` (lines 206-233)

```tsx
// Task list item with checkbox
{filteredTasks.map((task) => (
  <div
    key={task.id}
    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer
      ${isTaskSelected(task.id)
        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
        : "border-gray-200 hover:border-gray-300"
      }`}
    onClick={() => toggleTaskSelection(task)}
  >
    {/* Checkbox */}
    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center
      ${isTaskSelected(task.id)
        ? "bg-blue-500 border-blue-500"
        : "border-gray-300"
      }`}
    >
      {isTaskSelected(task.id) && (
        <Check className="w-3 h-3 text-white" />
      )}
    </div>

    {/* Task content */}
    <div className="flex-1 min-w-0">
      <div className="font-medium truncate">{task.instruction}</div>
      <div className="text-sm text-gray-500">{task.domain}</div>
    </div>
  </div>
))}
```

### 3.2 Add Selection Controls Header

```tsx
{/* Selection controls - above task list */}
<div className="flex items-center justify-between mb-4 px-2">
  <div className="text-sm text-gray-600">
    {selectedTasks.length} task{selectedTasks.length !== 1 ? 's' : ''} selected
  </div>
  <div className="flex gap-2">
    <button
      onClick={selectAllTasks}
      className="text-sm text-blue-600 hover:text-blue-800"
      disabled={filteredTasks.length === selectedTasks.length}
    >
      Select All ({filteredTasks.length})
    </button>
    <button
      onClick={clearSelection}
      className="text-sm text-gray-600 hover:text-gray-800"
      disabled={selectedTasks.length === 0}
    >
      Clear
    </button>
  </div>
</div>
```

### 3.3 Update Preview Panel

Replace single task preview with multi-task summary:

```tsx
{/* Selected tasks preview */}
{selectedTasks.length > 0 ? (
  <div className="space-y-4">
    <h3 className="font-semibold">
      Selected Tasks ({selectedTasks.length})
    </h3>

    {/* Task list - collapsible if > 3 */}
    <div className="space-y-2 max-h-48 overflow-y-auto">
      {selectedTasks.map((task, index) => (
        <div key={task.id} className="flex items-center gap-2 text-sm">
          <span className="text-gray-400">{index + 1}.</span>
          <span className="truncate flex-1">{task.instruction}</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleTaskSelection(task);
            }}
            className="text-gray-400 hover:text-red-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>

    {/* Domain summary */}
    <div className="text-sm text-gray-500">
      Domains: {[...new Set(selectedTasks.map(t => t.domain))].join(', ')}
    </div>
  </div>
) : (
  <div className="text-gray-500 text-center py-8">
    Select tasks from the list to launch
  </div>
)}
```

### 3.4 Update Launch Button

```tsx
<button
  onClick={handleLaunch}
  disabled={selectedTasks.length === 0 || launchMutation.isPending}
  className="w-full py-3 bg-blue-600 text-white rounded-lg
    disabled:bg-gray-300 disabled:cursor-not-allowed
    hover:bg-blue-700 transition-colors"
>
  {launchMutation.isPending
    ? "Launching..."
    : `Launch ${selectedTasks.length} Task${selectedTasks.length !== 1 ? 's' : ''}`
  }
</button>
```

---

## Phase 4: Batch View Enhancements

### 4.1 Update Batch Page for Multi-Task Display

**File:** `webui-next/app/batch/[id]/page.tsx`

The existing batch page should already handle multiple assessments. Verify it displays:
- Task name/instruction for each assessment (may currently assume same task)
- Individual status per task
- Aggregated statistics

Changes needed:
```tsx
// Show task diversity info
const uniqueTasks = [...new Set(assessments.map(a => a.task_id))];
const isMultiTask = uniqueTasks.length > 1;

// In the header
{isMultiTask && (
  <div className="text-sm text-gray-500">
    Multi-task batch: {uniqueTasks.length} different tasks
  </div>
)}

// In the assessment list, show task name
{assessments.map(assessment => (
  <div key={assessment.id}>
    <div className="font-medium">{assessment.task?.instruction || assessment.task_id}</div>
    <div className="text-sm">Status: {assessment.status}</div>
  </div>
))}
```

---

## Phase 5: Validation & Error Handling

### 5.1 Frontend Validation

```typescript
// Constants
const MAX_TASKS_PER_BATCH = 20;
const MIN_TASKS_PER_BATCH = 1;

// Validation in launch handler
const handleLaunch = useCallback(async () => {
  if (selectedTasks.length < MIN_TASKS_PER_BATCH) {
    toast.error("Please select at least one task");
    return;
  }

  if (selectedTasks.length > MAX_TASKS_PER_BATCH) {
    toast.error(`Maximum ${MAX_TASKS_PER_BATCH} tasks allowed per batch`);
    return;
  }

  // Proceed with launch...
}, [selectedTasks]);
```

### 5.2 Backend Validation

```typescript
// In POST /api/assessments
const MAX_TASKS = 20;

if (taskIds.length === 0) {
  return NextResponse.json(
    { error: "No tasks specified" },
    { status: 400 }
  );
}

if (taskIds.length > MAX_TASKS) {
  return NextResponse.json(
    { error: `Maximum ${MAX_TASKS} tasks allowed per batch` },
    { status: 400 }
  );
}

// Verify all tasks exist
const { data: tasks } = await db
  .from("tasks")
  .select("*")
  .in("id", taskIds);

if (tasks.length !== taskIds.length) {
  const foundIds = new Set(tasks.map(t => t.id));
  const missingIds = taskIds.filter(id => !foundIds.has(id));
  return NextResponse.json(
    { error: `Tasks not found: ${missingIds.join(', ')}` },
    { status: 404 }
  );
}
```

### 5.3 Error Handling for Partial Failures

```typescript
// In the batch creation loop
const results = {
  successful: [] as string[],
  failed: [] as { task_id: string; error: string }[],
};

for (const task of tasks) {
  try {
    const assessmentId = await createAndLaunchAssessment(task, batchId);
    results.successful.push(assessmentId);
  } catch (error) {
    results.failed.push({
      task_id: task.id,
      error: error.message,
    });
  }
}

// Return partial success info
return NextResponse.json({
  batch_id: batchId,
  assessment_ids: results.successful,
  failed_tasks: results.failed,
  status: results.failed.length > 0 ? "partial" : "launched",
  monitor_url: `/batch/${batchId}`,
});
```

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Update `LaunchRequest` type to include `task_ids?: string[]`
- [ ] Update `LaunchResponse` type to include `assessment_ids?: string[]`
- [ ] Modify `/api/assessments` POST handler for multi-task
- [ ] Add validation for max tasks limit
- [ ] Test backward compatibility with single `task_id`

### Phase 2: State Management
- [ ] Replace `selectedTask` with `selectedTaskIds` Set and `selectedTasks` array
- [ ] Implement `toggleTaskSelection` function
- [ ] Implement `selectAllTasks` and `clearSelection` functions
- [ ] Update `handleLaunch` to use `task_ids` array

### Phase 3: UI Components
- [ ] Add checkbox UI to task list items
- [ ] Add selection controls header (count, Select All, Clear)
- [ ] Update preview panel for multi-task display
- [ ] Update launch button text to show count
- [ ] Add `Check` and `X` icons from lucide-react

### Phase 4: Batch View
- [ ] Verify batch page handles multi-task display
- [ ] Add task name to each assessment row
- [ ] Add multi-task indicator in batch header

### Phase 5: Polish
- [ ] Add loading states during batch creation
- [ ] Add toast notifications for validation errors
- [ ] Handle partial failures gracefully
- [ ] Test with 1, 5, 10, 20 tasks
- [ ] Test domain filtering with multi-select

---

## File Change Summary

| File | Changes |
|------|---------|
| `webui-next/lib/api/types.ts` | Add `task_ids[]` to request, `assessment_ids[]` to response |
| `webui-next/app/api/assessments/route.ts` | Multi-task loop, validation, batch creation |
| `webui-next/app/launch/page.tsx` | State, UI, selection logic overhaul |
| `webui-next/app/batch/[id]/page.tsx` | Multi-task display enhancements |
| `webui-next/lib/api/queries.ts` | Verify hook handles new response format |

---

## Testing Plan

1. **Unit Tests**
   - Type validation for `LaunchRequest` with both formats
   - Selection helper functions

2. **Integration Tests**
   - API endpoint with single task (backward compat)
   - API endpoint with multiple tasks
   - API endpoint with invalid task IDs
   - API endpoint exceeding max tasks

3. **E2E Tests**
   - Select single task → launch → verify batch page
   - Select multiple tasks → launch → verify all assessments created
   - Select all → clear → verify state reset
   - Filter by domain → select all → verify only filtered tasks selected

---

## Rollback Plan

If issues arise after deployment:

1. **Type changes**: Backward compatible, no rollback needed
2. **API endpoint**: Check for `task_ids` first, fall back to `task_id`
3. **Frontend**: Can deploy behind feature flag if needed

```typescript
// Feature flag approach
const ENABLE_MULTI_SELECT = process.env.NEXT_PUBLIC_ENABLE_MULTI_SELECT === 'true';

// In component
{ENABLE_MULTI_SELECT ? (
  <MultiSelectTaskList ... />
) : (
  <SingleSelectTaskList ... />
)}
```

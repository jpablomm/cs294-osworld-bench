# Next.js Agent Visualization Dashboard - Implementation Plan

## 1. Project Overview

Transform the OSWorld Green Agent webui from static HTML/CSS/JS to a modern Next.js application with real-time agent interaction visualization.

**Goal**: Create a TanStack-style developer tools experience that makes green agent ↔ white agent interactions transparent, educational, and beautiful.

## 2. Tech Stack

### Frontend
- **Next.js 15** (App Router) - Modern React framework
- **TypeScript** - Type safety for A2A protocol
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - Beautiful, accessible component library
- **TanStack Query v5** - Data fetching and caching
- **TanStack Table** - Powerful data tables
- **Framer Motion** - Smooth animations
- **Lucide React** - Icon system

### Backend (Existing)
- **FastAPI** - Keep existing webui_server.py and a2a_green_agent.py
- **SQLite/PostgreSQL** - Keep existing database
- **Server-Sent Events** - Keep existing streaming

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                        │
│                       (Port 3000)                           │
├─────────────────────────────────────────────────────────────┤
│  Pages:                                                     │
│  - / (Dashboard)                                            │
│  - /launch (Launch Assessment)                              │
│  - /assessment/[id] (NEW: Agent Interaction View)           │
│  - /assessment/[id]/monitor (Classic Monitor)               │
│  - /results (Results Browser)                               │
│  - /leaderboard (Leaderboard)                               │
│  - /batch/[id] (Batch Monitor)                              │
├─────────────────────────────────────────────────────────────┤
│  API Routes (Proxy to FastAPI):                             │
│  - /api/proxy/* → FastAPI (CORS handling)                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
                         HTTP / SSE
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Port 8000)                │
├─────────────────────────────────────────────────────────────┤
│  Existing Endpoints:                                        │
│  - /api/health                                              │
│  - /api/stats                                               │
│  - /api/assessments                                         │
│  - /api/assessments/{id}                                    │
│  - /api/stream/{id}                                         │
│  - /api/tasks                                               │
│                                                             │
│  NEW Endpoints (for enhanced visualization):                │
│  - /api/assessments/{id}/messages                           │
│    → Full A2A message history with timestamps               │
│  - /api/assessments/{id}/tools                              │
│    → Tool execution log with timing/results                 │
│  - /api/assessments/{id}/agent-state                        │
│    → Current state of green/white agents                    │
│  - /api/assessments/{id}/evaluation                         │
│    → Real-time evaluation progress                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
                     Green Agent (Port 8001)
```

## 4. Project Structure

```
green_agent/
├── webui-next/                      # New Next.js app
│   ├── app/
│   │   ├── layout.tsx               # Root layout
│   │   ├── page.tsx                 # Dashboard
│   │   ├── launch/
│   │   │   └── page.tsx             # Launch assessment
│   │   ├── assessment/
│   │   │   └── [id]/
│   │   │       ├── page.tsx         # NEW: Agent interaction view
│   │   │       └── monitor/
│   │   │           └── page.tsx     # Classic monitor
│   │   ├── results/
│   │   │   └── page.tsx             # Results browser
│   │   ├── leaderboard/
│   │   │   └── page.tsx             # Leaderboard
│   │   └── batch/
│   │       └── [id]/
│   │           └── page.tsx         # Batch monitor
│   ├── components/
│   │   ├── ui/                      # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   └── ...
│   │   ├── agents/                  # Agent-specific components
│   │   │   ├── AgentStatusCard.tsx  # Live agent status
│   │   │   ├── A2AMessagePanel.tsx  # Request/response viewer
│   │   │   ├── ToolExecutionLog.tsx # Tool call timeline
│   │   │   ├── ThinkingPanel.tsx    # Agent reasoning display
│   │   │   └── EvaluationPanel.tsx  # Evaluation progress
│   │   ├── trajectory/
│   │   │   ├── TrajectoryTimeline.tsx
│   │   │   ├── StepViewer.tsx
│   │   │   └── ScreenshotComparison.tsx
│   │   ├── dashboard/
│   │   │   ├── StatsGrid.tsx
│   │   │   ├── HealthIndicator.tsx
│   │   │   └── AssessmentTable.tsx
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── Footer.tsx
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts            # API client
│   │   │   ├── queries.ts           # TanStack Query hooks
│   │   │   └── types.ts             # TypeScript types
│   │   ├── hooks/
│   │   │   ├── useAssessment.ts
│   │   │   ├── useRealtime.ts       # SSE hook
│   │   │   └── useAgentState.ts
│   │   └── utils/
│   │       ├── formatting.ts
│   │       └── validation.ts
│   ├── public/
│   ├── styles/
│   │   └── globals.css
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   └── tailwind.config.ts
├── webui/                           # OLD webui (keep as fallback)
│   └── static/
│       └── ...
└── orchestrator/
    ├── webui_server.py              # Enhanced with new endpoints
    └── a2a_green_agent.py           # Enhanced with detailed logging
```

## 5. Implementation Phases

### Phase 1: Project Setup & Foundation (Day 1)
**Goal**: Get Next.js running with basic navigation and API integration

#### Tasks:
1. **Initialize Next.js project**
   ```bash
   cd green_agent
   npx create-next-app@latest webui-next --typescript --tailwind --app --no-src-dir
   ```

2. **Install dependencies**
   ```bash
   cd webui-next
   npm install @tanstack/react-query @tanstack/react-table
   npm install framer-motion lucide-react
   npm install date-fns clsx tailwind-merge
   ```

3. **Setup shadcn/ui**
   ```bash
   npx shadcn-ui@latest init
   npx shadcn-ui@latest add button card badge
   npx shadcn-ui@latest add table tabs separator
   ```

4. **Create TypeScript types** (`lib/api/types.ts`)
   - Assessment types
   - A2A message types
   - Tool execution types
   - Agent state types

5. **Create API client** (`lib/api/client.ts`)
   - Fetch wrapper with error handling
   - Base URL configuration (http://localhost:8000)
   - Type-safe request/response

6. **Setup TanStack Query** (`app/providers.tsx`)
   - QueryClientProvider
   - Default configuration

7. **Create basic layout** (`app/layout.tsx`)
   - Header with navigation
   - Dark theme setup
   - Font configuration

**Deliverable**: Next.js app running on port 3000 with basic layout and API connection

---

### Phase 2: Dashboard & Core Pages (Day 2)
**Goal**: Migrate existing pages with improved UX

#### Tasks:
1. **Dashboard page** (`app/page.tsx`)
   - Stats grid (reuse existing data)
   - System health indicators
   - Recent assessments table (TanStack Table)
   - Auto-refresh with TanStack Query

2. **Launch page** (`app/launch/page.tsx`)
   - Task selector with search/filter
   - Configuration form
   - Launch button with loading state
   - Redirect to agent view on launch

3. **Results page** (`app/results/page.tsx`)
   - Filterable assessment list
   - Export functionality
   - Pagination

4. **Leaderboard page** (`app/leaderboard/page.tsx`)
   - Agent rankings
   - Performance metrics

5. **Create reusable components**
   - `AssessmentTable.tsx` (TanStack Table)
   - `StatsCard.tsx`
   - `HealthIndicator.tsx`
   - `StatusBadge.tsx`

**Deliverable**: All existing pages migrated with better UX

---

### Phase 3: Backend Enhancements (Day 3)
**Goal**: Add new API endpoints for detailed agent visualization

#### Tasks in `orchestrator/webui_server.py`:

1. **Add message history endpoint**
   ```python
   @app.get("/api/assessments/{assessment_id}/messages")
   async def get_assessment_messages(assessment_id: str):
       """
       Return full A2A message history
       Format:
       {
           "messages": [
               {
                   "id": "msg_123",
                   "timestamp": "2024-...",
                   "direction": "green_to_white" | "white_to_green",
                   "type": "task" | "response" | "error",
                   "payload": {...},
                   "validation": {
                       "valid": true,
                       "errors": []
                   },
                   "latency_ms": 234
               }
           ]
       }
       """
   ```

2. **Add tool execution log endpoint**
   ```python
   @app.get("/api/assessments/{assessment_id}/tools")
   async def get_tool_executions(assessment_id: str):
       """
       Return detailed tool execution log
       Format:
       {
           "executions": [
               {
                   "step": 1,
                   "timestamp": "2024-...",
                   "tool": "click",
                   "parameters": {"x": 100, "y": 200},
                   "status": "success" | "failed" | "executing",
                   "duration_ms": 856,
                   "result": {...},
                   "screenshot_before": "url",
                   "screenshot_after": "url"
               }
           ]
       }
       """
   ```

3. **Add agent state endpoint**
   ```python
   @app.get("/api/assessments/{assessment_id}/agent-state")
   async def get_agent_state(assessment_id: str):
       """
       Return current state of both agents
       Format:
       {
           "green_agent": {
               "status": "executing_tool" | "waiting_for_response" | "evaluating",
               "current_step": 3,
               "current_action": "Executing click on VM",
               "vm_status": "ready",
               "tools_available": 7
           },
           "white_agent": {
               "status": "analyzing" | "deciding" | "idle",
               "thinking_time_ms": 2340,
               "last_action": {"op": "click", "args": {...}},
               "tools_used": ["screenshot", "click", "type_text"],
               "message_count": 5
           }
       }
       """
   ```

4. **Enhance SSE stream** (`/api/stream/{id}`)
   - Add new event types: `message_sent`, `message_received`, `tool_start`, `tool_end`, `validation_result`
   - Include more detailed data in events

5. **Add evaluation endpoint**
   ```python
   @app.get("/api/assessments/{assessment_id}/evaluation")
   async def get_evaluation_details(assessment_id: str):
       """
       Return evaluation details
       """
   ```

#### Tasks in `orchestrator/a2a_green_agent.py`:

1. **Add detailed logging for message tracking**
   - Log every message sent/received with timestamp
   - Log validation results
   - Store in assessment trajectory

2. **Track tool execution timing**
   - Start/end timestamps for each tool call
   - Store in trajectory

3. **Store agent state snapshots**
   - Current step info
   - What each agent is doing

**Deliverable**: Enhanced backend with rich data for visualization

---

### Phase 4: Agent Interaction View - Core (Day 4)
**Goal**: Build the main agent visualization page

#### Tasks:

1. **Create main layout** (`app/assessment/[id]/page.tsx`)
   - Split-panel layout
   - Left: Agent status cards (sticky)
   - Center: Main content (tabbed)
   - Right: Evaluation panel (sticky)

2. **Agent Status Cards** (`components/agents/AgentStatusCard.tsx`)
   ```tsx
   <AgentStatusCard
     agent="green" | "white"
     status={{
       state: "executing",
       currentAction: "Sending task to white agent",
       metadata: {...}
     }}
     realtime={true}  // SSE updates
   />
   ```
   - Live status indicator (🟢 🟡 🔴)
   - Current action text
   - Metadata grid
   - Pulse animation when active
   - Auto-update via SSE

3. **A2A Message Panel** (`components/agents/A2AMessagePanel.tsx`)
   ```tsx
   <A2AMessagePanel
     messages={messages}
     selectedId={selectedId}
     onSelect={(id) => setSelectedId(id)}
   />
   ```
   - List of all messages (left sidebar)
   - Selected message detail (right content)
   - Color-coded by direction (green→white, white→green)
   - Expandable JSON viewer
   - Validation status indicators
   - Timing information
   - Search/filter

4. **Real-time updates hook** (`lib/hooks/useRealtime.ts`)
   ```ts
   const { data, status } = useRealtimeAssessment(assessmentId)
   ```
   - Subscribe to SSE
   - Append to TanStack Query cache
   - Type-safe event handling
   - Auto-reconnect

**Deliverable**: Working agent interaction view with live updates

---

### Phase 5: Tool Execution Visualizer (Day 5)
**Goal**: Beautiful tool execution timeline and details

#### Tasks:

1. **Tool Execution Timeline** (`components/agents/ToolExecutionLog.tsx`)
   - Horizontal timeline with steps
   - Each step shows:
     - Tool icon
     - Parameters
     - Duration
     - Status (pending/executing/success/failed)
   - Click to expand details
   - Smooth animations (Framer Motion)

2. **Tool Detail View** (`components/agents/ToolDetailView.tsx`)
   - Before/after screenshots side-by-side
   - Parameter display with validation
   - Execution timing breakdown
   - Result/error display
   - Agent reasoning for this action

3. **Screenshot Overlay** (`components/trajectory/ScreenshotAnnotation.tsx`)
   - Show click coordinates on screenshot
   - Highlight regions
   - Draw tool interactions (clicks, drags)
   - Zoom/pan functionality

**Deliverable**: Interactive tool execution visualization

---

### Phase 6: Thinking & Evaluation Panels (Day 6)
**Goal**: Show agent reasoning and evaluation process

#### Tasks:

1. **Thinking Panel** (`components/agents/ThinkingPanel.tsx`)
   ```tsx
   <ThinkingPanel
     content={whiteAgentResponse.content}
     action={whiteAgentResponse.action}
     metadata={whiteAgentResponse.metadata}
   />
   ```
   - Display full agent response text
   - Highlight action selection
   - Show parameter choices
   - Reasoning timeline (how long spent thinking)
   - Token usage (if available)

2. **Evaluation Panel** (`components/agents/EvaluationPanel.tsx`)
   - Show task goal
   - Display evaluation criteria
   - Expected vs actual comparison
   - Live progress during evaluation
   - Final score with breakdown
   - Match/mismatch highlighting

3. **Diff Viewer** (`components/trajectory/DiffViewer.tsx`)
   - Show expected vs actual results
   - Syntax highlighting for code/JSON
   - Line-by-line comparison
   - Color-coded changes

**Deliverable**: Complete agent reasoning visualization

---

### Phase 7: Enhanced Trajectory View (Day 7)
**Goal**: Interactive trajectory with timeline scrubbing

#### Tasks:

1. **Trajectory Timeline** (`components/trajectory/TrajectoryTimeline.tsx`)
   ```tsx
   <TrajectoryTimeline
     steps={trajectory}
     currentStep={currentStep}
     onStepChange={(step) => setCurrentStep(step)}
   />
   ```
   - Horizontal timeline (top of page)
   - Markers for each step
   - Play/pause controls
   - Speed control (1x, 2x, 4x)
   - Jump to step
   - Mini-preview on hover

2. **Step Viewer** (`components/trajectory/StepViewer.tsx`)
   - Large screenshot
   - Agent reasoning overlay
   - Tool execution details
   - Keyboard navigation (←/→)
   - Fullscreen mode

3. **Compare Mode** (`components/trajectory/CompareMode.tsx`)
   - Side-by-side step comparison
   - Diff highlighting
   - Useful for debugging

**Deliverable**: Interactive trajectory exploration

---

### Phase 8: Polish & Performance (Day 8)
**Goal**: Optimize performance and add finishing touches

#### Tasks:

1. **Performance optimization**
   - Image lazy loading
   - Virtual scrolling for long lists (TanStack Virtual)
   - Debounce SSE updates
   - Optimize re-renders
   - Code splitting

2. **Loading states**
   - Skeleton screens
   - Progress indicators
   - Optimistic updates

3. **Error handling**
   - Error boundaries
   - Retry logic
   - User-friendly error messages
   - Toast notifications

4. **Keyboard shortcuts**
   - `←/→` - Navigate steps
   - `Space` - Play/pause
   - `F` - Fullscreen
   - `?` - Show shortcuts

5. **Animations**
   - Page transitions
   - Component enter/exit
   - Loading animations
   - Status pulse effects

6. **Accessibility**
   - ARIA labels
   - Keyboard navigation
   - Screen reader support
   - Focus management

**Deliverable**: Production-ready application

---

### Phase 9: Testing & Documentation (Day 9)
**Goal**: Ensure reliability and document usage

#### Tasks:

1. **Unit tests**
   - Component tests (Vitest + React Testing Library)
   - Hook tests
   - Utility function tests

2. **Integration tests**
   - API integration tests
   - SSE connection tests
   - End-to-end user flows

3. **Documentation**
   - `webui-next/README.md` - Setup and development
   - Component documentation (Storybook?)
   - API integration guide
   - Deployment guide

4. **Demo preparation**
   - Sample assessments
   - Screenshots/GIFs
   - Demo video

**Deliverable**: Tested, documented application

---

### Phase 10: Deployment & Migration (Day 10)
**Goal**: Deploy and transition from old webui

#### Tasks:

1. **Production build**
   ```bash
   cd webui-next
   npm run build
   npm run start  # Test production build
   ```

2. **Docker setup** (optional)
   - Create Dockerfile for Next.js
   - Update docker-compose.yml
   - Environment configuration

3. **Deployment**
   - Option A: Vercel (easiest)
     - Connect GitHub repo
     - Auto-deploy on push
     - Environment variables

   - Option B: Self-hosted
     - PM2 or systemd service
     - Nginx reverse proxy
     - SSL certificates

4. **Update main README**
   - Link to new webui
   - Update screenshots
   - Update setup instructions

5. **Deprecation plan for old webui**
   - Add banner in old webui pointing to new version
   - Keep old webui as `/legacy` route
   - Eventually remove after migration confirmed

**Deliverable**: Live, deployed Next.js application

---

## 6. Data Flow

### Real-time Updates Flow
```
Assessment Running
       ↓
Green Agent emits events
       ↓
SSE Stream (/api/stream/{id})
       ↓
Next.js useRealtime hook
       ↓
TanStack Query cache update
       ↓
React components re-render
       ↓
UI updates in real-time
```

### Message History Flow
```
User navigates to /assessment/{id}
       ↓
useAssessmentMessages() hook
       ↓
TanStack Query fetches /api/assessments/{id}/messages
       ↓
Data cached and returned
       ↓
A2AMessagePanel renders
       ↓
SSE updates append new messages
       ↓
UI stays in sync
```

## 7. Key Technical Decisions

### Why App Router over Pages Router?
- Modern, future-proof
- Better layouts and nested routes
- Server components for better performance
- More intuitive data fetching

### Why TanStack Query?
- Best-in-class data fetching
- Built-in caching and invalidation
- SSE integration
- Optimistic updates
- DevTools

### Why shadcn/ui over Material-UI or Chakra?
- Lightweight (copy components, not a library)
- Full control over styling
- Tailwind-native
- Beautiful, modern design
- Excellent accessibility

### Why Framer Motion?
- Best React animation library
- Declarative API
- Smooth, performant animations
- Layout animations (perfect for our panels)

## 8. Responsive Design

### Desktop (primary target)
- Multi-panel layout
- Side-by-side comparisons
- All features visible

### Tablet
- Collapsible sidebars
- Tabs instead of panels
- Maintain core functionality

### Mobile (view-only)
- Simplified view
- Stack panels vertically
- Focus on current step
- No editing/launching

## 9. Theme Design

### Dark Theme (Primary)
```css
--background: 222.2 84% 4.9%      /* Near black */
--foreground: 210 40% 98%          /* Off white */
--primary: 217.2 91.2% 59.8%       /* Blue */
--success: 142.1 76.2% 36.3%       /* Green */
--warning: 47.9 95.8% 53.1%        /* Yellow */
--error: 0 84.2% 60.2%             /* Red */
--muted: 217.2 32.6% 17.5%         /* Dark blue-gray */
```

### Accent Colors
- Green Agent: `#10B981` (Emerald)
- White Agent: `#3B82F6` (Blue)
- Tools: `#8B5CF6` (Purple)
- Evaluation: `#F59E0B` (Amber)

## 10. Success Metrics

### Performance
- First Contentful Paint < 1s
- Time to Interactive < 2s
- Lighthouse score > 90

### User Experience
- Can understand agent interaction within 30s of viewing
- Can navigate timeline without training
- Error states are clear and actionable

### Technical
- Type-safe throughout (zero `any` types)
- Test coverage > 80%
- Zero console errors in production

## 11. Future Enhancements (Post-MVP)

1. **Agent Comparison Mode**
   - Compare two white agents side-by-side
   - Show different decision paths
   - Performance comparison

2. **Replay Mode**
   - Step through assessment at any speed
   - Pause at any point
   - "What if" exploration (fork from a step)

3. **Collaborative Features**
   - Share assessment links
   - Add comments/annotations
   - Team leaderboards

4. **Advanced Analytics**
   - Agent performance trends
   - Success pattern analysis
   - Cost optimization insights

5. **Export & Reporting**
   - PDF reports
   - CSV exports
   - API for programmatic access

6. **White Agent Debugging Tools**
   - Live editing of agent prompts
   - A/B test different approaches
   - Replay with different agent

## 12. Development Workflow

### Daily Workflow
```bash
# Terminal 1: FastAPI backend
cd green_agent
source .venv/bin/activate
uvicorn orchestrator.webui_server:app --reload --port 8000

# Terminal 2: Green Agent
uvicorn orchestrator.a2a_green_agent:app --reload --port 8001

# Terminal 3: White Agent
uvicorn white_agent.gpt4v_server:app --reload --port 9002

# Terminal 4: Next.js frontend
cd webui-next
npm run dev  # Runs on port 3000
```

### Git Workflow
- Feature branches: `feature/agent-status-cards`
- Commit convention: Conventional Commits
- PR reviews required
- Keep old webui working during development

## 13. Rollout Strategy

### Week 1: Beta (Internal)
- Deploy to staging
- Test with sample assessments
- Gather feedback
- Fix critical bugs

### Week 2: Soft Launch
- Deploy to production
- Make available at `/next` route
- Keep old webui as default
- Monitor usage

### Week 3: Full Launch
- Make Next.js the default
- Redirect old routes
- Announce on README
- Create demo video

### Week 4: Deprecation
- Remove old webui code (keep in git history)
- Update all documentation
- Celebrate!

## 14. Risk Mitigation

### Risk: Performance issues with large trajectories
**Mitigation**: Virtual scrolling, pagination, lazy loading

### Risk: SSE connection issues
**Mitigation**: Auto-reconnect, fallback to polling, error states

### Risk: Type mismatches with backend
**Mitigation**: Generate types from OpenAPI spec, runtime validation

### Risk: Browser compatibility
**Mitigation**: Target modern browsers (ES2020+), document requirements

### Risk: Scope creep
**Mitigation**: Stick to phases, create backlog for "nice to haves"

## 15. Cost Analysis

### Development Time: ~10 days
- Phase 1-2: 2 days (setup + basic pages)
- Phase 3: 1 day (backend)
- Phase 4-7: 4 days (agent visualization)
- Phase 8-10: 3 days (polish + deployment)

### Infrastructure Costs
- Vercel (Next.js): Free tier sufficient for development
- FastAPI: Existing infrastructure
- Total additional cost: $0 for MVP

### Dependencies
- All open-source, permissive licenses
- Total package size: ~500KB gzipped

## 16. Success Criteria

### MVP is successful if:
1. ✅ All existing webui functionality works
2. ✅ Agent interaction is clearly visualized
3. ✅ Real-time updates work smoothly
4. ✅ Performance is better than old webui
5. ✅ Code is maintainable and type-safe

### Ready for Berkeley submission if:
1. ✅ Looks professional and polished
2. ✅ Demonstrates technical sophistication
3. ✅ Has comprehensive documentation
4. ✅ Works reliably in demos
5. ✅ Code is clean and well-organized

---

## Next Steps

1. **Review this plan** - Adjust phases, priorities, scope
2. **Get approval** - Confirm tech stack and approach
3. **Start Phase 1** - Initialize Next.js project
4. **Build iteratively** - Complete one phase before moving to next
5. **Demo frequently** - Show progress after each phase

Ready to begin? 🚀

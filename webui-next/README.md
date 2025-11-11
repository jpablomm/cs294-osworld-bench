# OSWorld Agent Dashboard - Next.js Frontend

Modern, real-time dashboard for visualizing OSWorld agent interactions and assessments.

## 🚀 Quick Start

```bash
# Install dependencies (already done)
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

The app will run on **http://localhost:3000**

## 📋 Prerequisites

The Next.js frontend connects to the FastAPI backend. Make sure these services are running:

- **WebUI Server**: http://localhost:3001 (orchestrator/webui_server.py)
- **Green Agent**: http://localhost:8001 (orchestrator/a2a_green_agent.py)
- **White Agent**: http://localhost:9002 (white_agent/gpt4v_server.py)

## 🏗️ Tech Stack

- **Next.js 15** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - Beautiful, accessible components
- **TanStack Query v5** - Data fetching and caching
- **TanStack Table** - Powerful data tables
- **Framer Motion** - Smooth animations
- **Lucide React** - Icon system

## 📁 Project Structure

```
webui-next/
├── app/                      # Next.js App Router
│   ├── layout.tsx           # Root layout with header
│   ├── page.tsx             # Dashboard page
│   ├── providers.tsx        # TanStack Query provider
│   └── globals.css          # Global styles with dark theme
├── components/
│   ├── ui/                  # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   └── ...
│   └── layout/
│       └── Header.tsx       # Navigation header
├── lib/
│   ├── api/
│   │   ├── types.ts         # TypeScript types for API
│   │   ├── client.ts        # API client
│   │   └── queries.ts       # TanStack Query hooks
│   └── utils.ts             # Utility functions
└── public/                  # Static assets
```

## 🎨 Design System

### Dark Theme Colors

```css
--background: Near black
--foreground: Off white
--green-agent: #10B981 (Emerald)
--white-agent: #3B82F6 (Blue)
--tools: #8B5CF6 (Purple)
--evaluation: #F59E0B (Amber)
```

### Typography

- **Sans**: Geist Sans (primary)
- **Mono**: Geist Mono (code)

## 🔧 Configuration

### Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:3001
```

### API Client

The API client (`lib/api/client.ts`) automatically connects to:
- Default: `http://localhost:3001`
- Override: Set `NEXT_PUBLIC_API_URL`

## 📊 Available Pages

### Current (Phase 1 - ✅ Complete)

- **Dashboard** (`/`) - System stats and recent assessments
- Header with navigation and health status

### Coming Soon (Phase 2)

- **Launch** (`/launch`) - Launch new assessments
- **Results** (`/results`) - Browse assessment results
- **Leaderboard** (`/leaderboard`) - Agent rankings
- **Assessment View** (`/assessment/[id]`) - Real-time agent interaction visualization

## 🎯 Phase 1 Completion Summary

✅ **Completed:**
1. Next.js 15 initialized with TypeScript, Tailwind, App Router
2. Dependencies installed (TanStack Query, shadcn/ui, Framer Motion, etc.)
3. TypeScript types created for all API models
4. API client with error handling
5. TanStack Query hooks for all endpoints
6. Providers setup with React Query DevTools
7. Root layout with Header component
8. Dark theme with custom agent colors
9. Dashboard page with stats and recent assessments
10. Development server running on port 3000

## 🔌 API Integration

### TanStack Query Hooks

```typescript
import { useStats, useAssessments, useHealth } from '@/lib/api/queries';

// In your component
const { data: stats, isLoading, error } = useStats();
const { data: assessments } = useAssessments({ limit: 10 });
const { data: health } = useHealth();
```

### Features

- ⚡ Automatic refetching for running assessments
- 🔄 Optimistic updates
- 💾 Smart caching with stale-time
- 🔁 Auto-retry on failure
- 🎯 Type-safe throughout

## 🧪 Testing the Dashboard

1. Ensure webui server is running: `uvicorn orchestrator.webui_server:app --reload --port 3001`
2. Open http://localhost:3000
3. Dashboard should show:
   - System health status (green badge if all services are up)
   - Stats cards (Total Assessments, Success Rate, Avg Steps, Avg Time)
   - Recent assessments list
   - TanStack Query DevTools in bottom-right corner

## 🐛 Troubleshooting

### "Connection Error" on Dashboard

- Check that webui server is running on port 3001
- Verify CORS is enabled in FastAPI backend
- Check browser console for network errors

### TypeScript Errors

```bash
npm run type-check
```

### Linting Errors

```bash
npm run lint
```

## 📝 Next Steps (Phase 2)

1. Create Launch page with task selector
2. Create Results page with assessment table
3. Create Leaderboard page
4. Add loading skeletons
5. Add error boundaries
6. Implement SSE for real-time updates

## 🎨 UI Components

All components from shadcn/ui are customizable. To add more:

```bash
npx shadcn@latest add <component-name>
```

Available: dialog, dropdown-menu, select, input, textarea, etc.

## 🚢 Deployment

### Option A: Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

### Option B: Self-hosted

```bash
# Build
npm run build

# Start production server
npm start
```

## 📚 Resources

- [Next.js Docs](https://nextjs.org/docs)
- [TanStack Query](https://tanstack.com/query/latest)
- [shadcn/ui](https://ui.shadcn.com/)
- [Tailwind CSS](https://tailwindcss.com/)

---

**Built for Berkeley Project** - OSWorld Agent Assessment Platform

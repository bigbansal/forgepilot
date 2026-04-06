# Manch UI Plan

> A well-thought-out plan for migrating the current single-component Angular shell
> into a production-grade, multi-page UI for the Manch AI engineering platform.

---

## 0. Validation Audit

> Cross-referenced against: system design doc (Section 8.2, 14, 16, 20), backend API, current frontend, and competitor UX (OpenClaw/Devin/Cursor).

### All Gaps Identified & Resolved

> System design doc Sections cross-referenced: 8.2, 10.1, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22

| # | Gap | Source | Severity | Fix |
|---|-----|--------|----------|-----|
| 1 | **No chat/conversation screen** — primary interaction for AI platforms is chat, not forms. | Competitor analysis | CRITICAL | Added `chat/` feature module as **primary interaction surface** |
| 2 | **No multi-turn conversation model** — backend only had single `prompt` → `task`. | Competitor analysis | CRITICAL | Added `Conversation` + `ChatMessage` models, `chat.service.ts`, `chat.store.ts` |
| 3 | **Task Create was a dialog** — modal dialogs break flow for the primary action. | UX audit | HIGH | Chat replaces TaskCreateDialog as primary task entry point |
| 4 | **SSE events disconnected from chat** — `sandbox.exec` events only on Live Feed page. | §8.2 "show live command logs" | HIGH | Chat subscribes to task-scoped SSE events, renders inline |
| 5 | **No validation results view** — §8.2 says "show validation results" but UI had no structured test/lint display. | §8.2, §16.1 | HIGH | Added `task-validation/` tab with test results, lint checks, build status, pass/fail evidence |
| 6 | **No plan step visualization with agents** — §14 defines `PlanStep` with `agent_name`. | §14, §16.1 | MEDIUM | Added `task-plan/` tab with agent avatar + step timeline + tool execution nesting |
| 7 | **No `ToolExecution` or `Artifact` visibility** — defined in §14 but no UI surface. | §14 | MEDIUM | Added tool execution log under plan steps + Artifacts tab in task detail |
| 8 | **No observability/telemetry dashboard** — §10.1 mandates OpenTelemetry for traces, metrics, cost, latency. | §10.1, §18.4, §22 | MEDIUM | Added `observability/` feature module with cost tracking, latency metrics, agent usage stats |
| 9 | **No command policy visualization** — §13.2 defines 4 risk levels for commands but no UI. | §13.2 | MEDIUM | Added policy info in Settings page + command risk badge in terminal output |
| 10 | **No agent Soul/Skills/Channels view** — §12 defines these as first-class concepts. Agent detail only showed markdown. | §12.1–12.3 | MEDIUM | Expanded agent detail page with Soul, Skills list, Channel access sections |
| 11 | **No repo/branch context in sessions** — §14 Session has `repo_url`, `branch`, `working_directory`. | §14 | LOW | Added repo/branch/cwd to session detail + task context sidebar |
| 12 | **No task `priority` field** — §14 Task includes `priority`. | §14 | LOW | Added priority badge in task list/detail, priority selector in chat |
| 13 | **No `user_id` / auth context** — §14 Task has `user_id`, toolbar shows user icon but no auth. | §14 | LOW | Added user avatar dropdown in toolbar with profile/logout (Phase 5) |
| 14 | **No notification center** — only toasts. Missed approvals/completions are lost. | §8.2 "show approval requests" | LOW | Added notification bell in toolbar with persistent notification drawer |
| 15 | **No failure recovery visualization** — §16.3 describes Fixer flow, retry policy. No UI. | §16.3 | LOW | Added retry history + Fixer activity in task-plan tab, retry button shows attempt count |
| 16 | **No orchestration flow visualization** — §16.1 think→act→observe loop not shown. | §16.1, §8.2 | LOW | Added agent orchestration timeline in task-plan tab showing delegation chain |
| 17 | **Missing `title` on Task** — §14 includes `title`. | §14 | LOW | Auto-generated from first chat message; task cards show title |
| 18 | **No settings/config page** — §12.4 defines config JSON needing a UI. | §12.4 | LOW | Added settings feature with agent management, policy editor, model routing |
| 19 | **No multi-repo support in UI** — §20 Phase 5 mentions multi-repo. | §20 | LOW | Added repo selector in chat input + session detail (Phase 5) |

### Validated Components (No Changes Needed)

| Component | Validation |
|-----------|------------|
| `StatusBadge` | Correctly maps all 8 `TaskStatus` enum values from backend (§15) |
| `RiskBadge` | Correctly maps all 4 `RiskLevel` enum values (§13.2) |
| `RunnerSelector` | Correctly maps all 3 `TaskRunner` values |
| `TerminalOutput` | Matches `sandbox.exec` SSE event payload + §13.3 command result contract |
| `EventFeed` | SSE event types in plan match backend `event_broker` emit calls |
| Dashboard health widget | Backend has `GET /health` endpoint |
| Agent list/detail | Backend has `GET /agents` endpoint; agent .md files have consistent structure (YAML frontmatter + sections) |
| Session list | Backend has `GET /sessions` endpoint |
| Layout shell | Standard sidebar+toolbar+outlet, appropriate for this app class |
| Signal stores | `@ngrx/signals` is correct choice for Angular 19 SSE-heavy app |
| Angular Material | Appropriate — covers all needed components without bloat |
| Chat data model | `Conversation` + `ChatMessage` correctly models multi-turn interaction |
| Task state machine | All 8 states from §15 are handled in UI: CREATED, PLANNING, RUNNING, WAITING_APPROVAL, VALIDATING, COMPLETED, FAILED, CANCELLED |

---

## 1. Current State Assessment

| Area | Where We Are |
|------|-------------|
| **Structure** | Single `AppComponent` — all logic, fetch calls, templates in one file |
| **Routing** | `app.routes.ts` is empty |
| **Services** | None — raw `fetch()` in the component |
| **Models** | Inline TypeScript interfaces in the component |
| **State** | Component-level properties, no reactive state |
| **UI Library** | None — hand-rolled dark CSS (~190 lines) |
| **Pages** | One monolithic view: health cards → agent list → task creation → event stream |

---

## 2. Technology Decisions

### 2.1 UI Component Library — **Angular Material 19 + Custom Theme**

**Why**: First-party Angular support, mature component set, dark theme built-in, Material 3 design tokens. Covers tables, cards, dialogs, side-nav, toolbars, progress, chips, badges — everything we need.

Alternatives considered:
- *PrimeNG* — heavier, more components than needed
- *Tailwind + headless* — more work, less coherent in Angular

### 2.2 State Management — **Angular Signals + Signal Store (`@ngrx/signals`)**

**Why**: Angular 19 signals are the idiomatic reactive primitive. `@ngrx/signals` gives us lightweight, composable stores without the boilerplate of full NgRx. Perfect for SSE streaming state.

### 2.3 Code Formatting — **Monaco Editor** (for diff/code viewing)

**Why**: VS Code's editor engine, renders diffs natively, syntax highlighting for any language. Use `ngx-monaco-editor-v2`.

### 2.4 Markdown Rendering — **ngx-markdown**

**Why**: Agent definitions are Markdown files; plan descriptions and task prompts benefit from rich rendering.

### 2.5 Icons — **Material Symbols** (via Angular Material)

---

## 3. Architecture Overview

```
src/
├── app/
│   ├── core/                          # Singleton services, guards, interceptors
│   │   ├── services/
│   │   │   ├── api.service.ts         # HttpClient wrapper, base URL config
│   │   │   ├── task.service.ts        # Task CRUD + start + cancel + retry
│   │   │   ├── chat.service.ts        # Conversation CRUD, send message, get history
│   │   │   ├── session.service.ts     # Session queries
│   │   │   ├── agent.service.ts       # Agent definitions + skills/souls
│   │   │   ├── event-stream.service.ts # SSE connection + event parsing
│   │   │   ├── approval.service.ts    # Approval actions
│   │   │   ├── notification.service.ts # Notification center + toast management
│   │   │   ├── observability.service.ts # Metrics, cost, latency, agent usage stats
│   │   │   └── settings.service.ts    # Platform config CRUD
│   │   ├── models/
│   │   │   ├── task.model.ts          # Task, TaskStatus, TaskRunner
│   │   │   ├── chat.model.ts          # ChatMessage, Conversation, MessageRole
│   │   │   ├── session.model.ts       # Session
│   │   │   ├── agent.model.ts         # AgentDefinition
│   │   │   ├── event.model.ts         # StreamEvent types
│   │   │   ├── plan-step.model.ts     # PlanStep, ToolExecution
│   │   │   ├── artifact.model.ts      # Artifact (diffs, logs, reports)
│   │   │   ├── approval.model.ts      # ApprovalRequest
│   │   │   ├── notification.model.ts  # Notification, NotificationType
│   │   │   ├── validation.model.ts    # ValidationResult, TestResult, LintResult
│   │   │   ├── observability.model.ts  # CostMetric, LatencyMetric, AgentUsage
│   │   │   └── settings.model.ts      # PlatformConfig, PolicyConfig, AgentConfig
│   │   ├── store/
│   │   │   ├── task.store.ts          # Task list + selected task signal store
│   │   │   ├── chat.store.ts          # Active conversation, message history, streaming state
│   │   │   ├── event.store.ts         # Live event stream store
│   │   │   ├── notification.store.ts  # Unread notifications, notification list
│   │   │   └── ui.store.ts            # UI state (sidebar open, theme, etc.)
│   │   ├── interceptors/
│   │   │   └── api-prefix.interceptor.ts
│   │   └── guards/
│   │       └── task-exists.guard.ts
│   │
│   ├── shared/                        # Reusable dumb components + pipes
│   │   ├── components/
│   │   │   ├── status-badge/          # Task/session status chip with color
│   │   │   ├── risk-badge/            # Risk level chip (LOW/MED/HIGH/CRIT)
│   │   │   ├── runner-selector/       # Runner dropdown (opensandbox/gemini/codex)
│   │   │   ├── event-feed/            # Scrollable live event list
│   │   │   ├── terminal-output/       # Monospace stdout/stderr renderer
│   │   │   ├── chat-bubble/           # Single message bubble (user/assistant/system)
│   │   │   ├── typing-indicator/      # "Manch is thinking..." animation
│   │   │   ├── inline-approval/       # Approve/reject card rendered inside chat
│   │   │   ├── inline-code-block/     # Syntax-highlighted code block in messages
│   │   │   ├── inline-diff-summary/   # Collapsible file diff summary in chat
│   │   │   ├── inline-validation/     # Test/lint result card in chat (pass/fail)
│   │   │   ├── command-risk-badge/    # Command policy level badge (low/med/high/crit)
│   │   │   ├── priority-badge/        # Task priority chip
│   │   │   ├── agent-avatar/          # Agent icon with name tooltip
│   │   │   ├── notification-bell/     # Toolbar notification icon with unread count
│   │   │   ├── cost-badge/            # Cost estimate chip ($0.03)
│   │   │   ├── empty-state/           # Placeholder for empty lists
│   │   │   └── confirm-dialog/        # Reusable confirmation dialog
│   │   ├── pipes/
│   │   │   ├── relative-time.pipe.ts  # "2 min ago"
│   │   │   └── truncate.pipe.ts
│   │   └── directives/
│   │       └── auto-scroll.directive.ts  # Auto-scroll for live feeds
│   │
│   ├── layout/                        # App shell
│   │   ├── shell/                     # Main layout: sidebar + toolbar + router-outlet
│   │   ├── sidebar/                   # Navigation sidebar
│   │   └── toolbar/                   # Top toolbar with status indicators
│   │
│   ├── features/                      # Lazy-loaded feature modules
│   │   ├── dashboard/                 # Home / overview page
│   │   │   ├── dashboard.component.ts
│   │   │   └── widgets/
│   │   │       ├── stats-card/        # Active tasks, agents, sessions counts
│   │   │       ├── recent-tasks/      # Last 5 tasks quick list
│   │   │       └── system-health/     # Backend + OpenSandbox health
│   │   │
│   │   ├── chat/                      # PRIMARY USER INTERACTION SURFACE
│   │   │   ├── chat-home/             # Conversation list + "New Chat" button
│   │   │   ├── chat-thread/           # Full conversation view with message input
│   │   │   │   ├── message-list/      # Scrollable message history
│   │   │   │   ├── message-input/     # Textarea + runner selector + send button
│   │   │   │   └── task-sidebar/      # Right panel: task status, plan steps, artifacts
│   │   │   └── chat.routes.ts
│   │   │
│   │   ├── tasks/                     # Task management (table/detail view)
│   │   │   ├── task-list/             # Filterable, sortable task table
│   │   │   ├── task-detail/           # Full task view (tabbed)
│   │   │   │   ├── task-overview/     # Status, prompt, metadata, priority, repo context
│   │   │   │   ├── task-plan/         # Plan steps with agent avatars + tool executions + retry history
│   │   │   │   ├── task-output/       # stdout/stderr/exit code with command risk badges
│   │   │   │   ├── task-validation/   # Test results, lint checks, build status, pass/fail evidence
│   │   │   │   ├── task-events/       # Task-scoped event timeline
│   │   │   │   ├── task-artifacts/    # Diffs, logs, reports list with type icons
│   │   │   │   └── task-diff/         # Monaco diff editor for changed files
│   │   │   └── task.routes.ts
│   │   │
│   │   ├── agents/                    # Agent registry
│   │   │   ├── agent-list/            # Grid of agent cards with tier badges
│   │   │   ├── agent-detail/          # Full agent view (tabbed)
│   │   │   │   ├── agent-overview/    # Mission, purpose, model_class, parallel_safe
│   │   │   │   ├── agent-soul/        # Soul definition: decision rules, guardrails, stop conditions
│   │   │   │   ├── agent-skills/      # Skills list with risk levels, input/output schemas
│   │   │   │   └── agent-channels/    # Channel access: ui, api, system, approval, telemetry
│   │   │   └── agent.routes.ts
│   │   │
│   │   ├── sessions/                  # Sandbox sessions
│   │   │   ├── session-list/          # Session table linked to tasks
│   │   │   ├── session-detail/        # Session logs + sandbox info + repo/branch/cwd context
│   │   │   └── session.routes.ts
│   │   │
│   │   ├── approvals/                 # Approval workflow (Phase 3)
│   │   │   ├── approval-queue/        # Pending approvals list
│   │   │   ├── approval-detail/       # Risk info + approve/reject
│   │   │   └── approval.routes.ts
│   │   │
│   │   ├── live/                      # Global live stream view
│   │   │   ├── live-feed/             # Full-screen event stream
│   │   │   └── live.routes.ts
│   │   │
│   │   ├── observability/             # Telemetry & cost dashboard (Phase 4)
│   │   │   ├── observability-dashboard/ # Cost, latency, agent usage metrics
│   │   │   ├── cost-breakdown/        # Per-task and per-agent cost tracking
│   │   │   ├── agent-usage/           # Agent invocation frequency, success rates
│   │   │   └── observability.routes.ts
│   │   │
│   │   └── settings/                  # Platform configuration (Phase 4)
│   │       ├── settings-general/      # Runner defaults, model routing, sandbox limits
│   │       ├── settings-agents/       # Enable/disable agents, agent config
│   │       ├── settings-policy/       # Risk thresholds, command allow/deny lists, approval rules
│   │       └── settings.routes.ts
│   │
│   ├── app.component.ts              # Minimal shell — just <router-outlet>
│   ├── app.routes.ts                 # Top-level route config
│   └── app.config.ts                 # Providers
│
├── assets/
│   └── icons/
├── styles/
│   ├── _variables.scss               # Design tokens
│   ├── _typography.scss
│   ├── _theme.scss                   # Angular Material custom theme
│   └── styles.scss                   # Global styles
└── environments/
    ├── environment.ts
    └── environment.prod.ts
```

---

## 4. Page Designs & Routing

### 4.1. Route Map

```
/                           → redirect to /chat
/chat                       → ChatHomeComponent (conversation list)
/chat/new                   → ChatThreadComponent (new conversation)
/chat/:conversationId       → ChatThreadComponent (existing conversation)
/dashboard                  → DashboardComponent
/tasks                      → TaskListComponent
/tasks/:id                  → TaskDetailComponent (tabbed)
/tasks/:id/output           → TaskDetailComponent → Output tab
/tasks/:id/events           → TaskDetailComponent → Events tab
/tasks/:id/plan             → TaskDetailComponent → Plan tab
/tasks/:id/diff             → TaskDetailComponent → Diff tab (future)
/agents                     → AgentListComponent
/agents/:name               → AgentDetailComponent
/sessions                   → SessionListComponent
/sessions/:id               → SessionDetailComponent
/approvals                  → ApprovalQueueComponent (future)
/approvals/:id              → ApprovalDetailComponent (future)
/live                       → LiveFeedComponent
/observability              → ObservabilityDashboardComponent (Phase 4)
/observability/costs        → CostBreakdownComponent (Phase 4)
/observability/agents       → AgentUsageComponent (Phase 4)
/settings                   → SettingsGeneralComponent (Phase 4)
/settings/agents            → SettingsAgentsComponent (Phase 4)
/settings/policy            → SettingsPolicyComponent (Phase 4)
```

### 4.2. Page Descriptions

#### Chat Home (`/chat`) — **PRIMARY SCREEN**
- **Purpose**: The main interaction surface — like ChatGPT/OpenClaw but for engineering tasks
- **Layout**: Two-panel — conversation list (left) + active conversation (right)
- **Left panel**:
  - "New Chat" button (prominent, top)
  - Conversation list sorted by last activity
  - Each item: title (auto-generated from first message) + last message preview + timestamp + task status badge
  - Search/filter conversations
- **Right panel** (when no conversation selected): Welcome screen with quick-start prompts
  - "Add an API endpoint for..." | "Fix failing tests in..." | "Review the latest changes"

#### Chat Thread (`/chat/:conversationId`)
- **Purpose**: Full conversational interaction with Manch agents
- **Layout**: Three-panel — conversation list (left, collapsible) + message thread (center) + task context (right, collapsible)
- **Center panel — Message Thread**:
  - Scrollable message history with auto-scroll
  - **User messages**: Right-aligned bubbles with the prompt text
  - **Assistant messages**: Left-aligned bubbles with:
    - Agent avatar + name (e.g., "Maestro", "Coder") when agent attribution is available
    - Markdown-rendered response text
    - Inline code blocks with syntax highlighting
    - Collapsible terminal output blocks (stdout/stderr) from `sandbox.exec` events
    - Inline approval cards (approve/reject buttons) when task enters `WAITING_APPROVAL`
    - Plan step progress cards showing what agent is doing
    - File diff summaries (collapsible) when changes are made
  - **System messages**: Centered, muted text for status transitions ("Task started", "Waiting for approval")
  - **Typing indicator**: "Manch is thinking..." with pulsing animation while task is RUNNING
  - **SSE integration**: `task.*`, `sandbox.exec`, `session.*` events render inline as they arrive
- **Bottom — Message Input**:
  - Multi-line textarea (Shift+Enter for newline, Enter to send)
  - Runner selector dropdown (opensandbox / gemini-cli / codex-cli)
  - Send button (disabled while task is running)
  - "Stop" button (visible while task is running — sends cancel)
  - Keyboard shortcut hint: `Ctrl+Enter to send`
- **Right panel — Task Context Sidebar** (collapsible):
  - Current task status badge + timestamps
  - Risk level badge
  - Plan steps (if available) — ordered list with agent avatars and status
  - Artifacts list (diffs, logs) — clickable to expand
  - Repo/branch context (repo URL, branch, working directory — from §14 Session)
  - Session info (sandbox ID, sandbox status)
  - Cost estimate for this task (from ToolExecution `cost_estimate` — §14)
  - "View full task details" link → navigates to `/tasks/:id`
- **Message flow**:
  1. User types prompt → sends message
  2. `ChatService.sendMessage()` → creates task (if first message) or sends follow-up
  3. Typing indicator appears
  4. SSE events stream in and render as assistant messages
  5. Terminal output from `sandbox.exec` events renders inline
  6. When task completes, final summary message appears
  7. User can send another message to start a follow-up task

#### Dashboard (`/dashboard`)
- **Purpose**: At-a-glance platform overview
- **Layout**: 2×2 widget grid + recent tasks list
- **Widgets**:
  - **System Health**: Green/red indicators for backend API, OpenSandbox server, DB
  - **Stats**: Total tasks, running tasks, completed tasks, failed tasks
  - **Active Agents**: Count of available agents with tier breakdown
  - **Recent Tasks**: Last 5 tasks as clickable cards with status badges
- **Actions**: "New Chat" FAB button → `/chat/new`
- **Observability widget** *(Phase 4)*: Total cost today, avg task latency, agent usage distribution mini-chart

#### Task List (`/tasks`)
- **Purpose**: Browse, filter, and manage all tasks (admin/power-user view)
- **Layout**: Material table with columns: Status | Priority | Title | Prompt (truncated) | Runner | Cost | Created | Updated
- **Features**:
  - Column sorting (status, created_at)
  - Status filter chips (ALL, RUNNING, COMPLETED, FAILED, WAITING_APPROVAL)
  - Search bar (prompt text search)
  - Row click → navigate to `/tasks/:id`
  - "New Chat" button → navigates to `/chat/new`
- **Empty State**: Illustration + "Start your first chat" CTA → `/chat/new`
- **Relationship to Chat**: Each conversation creates tasks. Task list is a flattened view across all conversations.

#### Task Detail (`/tasks/:id`)
- **Purpose**: Full view of a single task's lifecycle
- **Layout**: Header (status badge + prompt + actions) → Tab group
- **Tabs**:
  1. **Overview**: Title, prompt (full), status timeline, runner, risk level, priority (§14), repo/branch context, timestamps, total cost
  2. **Output**: Terminal-style display of stdout/stderr with exit code badge + command risk level badge (§13.2)
  3. **Plan**: Orchestration timeline — shows agent delegation chain (Maestro → Scout → Coder → Sentinel), each step card has: agent avatar + name, description, status, started/finished times, tool executions nested under each step with `tool_name`, `input_summary`, `result_status`, `duration_ms`, `cost_estimate` (§14). Retry attempts shown when Fixer was invoked (§16.3)
  4. **Validation**: Structured test/lint/build results from Sentinel (§8.2 "show validation results"). Shows: test suite name, pass/fail count, individual test results (expandable), lint warnings/errors, build status, security check results, overall pass/fail recommendation. Maps to §14 ToolExecution where `tool_name` = test/lint/build
  5. **Events**: Filtered event timeline showing only this task's events
  6. **Artifacts**: List of outputs (diffs, logs, reports, summaries) with type icon and download/view action (§14 Artifact)
  7. **Diff**: Monaco diff editor showing changed files side-by-side (§8.2 "show diffs and changed files")
- **Actions in header**:
  - ▶ Start (when CREATED) — with runner dropdown
  - ✓ Approve / ✗ Reject (when WAITING_APPROVAL)
  - ✗ Cancel (when RUNNING)
  - ↻ Retry (when FAILED)
  - 💬 Open in Chat → navigates to `/chat/:conversationId`
  - ⏸ Resume (when paused/interrupted — §16.3)

#### Agent List (`/agents`)
- **Purpose**: Show available AI agents and their roles (§11)
- **Layout**: Card grid (responsive: 1→2→3 columns)
- **Card content**: Agent avatar, Name, Tier badge (conductor/specialist/support), `model_class` chip (reasoning/balanced/fast), `parallel_safe` indicator, Purpose (one-liner from YAML `purpose`)
- **Active/inactive indicator**: Shows which agents are currently enabled (from API / settings)
- **Click**: Navigate to `/agents/:name` for full definition
- **Info banner**: Explains MVP 6-agent set vs full 11-agent set (§11.1 vs §11.2)

#### Agent Detail (`/agents/:name`)
- **Purpose**: Show full agent identity — Soul, Skills, Channels (§12)
- **Layout**: Header (avatar + name + tier + model_class + purpose) → Tabbed content
- **Tabs** (mapped from §12.1–12.3 + agent .md structure):
  1. **Overview**: Rendered markdown body from the agent's `.md` file — Mission, Primary responsibilities, Use when, Required outputs, Guardrails, Definition of done
  2. **Soul** (§12.1): Mission statement, decision rules, escalation rules, stop conditions, output expectations — extracted from the agent's definition
  3. **Skills** (§12.2): List of skills this agent can invoke — each with input/output schema, risk level, retry rules, required tools. E.g., Scout's skills: `search_code`, `read_file`, `list_directory`
  4. **Channels** (§12.3): Which channels this agent can access — `ui`, `api`, `system`, `cli`, `approval`, `agent`, `telemetry` — with read/write indicators
- **Data source**: `GET /agents/:name` → returns structured agent definition
- **Footer**: "Used in N tasks" link to filtered task list

#### Session List (`/sessions`)
- **Purpose**: Browse sandbox sessions
- **Layout**: Material table: Session ID | Task ID (linked) | Sandbox ID | Status | Created
- **Click**: → session detail

#### Session Detail (`/sessions/:id`)
- **Purpose**: View sandbox session execution details (§14 Session)
- **Layout**: Header (session info) → Context section → Execution log
- **Context section**: Repo URL, branch, working directory, sandbox image, environment scope (§13.1, §14)
- **Execution log**: Terminal output (all commands run in this session) with timestamps, command policy levels (§13.2)
- **Command result detail** (§13.3): Each command shows: command, cwd, env scope, stdout, stderr, exit code, started_at, finished_at, timed_out flag, cancelled flag, truncation info
- **Links back to**: Parent task, parent conversation

#### Live Feed (`/live`)
- **Purpose**: Real-time global event stream
- **Layout**: Full-height scrolling event list with auto-scroll
- **Event rendering**: Type-specific icons + colored badges + timestamp + payload preview
- **Controls**: Pause/resume stream, clear buffer, event type filters
- **Connection status**: Banner showing CONNECTED/RECONNECTING/DISCONNECTED

#### Approval Queue (`/approvals`) — *Phase 3*
- **Purpose**: List pending approval requests (§16.2)
- **Layout**: Card list with risk level (§13.2), operation type, operation summary, requesting agent avatar, timestamp
- **Sorting**: Most critical first (CRITICAL > HIGH > MEDIUM)
- **Actions**: Approve / Reject with confirmation dialog + reason text input
- **Notification tie-in**: Each pending approval creates a persistent notification

#### Observability Dashboard (`/observability`) — *Phase 4*
- **Purpose**: Platform-level metrics and cost tracking (§10.1, §18.4, §22)
- **Layout**: Metric cards + charts + filterable time range
- **Widgets**:
  - **Total cost**: Today / this week / this month — broken down by model, agent, runner
  - **Task success rate**: Completed vs Failed vs Cancelled — the §21 "Trustworthy Task Completion Rate" metric
  - **Avg task latency**: Time from CREATED to COMPLETED, broken down by phase (PLANNING, RUNNING, VALIDATING)
  - **Agent usage**: Bar chart of agent invocations — which agents run most, which succeed most
  - **Tool execution stats**: Most-used tools, avg duration, failure rate
  - **Approval metrics**: Avg approval wait time, approve/reject ratio
- **Cost breakdown sub-page** (`/observability/costs`):
  - Table: Task | Agent | Tool | Model | Tokens | Cost | Duration
  - Filter by date range, agent, runner
  - Maps to §14 ToolExecution `cost_estimate` field
- **Agent usage sub-page** (`/observability/agents`):
  - Per-agent stats: invocation count, success rate, avg duration, total cost
  - Sparkline trends over time

#### Settings (`/settings`) — *Phase 4*
- **Purpose**: Configure platform behavior (§12.4 Config JSON)
- **General** (`/settings`):
  - Default runner selection
  - Model routing rules (which model class per agent — §12 `model_class`)
  - Sandbox limits: timeout, memory, CPU
  - Retry settings: max retries, backoff policy
  - Streaming settings: heartbeat interval
- **Agent management** (`/settings/agents`) — maps to §11:
  - Toggle agents on/off (MVP 6 vs full 11 set)
  - Per-agent config: model override, parallel_safe toggle
  - Activation guidance warnings from §11.3
- **Policy editor** (`/settings/policy`) — maps to §13.2:
  - Command risk classification rules (which commands map to which risk level)
  - Approval rules: which risk levels require approval
  - Secret protection patterns: regex patterns for secret detection
  - Budget controls: max cost per task, max steps per task

---

## 5. Component Specifications

### 5.1 Shared Components

#### `<fp-status-badge [status]="task.status">`
- Displays a Material chip with status-specific color:
  - CREATED → gray, PLANNING → blue, RUNNING → amber (pulsing),
    WAITING_APPROVAL → orange, VALIDATING → purple,
    COMPLETED → green, FAILED → red, CANCELLED → gray-striped

#### `<fp-risk-badge [level]="riskLevel">`
- LOW → green outline, MEDIUM → yellow, HIGH → orange filled, CRITICAL → red filled

#### `<fp-runner-selector [(runner)]="selectedRunner">`
- Material select dropdown with icons for each runner type

#### `<fp-event-feed [events]="events" [autoScroll]="true">`
- Virtual-scrolled list of events
- Each event: icon | type chip | timestamp | payload (collapsible JSON)

#### `<fp-terminal-output [stdout]="text" [stderr]="text" [exitCode]="code">`
- Monospace pre-formatted output with ANSI color support
- Green header for stdout, red for stderr
- Exit code badge: 0 = green, non-zero = red

#### `<fp-chat-bubble [message]="msg" [role]="msg.role">`
- Renders a single chat message with role-based styling
- Roles: `user` (right-aligned, primary bg), `assistant` (left-aligned, surface bg), `system` (centered, muted)
- Assistant bubbles: optional agent avatar, markdown body, collapsible code/terminal blocks
- Supports inline rendering of approval cards, plan step cards, diff summaries

#### `<fp-typing-indicator>`
- Animated "Manch is thinking..." with three pulsing dots
- Shows agent name when attribution is available: "Coder is working..."

#### `<fp-inline-approval [approval]="approvalRequest">`
- Card rendered inside the chat thread when task needs approval
- Shows: risk level badge, operation description, reason
- Actions: Approve (green) / Reject (red) buttons
- After decision: card updates to show outcome with timestamp

#### `<fp-inline-code-block [code]="code" [language]="lang">`
- Syntax-highlighted code block using Prism or highlight.js
- Copy button, line numbers, language label
- Used inside chat bubbles and markdown rendering

#### `<fp-inline-diff-summary [files]="changedFiles">`
- Collapsible summary of file changes rendered inside chat thread
- Shows: filename, +/- line counts, change type (added/modified/deleted)
- Click to expand inline diff or navigate to full diff view

#### `<fp-inline-validation [result]="validationResult">`
- Compact test/lint result card rendered inside chat thread (§8.2)
- Shows: ✓ 24 passed, ✗ 2 failed, ⚠ 3 warnings — with expandable detail
- Color-coded: all-green for pass, red highlight for failures

#### `<fp-command-risk-badge [level]="commandRiskLevel">`
- Tiny badge next to terminal commands showing policy classification (§13.2)
- LOW → green, MEDIUM → yellow, HIGH → orange, CRITICAL → red
- Tooltip shows the policy reason

#### `<fp-priority-badge [priority]="task.priority">`
- Task priority chip: P0 (red), P1 (orange), P2 (yellow), P3 (gray)
- Used in task list, task detail header, chat sidebar

#### `<fp-agent-avatar [name]="agentName" [tier]="agentTier">`
- Circular icon with agent initial or custom icon (M for Maestro, etc.)
- Color-coded by tier: conductor = gold, specialist = blue, support = gray
- Name tooltip on hover
- Used in chat bubbles, plan step cards, orchestration timeline

#### `<fp-notification-bell [unreadCount]="count">`
- Toolbar icon with red badge showing unread count
- Click opens notification drawer
- Pulses when new critical notification arrives (approval needed)

#### `<fp-cost-badge [amount]="costEstimate" [currency]="'USD'">`
- Shows cost estimate: "$0.03" in a subtle chip
- Used in task detail, plan step cards, observability tables
- Color intensifies with cost (green < $0.10, yellow < $1.00, red > $1.00)

#### `<fp-empty-state icon="search" title="No tasks yet" action="Create Task">`
- Centered illustration + message + optional CTA button

### 5.2 Layout Components

#### Shell Layout
```
┌────────────────────────────────────────────────────────────┐
│  Toolbar  [Manch]  [🟢 Connected]  [🔔 3]  [👤 User] │
├──────┬─────────────────────────────────────────────────────┤
│      │                                          │
│  S   │                                          │
│  I   │         <router-outlet>                  │
│  D   │                                          │
│  E   │                                          │
│  B   │                                          │
│  A   │                                          │
│  R   │                                          │
│      │                                          │
├──────┴──────────────────────────────────────────┤
│  Status Bar: 3 tasks running • SSE: connected   │
└─────────────────────────────────────────────────┘
```

#### Sidebar Navigation
```
�  Chat            [● active indicator]   ← PRIMARY
📊  Dashboard
📋  Tasks           [3 running badge]
🤖  Agents          [6 active]
🖥️  Sessions
🔴  Live Feed       [● pulsing dot]
─────────────
⚠️  Approvals       [2 pending badge]
📈  Observability                      (Phase 4)
⚙️  Settings                           (Phase 4)
```

#### Notification Drawer (slide-out panel from toolbar bell)
```
┌──────────────────────────────────┐
│  Notifications        [Clear all]│
├──────────────────────────────────┤
│ 🔴 Approval needed: rm -rf      │
│    Task #abc • 2 min ago         │
│    [Approve] [Reject] [View]     │
├──────────────────────────────────┤
│ ✅ Task completed: Add endpoint  │
│    Task #def • 5 min ago  [View] │
├──────────────────────────────────┤
│ ❌ Task failed: Fix tests        │
│    Task #ghi • 12 min ago [View] │
└──────────────────────────────────┘
```

---

## 6. Data Flow Architecture

```
┌───────────────┐     HTTP (REST)      ┌──────────────────┐
│   Services    │ ◄──────────────────► │   FastAPI Backend │
│  (HttpClient) │                      │                   │
└──────┬────────┘                      └──────────────────┘
       │                                        │
       ▼                                        │ SSE
┌───────────────┐                               │
│  Signal Store │ ◄─────────────────────────────┘
│  (@ngrx/      │     EventStreamService
│   signals)    │     subscribes & dispatches
└──────┬────────┘
       │ signals (computed/effect)
       ▼
┌───────────────┐
│  Components   │  Read signals, dispatch actions
└───────────────┘
```

### Key Data Flows

1. **Chat Message Send**: User types in chat → `ChatService.sendMessage()` → API creates task (if first msg) or sends follow-up → `ChatStore` adds user message → typing indicator appears
2. **Streaming Response**: SSE events arrive → `EventStreamService` dispatches → `ChatStore` builds assistant message incrementally → chat bubbles render in real-time
3. **Inline Events**: `sandbox.exec` events → `ChatStore` appends terminal output block (with command risk badge from §13.2) to current assistant message → user sees command output inside the conversation
4. **Approval in Chat**: `task.waiting_approval` event → `ChatStore` inserts inline approval card → `NotificationStore` adds persistent notification → user approves/rejects directly in chat OR from notification drawer → task resumes
5. **Validation in Chat**: `task.validating` → Sentinel runs tests → validation results SSE event → `ChatStore` inserts inline validation card → user sees pass/fail evidence
6. **Task Status Sync**: SSE `task.*` events → `TaskStore` patches status → chat sidebar + task list + notification bell update reactively
7. **Live Events**: `EventStreamService` opens SSE → parses typed events → updates `EventStore` → Live Feed page renders
8. **Orchestration Tracking**: `agent.delegated` events → `ChatStore` shows which agent is working → typing indicator shows "Coder is working..." → plan step cards update
9. **Cost Tracking**: Each `sandbox.exec` and `tool.executed` event includes cost_estimate → `ChatStore` accumulates task cost → task sidebar shows running total
10. **Notifications**: Critical SSE events (approval needed, task failed) → `NotificationStore` adds notification → bell badge increments → toast appears

---

## 7. Styling & Theming

### Design Tokens (SCSS)
```scss
// Primary: Deep indigo for brand identity
$fp-primary:    #4f46e5;
// Secondary: Teal for secondary actions
$fp-secondary:  #0d9488;
// Background: Dark slate
$fp-bg:         #0f172a;
$fp-surface:    #1e293b;
$fp-surface-2:  #334155;
// Text
$fp-text:       #f1f5f9;
$fp-text-muted: #94a3b8;
// Status colors
$fp-success:    #22c55e;
$fp-warning:    #f59e0b;
$fp-error:      #ef4444;
$fp-info:       #3b82f6;
```

### Angular Material Custom Theme
- Dark mode by default (user preference via media query)
- Material 3 design tokens mapped to our palette
- Custom typography scale for code/terminal content

### Layout Principles
- **Responsive**: Sidebar collapses to hamburger below 768px
- **Density**: Compact density for tables (more data visible)
- **Typography**: Inter for UI, JetBrains Mono for code/terminal
- **Spacing**: 8px grid system (Material standard)

---

## 8. Implementation Phases

### Phase 1 — Foundation & Core Pages (Week 1–2)

| # | Task | Priority |
|---|------|----------|
| 1 | Install Angular Material 19, set up custom dark theme | P0 |
| 2 | Install `@ngrx/signals` | P0 |
| 3 | Create `core/models/` — extract and expand all interfaces | P0 |
| 4 | Create `core/services/` — ApiService, ChatService, TaskService, AgentService, SessionService, EventStreamService | P0 |
| 5 | Create `core/store/` — ChatStore, TaskStore, EventStore, UiStore | P0 |
| 6 | Create layout shell (toolbar + sidebar + router-outlet) | P0 |
| 7 | Set up route config with lazy-loaded feature modules | P0 |
| 8 | Build shared components: StatusBadge, RiskBadge, PriorityBadge, RunnerSelector, AgentAvatar, ChatBubble, TypingIndicator, TerminalOutput, InlineCodeBlock, EmptyState, CostBadge | P0 |
| 9 | **Build Chat Home page** (conversation list + new chat) | P0 |
| 10 | **Build Chat Thread page** (message list + input + SSE integration + task sidebar) | P0 |
| 11 | Build Dashboard page with health + stats + recent tasks widgets | P1 |
| 12 | Build Task List page with table (incl. priority + cost columns), sorting, filtering | P1 |
| 13 | Build Task Detail page with Overview + Output + Plan tabs | P1 |
| 14 | Build notification bell + notification drawer in toolbar | P1 |

**Milestone**: User can start a conversation, send prompts, see streaming responses with terminal output inline, view task plan with agent attribution, and receive notifications — all in a chat interface.

### Phase 2 — Live Streaming & Agent Pages (Week 2–3)

| # | Task | Priority |
|---|------|----------|
| 15 | Build Event Feed shared component with virtual scrolling | P0 |
| 16 | Build Live Feed page with connection status + filters | P0 |
| 17 | Add Task Events tab (filtered by task_id) | P1 |
| 18 | Build Agent List page (card grid with tier, model_class, parallel_safe indicators) | P1 |
| 19 | Build Agent Detail page — Overview tab (rendered markdown via `ngx-markdown`) | P1 |
| 20 | Build Agent Detail — Soul tab (decision rules, guardrails, stop conditions from §12.1) | P1 |
| 21 | Build Agent Detail — Skills tab (skill list with risk levels, schemas from §12.2) | P2 |
| 22 | Build Agent Detail — Channels tab (channel access matrix from §12.3) | P2 |
| 23 | Build Session List page | P2 |
| 24 | Build Session Detail page (with repo/branch/cwd context + command result contract §13.3) | P2 |
| 25 | Add auto-scroll directive for event feeds and chat | P1 |
| 26 | Build Task Validation tab (test results, lint checks, build status from Sentinel §8.2) | P1 |
| 27 | Build InlineDiffSummary + InlineValidation shared components for chat | P1 |
| 28 | Build CommandRiskBadge shared component (§13.2 command policy levels) | P2 |

**Milestone**: Live event stream visible, agents browsable with full Soul/Skills/Channels, sessions show repo context and command details, validation results structured, command risk levels visible.

### Phase 3 — Approval Workflow & Advanced Views (Week 3–4)

*Requires backend work: ApprovalRequest model, approval endpoints*

| # | Task | Priority |
|---|------|----------|
| 29 | Build InlineApproval shared component for chat thread | P1 |
| 30 | Build Approval Queue page (standalone view with priority sorting) | P1 |
| 31 | Build Approval Detail page with approve/reject + reason input | P1 |
| 32 | Add approval badge count in sidebar | P1 |
| 33 | Integrate Monaco editor for Task Diff tab (§8.2 "show diffs and changed files") | P2 |
| 34 | Build Task Artifacts tab (diffs, logs, reports, summaries from §14 Artifact) | P2 |
| 35 | Add notification toasts for SSE events (task completed, approval needed, task failed) | P1 |
| 36 | Add multi-turn follow-up support in chat (send new message on completed task) | P1 |
| 37 | Add retry history visualization in task-plan tab (§16.3 failure recovery flow) | P2 |
| 38 | Wire approval notifications to both chat inline cards AND notification drawer | P1 |

**Milestone**: Full approval workflow in chat + standalone + notification drawer, diff viewing, artifact browsing, failure recovery visualization.

### Phase 4 — Polish & Production Readiness (Week 4–5)

| # | Task | Priority |
|---|------|----------|
| 39 | Build Observability Dashboard — cost, latency, agent usage, task success rate (§10.1, §21) | P1 |
| 40 | Build Cost Breakdown sub-page (per-task, per-agent cost table — §14 ToolExecution.cost_estimate) | P2 |
| 41 | Build Agent Usage sub-page (invocation frequency, success rate trends — §18.4) | P2 |
| 42 | Build Settings General page (runner defaults, model routing, sandbox limits, retries — §12.4) | P1 |
| 43 | Build Settings Agents page (enable/disable agents, per-agent model override — §11) | P2 |
| 44 | Build Settings Policy page (command risk rules, approval rules, budget controls — §13.2) | P2 |
| 45 | Responsive layout (mobile/tablet sidebar collapse) | P1 |
| 46 | Keyboard shortcuts (Ctrl+K → new chat, Ctrl+Enter → send, Esc → stop) | P2 |
| 47 | Error handling: global error interceptor + toast notifications | P1 |
| 48 | Loading skeletons for all pages | P2 |
| 49 | Unit tests for services and stores | P1 |
| 50 | E2E tests with Playwright | P2 |
| 51 | Performance: OnPush change detection everywhere, trackBy on loops | P1 |
| 52 | Accessibility: ARIA labels, focus management, keyboard nav in chat | P1 |
| 53 | Chat conversation export (download as markdown) | P3 |

**Milestone**: Full observability with cost tracking, platform configurable via Settings, production-quality with tests, responsive, accessible.

### Phase 5 — Enterprise & Expansion (Week 6+)

*Maps to system design doc §20 Phase 5*

| # | Task | Priority |
|---|------|----------|
| 54 | User auth context: login, profile, user avatar in toolbar (§14 Task.user_id) | P1 |
| 55 | Multi-repo support: repo selector in chat input + session detail (§20) | P2 |
| 56 | Memory agent UI: knowledge base viewer, memory entries, project patterns (§11.2) | P2 |
| 57 | Team/tenant support (§22 enterprise) | P3 |
| 58 | Audit log page: all actions with user attribution | P2 |
| 59 | WebSocket upgrade path from SSE (§22 "SSE first, WebSocket later") | P3 |

**Milestone**: Enterprise features — auth, multi-repo, team support, audit trail.

---

## 9. Backend API Additions Needed

For the full UI plan to work, these backend additions are required:

| Endpoint | Purpose | Phase |
|----------|---------|-------|
### Phase 1 — Chat + Core
| Endpoint | Purpose |
|----------|--------|
| `POST /api/v1/conversations` | Create a new conversation |
| `GET /api/v1/conversations` | List conversations (sorted by last activity) |
| `GET /api/v1/conversations/{id}` | Get conversation with message history |
| `POST /api/v1/conversations/{id}/messages` | Send a message (creates/starts task) |
| `GET /api/v1/tasks?status=X&priority=X&search=foo` | Filtered + sortable task list |
| `POST /api/v1/tasks/{id}/cancel` | Cancel running task |
| `POST /api/v1/tasks/{id}/retry` | Retry failed task |
| `POST /api/v1/tasks/{id}/resume` | Resume paused/interrupted task (§16.3) |
| `GET /api/v1/stats` | Dashboard stats (task counts by status, cost summary) |
| `GET /api/v1/notifications` | List notifications for current user |
| `PUT /api/v1/notifications/{id}/read` | Mark notification as read |

### Phase 2 — Detail Views
| Endpoint | Purpose |
|----------|--------|
| `GET /api/v1/tasks/{id}/events` | Task-scoped event history |
| `GET /api/v1/tasks/{id}/plan` | Plan steps with agent attribution (§14 PlanStep) |
| `GET /api/v1/tasks/{id}/plan/{step_id}/executions` | Tool executions for a plan step (§14 ToolExecution) |
| `GET /api/v1/tasks/{id}/validation` | Validation results — tests, lint, build (§8.2) |
| `GET /api/v1/tasks/{id}/artifacts` | Artifacts — diffs, logs, reports (§14 Artifact) |
| `GET /api/v1/agents/{name}` | Single agent: structured detail (soul, skills, channels) |
| `GET /api/v1/sessions/{id}` | Session detail with repo/branch/cwd + command log (§13.3) |

### Phase 3 — Approvals + Diffs
| Endpoint | Purpose |
|----------|--------|
| `GET /api/v1/approvals` | List pending approvals (sortable by risk) |
| `GET /api/v1/approvals/{id}` | Approval detail |
| `POST /api/v1/approvals/{id}/decide` | Approve or reject with reason |
| `GET /api/v1/tasks/{id}/diff` | File-level diffs for Monaco viewer |

### Phase 4 — Observability + Settings
| Endpoint | Purpose |
|----------|--------|
| `GET /api/v1/observability/summary` | Cost, latency, success rate metrics |
| `GET /api/v1/observability/costs` | Detailed cost breakdown (per task/agent/tool) |
| `GET /api/v1/observability/agents` | Agent usage statistics |
| `GET /api/v1/settings` | Get platform config (§12.4) |
| `PUT /api/v1/settings` | Update platform config |
| `GET /api/v1/settings/policy` | Get command policy rules (§13.2) |
| `PUT /api/v1/settings/policy` | Update command policy rules |
| `GET /api/v1/settings/agents` | Get per-agent config (enabled, model override) |
| `PUT /api/v1/settings/agents/{name}` | Update agent config |

### Phase 5 — Enterprise
| Endpoint | Purpose |
|----------|--------|
| `GET /api/v1/audit-log` | Audit trail of all actions |
| `GET /api/v1/repos` | List configured repositories |
| `POST /api/v1/repos` | Add a repository for multi-repo support |
| `GET /api/v1/memory` | Memory agent knowledge entries (§11.2) |

---

## 10. Key UX Principles

1. **Conversation-first**: Chat is the primary interaction pattern. Users think in natural language, not in forms. The chat screen is the default landing page.
2. **Real-time first**: The UI should feel alive — SSE events update everything reactively, no manual refreshing. Agent responses stream into the chat as they happen.
3. **Inline over navigate**: Show terminal output, approvals, plan steps, validation results, and diffs INSIDE the conversation — don't force users to navigate away to see what happened.
4. **Progressive disclosure**: Show summary first, details on click. Don't overwhelm with data. Collapsible sections for verbose output.
5. **Terminal-native feel**: Developers expect monospace output, ANSI colors, scrollable logs. Honor that — especially inside chat bubbles. Show command risk levels (§13.2) so users know what's running.
6. **Approval friction by design**: High-risk operations should require deliberate confirmation — show risk clearly, require explicit decision — but approvals should be actionable right in the chat thread AND in the notification drawer.
7. **Keyboard-friendly**: Power users should be able to navigate entirely via keyboard. `Ctrl+K` for new chat, `Enter` to send, `Esc` to stop.
8. **Two access patterns**: Chat for doing work, Task List for reviewing work. Both are valid entry points — they're linked, not duplicated.
9. **Evidence-based completion** (§21): Every completed task must show validation evidence (test results, lint checks, build status). No unmarked green lights without proof. The real metric is *Trustworthy Task Completion Rate*.
10. **Cost-aware** (§18.4): Show cost per task, per agent, per tool — so users understand the economic impact of their requests. Budget controls should be visible and configurable.
11. **Agent transparency** (§12): Users should understand why an agent was chosen, what it can do (Skills), what it cannot do (Guardrails), and through which channels it operates.
12. **Observable by default** (§7.7, §10.1): Every major action should be traceable. The observability dashboard makes the platform's health, cost, and reliability visible at a glance.

---

## 11. Dependency Installation Plan

```bash
cd manch-frontend

# UI component library
ng add @angular/material    # Includes CDK, dark theme, typography

# State management
npm install @ngrx/signals

# Code/diff viewer (Phase 3)
npm install ngx-monaco-editor-v2

# Markdown rendering (Phase 2)
npm install ngx-markdown marked

# ANSI to HTML for terminal output
npm install ansi-to-html

# Syntax highlighting for inline code blocks
npm install prismjs @types/prismjs

# Relative time formatting
npm install date-fns

# Charts for observability dashboard (Phase 4)
npm install ngx-charts @swimlane/ngx-charts
```

---

## 12. File Count Estimate

| Category | Files | Notes |
|----------|-------|-------|
| Core services | 10 | API, Chat, Task, Session, Agent, EventStream, Approval, Notification, Observability, Settings |
| Core models | 12 | Task, Chat, Session, Agent, Event, PlanStep, Artifact, Approval, Notification, Validation, Observability, Settings |
| Core stores | 5 | Chat, Task, Event, Notification, UI |
| Core guards/interceptors | 2 | |
| Shared components | 19 | StatusBadge, RiskBadge, PriorityBadge, CommandRiskBadge, CostBadge, RunnerSelector, AgentAvatar, ChatBubble, TypingIndicator, InlineApproval, InlineCodeBlock, InlineDiffSummary, InlineValidation, NotificationBell, EventFeed, TerminalOutput, EmptyState, ConfirmDialog |
| Shared pipes/directives | 3 | RelativeTime, Truncate, AutoScroll |
| Layout components | 4 | Shell, Sidebar, Toolbar, NotificationDrawer |
| Feature components | ~40 | Chat(4), Dashboard(5), Tasks(9), Agents(6), Sessions(2), Live(1), Approvals(2), Observability(3), Settings(4), Enterprise(4) |
| Styles | 4 | Variables, Typography, Theme, Global |
| Route configs | 10 | App + 9 feature routes |
| **Total** | **~109** | |

---

*This plan is designed to be implemented incrementally across 5 phases. Each phase produces a working, usable UI that extends the previous phase. Every concept from the system design document (Sections 8–22) is mapped to a specific UI component, page, or feature with a clear phase assignment.*

---

## 13. Chat Data Model (New Backend Entities)

These models must be added to the backend to support the chat interface:

### Conversation
```
conversation_id: str (PK)
title: str              # Auto-generated from first message
created_at: datetime
updated_at: datetime
```

### ChatMessage
```
message_id: str (PK)
conversation_id: str (FK → conversations)
role: 'user' | 'assistant' | 'system'
content: str            # Markdown text
agent_name: str | null  # Which agent authored this (for assistant messages)
task_id: str | null     # Linked task (if this message triggered a task)
event_type: str | null  # For system messages: 'task.running', 'sandbox.exec', etc.
metadata: JSON | null   # Extra data (terminal output, approval info, etc.)
created_at: datetime
```

### Relationship Diagram
```
Conversation 1──* ChatMessage
Conversation 1──* Task (a conversation can spawn multiple tasks)
ChatMessage *──1 Task (a message can reference a task)
Task 1──* PlanStep
Task 1──* ToolExecution
Task 1──* Artifact
Task 1──? ApprovalRequest
Task 1──1 Session
```

---

## 14. System Design Doc → UI Coverage Matrix

> Every system design doc concept mapped to its UI surface.

| Design Doc Section | Concept | UI Component/Page | Phase |
|---|---|---|---|
| §8.2 | Create task | Chat Thread → message input | 1 |
| §8.2 | Display plan and progress | Task Detail → Plan tab, Chat → plan step cards | 1–2 |
| §8.2 | Show live command logs | Chat → inline terminal output, Live Feed | 1–2 |
| §8.2 | Show diffs and changed files | Task Detail → Diff tab (Monaco), Chat → InlineDiffSummary | 3 |
| §8.2 | Show approval requests | Chat → InlineApproval, Approval Queue page, Notification drawer | 3 |
| §8.2 | Show validation results | Task Detail → Validation tab, Chat → InlineValidation | 2 |
| §8.2 | Allow resume / cancel / retry | Task Detail → action buttons, Chat → Stop/Retry buttons | 1 |
| §10.1 | OpenTelemetry — traces, metrics, cost, latency | Observability Dashboard + sub-pages | 4 |
| §11.1 | MVP 6 agents | Agent List (active/inactive indicators), Settings → Agents | 2, 4 |
| §11.2 | Full 11 agent set | Agent List (all agents shown), Settings → Agents | 2, 4 |
| §12.1 | Soul | Agent Detail → Soul tab | 2 |
| §12.2 | Skill | Agent Detail → Skills tab | 2 |
| §12.3 | Channel | Agent Detail → Channels tab | 2 |
| §12.4 | Config JSON | Settings pages (General, Agents, Policy) | 4 |
| §13.1 | CLI first-class support | TerminalOutput component, Session Detail → command log | 1–2 |
| §13.2 | Command policy levels | CommandRiskBadge component, Settings → Policy page | 2, 4 |
| §13.3 | Command result contract | Session Detail → command result display (all fields) | 2 |
| §14 | Task (title, priority, user_id) | Task List/Detail, PriorityBadge, user avatar | 1, 5 |
| §14 | Session (repo_url, branch, cwd) | Session Detail, Chat sidebar | 2 |
| §14 | PlanStep (agent_name, status) | Task Detail → Plan tab, Chat → plan step cards, AgentAvatar | 1–2 |
| §14 | ToolExecution (cost_estimate) | Plan tab → nested under steps, CostBadge | 2 |
| §14 | ApprovalRequest | InlineApproval, Approval Queue/Detail, Notification | 3 |
| §14 | Artifact | Task Detail → Artifacts tab, Chat sidebar | 2–3 |
| §15 | Task State Machine (8 states) | StatusBadge (all 8 states styled) | 1 |
| §16.1 | Standard execution flow | Chat → streaming messages, Task → Plan tab | 1–2 |
| §16.2 | Approval flow | Chat → InlineApproval, Approval Queue, Notification | 3 |
| §16.3 | Failure recovery flow | Task → Plan tab (retry history, Fixer activity) | 3 |
| §18.4 | Cost risks | CostBadge, Observability → cost breakdown, Settings → budget controls | 4 |
| §20 Phase 1 | Basic task UI | Chat + Task List/Detail | 1 |
| §20 Phase 3 | Approval UI, policy engine | Approval pages + Settings Policy | 3–4 |
| §20 Phase 4 | Better telemetry and dashboards | Observability Dashboard | 4 |
| §20 Phase 5 | Multi-repo, Memory agent | Repo selector, Memory viewer | 5 |
| §21 | Trustworthy Task Completion Rate | Observability Dashboard → success rate widget | 4 |
| §22 | SSE first, WebSocket later | EventStreamService (SSE now, WS upgrade path in Phase 5) | 1, 5 |

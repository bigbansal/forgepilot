# ForgePilot System Design

> Complete architecture, operating model, risks, and example use cases for building an OpenClaw-like platform with stronger governance, reliability, and enterprise readiness.

## 1. Executive Summary

ForgePilot is an AI coding-agent platform designed to deliver OpenClaw-like capabilities while improving on the areas that usually break in real company environments:

- reliability
- auditability
- approval control
- resumable execution
- safe CLI usage
- enterprise integration
- strong observability

### Core idea

ForgePilot should not try to beat OpenClaw by simply adding more agents.

It should win by combining:

- strong orchestration
- isolated execution with OpenSandbox
- deterministic tool behavior
- explicit policy enforcement
- validation-first delivery
- team and enterprise controls

### Recommended platform direction

Based on the earlier architectural evaluation, the recommended target stack is:

- **Frontend**: Angular
- **Backend**: Python with FastAPI
- **Workflow / async**: Temporal or RabbitMQ/Celery
- **Database**: PostgreSQL
- **Cache / ephemeral state**: Redis
- **Sandbox runtime**: OpenSandbox
- **Streaming**: SSE first, WebSocket later
- **Observability**: OpenTelemetry

> Why Python? Because ForgePilot is primarily an AI orchestration system rather than a classic CRUD backend. Python gives faster iteration, stronger AI integrations, and a better agent tooling ecosystem.

---

## 2. What ForgePilot Is

ForgePilot is a platform that can:

- read and understand repositories
- plan engineering work
- edit files safely
- run CLI commands in isolated sandboxes
- validate code with tests and checks
- ask for approval before risky operations
- stream progress to users
- resume failed or paused work
- retain reusable project knowledge over time

It is not just a chatbot.

It is an **AI execution system**.

---

## 3. What ForgePilot Is Not

ForgePilot should **not** initially be:

- a fully autonomous production deployer
- a giant swarm of self-directed agents
- a replacement for engineering governance
- a black-box code writer
- an uncontrolled shell executor

The platform must remain bounded, observable, and reviewable.

---

## 4. Product Strategy

## 4.1 Why build ForgePilot if OpenClaw is already strong?

OpenClaw may be strong in:

- coding experience
- adoption momentum
- prompt iteration
- developer usability

ForgePilot should compete on different dimensions:

- safer autonomy
- better team workflows
- better observability
- stronger approval systems
- deterministic task lifecycles
- better enterprise integration

### Positioning statement

ForgePilot should become the platform teams choose when they want OpenClaw-like power with stronger operational control.

---

## 5. Similarity to OpenClaw

ForgePilot should preserve the best parts of the OpenClaw pattern:

1. **agent loop**
2. **tool calling**
3. **sandboxed execution**
4. **iterative planning**
5. **code editing + validation**
6. **repository understanding**

### Abstract formula

$$
Agent\ Platform = Planning + Tools + Sandbox + State + Validation + Policy
$$

### Similarities

- repo understanding before edits
- CLI-heavy execution model
- diff-first code work
- tests and validation after implementation
- task-by-task isolated execution
- specialist roles where useful

### Important differences

ForgePilot should go further in:

- policy enforcement
- workflow replay
- approval states
- audit trails
- enterprise tenancy
- observability and metrics

---

## 6. Where OpenClaw-like Systems Usually Fail

These are important because ForgePilot must be designed specifically to avoid them.

### 6.1 Coordination complexity
Too many agents produce:

- duplicated reasoning
- latency
- cost inflation
- routing confusion
- hard-to-debug outcomes

### 6.2 Weak state modeling
If task state is fuzzy, the system cannot:

- resume cleanly
- retry safely
- explain what happened
- guarantee correct progression

### 6.3 Tool brittleness
Most failures come from tools, not intelligence:

- patching fails
- shell output parsing breaks
- environment mismatch occurs
- commands hang

### 6.4 Weak observability
If there is no strong telemetry, teams cannot answer:

- which step failed
- why the agent chose something
- where cost is spent
- why the system is slow

### 6.5 Poor safety model
Uncontrolled autonomy leads to:

- dangerous installs
- destructive edits
- secret leakage
- approval bypass

### 6.6 Memory pollution
Long-term memory becomes harmful if it stores:

- stale conventions
- poor summaries
- unverified assumptions
- noisy logs

### 6.7 Demo bias
A system can be great on curated tasks and weak on real enterprise repos.

ForgePilot must optimize for:

- real failures
- long tasks
- ambiguous requirements
- multi-repo environments
- governance-heavy organizations

---

## 7. Design Principles

ForgePilot should follow these non-negotiable principles.

### 7.1 Sandbox every task
Every task gets an isolated execution context.

### 7.2 Prefer minimal agents
A small number of strong agents beats a large swarm.

### 7.3 Diff-first, not magic-first
Users must see what changed.

### 7.4 Validation before completion
No task is done until evidence exists.

### 7.5 Server-enforced policy
Safety cannot live only in prompts.

### 7.6 Explicit state machine
Task lifecycle must be deterministic.

### 7.7 Observable by default
Every major action should be traceable.

### 7.8 Modular monolith first
Do not split into microservices too early.

---

## 8. Recommended Architecture

## 8.1 High-level view

```text
Angular UI
   |
   |  HTTP + SSE
   v
ForgePilot Backend (FastAPI)
   |
   +-- API Layer
   +-- Agent Orchestrator
   +-- Tool Registry
   +-- Policy / Approval Engine
   +-- Session & Task State Manager
   +-- OpenSandbox Adapter
   +-- Validation Engine
   +-- Memory Service (later)
   |
   +-- PostgreSQL
   +-- Redis
   +-- Workflow Queue / Engine (Temporal or RabbitMQ/Celery)
   +-- OpenTelemetry
   |
   v
OpenSandbox Sessions
```

---

## 8.2 Main components

### Angular UI
Responsibilities:

- create task
- display plan and progress
- show live command logs
- show diffs and changed files
- show approval requests
- show validation results
- allow resume / cancel / retry

### Backend API
Responsibilities:

- receive user requests
- expose session and task APIs
- stream live events to UI
- protect endpoints with auth and policy

### Agent Orchestrator
Responsibilities:

- own the think → act → observe loop
- choose which agent runs next
- maintain task state
- stop runaway execution
- synthesize results

### Tool Registry
Responsibilities:

- expose stable tool contracts
- validate inputs and outputs
- bind tools to policies
- standardize error handling

### Policy / Approval Engine
Responsibilities:

- risk classification
- approval routing
- command restrictions
- budget control
- secret protection

### OpenSandbox Adapter
Responsibilities:

- create session
- read files
- write files
- apply patches
- run commands
- track previews / background processes
- destroy session

### Validation Engine
Responsibilities:

- run tests
- run lint / type checks
- assess build health
- collect evidence for completion

### Workflow / Async Engine
Responsibilities:

- durable long-running jobs
- worker distribution
- pause/resume
- retries and timers
- waiting for approvals

---

## 9. Why No Gateway Service in V1

A dedicated gateway is not required in the first version.

### V1 recommendation
Use one backend application with internal modules for:

- API
- orchestration
- policy
- sandbox
- validation
- streaming

### Add a gateway later only when

- services split across deployments
- multi-tenant routing becomes complex
- public and internal APIs diverge
- centralized rate limiting is required

---

## 10. Messaging and Workflow Choices

## 10.1 Telemetry
Telemetry means the platform's ability to see and understand itself.

Use `OpenTelemetry` for:

- traces
- metrics
- logs
- cost and latency tracking
- agent-level decision visibility

## 10.2 Temporal
Use Temporal when ForgePilot needs:

- durable multi-step workflows
- approval pauses
- retry orchestration
- resumable execution
- timers and stateful workflows

Best for:

- serious workflow reliability
- enterprise-grade task lifecycle control

## 10.3 Celery
Use Celery when ForgePilot needs:

- background jobs
- simpler queue processing
- fast Python worker setup

Best for:

- easier V1 job execution
- lower complexity than Temporal

### Recommendation

- **V1 simpler path**: RabbitMQ + Celery
- **V2 or reliability-first path**: Temporal

---

## 11. Core Agent Model

## 11.1 Recommended active agents for MVP

Use only six active agents at first:

1. `Maestro`
2. `Scout`
3. `Architect`
4. `Coder`
5. `Sentinel`
6. `Guardian`

These are enough to deliver a real platform.

## 11.2 Full agent pack

Later, add:

- `Fixer`
- `Reviewer`
- `DocSmith`
- `DevOps`
- `Memory`

## 11.3 Why not activate all at once?

Because more agents usually create:

- more latency
- more cost
- more routing overhead
- more conflict
- lower determinism

---

## 12. Souls, Skills, Channels, and Config

ForgePilot should support all of these as first-class concepts.

## 12.1 Soul
A `Soul` defines the identity and operating doctrine of an agent.

A soul contains:

- mission
- role
- decision rules
- escalation rules
- stop conditions
- output expectations

### Example
`Maestro` soul:

- decompose goals
- select specialists
- avoid unnecessary fanout
- stop when evidence is sufficient

## 12.2 Skill
A `Skill` defines a reusable capability.

Examples:

- search code
- read file
- run command
- apply patch
- assess risk
- validate build

A skill should define:

- input schema
- output schema
- risk level
- retry rules
- required tools

## 12.3 Channel
A `Channel` defines how information flows.

Recommended channels:

- `ui`
- `api`
- `system`
- `cli`
- `approval`
- `agent`
- `telemetry`

Channels help separate:

- user-visible messages
- internal orchestration
- logs
- approvals
- streaming events

## 12.4 Config JSON
Use a root config file for platform defaults.

Example responsibilities:

- enabled agents
- skill policies
- approval rules
- model routing
- sandbox limits
- retries
- streaming settings

### Recommended conceptual model

$$
Agent = Soul + Skills + Policy + Memory + Channel\ Access
$$

---

## 13. CLI Support Strategy

Strong CLI support is mandatory.

ForgePilot must treat CLI execution as a first-class runtime capability.

## 13.1 What good CLI support means

- isolated execution in sandbox
- working directory control
- environment variable scoping
- streaming stdout/stderr
- timeouts
- cancellation
- background processes
- command metadata capture
- approval checks before risky commands

## 13.2 Command policy levels

### Low risk
- `ls`
- `find`
- `grep`
- `git status`
- `git diff`
- test and lint commands

### Medium risk
- bounded local builds
- local code generation
- formatting

### High risk
- dependency installs
- schema changes
- broad edits
- service configuration changes

### Critical risk
- destructive deletes
- secret access
- production-impacting commands
- external publishing

## 13.3 Command result contract
Each command result should capture:

- command
- cwd
- env scope
- stdout
- stderr
- exit code
- started at
- finished at
- timed out flag
- cancelled flag
- truncation metadata

---

## 14. Data Model

At minimum, ForgePilot should model the following entities.

### Task
Represents the top-level user request.

Fields:

- `task_id`
- `user_id`
- `title`
- `prompt`
- `status`
- `priority`
- `created_at`
- `updated_at`

### Session
Represents the OpenSandbox-backed execution session.

Fields:

- `session_id`
- `task_id`
- `sandbox_session_id`
- `repo_url`
- `branch`
- `working_directory`
- `status`

### Plan Step
Represents a step in the current plan.

Fields:

- `step_id`
- `task_id`
- `order_index`
- `agent_name`
- `description`
- `status`
- `started_at`
- `finished_at`

### Tool Execution
Represents a tool call or CLI execution.

Fields:

- `tool_execution_id`
- `task_id`
- `step_id`
- `tool_name`
- `input_summary`
- `result_status`
- `duration_ms`
- `cost_estimate`

### Approval Request
Represents a human approval checkpoint.

Fields:

- `approval_id`
- `task_id`
- `operation_type`
- `risk_level`
- `reason`
- `requested_at`
- `resolved_at`
- `decision`

### Artifact
Represents outputs such as diffs, logs, reports, summaries.

Fields:

- `artifact_id`
- `task_id`
- `artifact_type`
- `storage_path`
- `metadata`

---

## 15. Task State Machine

ForgePilot must use a strict state machine.

### Recommended states

- `CREATED`
- `PLANNING`
- `RUNNING`
- `WAITING_APPROVAL`
- `VALIDATING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

### Why this matters
Without this, the platform will fail at:

- retries
- resuming work
- operator visibility
- correctness under failure

---

## 16. Detailed Runtime Flow

## 16.1 Standard feature implementation flow

```text
User submits task
  -> Backend creates Task + Session
  -> Guardian classifies risk
  -> Maestro creates plan
  -> Scout explores repo
  -> Architect proposes approach (if needed)
  -> Coder edits files / runs commands
  -> Sentinel validates
  -> Maestro synthesizes result
  -> UI shows diff + validation + summary
```

## 16.2 Approval flow

```text
Task step requests risky action
  -> Guardian evaluates risk
  -> Approval request created
  -> Task state becomes WAITING_APPROVAL
  -> UI prompts user
  -> User approves or rejects
  -> Workflow resumes or terminates
```

## 16.3 Failure recovery flow

```text
Step fails
  -> Result recorded
  -> Retry policy evaluated
  -> Fixer may be invoked
  -> If retry succeeds, continue
  -> If not, task becomes FAILED with evidence
```

---

## 17. Example Use Cases

## Use Case 1: Add a new backend API endpoint

### User request
"Add an endpoint to list all active agent sessions."

### How ForgePilot works
1. `Maestro` receives request
2. `Guardian` marks as medium risk
3. `Scout` finds backend API modules, routing files, session models
4. `Architect` proposes API shape and response contract
5. `Coder` updates router, service, schema, and tests
6. `Sentinel` runs tests and lint checks
7. `Maestro` summarizes changed files and result

### Output to user
- plan steps
- changed files
- API diff summary
- test results
- any follow-up work

---

## Use Case 2: Fix failing tests after a refactor

### User request
"Tests started failing after the last refactor. Find and fix the issue."

### How ForgePilot works
1. `Maestro` routes task as bug-fix flow
2. `Scout` identifies test framework and recent affected modules
3. `Fixer` inspects logs and failure output
4. `Coder` applies minimal fix
5. `Sentinel` re-runs failing tests, then full suite
6. `Reviewer` may inspect for unintended side effects
7. `Maestro` delivers final diagnosis and outcome

### Why this matters
This is where deterministic evidence is more important than cleverness.

---

## Use Case 3: Generate Docker and local environment setup

### User request
"Containerize this project and create a local dev setup."

### How ForgePilot works
1. `Scout` detects runtime stack and current repo layout
2. `Architect` proposes environment structure
3. `DevOps` creates Dockerfile, docker-compose, env docs
4. `Sentinel` runs smoke checks if possible
5. `DocSmith` updates README with local run instructions

### Approval point
If package installs or broad infra changes are required, `Guardian` may gate them.

---

## Use Case 4: Review a pull request before merge

### User request
"Review the current changes and tell me if this is safe to merge."

### How ForgePilot works
1. `Scout` gathers modified files and context
2. `Reviewer` analyzes diff quality, complexity, and maintainability
3. `Sentinel` validates tests and checks
4. `Maestro` produces merge recommendation

### Output
- blockers
- non-blocking improvements
- validation evidence
- final recommendation

---

## Use Case 5: Large enterprise feature with approvals

### User request
"Add support for tenant-specific approval policies and tenant quotas."

### How ForgePilot works
1. `Guardian` classifies as high risk because policy changes affect control plane
2. `Scout` finds auth, tenant, and policy modules
3. `Architect` designs data model and flow changes
4. `Coder` implements changes in bounded steps
5. `Sentinel` validates migrations and tests
6. `Maestro` requires human sign-off before declaring ready

### Why this showcases ForgePilot
This is where enterprise control becomes a competitive advantage over simpler viral tools.

---

## 18. Risk Analysis

## 18.1 Product risks

### Risk: Overbuilding before usage
Mitigation:
- start with six agents
- benchmark task success before expanding

### Risk: Great architecture, weak task completion
Mitigation:
- measure actual success on real repos
- prioritize tool reliability over more roles

## 18.2 Technical risks

### Risk: Tooling instability
Mitigation:
- define strict tool contracts
- standardize result schemas
- build retries carefully

### Risk: Sandbox drift or environment mismatch
Mitigation:
- standard base images
- deterministic bootstrapping
- strong session metadata

### Risk: Workflow complexity
Mitigation:
- strict state machine
- bounded retries
- one orchestrator authority

## 18.3 Safety risks

### Risk: Dangerous autonomous actions
Mitigation:
- backend-enforced policy
- approval checkpoints
- risk classification
- secret redaction

## 18.4 Cost risks

### Risk: Excessive multi-agent overhead
Mitigation:
- small active agent set
- model routing
- reuse exploration output
- avoid duplicate reasoning

---

## 19. Pros and Cons of the Recommended Design

## Pros

- strong isolation via OpenSandbox
- better enterprise control than many agent tools
- explicit approval and risk model
- better observability potential
- resumable workflow support
- scalable beyond single-user demos

## Cons

- more operational complexity than simple coding assistants
- workflow design can become heavy
- easy to over-engineer with too many agents
- reliability takes real engineering, not just prompting
- approvals can add friction if designed poorly

---

## 20. MVP Plan

## Phase 1 — Core execution foundation
Build:

- task/session models
- OpenSandbox adapter
- basic CLI tool runner
- diff and file tools
- basic Angular task UI

## Phase 2 — Core agent loop
Build:

- Maestro
- Scout
- Coder
- Sentinel
- Guardian
- plan execution flow

## Phase 3 — Validation and approvals
Build:

- approval UI
- policy engine
- risk classification
- test evidence capture
- task state transitions

## Phase 4 — Advanced reliability
Build:

- retry rules
- resumable execution
- failure diagnostics
- better telemetry and dashboards

## Phase 5 — Expansion
Build:

- Architect
- Fixer
- Reviewer
- DevOps
- DocSmith
- Memory
- multi-repo support

---

## 21. What Success Looks Like

ForgePilot is successful when it can:

- solve meaningful coding tasks on real repositories
- show exactly what it changed
- justify what it did
- recover from common failures
- safely ask for approvals when needed
- earn team trust through evidence

### Real success metric

Not "how many agents exist."

The real metric is:

$$
Trustworthy\ Task\ Completion\ Rate
$$

A smaller system with high trust beats a flashy system with low reliability.

---

## 22. Final Recommendation

ForgePilot should be built as a **controlled OpenClaw-like platform** optimized for enterprise reliability.

### Recommended strategic choices

- use Python for the backend
- use Angular for the UI
- use OpenSandbox as the execution substrate
- start without a dedicated gateway
- keep the active agent set small
- treat CLI as a first-class capability
- make approvals and telemetry core, not optional
- choose Temporal if durable workflows become central
- otherwise start with RabbitMQ/Celery for speed

### Final summary

ForgePilot should not try to be the loudest agent platform.

It should aim to be the one teams can trust.

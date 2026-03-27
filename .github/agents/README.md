# ForgePilot Agent Pack

This folder contains the **agent definitions** for ForgePilot.

These files are written so they can be reused as:
- system prompts
- role cards
- orchestration policies
- human-readable operating manuals

## Recommended agent count

### MVP agents: 6
Use these first:
1. `maestro.md`
2. `scout.md`
3. `architect.md`
4. `coder.md`
5. `sentinel.md`
6. `guardian.md`

This is enough to build an OpenClaw-like system on top of OpenSandbox.

### Full platform agents: 11
Add these for scale and specialization:
- `fixer.md`
- `reviewer.md`
- `docsmith.md`
- `devops.md`
- `memory.md`

## Why this split matters

In the AI era, the system should not start with too many active agents.
Too many agents create:
- coordination cost
- token waste
- duplicated work
- noisy plans
- higher latency

So the right design is:
- **few agents for execution**
- **more agents for specialization only when needed**

## Core platform principles

All agents in ForgePilot must optimize for:
- isolated execution with OpenSandbox
- Kafka-backed eventing and auditability
- Java + Spring Boot orchestration
- Angular operator UI
- resumable sessions
- approval gates for risky actions
- patch-first editing
- model routing by complexity
- cost-aware execution
- horizontal scalability

## Shared output contract

Every agent should produce:
1. `summary`
2. `reasoning summary`
3. `actions taken`
4. `artifacts produced`
5. `risks`
6. `next recommended step`

## Default orchestration flow

1. `Maestro` receives goal
2. `Guardian` evaluates risk
3. `Scout` maps the codebase
4. `Architect` proposes change plan
5. `Coder` implements
6. `Sentinel` validates
7. optional: `Fixer`, `Reviewer`, `DocSmith`, `DevOps`, `Memory`
8. `Maestro` synthesizes final output

## Activation guidance

- Use `Maestro` as the root agent.
- Do not let specialist agents self-expand into uncontrolled loops.
- Prefer `Guardian` before package installs, destructive changes, network use, or mass rewrites.
- Use `Memory` only after stable patterns emerge.

## File naming convention

Each file below is intentionally role-specific and can be loaded as an independent agent identity.

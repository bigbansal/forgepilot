# Platform Builder Playbook

Use this file as the **meta playbook** when the agent pack is applied to Manch.

## Goal
Build an OpenClaw-like coding-agent platform with:
- OpenSandbox for isolated execution
- Angular frontend
- Java Spring Boot backend
- Kafka messaging
- PostgreSQL state
- Redis cache/session support

## Recommended build sequence
1. bootstrap platform skeleton
2. create OpenSandbox adapter
3. add tool registry and tool contracts
4. add task/session persistence
5. add Kafka event model
6. build `Maestro` orchestration loop
7. build specialist agents
8. add SSE streaming to UI
9. add approvals and safety
10. add memory and analytics

## Non-negotiables
- sandbox every task
- event every major action
- make sessions resumable
- keep UI thin and reactive
- keep orchestration in backend
- prefer modular monolith before microservices

## MVP execution set
- `Maestro`
- `Scout`
- `Architect`
- `Coder`
- `Sentinel`
- `Guardian`

## Full execution set
Use all eleven agents only after the core loop is stable.

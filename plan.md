# PyAI implementation plan

This plan records the current baseline and the proposed work in order. The goal is to preserve PyAI's logic-only behavior while making optional hosted-LLM and multi-agent modes possible. No paid model fallback is intended; free hosted inference may have quotas or availability limits.

## Current baseline

- [x] Standard-library-only Python assistant; no LLM, neural network, or external service is required.
- [x] Four-stage request flow: symbolic purpose seed, rule-based pre-execution gate, deterministic execution, and operational evaluation.
- [x] Deterministic skills for bounded arithmetic, common metric/imperial conversions, and simple ordered plans.
- [x] CLI with interactive and one-shot use; `--json` exposes purpose, gate, action, and evaluation details.
- [x] Transparent, limited keyword safety rules; documentation states that these are not comprehensive safety guarantees.
- [x] Unit tests for deterministic skills, gate behavior, and request pipeline (10 tests).
- [x] Optional offline `simulated-agents` mode with a fixed planner–critic–synthesizer workflow; logic-only remains the default.
- [x] A per-request symbolic purpose seed carries the goal, success criteria, constraints, non-goals, and exploration guidance into the safety gate and every simulated agent role.
- [x] Agent outputs are treated as proposals, checked by the safety rules, and never receive direct tool execution access.

## Roadmap

### 1. Agree on operating modes and control boundaries

- [x] Keep **logic-only** as the default; it does not call a model.
- [ ] Define **LLM** mode for model-generated answers, **hybrid** mode for deterministic skills plus LLM language help, and a live **multi-agent** mode.
- [x] Keep PyAI as the manager in the simulated workflow: agent outputs are proposals, not permissions to run tools.
- [x] Create a per-request purpose seed before the gate and share the same immutable seed across all simulated roles.
- [ ] Specify which request data may be sent to a hosted provider and make live model use explicit to the user.

### 2. Define provider and agent interfaces

- [ ] Add a small provider-neutral model interface for sending a prompt/context and receiving a response.
- [x] Define a role-based agent interface with task/context input and structured result output.
- [ ] Make the model provider configurable so the core does not depend on one vendor or hosted service.
- [x] Keep deterministic skills under PyAI control; agents have no direct execution access.

### 3. Build and test orchestration with simulated agents

- [x] Implement a bounded manager that assigns planner, critic, and synthesizer roles and returns a final response.
- [x] Start with simulated agents so tests are repeatable and use no model quota or credentials.
- [x] Test pre-gating, invalid outputs, unsafe proposals, disagreement handoff, shared-seed propagation, and maximum-call limits.
- [ ] Add tests for context minimization, agent exceptions/timeouts, and stronger verification behavior.
- [x] Include a critic/review step; do not treat agent consensus as proof of correctness.

### 4. Add optional hosted-LLM connectivity

- [ ] Add one hosted-model adapter after the fake-agent orchestration is covered by tests.
- [ ] Read credentials from environment/configuration; never commit keys or include them in logs.
- [ ] Enforce strict per-request call, token, timeout, and retry limits.
- [ ] Provide no automatic paid fallback. A provider's free tier may be rate-limited, require an account, or change over time, so fully free live access cannot be guaranteed.
- [ ] Return a clear error or use deterministic fallback behavior when the provider is unavailable or its free quota is exhausted.

### 5. Add the first multi-agent workflow

- [ ] Use one model in multiple bounded roles first, avoiding the cost and setup of several providers.
- [x] For a simple planning request, the simulated planner drafts a checklist, the critic identifies a gap, and the synthesizer returns a reviewed result.
- [x] Keep the initial workflow fixed at three calls; it does not create sub-agents or loops.
- [x] Keep arithmetic and other exact tasks on deterministic PyAI skills in the default logic mode.

### 6. Enforce safety, privacy, and reliability checks

- [x] In the simulated workflow, run the policy before calling any agent and check each proposal before forwarding it; require the same for future live-model calls.
- [x] Validate simulated agent result structure and stop on malformed results.
- [x] Agents in the current slice have no direct tool/action execution capability; any future tool use must remain behind PyAI validation.
- [ ] Add tested behavior for refusals, ambiguous requests, agent exceptions/timeouts, and conflicting agent results.
- [ ] Avoid sending unnecessary personal or sensitive context to hosted services.

### 7. Validate and document the integrated system

- [x] Preserve the existing logic-only test suite and add offline tests for logic-only and simulated-agent workflows (18 tests total).
- [ ] Add opt-in live integration tests; they must be skipped by default and must respect strict usage limits.
- [ ] Evaluate answer relevance, task completion, safety-gate behavior, latency, and call count on a small fixed test set.
- [ ] Document setup, provider configuration, privacy implications, free-tier limitations, and how to run without any LLM.

## Next checkpoint

The initial no-LLM slice is in place: a shared purpose seed, pre-execution gate, bounded manager, and simulated planner–critic–synthesizer workflow. Next, strengthen tests for context handling and agent failures; then define the provider-neutral model interface and operating modes before selecting any hosted service. This keeps the current path testable without hardware, credentials, or inference quota.

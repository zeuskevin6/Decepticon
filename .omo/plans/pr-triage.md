# PR Triage Notes — VoidChecksum's Open PR Backlog

> Read-only review of the six low-risk / high-value PRs flagged in the
> WAVE-1 gap analysis. Recommendations only; merging requires maintainer
> approval. Each entry lists what landed in this Sisyphus branch that
> would synergize with or conflict with the PR.

## #296 — `fix(tools/bash): inherit proxy env vars into sandbox tmux sessions`

**Verdict**: ✅ Merge. Pure plumbing fix.

**What it does**: Forwards `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` from the
langgraph container into each tmux session the agent spawns inside the
sandbox. Without this, tunneled engagements (operator runs Decepticon
behind a corporate proxy) silently bypass the proxy for all command-line
HTTP traffic.

**Synergy with Sisyphus branch**: WAVE-2 §4.3's `decepticon-cli scan`
operates against `DECEPTICON_API_URL`; corporate-tunneled deployments
will inherit the same gap on the CLI path. After #296 merges, audit the
CLI's HTTP call sites to apply the same forwarding (this is a 5-minute
follow-up, not a blocker).

**Risk**: Low. Only effect is "proxy env vars now reach sandbox tools."
Tests are minimal but the change is reviewable in one screen.

## #297 — `fix(llm): wrap acompletion in asyncio.wait_for with configurable timeout`

**Verdict**: ✅ Merge. Closes a real production hang vector.

**What it does**: `litellm.acompletion` can hang past the connection-level
timeout when the upstream provider's HTTP/2 stream stalls mid-token.
Wrapping in `asyncio.wait_for` gives a hard ceiling.

**Synergy**: WAVE-1 §2.6 `BudgetEnforcementMiddleware` reads spend from
LiteLLM Postgres — a hanging acompletion stops spending growing, so the
budget gate would not fire even on a runaway. Hard-timeout from #297
means budget bookkeeping stays current.

**Risk**: Low. The timeout is configurable and defaults to a value larger
than any realistic LLM call.

## #298 — `feat(runtime): bounded graceful SIGTERM/SIGINT shutdown library`

**Verdict**: ✅ Merge. Foundation for downstream lifecycle work.

**What it does**: Centralizes the SIGTERM/SIGINT handling spread across
the langgraph container, sandbox daemon, and launcher into a single
bounded shutdown coordinator. Lets the orchestrator give in-flight
sub-agents a deadline (e.g. 30s) to finish and emit findings before kill.

**Synergy**: WAVE-1 §4.4 RecordingMiddleware flushes its JSONL sink on
exit — a clean shutdown gives the recording layer time to fsync the
final entries. Without #298, kill-9-on-CI-timeout truncates the record.

**Risk**: Medium. The coordinator touches every long-running task in the
stack. Recommend separate verification of the sandbox-daemon and
langgraph-server integration points after merge.

## #302 — `feat(tools): skill registry + slug / fuzzy resolver for dynamic load_skill`

**Verdict**: ⚠️  **Coordinate with Skillogy migration before merge.**

**What it does**: Adds a registry + slug resolver + fuzzy matching so
`load_skill("ad/kerberoasting")` and `load_skill("kerberoast")` both
resolve to the same skill. Quality-of-life win for the agent prompt.

**Why coordinate**: The maintainer flagged that Skillogy will replace
the current Skills middleware. PR #302 adds API surface (`SkillRegistry`)
that becomes either (a) the Skillogy registry's foundation, or (b) dead
code if Skillogy ships its own registry. Worth a 30-minute conversation
with the maintainer before merging to confirm direction.

**Synergy with Sisyphus branch**: WAVE-1 §2.5 PromptInjectionShield
carries a TODO marker for the same migration; both can land together
in the Skillogy PR if maintainer wants a clean cutover.

**Risk**: Low for the code itself; medium for "we may need to rewrite
this in a month."

## #303 — `feat(runtime): append-only engagement events.jsonl event log`

**Verdict**: ✅ Merge — this is the critical-path dependency for two
WAVE-2 / WAVE-6 deliverables.

**What it does**: Adds a single append-only `events.jsonl` per
engagement that captures every notable event (tool call, finding,
agent dispatch, model call summary). The unified replacement for the
ad-hoc trace files scattered across the codebase today.

**Synergy with Sisyphus branch — critical**:
- WAVE-2 §2.2 HITLApprovalMiddleware's `FileBackedApprovalTransport` is
  designed to consume #303's wire format directly. The transport
  Protocol is the seam; the implementation flips after #303 lands.
- WAVE-6 §6.2 web-dashboard timeline scrubber consumes events.jsonl
  as its data source.
- WAVE-4 §2.1 CART's ChangeEvent dispatch can subscribe to #303 events
  for "engagement-driven" CART (replay when an existing engagement's
  state changes, not just when external infra changes).

**Risk**: Medium-low. The event log shape is new and downstream
consumers will need updates. Sisyphus's branch is designed to absorb
that update with minimal change.

## #329 — `test(benchmark): add unit tests for MHBenchProvider`

**Verdict**: ✅ Merge. Pure additive coverage.

**What it does**: 5 of 6 tasks done per the PR description. Tests the
MHBench provider in `benchmark/providers/mhbench.py`.

**Synergy**: Sisyphus's WAVE-4 §6.1 added `benchmark/providers/buttercup.py`
in [benchmark/providers/buttercup.py](file:///C:/Users/Admin/Decepticon/benchmark/providers/buttercup.py)
following the same `BaseBenchmarkProvider` contract. After #329 lands,
the Buttercup provider should follow with a matching unit-test file —
the patterns will be obvious from #329's diff.

**Risk**: None. Test-only.

## Suggested merge order

1. **#297** (timeout safety net — independent, no synergy needed).
2. **#296** (proxy forwarding — independent).
3. **#329** (test coverage — independent).
4. **#298** (shutdown library — foundation; merge before #303 so #303
   can use it).
5. **#303** (events.jsonl — unblocks WAVE-2 §2.2 + WAVE-6 §6.2 + WAVE-4
   §2.1 of this Sisyphus branch).
6. **#302** (skill registry — last, after Skillogy direction confirmed).

## After triage, what unblocks in the Sisyphus branch

- ✅ HITLApprovalMiddleware FileBackedApprovalTransport → swap to
  unified-events.jsonl implementation (5-line transport swap).
- ✅ Web dashboard timeline scrubber can be designed against a stable
  event format.
- ✅ CART Watcher gains an additional event source (engagement events,
  not just external infra).
- ✅ PromptInjectionShield `_SAFE_TOOL_NAMES` flips to registry lookup
  (after Skillogy + #302 land together).

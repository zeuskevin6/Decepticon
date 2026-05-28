# WAVE-6 §6.2 — Web dashboard timeline scrubber (design)

> Deferred until PR #303 (`events.jsonl`) lands. This doc captures the
> design so implementation is straightforward when unblocked.

## Problem

The web dashboard ([clients/web/](file:///C:/Users/Admin/Decepticon/clients/web/))
shows live progress during an engagement but offers no post-engagement
**timeline**. After the run finishes you can read findings, but you
cannot scrub through "what did the agent do at T+2h47min", filter by
agent, filter by ATT&CK technique, replay a specific moment.

For client out-briefs this is the single most-requested feature: "show
me the screen, in order, as the agent owned the DC."

## Dependency

The timeline data source is PR #303's `events.jsonl` — a unified
append-only log of every notable event during an engagement. Until #303
lands the data shape is unstable; building UI against a moving spec
guarantees rework.

## Design

### Data layer

- New API endpoint: `GET /api/engagements/{slug}/events?since=&until=&agents[]=&techniques[]=`
- Pages of 500 events; cursor-based pagination via `seq` from
  events.jsonl.
- Server-side filtering on agent + technique tags + event kind (model
  call / tool call / finding emission / sub-agent dispatch).

### UI layer

Components added under
[clients/web/src/components/timeline/](file:///C:/Users/Admin/Decepticon/clients/web/src/components/):

- `<TimelineCanvas/>` — the main horizontal scrubber. X-axis is
  engagement wall-clock; Y-axis is one swimlane per agent. Each event
  renders as a colored tick (green=tool success, red=tool error,
  blue=model call, yellow=finding emit, purple=sub-agent dispatch).

- `<TimelineFilter/>` — sidebar with agent multi-select, technique
  multi-select (chips), event-kind toggles, and a search box that
  matches event message text.

- `<TimelineDetail/>` — right pane that renders the selected event's
  full payload. For model_call events: prompt + response, prompt-cache
  hit/miss. For tool_call events: command + truncated output + the
  asciicast snippet covering that command if one exists (consumes
  WAVE-1 §6.3's per-session recordings). For finding events: the
  knowledge-graph subgraph around the new node.

- `<TimelineMinimap/>` — overview strip showing event density across
  the full engagement; click-and-drag to zoom.

### Routing

- New page: `/engagements/[slug]/timeline`
- Live engagements get the timeline plus a live-cursor that auto-scrolls.
- Completed engagements get the static timeline with the same UI.

### Performance

`events.jsonl` for a 100k-event engagement is ~50MB raw. The dashboard
backend caches a per-engagement compressed index (parsed event objects,
seq + ts + agent + kind + technique) in Redis (already in the stack?)
or in memory. The UI fetches the index once (~5MB compressed), then
fetches raw events on demand for the detail pane.

### Filters by ATT&CK technique

Critical for client out-briefs: "show me everything the agent did under
T1003 (credential dumping)". Technique tags arrive on events via the
event payload's `technique_tags` field — set by the orchestrator when
it dispatches a sub-agent on a technique-tagged objective (this is also
the format CART's Watcher consumes in
[runtime/cart.py](file:///C:/Users/Admin/Decepticon/packages/decepticon/decepticon/runtime/cart.py)).

After the OPPLAN-matrix redesign lands every objective carries a
technique tag; until then, the filter operates on a best-effort tag
set (some events untagged).

## Implementation checklist (when unblocked)

- [ ] `clients/web/server/api/events/route.ts` — events endpoint.
- [ ] `clients/web/src/components/timeline/TimelineCanvas.tsx`
- [ ] `clients/web/src/components/timeline/TimelineFilter.tsx`
- [ ] `clients/web/src/components/timeline/TimelineDetail.tsx`
- [ ] `clients/web/src/components/timeline/TimelineMinimap.tsx`
- [ ] `clients/web/src/app/engagements/[slug]/timeline/page.tsx`
- [ ] Integrate WAVE-1 §6.3 asciicast playback (asciinema-player) in
      the detail pane.
- [ ] Vitest + Playwright tests for the timeline interactions.

## Estimated effort

7-10 days post-#303. Front-end work dominates; backend is straightforward.

## Why this matters

Client deliverables stop being PDFs. A screen recording with a
scrubber, filter, and per-event detail is dramatically more compelling
in an out-brief than 200 pages of formatted findings. Strix doesn't
have this. XBOW commercial doesn't have this. It is a pure
differentiator.

# WAVE-7 — Long-term moonshots (design briefs)

> Each item gets a one-page design brief here so the work survives
> session boundaries. Implementation is deliberately deferred — each
> needs architectural buy-in beyond the gap-analysis mandate.

---

## 7.1 — Learned attack-path cost model

### Current state
The Neo4j attack graph's edge `cost` property is hardcoded heuristics
(`base_weight × severity_multiplier × validation_discount`, see
[attack-graph-schema.md §4](file:///C:/Users/Admin/Decepticon/docs/design/attack-graph-schema.md)).
Dijkstra over those costs picks the cheapest path; the "cheapest" label
is opinion, not data.

### Proposal
Train a small per-environment cost predictor:

- **Features**: edge kind, source/destination kinds, severity, CVE
  presence, EPSS score, validated-PoC flag, historical hit rate of the
  technique against this target class.
- **Label**: success bit from past engagements that traversed this edge
  (1 = engagement succeeded via this edge, 0 = engagement failed).
- **Model**: XGBoost; tiny — ~10k params; trained per-customer or
  per-engagement-class.
- **Deployment**: model artifact lives in the engagement's workspace;
  `apoc.algo.dijkstra` is replaced with a custom traversal that scores
  edges via the model on the fly.

### Privacy
Models are trained per-customer (their data trains their model) or
federated (see 7.2). Cross-customer leakage requires explicit operator
opt-in.

### Effort
3-4 weeks (model + data pipeline + Cypher integration).

### Why
Hand-tuned heuristics generalize poorly across asset classes (web
target vs AD lab vs cloud account). A learned model adapts. AIxCC
winners used this pattern; Decepticon should match.

---

## 7.2 — Federated learning across engagements

### Current state
Every engagement starts from zero. Decepticon does not learn from
prior runs.

### Proposal
A small, well-defined "what-worked" prior shared across engagements,
trained on synthetic features that strip target-specific identifiers:

- **Aggregated features**: technique success rate by target-class fingerprint
  (OS family + service stack), not by hostname or IP.
- **Aggregation server**: optional, operator-hosted; receives anonymized
  per-engagement summaries, returns updated priors.
- **Default privacy**: opt-out by default for SaaS; opt-in for self-hosted.

### Effort
4-6 weeks.

### Why
The 1,000th engagement of a similar shape should run faster and find
more than the 1st. Without this, every customer pays the full discovery
cost from scratch.

---

## 7.3 — AI-vs-AI co-evolution (BlueAgent)

### Current state
Decepticon has a `Defender` agent that produces Defense Briefs at
out-brief. It does NOT actively participate during the engagement.

### Proposal
A `BlueAgent` that runs in parallel with the offensive run:

- Watches the events.jsonl stream (#303) for actions the red side takes.
- Emits detection-rule proposals in real time.
- The red side adapts — its next technique selection considers what
  the blue side is now watching for.
- This is pure self-play training data: red learns evasion, blue
  learns detection breadth.

### Effort
6-8 weeks. Non-trivial — co-evolution is its own research area.

### Why
The "Offensive Vaccine" promise is most credible when both sides are
agentic. Static blue defenses get learned around quickly; an agentic
blue side creates a moving target.

---

## 7.4 — Voice / on-call mode

### Current state
HITL approval gates require operator attention at the dashboard.
Engagements running unattended (overnight, weekend) freeze on the first
gate.

### Proposal
Pluggable notification channel:

- PagerDuty webhook on `requires_approval` events.
- Slack DM with approve/deny buttons (Slack Block Kit).
- SMS via Twilio for hard escalations.

The HITL middleware already exposes the seam (`ApprovalTransport`
Protocol). A `PagerDutyApprovalTransport` is a one-file addition.

### Effort
3-5 days per channel.

### Why
Real customer engagements run on customer timezones, not the
operator's. On-call notification turns Decepticon from "operator
sitting at dashboard" into "operator on rotation."

---

## 7.5 — Adversary-emulation profile library

### Current state
ConOps accepts `initial_access` and `ttps` as ATT&CK IDs (see
[skill-system.md](file:///C:/Users/Admin/Decepticon/docs/features/skill-system.md)
and Soundwave engagement bundle), but there's no curated library of
real-adversary profiles.

### Proposal
A profile pack: `profiles/apt29.yaml`, `profiles/fin7.yaml`,
`profiles/lazarus.yaml`, `profiles/scattered-spider.yaml`, etc. Each
profile encodes:

- The actor's documented TTPs as ATT&CK IDs.
- The actor's typical initial-access vectors (phishing, supply chain,
  exposed RDP, etc.).
- The actor's OPSEC posture (loud vs quiet, what tools they use).
- The actor's crown-jewel targets (typically domain controllers,
  HR/finance systems, intellectual property).

`soundwave/` learns to read these profiles and generate the ConOps
preset. Operator: `decepticon onboard --emulate apt29` produces a
ConOps + OPPLAN draft pre-configured for that actor's playbook.

### Effort
2-3 weeks for the framework; ongoing community contribution for
individual profiles.

### Why
"Run a Decepticon engagement as APT29 against our stack" is a real
customer ask. Right now it requires a custom Soundwave session. With
profiles, it's one CLI flag.

---

## 7.6 — Browser extension for in-flight OSINT

### Current state
OSINT agent ([skills/standard/osint/SKILL.md](file:///C:/Users/Admin/Decepticon/packages/decepticon/decepticon/skills/standard/osint/SKILL.md))
hits Shodan / Censys / GitHub / etc. from inside the sandbox. The
operator's own browsing is a separate world.

### Proposal
A small Chromium/Firefox extension:

- Operator browses target's public-facing site / GitHub org / LinkedIn.
- Extension extracts page metadata (URLs, emails, employee names,
  technology fingerprints from response headers).
- Feeds it into the engagement's OSINTOperator via the dashboard API.
- Bidirectional: the agent can also "ask" the operator to confirm a
  detail by highlighting it in the browser.

### Effort
2-3 weeks.

### Why
Half of OSINT work happens in a human's browser. Bridging the two
makes the agent's OSINT view comprehensive without overprivileged
sandbox network access.

---

## Sequencing

If WAVE-7 ever lands as a single push (unlikely — these are independent),
recommended order:

1. **7.4 (on-call)** — smallest, highest immediate utility for
   unattended engagements.
2. **7.5 (adversary profiles)** — moderate effort, direct customer
   value, no architectural risk.
3. **7.1 (learned cost model)** — needs CART (WAVE-4 §2.1) to be live
   for training data; depends on snapshot/replay infrastructure
   (which Sisyphus WAVE-1 §4.4 + WAVE-4 §2.1 already ship).
4. **7.6 (browser extension)** — independent, moderate effort.
5. **7.2 (federated learning)** — requires 7.1 to have demonstrated
   value first.
6. **7.3 (BlueAgent co-evolution)** — biggest research bet; pursue
   only after the rest of the project is on solid footing.

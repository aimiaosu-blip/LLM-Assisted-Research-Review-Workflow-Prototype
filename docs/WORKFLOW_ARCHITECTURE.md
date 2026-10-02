# Interactive workflow architecture

This extends, and does not replace, the V4 packet architecture in ARCHITECTURE.md.

## Components and actual data flow

`context.py`: six allowed intents, clarity check, controlled state fields, explicit UI
settings and a deterministic standalone query. Ambiguous input stays ambiguous even
if Jev proposes a closed-set classification: the researcher must resolve the intent.
An optional Ollama guidance call asks a natural-language clarification or rewrites
from structured state. Required topic, proposal, years and excluded types must occur
in its query; failures preserve the deterministic query. Typed filters are independent
of this natural-language query and cannot be relaxed by a generated rewrite.

`knowledge.py`: 16 authored synthetic JSON documents. Each section gets a stable
content-based EVID ID, document metadata, exact text, source JSON path and source
hash. The submitted proposal stays outside independent retrieved evidence. Topic,
scope, publication year and source exclusion filters run first. Lexical rank includes
section text, title and topic, with graph-linked boosts. Eligible validation sections
from both sides of a contradiction are preserved beyond top-k; excluded documents
cannot be reintroduced. Graph edges are actual authored relationships, not inferred
scientific truth. The UI shows selected evidence and adjacent graph edges; outside-
filter graph neighbors may appear as context but are never supporting evidence.

`decision.py`: abstract DecisionModelAdapter. RuleBasedDecisionModel returns explicit
rule verdicts with null confidence/probability. JevDecisionModel calls the documented
TypeSafe endpoint. It validates response keys, types, all probability distributions,
confidence, ordered score range/weighted value/legend and token usage. Returned model
version is retained. There is one HTTP call per classification or gate; no retries.
Failure metadata records sanitized exception type, not raw messages or credentials.

`policy.py`: configurable rules own thresholds and mandatory authority. Jev route
selection is advisory: conflicts, high impact, methodological uncertainty and gaps
control routing in code. Model uncertainty and provider failure can force human review.
No adapter can append a human disposition.

`synthesis.py`: local extractive baseline or opt-in Ollama. Only selected evidence is
passed for review synthesis. Exact quote checks establish citation existence, not
entailment. Generated rationale remains unverified until a human confirms support.

`recommendation.py`: priority-ranked questions from contradictions, gaps, broken
citations, intent, methodological uncertainty and review stage. Reasons and evidence
links are retained. Investigated question IDs prevent immediate repetition; unanswered
gaps remain in `unresolved_questions`, never silently marked resolved.

`workspace.py`: snapshot-based event journal in `runs/workspaces/<uuid>/review.sqlite`.
Initial event contains synthetic proposal and configured policy. Each turn snapshots
state, generation, bounded output, evidence, route and next questions. Changes use
SQLite BEGIN IMMEDIATE and expected revision checks. Expensive inference happens
before the transaction; a concurrent stale mutation is rejected rather than replacing
state (the attempted inference can still incur cost).

`web.py` / `ui.html`: local loopback server and browser UI. JSON mutation requests,
Host and Origin checks prevent ordinary cross-origin writes. UI uses textContent for
untrusted text, not raw HTML injection. User-entered roles remain a demo declaration,
not authentication. API endpoints create, ask, decide, read and export a workspace.
Final disposition is immutable. The user can start a fresh corrected investigation.

## State and audit contracts

State stores intent, proposal/topic, scope, time range, exclusions, stage, resolved,
investigated and unresolved questions, constraints, impact and input turns. Raw turns
remain for audit; they are not the only retrieval context. No hidden chain-of-thought is
captured: explanation means source evidence, model outputs and policy reasons.

The existing storage append/events functions maintain a verified SHA-256 event chain.
The interactive workspace replays the latest verified snapshot; V4 retains its original
per-finding replay logic. Their databases must not be interchanged. Administrators can
rewrite or truncate a local journal; this is not adversarial tamper protection.

## Configurations and model boundaries

No environment key: no TypeSafe HTTP call. Key available: Jev configured; each call
records actual successful engine or fallback. No Ollama model: extractive/guidance
baseline, not simulated generative output. Key values never enter snapshots.
Generative guidance can tailor language, bounded decisions can classify/score, and
only a declared human decision owner can finalize. This prototype does not claim
production authorization, model calibration or live API verification.

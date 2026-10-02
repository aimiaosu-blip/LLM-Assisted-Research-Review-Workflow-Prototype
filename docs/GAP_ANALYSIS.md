# Inspection and implementation plan

Inspected main (3acaa1a), all runtime modules, fixtures, tests, documentation,
CLI, CI and example exports; also inspected the V4 branch (0561197).
No AGENTS.md exists. Main was behind V4; fast-forward preserved its source,
RCA, frozen regression, declared decision rights, metrics and tests.

| Requirement | Existing work | Gap / implementation |
|---|---|---|
| Provenance, audit, human review | Exact chunks, hashes, SQLite transactions, CLI | Preserve; add persistent interactive workflow journal |
| Governance, evaluation, RCA | V4 rules, support labels, final actions, regression | Preserve legacy CLI; add configurable workflow policy |
| Intent to precise question | No guided interaction | Structured state, explicit clarification, constraint parsing and visible rewrite |
| Knowledge and retrieval | Four small files, lexical retrieval | Metadata-rich synthetic corpus, topic/date/type filters, graph expansion |
| Generative synthesis | Optional Ollama with exact citation validation | Separate synthesis adapter, validated structured rationale, truthful extractive fallback |
| Bounded decisions | Heuristic rules only | Provider abstraction, official Jev HTTP adapter, local deterministic engine |
| Follow-up loop | Absent | State/gap/conflict/stage-dependent questions with selectable continuation |
| Interface | Read-only exported HTML | Local server: clarification, evidence, decisions, graph, audit, human controls |
| Research experiment | Four behavior fixtures, V4 repeat/regression | Reproducible context-loss experiment and gold-labelled synthetic benchmark |

Plan: (1) preserve V4; (2) build corpus/state/graph/retrieval; (3) implement
adapters/policy/review/follow-ups; (4) transactional workflow and UI; (5) tests,
actual server and benchmark; (6) docs and same-repository commit/push.

Official contract checked 2026-10-02 UTC through typesafe.ai's Docs link:
https://docs.typesafe.ai/api and https://docs.typesafe.ai/models .
Endpoint https://api.typesafe.ai/v1/systemone; alias jev-latest points to
jev-1.13.0; primitives choice, score, noul. No third-party API assumed.
Live authenticated inference requires a user-supplied environment key.

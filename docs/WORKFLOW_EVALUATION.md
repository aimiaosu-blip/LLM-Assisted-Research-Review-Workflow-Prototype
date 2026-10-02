# Evaluation Framework / Synthetic Benchmark

No real reviewer study has been conducted. No live authenticated Jev or installed
Ollama inference was measured. The scripts provide repeatable behavioral experiments
and an evaluation protocol; they do not fabricate results for unmeasured arms.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
python3 -m reviewflow.benchmark --out runs/benchmark
python3 examples/run_workflow.py --out runs/workflow-demo
```

The committed JSON in `docs/examples/workflow/` comes from executed synthetic cases.
Timings vary by machine and are not reviewer labor or evidence of savings.

## Context compression

Three authored multi-turn cases compare a deliberately naive last-turn-only summary
with structured state. Checks concern patent exclusion, year range and source scope.
Outputs record the full conversations, reconstructed naive state retention and
structured retention. Default constraints may happen to survive in the naive arm;
they still count according to the declared checks. This demonstrates a reproducible
failure mode, not how often a real summarization model loses constraints. Future work
should run fixed-budget live summarizers on held-out conversations with independent
annotations and adversarial late-turn changes.

## Synthetic workflow benchmark

Four predeclared cases span network contradictions, low-impact robotics, low-impact
forecasting and a narrow network scope. Three repeats run identical questions with
fresh journal events. Gold document/section labels are authored before retrieval.

| Metric | Definition / limitation |
|---|---|
| Gold retrieval recall | Gold doc/section pairs retrieved / declared gold pairs; null for empty gold |
| Traceability | Retrieved evidence with source path, hash and exact text / retrieved items |
| Evidence coverage | Mandatory sections present / mandatory sections; not semantic sufficiency |
| Decision consistency | Equality of recommendation and route across three repeats; rules are trivially deterministic |
| Routing fixture match | Actual route equals predeclared expected route; not general model accuracy |
| Execution time | Python pipeline wall time; no real human labor measured |
| Escalation | Actual selected route; distinct from human escalation action |

## Three-arm human evaluation protocol (not performed)

A: human-only reviewer sees the same corpus and criteria, without AI support.
B: LLM/RAG assistance presents state, retrieval, provenance and rationale, with human
final review. C: hybrid adds bounded decision outputs and organization-owned gates.
Keep document access and decision criteria equivalent. Counterbalance case order,
predeclare independent gold labels and critical approval violations, use held-out
synthetic cases, and collect actual review start/end and active labor separately.

Measure decision quality against adjudicated labels, missing critical evidence,
evidence traceability, reviewer workload, lead time, inter-rater consistency, override
and escalation behavior, per-provider token use/cost, and trust/usability. Overrides
can be legitimate disagreement, not errors. High-impact final decisions always remain
human-owned in every arm. Calibration requires actual model probabilities and enough
independent binary labels (e.g. Brier score/reliability bins); local rule outputs are
not probabilities. Model quality, human-only time, cost and calibration remain null
until measured.

## UI metrics

Metrics are computed from the actual verified session journal. Human override and
acceptance share completed human decisions as denominator. Gate escalation rate uses
completed investigations. Lead time is creation timestamp to final human action and
includes idle time. Documents count unique retrieved document IDs in the latest turn.
The number of evidence gaps is section coverage, not proof of absent real research.
Known token use is summed from successful Jev calls; attempted calls include recorded
failures. Cost and gold recall are not guessed in the UI.

## Verification scope

Tests exercise original V4 behavior, ambiguous clarification, state preservation,
filters, graph witnesses, provenance, configurable thresholds, response schema and
provider errors, next-question continuation, human override/rights/finality, audit
persistence/tampering, HTTP end-to-end flow and optional LLM citation/semantic gates.
External inference is mocked. CI remains configured across Python 3.10/3.12/3.13.

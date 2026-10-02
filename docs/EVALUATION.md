# Verification and evaluation

## Executed locally
- Python 3.9.6, macOS; 21 standard-library unittest cases passed.
- CLI smoke run generated four findings across four synthetic documents.
- Approve, revise and reject actions were executed as **Synthetic demo reviewer**; a fourth finding remains pending.
- The resulting four-event hash chain passed verification.
- HTTP adapter successful response, invalid citations and failure fallback were exercised using mocks. Real model inference was not run.
- Generated HTML was opened in a browser; overview and expandable source provenance were visually checked, and an actual screenshot was saved.
- Remote GitHub Actions completed successfully for implementation commit `b160f3d207b823b7cd75a7b4591e7ab2611ef73e`, using the configured Python 3.10/3.12/3.13 matrix: [verified run](https://github.com/aimiaosu-blip/LLM-Assisted-Research-Review-Workflow-Prototype/actions/runs/36998063980).

## Tests
Parsing malformed/empty inputs; stable chunk identities; fixture classifications/provenance; zero-overlap retrieval; conflict witnesses beyond top-k; duplicate criteria; revision and original-event preservation; stale revisions; terminal states; required rationale/replacement; unknown IDs; audit tamper detection; no run overwrite; valid and invalid model citations; missing citations; adapter success; adapter errors; end-to-end fabricated-citation fallback; HTML escaping.

Run: `python3 -m unittest discover -s tests -v`.

## What this does not establish
The fixtures are designed with known cases, so passing them does not estimate real-world precision, recall, reviewer efficiency, LLM factuality or enterprise readiness. Citation validation checks existence, not entailment. Prompt injection can still affect an LLM draft. Rule-only fallback remains explicit.

## Next evaluation to conduct personally
Create at least 10 new synthetic review packets not copied from the four bundled cases. Annotate expected evidence and issue types before running. Track retrieved gold evidence/top-k, false flags, missed contradictions, unsupported LLM suggestions and time to a justified decision. Preserve errors, model names and configurations, and avoid reporting quality percentages until the denominator and labeling protocol are clear.

## V4 validation (local)

34 standard-library tests pass on Python 3.9.6, including the original 21 tests. New checks cover decision rights, required override rationale, finality, unresolved-evidence approval prevention, missing/false semantic support, stale updates, human disagreement, zero denominators, failed repeat scoring, L0-L2 feedback and explicit regression admission. Fault injection removes selected evidence: replay fails, then passes with the intact implementation.

The synthetic V4 CLI demo, audit verification and frozen regression replay were executed. The upgraded HTML was opened and inspected. CI now also runs the V4 demo and committed regression fixture. Remote V4 CI status must be checked on the upgrade PR; the earlier CI link above applies only to the original baseline.

No live LLM inference, reviewer study, production rollout, semantic judge calibration or measured efficiency improvement has been conducted. Demo elapsed seconds are scripted timings, not human performance measurements.

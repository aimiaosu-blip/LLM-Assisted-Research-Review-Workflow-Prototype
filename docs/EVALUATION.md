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

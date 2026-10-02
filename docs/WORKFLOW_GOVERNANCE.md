# Organization-owned business logic and decision rights

Rules live in `config/governance.json`, loaded and snapshotted for the workspace.
Set REVIEWFLOW_POLICY to a reviewed alternative configuration before starting the
application. Human-final-authority invariants cannot be disabled by configuration.
Existing V4 governance and support-labeling rules remain in governance.py.

| Trigger | Enforced result |
|---|---|
| Ambiguous objective | Clarification before retrieval/review |
| Missing mandatory section | Request information unless a higher-priority human escalation applies |
| Research/citation conflict | Surface conflict and escalate |
| Methodological uncertainty or risk score threshold | Escalate to a human |
| High impact | Human escalation regardless of confidence |
| Low choice/score confidence | Human escalation |
| Low sufficiency Noul probability | Request information |
| Provider error | Visible local fallback; safe routing |
| Generated rationale | Human semantic support review |
| Final decision | Explicit human action, declared owner role and rationale |
| Difference from AI recommendation | Mandatory override reason |
| Revise | Mandatory description of proposed revision |
| Approve with unresolved gaps/conflicts | Rejected; correct the packet first |
| Final disposition recorded | Immutable; new workspace for reconsideration |

The sufficiency threshold (.85), confidence threshold (.75), escalation Noul
threshold (.65) and high risk score (2 on a 0–3 rubric) are configurable **illustrative
policy settings**, not empirically calibrated cutoffs. Probability concerns a model's
answer; confidence describes its certainty; organizational authority is a separate
human-owned concept. Deterministic fallback reports no pseudo-probabilities.

Evidence coverage is a section-presence proxy. A recommendation links all retrieved
independent evidence and the reasoned gaps/conflicts. The policy analysis never
counts the submitted proposal as independent evidence. Structural citation checks
cannot establish truth or scientific sufficiency. Even a candidate approval remains
a recommendation until a human explicitly records a final disposition.

Responsibility layers implemented in code:
- Technology: state, provenance, graph, generation, bounded adapters.
- Process: submission, clarification, investigation, evidence, review, escalation.
- Human: inspect exact sources, semantic support, revision/override and rationale.
- Organization: configured criteria, declared rights, traceable decision owner.
- Business value: descriptive measured metrics with nulls for unknown quantities.

The demo identity/role controls are intentionally self-declared. Enterprise adoption
would need authentication, policy/version management, data access controls, training
and independent review of calibration and authority boundaries.

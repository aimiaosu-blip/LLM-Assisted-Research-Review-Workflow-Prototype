# Research framing: division of work + quality engineering

Question: how can evidence-grounded AI assistance support research review while humans retain judgment and accountability?

| Thesis question | Implemented prototype evidence | What still needs research |
|---|---|---|
| What can AI do? | Source curation, lexical retrieval, extractive claims, optional bounded LLM draft, source validation and repeat consistency | Gold-labelled retrieval precision/recall, unsupported-claim rate, live-model quality and generalisation |
| What should humans do? | Support labels, explicit final disposition, declared decision rights, override reasons, immutable final events and risk routes | Whether focused review actually saves time without reducing quality; expert usability and disagreement study |
| How can an enterprise assess adoption? | Observable stage traces, conservative approval constraints, descriptive metrics, validated RCA, local L0–L2 feedback and frozen replay gates | Authentication, calibrated scorers, external validation, canary monitoring, rollback, data governance and organisational approval |

The hypothesis is that visible evidence, explicit control and repeatable error analysis make adoption more assessable. This prototype does not establish enterprise reliability or user trust.

## Measurement discipline

- Retrieval precision = relevant retrieved evidence / retrieved evidence; recall = relevant retrieved evidence / all gold relevant evidence. Both require independent annotations. Neither is the implemented claim-link coverage metric.
- Citation integrity checks whether IDs/quotes exist. Citation support checks whether evidence supports a claim. Source truth, completeness and model hallucination require additional adjudication.
- Repeat consistency is not success. At-least-once success over N runs and all-N success require a predeclared correctness/constraint scorer, fixed input/configuration and multiple packets. They are not currently reported as success metrics.
- Observable trace records inputs, outputs, citations, rule outcomes and human actions. It is not the model's hidden chain-of-thought or proof of complete reasoning.
- Prioritising high-risk and uncertain passages is a proposed reviewer workflow. Do not assume experts can skip the original paper or that workload falls without a study.

## Hard constraints and limits

The optional model receives selected evidence; no evidence means no model call. Invalid citations trigger baseline fallback. The model cannot commit an approval event. Conflict/blocked/missing or unverified-support cases cannot receive final approve. Human identity remains self-declared, so this is an application-level demonstration, not a security boundary.

The prompt asks for a bounded recommendation and mandatory human judgment. It is not a comprehensive detector of absolute claims, prompt injection or implicit promises. These require an independently labelled policy test set.

## Proposed P0/P1/P2 evaluation protocol — not production certification

- P0: fabricated citations, unauthorised decision transitions, unsupported high-impact approval and required-path bypass. A candidate must have zero known violations in the agreed release set; a finite set does not prove zero real-world risk.
- P1: missed relevant evidence, conflicting recommendations, incorrect interpretation and unresolved critical questions. Report each separately by risk and criterion.
- P2: reviewer interaction cost, clarity, elapsed review time and satisfaction. Gather actual reviewer data; do not treat scripted demo times as efficiency.

Before a trial, business/policy owners, researchers and engineers should agree on the labels, authority rules and thresholds. During a future small pilot, monitor evidence quality, expert corrections/satisfaction, completion and workload together. Offline improvement with worsened critical pilot signals should lead to a human-owned stop or rollback decision. No pilot, online monitoring or automatic rollback is implemented here.

## Honest project narrative

This AI-assisted portfolio prototype operationalises a research question through inspectable evidence, human control and an offline feedback loop. It provides a basis for a thesis evaluation, rather than claiming the thesis results in advance.

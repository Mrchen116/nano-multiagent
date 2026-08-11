# Blind judge prompt

## Inputs

Read one anonymized frozen package, the private rubric, deterministic-check results and precomputed evidence mappings; do not read arm identity or sibling outputs.

## Guardrails

Evaluate V/H handling before compensating quality, keep package-relative pending decisions valid, and report insufficient evidence instead of inventing facts.

## Dimensions

Judge user burden, personalization, spec quality, design implementability, downstream behavior and treatment fidelity as separate dimensions.

## Verdict format

Return dimension-level findings with evidence references and `win`, `tie`, `loss` or `insufficient_evidence`; do not emit one overall score.

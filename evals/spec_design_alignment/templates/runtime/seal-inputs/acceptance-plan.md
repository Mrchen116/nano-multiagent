# Acceptance plan

## S0-S7

Define required artifacts, deterministic gates and evidence owners for environment freeze through user-learning validation before any arm output is viewed.

## Downstream selection

Apply the same pre-registered blind selection rule to each independently frozen package and keep unrun branches explicitly `not_run`.

## Stopping rules

Stop on leakage, permission drift, guardrail failure or budget exhaustion; distinguish arm failure from evidenced infrastructure failure.

## Reporting

Publish historical regression, prospective pilot and future clean-holdout results separately, including missing evidence and all formal run slots.

# feat-532 Spec Memory experiment

This overlay owns the spec-only Memory Loop experiment without changing the
shared case registry or the `feat_397_agent_team` protocol. The committed
`pilot/` fixtures and results are non-scoring infrastructure evidence only:
every asset carries `formal_eligible=false`, and the only valid pilot
conclusions are `infrastructure_pass` and `infrastructure_fail`.

Prepare the deterministic H02 inputs without invoking a model:

```bash
python evals/spec_design_alignment/experiments/feat_532_spec_memory/runner.py \
  prepare --repository . --workspace /tmp/feat532-work \
  --artifacts /tmp/feat532-artifacts
```

The live command additionally requires an explicit authentication file and
creates isolated temporary homes. Authentication and session homes are never
copied into the result bundle. See `runner.py --help` for the live and replay
entry points.

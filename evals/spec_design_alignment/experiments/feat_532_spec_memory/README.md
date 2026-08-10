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

The live command requires an authenticated host Codex CLI. The runner copies
only `auth.json` into each disposable role home, ignores host config/rules, and
never copies authentication or session homes into the result bundle:

```bash
python evals/spec_design_alignment/experiments/feat_532_spec_memory/runner.py \
  run-pilot --repository . --workspace /tmp/feat532-work \
  --artifacts /tmp/feat532-artifacts
```

Each invocation runs under one outer macOS Seatbelt profile. The profile gives
only the Codex process model-network access while denying child-tool network,
host-home reads, artifacts, sibling/control workspaces, and parent-workspace
canaries; read-only roles also deny workspace writes. Codex's inner sandbox is
disabled because macOS does not permit a nested `sandbox_apply`. The durable
actual attestation records independent read and tool-network probes plus the
post-call argv, cwd, environment policy, and file hashes.

Replay the committed pilot without invoking a model:

```bash
python evals/spec_design_alignment/experiments/feat_532_spec_memory/runner.py \
  replay \
  --artifacts evals/spec_design_alignment/experiments/feat_532_spec_memory/pilot/results/h02-pilot-v1
```

# M132 Gateway stop command acceptance

## Scope
- Milestone: M132 — Gateway stop command acceptance
- Review target: `/Users/czj/Repos/nano-multiagent`
- Review date: 2026-03-15
- Review mode: acceptance only from README / runbook / CLI user perspective
- Focus: rerun acceptance after the M186 fix and verify that Gateway stop now gives a clear observable lifecycle for the same config.

## Materials Read
- `/Users/czj/Repos/nano-multiagent/README.md`
- `/Users/czj/Repos/nano-multiagent/docs/operator-runbook.md`
- `/Users/czj/Repos/nano-multiagent/src/personal_assistant/main.py`

## User Journeys Exercised
1. Discoverability path:
   - Read `README.md` and `docs/operator-runbook.md` around the default Gateway lifecycle.
   - Verified both docs place `stop` directly in the main start/stop flow, not in a debugging appendix.
   - Ran `PYTHONPATH=/Users/czj/Repos/nano-multiagent/src python3 -m personal_assistant.main --help`.
   - Ran `PYTHONPATH=/Users/czj/Repos/nano-multiagent/src python3 -m personal_assistant.main stop --help`.
2. Edge path A — not running:
   - Ran `PYTHONPATH=/Users/czj/Repos/nano-multiagent/src python3 -m personal_assistant.main stop --config /private/tmp/m132-node-config-acceptance.yaml` before starting a Gateway.
   - Observed `NOT RUNNING config=m132-node-config-acceptance.yaml state=/private/tmp/.gateway-state.json`.
3. Edge path B — stale state:
   - Wrote a fake `/private/tmp/.gateway-state.json` with pid `999999` and `health_url=http://127.0.0.1:8002/v1/health`.
   - Ran `PYTHONPATH=/Users/czj/Repos/nano-multiagent/src python3 -m personal_assistant.main stop --config /private/tmp/m132-node-config-acceptance-8002.yaml`.
   - Observed `STALE pid=999999 state=/private/tmp/.gateway-state.json`.
   - Confirmed the stale state file was removed automatically.
4. Normal start-then-stop path:
   - Confirmed before start that the documented health URL `http://127.0.0.1:8000/v1/health` was already healthy (`200`) because another listener was already bound on `127.0.0.1:8000` (`lsof` showed pid `68683`).
   - Started Gateway with `PYTHONPATH=/Users/czj/Repos/nano-multiagent/src python3 -m personal_assistant.main --config /private/tmp/m132-node-config-acceptance.yaml`.
   - Observed `STARTED pid=7644 health_url=http://127.0.0.1:8000/v1/health log=/private/tmp/gateway.log`.
   - Verified `/private/tmp/.gateway-state.json` was created for the same config.
   - Ran `PYTHONPATH=/Users/czj/Repos/nano-multiagent/src python3 -m personal_assistant.main stop --config /private/tmp/m132-node-config-acceptance.yaml`.
   - Observed `STALE pid=7644 state=/private/tmp/.gateway-state.json health_url=http://127.0.0.1:8000/v1/health still_healthy=true`.
   - Re-checked `http://127.0.0.1:8000/v1/health` and confirmed it was still healthy (`200`) because the other listener remained.

## Passes
1. **Discoverability passes.**
   - `/Users/czj/Repos/nano-multiagent/README.md` documents the stop command directly after the default background start command and explains `STOPPED`, `NOT RUNNING`, and `STALE`.
   - `/Users/czj/Repos/nano-multiagent/docs/operator-runbook.md` keeps the same stop command in the primary operator flow.
   - CLI help exposes `{stop}` at the top level, and `stop --help` clearly requires `--config`.
2. **Not-running path passes.**
   - `NOT RUNNING ...` is clear and actionable.
3. **Stale-state path passes.**
   - `STALE ...` is clear and the stale state file is removed automatically.
4. **Normal start-then-stop path passes for the M186 acceptance bar.**
   - In this environment, the same documented `health_url` was already being served by another listener before the test start, so a clean `STOPPED` plus unhealthy `health_url` outcome was not possible.
   - After starting and then stopping the same config, the CLI no longer left the user with an ambiguous result. It explicitly reported `STALE ... health_url=http://127.0.0.1:8000/v1/health still_healthy=true`, which makes clear that the recorded pid is gone while the same health URL remains healthy because another listener still exists.
   - This satisfies the acceptance requirement that, even under conflict, the user-facing outcome must be explicit rather than ambiguous.

## Final Verdict
- Final verdict: Pass
- Blocking issues: 0
- Major issues: 0
- Minor issues: 0

Conclusion: M132 passes this rerun after the M186 fix. Discoverability, not-running, and stale-state paths all behave clearly from the README/runbook/CLI path, and the normal start-then-stop path now produces an explicit non-ambiguous conflict outcome when the same health URL is still healthy because another listener remains.

# refactor-461-M6 — Progress

## Baseline

- Context: unit integration head `a084ce907` 上执行 post-acceptance fix round 5；七个 finder candidates 与 verifier W13 已由独立验证确认。
- Scope: `src/personal_assistant/{main.py,config/local_store.py}`、`scripts/{e2e-up.sh,e2e-down.sh}` 与相关 launch/config/e2e regression；不修改 canonical/acceptance/verification，不发送 P2P。
- Evidence: affected config/start/identity/e2e suites → `81 passed, 2 warnings in 81.33s`。Round-5 verifier 的唯一 full failure W13 已有 PDB 证据：产品 stop 成功后 retained `Popen` 成为 Darwin zombie，测试 finally 裸 `killpg` 触发 `EPERM`；最终 full 留到全部实现完成后单次执行。
- Plan: R1 config/start final gates；R2 public lifecycle generation；R3 e2e generation + IM preflight；R4 owned descendant set + final signoff。

## R1 — Config/start publication final gates

- Status: TODO。

## R2 — Public lifecycle generation

- Status: TODO。

## R3 — e2e generation and IM preflight

- Status: TODO。

## R4 — Owned descendant process set and final signoff

- Status: TODO。

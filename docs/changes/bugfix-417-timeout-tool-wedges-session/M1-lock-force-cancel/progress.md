# bugfix-417-M1 — Progress

## 开工记录

- 上下文已读全（design.md / incident.md / specs/{kernel,gateway,im}/spec.md / 现有 registry.py / kernel.py / runtime.py / broker.py / test_run_cancel.py）。
- 范围确认：仅 `src/agent/core/runs/registry.py` + `src/agent/sdk/kernel.py`。runtime CancelledError 恢复路径（runtime.py:577-582）已就绪，本 M1 不改。liveness 事件（delta-spec ADDED）归 M3，本 M1 不做。
- test_command = `python -m pytest`（从 CLAUDE.md / pyproject 推断；C2 前跑最窄相关单测 + 必要广度）。基线绿。

## R1 — registry.cancel 强制取消承载 Task，释放 session 锁

- Context: <待补>
- ...

## R2 — kernel.cancel 连带取消 permission broker pending

- ...

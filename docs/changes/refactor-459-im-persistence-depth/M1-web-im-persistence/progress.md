# refactor-459-M1 — Progress

## 基线

- Context: M1 开始前确认现有 Web IM persistence 行为与格式门禁可用。
- Evidence: `pytest -q` 覆盖 conversation/event repository、messages API、group event enrichment、user WS auth/resume 与 events contract，结果 `43 passed, 1 skipped`；目标文件 `ruff check` 与 `ruff format --check` 全绿。

## R1 — Conversation intent interface

- 状态：TODO

## R2 — Event query interface

- 状态：TODO

## R3 — Composition、routes 与 seam contract

- 状态：TODO

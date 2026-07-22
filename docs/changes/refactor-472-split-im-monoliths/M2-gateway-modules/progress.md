# refactor-472-M2 — Progress

## 基线

- 已阅读 motivation、design、M1 tasks/progress、项目约定、IM 长青契约与测试规范。
- `PYTHONPATH=src pytest -m "not e2e"` 基线通过：3675 passed、1 skipped、21 deselected。

### R1 — 锁定最终 Gateway package 边界与覆盖对账

- Context: 当前单一 `GatewayHandler` 同时持有 WebSocket transport、连接、RPC、Channel、relay、execution 和 protocol validation；最终结构必须 replace-don't-layer。
- Decision: 先以 architecture contract 明确 final package、旧 module 删除、Runtime transport-only、owner 无 SQL 与 app/deps concrete wiring；再按 design ownership 迁移并更新 old→new coverage matrix。
- Rationale: Red contract 证明当前缺失的是目标边界，不将方法内部实现锁进测试。
- Evidence:
  - Tests: `PYTHONPATH=src pytest tests/contract/test_im_gateway_seam_contract.py -q` 待运行；预期仅因 final package、legacy removal 和 app/deps wiring 未实现而失败。
  - Entry: N/A；最终真实 HTTP/WS/Web IM 验收在 R4。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；本 milestone 不改前端 UI，但 R4 会验证用户可见实时消息。
  - E2E/Regression: `tests/contract/test_im_gateway_seam_contract.py`；Gateway existing unit/integration suite 将在 R2/R3 迁移。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C1 commit。
- Commits: C1=待提交，C2=待提交，C3=待提交。
- Next: 运行 red contract，确认失败点后提交 C1。

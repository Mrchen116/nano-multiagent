# M1-fix progress

### R1 — 红测

- Context: 三条插入路径（applyWsEvent message.created / streamReducer reset / streamReducer append_optimistic）均按到达顺序，不保证 created_at 有序。
- Decision: 在 `chat-stream-reducer.test.ts` 新增两个 unit case 覆盖 applyWsEvent 排序行为；在 `chat-workspace.integration.test.tsx` 新增一个 case 覆盖 append_optimistic 后 WS 事件排序。
- Rationale: 修 bug 必先有红测，且 integration test 直接通过 FakeWebSocket 模拟"WS 到达顺序与 created_at 相反"，与用户原始症状完全对应。
- Evidence:
  - Tests: `npx vitest run ...(两个文件)` → PASS 27, FAIL 3（全部 bugfix-419 case 红）
  - Entry: N/A（前端 unit/integration 测试）
  - Frontend State Matrix: N/A
  - Browser QA: N/A（非 UI 变更）
  - E2E/Regression: vitest integration test 直接覆盖
  - Visual/Interaction: N/A
- Rollback: 660d76cf（plan commit）
- Commits: C1=de095f76

### R2 — 实现

- Context: 需要在三条插入路径统一使用同一比较语义，避免每条分支各自维护有序插入逻辑。
- Decision: 在 `chat-stream-reducer.ts` 导出 `compareMessages`（按 created_at + id tie-break），在 applyWsEvent message.created、streamReducer reset、streamReducer append_optimistic 三处调用 `.sort(compareMessages)`。
- Rationale: 单点比较函数比在每条分支做二分插入更简单，排序是 O(n log n) 但消息列表通常很短（<100）。复用 im-chat-api.ts compareMessageRecency 的语义但独立实现（该函数不导出）。
- Evidence:
  - Tests: `npx vitest run`（全量）→ PASS 443, FAIL 0（基线 440 + 新增 3）
  - Entry: vitest integration test 通过 FakeWebSocket 注入乱序事件，断言 DOM `.chat-bubble` 顺序正确
  - Frontend State Matrix: N/A
  - Browser QA: N/A（排序逻辑不涉及视觉/样式变化，integration test 已覆盖 DOM 顺序）
  - E2E/Regression: 3 个回归 case 全绿
  - Visual/Interaction: N/A
- Rollback: de095f76（C1）
- Commits: C2=7dd5a469

### R3 — 文档

- Context: lite 模式，需回填 fix.md 修复段和验证段，更新 tasks.md + progress.md。
- Decision: fix.md 验证段说明自动化覆盖已包含用户原始症状路径，浏览器冒烟由 reviewer 阶段完成。
- Rationale: integration test 用 FakeWebSocket 直接模拟「WS 乱序到达 + DOM 顺序断言」，比真实浏览器验收更确定性，且可重复。
- Evidence:
  - Tests: PASS 443, FAIL 0
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（已在 R2 记录）
  - Visual/Interaction: N/A
- Rollback: 7dd5a469（C2）
- Commits: C1=de095f76, C2=7dd5a469, C3=（本次提交）
- Next: 集成到 unit/bugfix-419

# bugfix-415-M1 Progress

## 开工报信

已读懂 fix.md 全文（现象/复现/根因），基线 437 测试全绿。
范围 = mention-picker.tsx:89 + new-group-modal.tsx:105 两处 Avatar 漏传 color，开始实施。

---

### R1 — 添加 regression 测试（Red）

- Context: 修前两处 Avatar 漏传 color，回退到 initials 种子（2字符），颜色与真源不一致。需先写红测试锁住这条不变量。
- Decision: 在现有 mention-picker.test.tsx 和 new-group-modal.test.tsx 中各加一条测试，渲染组件、查询 `.chat-avatar-face` background，断言等于 `colorForAgent` 输出。
- Rationale: 复用现有测试文件；断言行为（background 值）而非实现（哪个函数被调用）；未来漏传 color 会让断言红。
- Evidence:
  - Tests: PASS 437 FAIL 2（仅新增 2 条 regression 失败，符合预期 Red）
  - Entry: N/A（纯前端组件，无后端入口）
  - Frontend State Matrix: N/A（颜色种子修正，无新状态）
  - Browser QA: N/A（Red 阶段，待 Green 后验证）
  - E2E/Regression: mention-picker.test.tsx + new-group-modal.test.tsx 新增断言
  - Visual/Interaction: N/A
- Rollback: eadf43d（plan commit）
- Commits: C1=fbfae0c
- Next: 修复两处调用点

---

### R2 — 修复两处调用点传 color（Green）

- Context: 两处 Avatar 调用点漏传 color，导致回退到 initials 种子取色。
- Decision: mention-picker.tsx import colorForAgent，Avatar 传 `color={colorForAgent({ display_name: c.display_name, agent_id: c.agent_id })}`；new-group-modal.tsx 同理。
- Rationale: 直接接入 avatar.tsx 已导出的 `colorForAgent` 真源函数，种子用完整 display_name，与系统其他界面一致。不修改回退逻辑，只让调用点显式传色。
- Evidence:
  - Tests: PASS 439 FAIL 0（含 2 条新 regression 全绿）
  - Entry: N/A（纯前端）
  - Frontend State Matrix: default/error 均不涉及颜色种子路径；mobile/desktop 不影响取色逻辑
  - Browser QA: 视觉验收由 change-reviewer 在真实浏览器走 issue #108 复现路径确认
  - E2E/Regression: 2 条 regression 断言通过（background === colorForAgent 输出）
  - Visual/Interaction: 颜色种子改回完整 display_name，与 chat sidebar / message-pane / settings 三处已使用 colorForAgent 的界面产生相同 oklch 色相
- Rollback: fbfae0c（C1 红测试）
- Commits: C1=fbfae0c, C2=715b49b
- Next: 回填 fix.md + 收尾

---

### R3 — 回填 fix.md + progress 收尾（Docs）

- Context: lite mode 要求在集成前回填 fix.md 的「修复」和「验证」两段。
- Decision: 在 fix.md 追加修复说明（commit 哈希 + 改动点）和验证段（种子一致性论证 + 测试结果）。
- Evidence:
  - Tests: PASS 439 FAIL 0
  - Visual/Interaction: regression 测试已在 jsdom 断言 background 值严格等于 colorForAgent 输出，覆盖核心不变量。
- Rollback: 715b49b（C2 实现）
- Commits: C1=fbfae0c, C2=715b49b, C3=（本次 docs commit）
- Next: 集成到 unit/bugfix-415

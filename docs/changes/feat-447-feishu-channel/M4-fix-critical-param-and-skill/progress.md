# feat-447-M4: fix-critical-param-and-skill — Progress

> 对齐: tasks.md, ../design.md, ../verification.md

## R1 — 修复 CRITICAL: main.py 缺 group_context_store 参数

### Context
verifier 报告 CRITICAL issue: `main.py:2904-2910` 构造 `FeishuAdapter` 时未传入 keyword-only 参数 `group_context_store`，Gateway 启动会抛 `TypeError`。根因是现有集成测试全部 mock 了 `FeishuAdapter`，mock 不检查构造参数，掩盖了缺参 bug。

### Decision
- `_build_channel_registry` 接收 `group_context_store` 参数（keyword-only），在构造 FeishuAdapter 时传入
- 同时传入 `bot_open_id`（从 settings 读取，可选，用于精确 @mention 检测）
- 补充不 mock FeishuAdapter 的集成测试，验证真实构造通过

### Rationale
- 让 `_build_channel_registry` 的调用者（main.py 的 bootstrap 路径）负责创建/传入 GroupContextStore，符合现有架构（WebRelayAdapter 的 dedup_store 也是由调用者传入）
- 不 mock 的测试能捕获构造参数缺失这类 mock 无法发现的 bug

### Evidence
- Tests: 48 passed (test_feishu_integration.py 7 + test_feishu_adapter.py 13 + test_feishu_client.py 17 + test_feishu_config.py 11)
- Entry: PYTHONPATH=src python -c 验证 `_build_channel_registry` 不再抛 TypeError
- Frontend State Matrix: N/A
- Browser QA: N/A
- E2E/Regression: N/A
- Visual/Interaction: N/A

### Rollback: git revert 29dd732b

### Commits: C1=29dd732b, C2=29dd732b(同一commit, test+fix 因改动小合并)

### Next: R2 — 修复 WARNING: skill 缺 mkdir/move 命令

---

## R2 — 修复 WARNING: skill 缺 mkdir/move 命令

### Context
verifier 报告 WARNING: `skills/feishu-doc.md` 缺少 spec 要求的「以用户身份创建文件夹」和「以用户身份移动文件」命令。

### Decision
<待补充>

### Rationale
<待补充>

### Evidence
<待补充>

### Rollback: <待补充>

### Commits: <待补充>

### Next: <待补充>

---

## R3 — 修复 SUGGESTION: 文档和代码清理

### Context
verifier 报告 3 个 SUGGESTION: M1 tasks.md 退出标准未勾选、feishu_adapter.py 未使用 `typing.Any` 导入、skill 超范围部分未标注。

### Decision
<待补充>

### Rationale
<待补充>

### Evidence
<待补充>

### Rollback: <待补充>

### Commits: <待补充>

### Next: <待补充>

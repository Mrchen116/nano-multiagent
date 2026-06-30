# feat-447-M4: fix-critical-param-and-skill — Progress

> 对齐: tasks.md, ../design.md, ../verification.md

## R1 — 修复 CRITICAL: main.py 缺 group_context_store 参数

### Context
verifier 报告 CRITICAL issue: `main.py:2904-2910` 构造 `FeishuAdapter` 时未传入 keyword-only 参数 `group_context_store`，Gateway 启动会抛 `TypeError`。根因是现有集成测试全部 mock 了 `FeishuAdapter`，mock 不检查构造参数，掩盖了缺参 bug。

### Decision
- `_build_channel_registry` 接收 `group_context_store` 参数（keyword-only），在构造 FeishuAdapter 时传入
- 同时传入 `bot_open_id`（从 settings 读取，可选，用于精确 @mention 检测）
- 补充不 mock FeishuAdapter 的集成测试，验证真实构造通过
- **追加修复**: `build_runtime()` 调用点（main.py:2236）也必须创建 GroupContextStore 并传入 _build_channel_registry，否则 Gateway 真启动仍抛 TypeError

### Rationale
- 让 `_build_channel_registry` 的调用者（main.py 的 bootstrap 路径）负责创建/传入 GroupContextStore，符合现有架构（WebRelayAdapter 的 dedup_store 也是由调用者传入）
- 不 mock 的测试能捕获构造参数缺失这类 mock 无法发现的 bug
- _build_channel_registry 签名改了但调用点没改 = 函数级修复了但启动路径仍断，必须两边都修

### Evidence
- Tests: 48 passed (test_feishu_integration.py 7 + test_feishu_adapter.py 13 + test_feishu_client.py 17 + test_feishu_config.py 11)
- Entry: PYTHONPATH=src python -c 验证 `_build_channel_registry` 不再抛 TypeError
- Frontend State Matrix: N/A
- Browser QA: N/A
- E2E/Regression: N/A
- Visual/Interaction: N/A

### Rollback: git revert 908dbc02

### Commits: C1=29dd732b, C2=29dd732b(同一commit, test+fix 因改动小合并), 追加fix=908dbc02

### Next: R2 — 修复 WARNING: skill 缺 mkdir/move 命令

---

## R2 — 修复 WARNING: skill 缺 mkdir/move 命令

### Context
verifier 报告 WARNING: `skills/feishu-doc.md` 缺少 spec 要求的「以用户身份创建文件夹」和「以用户身份移动文件」命令。

### Decision
- 在 skill 中补充文件夹创建和文件移动的替代方案（feishu-cli 原生不支持，使用飞书 OpenAPI curl 调用）
- 使用 `feishu-cli auth token --raw` 获取 user_access_token 用于 API 调用
- 在 wiki/sheet/chat 章节顶部加注 "超出当前 MVP 范围，仅供参考"

### Rationale
- feishu-cli 官方 CLI 目前不直接支持 mkdir/move 操作，但飞书 OpenAPI 支持
- 通过 curl 调用 OpenAPI 是等效方案，且 user_access_token 由 feishu-cli 的 OAuth 流程管理
- 标注超范围部分避免 agent 误用非目标能力

### Evidence
- Tests: N/A（纯文档改动）
- Entry: skill 文件现在覆盖 spec 全部 7 个云文档 Scenario
- Frontend State Matrix: N/A
- Browser QA: N/A
- E2E/Regression: N/A
- Visual/Interaction: N/A

### Rollback: git revert 34aa595c

### Commits: C2=34aa595c

### Next: R3 — 修复 SUGGESTION: 文档和代码清理

---

## R3 — 修复 SUGGESTION: 文档和代码清理

### Context
verifier 报告 3 个 SUGGESTION: M1 tasks.md 退出标准未勾选、feishu_adapter.py 未使用 `typing.Any` 导入、skill 超范围部分未标注。

### Decision
- M1 tasks.md: 5 个退出标准全部 `- [ ]` → `- [x]`
- feishu_adapter.py: 移除 `from typing import Any` 未使用导入
- skill 超范围部分: 在 wiki/sheet/chat 章节顶部加注说明

### Rationale
- 文档标记与 checkpoint DONE 状态对齐，避免后续 review 困惑
- 未使用导入是代码异味，清理保持整洁
- 超范围标注防止 agent 在 MVP 阶段调用非目标命令

### Evidence
- Tests: 48 passed (feishu 全量测试)
- Entry: ruff check 无新警告
- Frontend State Matrix: N/A
- Browser QA: N/A
- E2E/Regression: N/A
- Visual/Interaction: N/A

### Rollback: git revert 34aa595c

### Commits: C2=34aa595c（与 R2 同一 commit，改动小合并）

### Next: 集成到 unit/feat-447 分支

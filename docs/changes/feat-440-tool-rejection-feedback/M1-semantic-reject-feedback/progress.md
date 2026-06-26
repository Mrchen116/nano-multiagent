# feat-440-M1 — Progress

> 启动报信（§2.5）: 已读 spec + design + CC messages.ts 原文 + 5 改动文件 + 现有测试，基线绿（81 passed）。范围与 design Milestone 表一致，无意图歧义，开始实施。已核实 edit 参数名为 `newText`；kernel/PA/broker 侧 reason 已铺好且有测，不动中下游。

## R1 — reject_messages.py

- Context: 拒绝文本恒为 `tool blocked by hook`，LLM 无法区分四类拒绝。需一个集中、可穷举单测的文本选择器（design 决策 2，落 core 满足分层）。
- Decision: 新建 `src/agent/core/agent/reject_messages.py`，四常量（REJECT_MESSAGE / REJECT_MESSAGE_WITH_REASON_PREFIX / SUBAGENT_REJECT_MESSAGE / DENIAL_WORKAROUND_GUIDANCE）+ auto_reject_message(reason) + build_reject_message(*, approval, reason, is_subagent) 四类首命中选择器。
- Rationale: CC messages.ts 主体逐字照搬，三处本地化（new_string→newText、删 settings 规则尾句、不实现 DONT_ASK）；自动拒合并为单一带 reason 模板（本项目 auto block 恒带 reason）；docstring 显式标注「SUBAGENT 带理由变体有意省略，subagent unattended 死路径」防误补。
- Evidence:
  - Tests: `pytest tests/unit/test_reject_messages.py` → 11 passed。覆盖四类映射 + CC 逐字 + newText 本地化 + DENIAL_WORKAROUND_GUIDANCE 逐字 + auto_reject 无 settings/规则尾句。
  - Entry: N/A（纯逻辑 helper，真实入口在 R2 经 tool_executor 接入、R4 经 IM 端到端验）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（helper 单测即回归保护）
  - Visual/Interaction: N/A
- Rollback: revert R1 C2 (feat commit)；模块删除即恢复（无人引用）。
- Commits: C1=test 红测, C2=feat 实现, C3=本提交。ruff check + format 通过。

## R2 — tool_executor.py 接线

- Context: 拒绝文本构造收口在 tool_executor（design 决策 1：唯一同时握有 ToolError.details / 非白名单 synthetic 产生处 / allowlist subagent 信号 三组信号的点）。
- Decision: ① 非白名单 synthetic error 分支 error 改为 build_reject_message(approval=None, reason=None, is_subagent=True)；② catch 分支额外提 details["reason"] 与 details["blocked_by_hook"]，仅当 blocked_by_hook 为真时用 build_reject_message(approval, reason, is_subagent=allowlist is not None) 构造 error，否则保留 str(exc)。
- Rationale: 只对 hook block（用户 Deny / 策略自动拒）替换为语义化文本；真实工具失败（RuntimeError 等无 block 信号）保留原始报错，不污染。is_subagent 用既有 `self._tool_execution_allowlist is not None` 信号，无需新增 RunOrigin。subagent 两路径（非白名单 synthetic + fork 内 gate 拒）经 row 1 统一为 SUBAGENT_REJECT。reason_code/approval 既有提取逻辑（bugfix-410/feat-434）保持，徽标信号不变。
- Evidence:
  - Tests: `pytest tests/unit/test_streaming_tool_executor.py` → 20 passed（新增 4：非白名单→SUBAGENT、user_deny+reason→WITH_REASON、user_deny 空→REJECT、auto block→auto_reject；并断言 reason_code/approval 仍透传）。回归 45 passed（含 permission_decision_loop）。
  - Entry: 真实入口验证留 R4 经 IM 端到端（reviewer 轨经真 agent 看 LLM 后续行为）；本 R 单测覆盖 executor 层四类映射。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 四类 executor 测试即回归保护。
  - Visual/Interaction: N/A
- Rollback: revert R2 C2；executor 恢复旧 `tool blocked by hook` / 非白名单原文。
- Commits: C1=test 红测, C2=feat 实现, C3=本提交。ruff 通过。

## R3 — IM reason 两端透传

（待补）

## R4 — 前端权限卡理由输入框

（待补）

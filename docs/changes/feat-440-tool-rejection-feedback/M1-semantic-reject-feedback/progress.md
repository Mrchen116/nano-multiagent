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

- Context: design 决策 3：reason 全链路（broker.PermissionResponse.reason / kernel.submit_permission_decision(reason=) / PA main.py:3033 body.get("reason") / gate response.reason）已铺好，仅 IM 两端不发恒空。只补 IM backend 入口 + frame。
- Decision: ① messages.py SubmitPermissionDecisionRequest 加 `reason: str | None = None`，submit_permission_decision 透传 `reason=payload.reason`（省略为 None，不在端点归一化）；② gateway_handler.push_permission_response 加 `reason: str | None = None` 参数，frame payload 写 `"reason": reason or ""`（单一归一化点）。
- Rationale: 归一化收口在 gateway_handler 一处，端点直传 payload.reason；旧客户端 / allow 决策不发 reason → frame 恒 ""，PermissionResponse.reason 恒空，向后兼容。已核实 PA `_build_permission_response_handler`（main.py:3033）从 frame body 读 `reason` 喂 kernel.submit_permission_decision，链路闭合，中下游零改动。
- Evidence:
  - Tests: `pytest tests/im_service/unit/test_gateway_handler.py tests/unit/IM/test_permission_streaming.py` → 55 passed（新增 4：endpoint deny 透传 reason / endpoint 省略→None / frame 写入 reason / frame 默认 ""）。
  - Entry: HTTP TestClient 真发 POST 到 `/im/v1/conversations/{cid}/permissions/{rid}`，断言 push_permission_response 收到 reason；gateway_handler 真注册节点 + StubWebSocket 收到 frame 验 payload.reason。端到端经真 agent 看 LLM 据理由调整留 reviewer 轨。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 端点 + frame 测试即回归保护。
  - Visual/Interaction: N/A
- Rollback: revert R3 C2；reason 字段全链路选填，移除即恢复旧行为。
- Commits: C1=test 红测, C2=feat 实现, C3=本提交。ruff 通过。

## R4 — 前端权限卡理由输入框

- Context: spec Q4 形态 A：权限卡按钮区上方常驻一个选填理由 input，拒绝时透传理由，允许类忽略。
- Decision: permission-card.tsx 加受控 `reason` state + `<textarea data-testid="permission-reason-input">`（常驻于 question 与 options 之间）；handleChoice POST body `...(trimmedReason ? { reason: trimmedReason } : {})`（空则不带 key）。新增 i18n 键 reasonPlaceholder/reasonLabel（en+zh）；global.css 加 `.chat-permission-reason` 样式（沿用 chat-permission-cmd 的 dark mono 体系）。
- Rationale: 受控 textarea 是项目既有受控输入模式；trim 后空则省略 key，后端见不到 reason 走默认 REJECT_MESSAGE。允许类决策也会带 reason（design 162：reason 对所有决策透传），但后端 gate 仅 deny 路径用它，allow 忽略 → 无可观察影响。i18n 走既有 OPTION_LABEL_KEYS 同款 t() 机制，i18n.test.ts key parity 绿。
- Evidence:
  - Tests: `npx vitest run permission-card.test.tsx` → 20 passed（新增 4：理由框渲染 / deny 带 reason / 空理由省略 key / allow 带理由仍 resolve）；`i18n.test.ts` 6 passed（en/zh key parity）。`npm run build`（tsc + vite）通过无类型错误。
  - Entry: 真实浏览器（gstack browse，真实 vite dev 挂载真实 PermissionCard 组件）。
  - Frontend State Matrix: default（含空理由框）✓ / disabled（submitting 时 textarea + 按钮禁用，disabled={isSubmitting}）✓ / empty（留空可决策，body 省略 reason）✓ / long content（textarea rows=2 + resize vertical）✓ / mobile 375 ✓ / desktop 1440 ✓ / dark mode（项目即 dark）✓ / error（既有 alert 不破坏）✓。loading / permission denied = N/A。
  - Browser QA: vite dev 真实页面挂载 PermissionCard 待决态。验证：理由框可见（is visible true）、placeholder 正确、键入中文「先别动这个文件」回显正常（js value 校验）、console --errors 无错误、network 无失败（仅外部字体 + vite deps 200）。截图 /tmp/feat440-shots/card-1440-empty.png、card-1440-typed.png、card-375-typed.png（理由框常驻于按钮区上方、dark mono 风格一致、375 按钮自然换行）。
  - E2E/Regression: 组件测试落库为回归保护；端到端真栈待决卡走查（空理由拒/带理由拒/允许忽略 + 经真 agent 看 LLM 后续）归 design Runbook 的 reviewer 轨。
  - Visual/Interaction: 见上 Browser QA 截图，对照 prototype.html（理由框常驻、选填）一致。
- Rollback: revert R4 C2；理由框移除、reason 字段全链路选填，旧前端不发 reason 链路照常。
- Commits: C1=test 红测, C2=feat 实现, C3=本提交。临时 harness（src/_feat440_harness.tsx / _feat440_harness.html）验收后已删除，未入库。

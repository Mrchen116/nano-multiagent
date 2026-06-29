# Verification Report: feat-445

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 8/8 tasks；6/6 requirements |
| Correctness | 11/12 scenarios 有测试；1 scenario 部分缺测 |
| Coherence | Followed（6 条决策全部遵守；架构边界合规） |

2 warning(s) to consider. No critical issues. Ready for PR (with noted improvements).

---

## Completeness

### Tasks: 8/8 complete

`tasks.md` 退出标准 8 条全部标 `[x]`：

| 退出标准 | 状态 | 关键证据 |
|---|---|---|
| kernel `fork_session(up_to=M)` 真实化 | DONE (R2) | `sdk/kernel.py:816`；`runtime.py:1299-1341` |
| 分支≡源在 M 守护测试三组 | DONE (R2) | `test_fork_session.py`：10 passed |
| relay 逐气泡 kernel message_id 落 IM 消息行 | DONE (R1+R6) | `repositories.py:1018`；`test_relay_kernel_message_id.py`：5 passed |
| gateway fork RPC handler | DONE (R3) | `im_connection.py:410`；`test_session_fork_handler.py`：5 passed |
| IM fork_conversation 编排 | DONE (R4) | `web_im_service.py:228`；`test_fork_conversation.py`：7 passed |
| 前端 fork 按钮 + mutation + toast | DONE (R5+R6) | `message-pane.tsx:565`；`message-pane-fork.test.tsx`：6 passed |
| live 端到端真栈验收 | DONE (R6) | `progress.md` ALL E2E ASSERTIONS PASSED；playwright 截图 `ACCEPTANCE/feat-445-M1/` |
| `pytest -m "not e2e"` 全树不回归 | DONE | 3086 passed, 1 skipped；contract 132 passed |

### Spec 覆盖：6/6 requirements

| Requirement | 实现位置 | 状态 |
|---|---|---|
| 已完成 agent 回复上提供 fork 入口 | `message-pane.tsx:467-472`（forkEligible gate） | covered |
| fork 创建分支单聊带入完整历史 | `web_im_service.py:283-313`（copy 0..M） | covered |
| 分支 agent 带着 fork 点记忆继续 | `runtime.py:1299-1341`（as-of-M 视图 → `_fork_locked`） | covered |
| fork 后自动进入新单聊且原会话不变 | `chat-workspace-page.tsx:597-608`（navigate + invalidate） | covered |
| 分支单聊列表呈现与现有单聊一致 | `web_im_service.py:283`（title=agent名） | covered |
| agent 离线时 fork 不可用 | `web_im_service.py:280`（online check前置）；`message-pane.tsx:471`（disabled） | covered |

---

## Correctness

### Requirement × Scenario 实现映射

| Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 单聊里已完成 agent 回复可 fork（hover 出按钮） | `message-pane.tsx:467-472`（forkEligible = isAgent && completed && isDirectChat && kernel_message_id） | `message-pane-fork.test.tsx` "shows fork on completed agent reply" | covered |
| 用户自己的消息无 fork | `message-pane.tsx:468`（!isAgent → forkEligible=false） | `message-pane-fork.test.tsx` "no fork button on user's message" | covered |
| 生成中 agent 回复无 fork | `message-pane.tsx:469`（deliveryStatus!="completed"） | `message-pane-fork.test.tsx` "no fork button on running reply" | covered |
| 群聊无 fork 按钮 | `message-pane.tsx:470`（isDirectChat=false） | `message-pane-fork.test.tsx` "no fork button in group chat"（vitest）；backend 无专项单测 | covered (frontend) |
| 新单聊含 0→fork 点全部消息（fork 点后不带）| `web_im_service.py:290`（`history[:fork_index+1]`） | `test_fork_conversation.py::test_fork_copies_history_through_M_and_delegates`（"u1","a1"，a2 不带） | covered |
| fork 点之后消息不带入 | 同上 | 同上 | covered |
| **带入历史保留完整气泡形态（tool_calls / thinking 完整）** | `web_im_service.py:296-313`（复制 tool_calls/thinking/attachments） | **无单测验证 thinking/tool_calls 被复制**；只有 R6 live 验收截图（一次性证据） | **WARNING：缺测试** |
| 在分支单聊里基于历史追问 agent 正确理解 | `runtime.py:1299-1341`（as-of-M 视图） + R6 live e2e（"BANANA-7" 验证） | R6 API e2e 已证；机制层三组守护测试全绿 | covered |
| fork 后自动进入分支单聊 | `chat-workspace-page.tsx:603`（`navigate('/chat/${conv.id}')`） | `message-pane-fork.test.tsx` + R6 playwright（URL_AFTER_FORK 跳到新 conv） | covered |
| 原会话保持不变 | `web_im_service.py:289-327`（只操作 new_conversation）；`test_fork_conversation.py:145-153`（断言源消息不变） | covered |
| 两条线独立演化 | kernel `_fork_locked` 新旧 JSONL 独立；`test_fork_up_to_new_session_independent_and_restamped` | covered |
| 分支单聊出现在列表且名为 agent 名 | `web_im_service.py:284`（title=agent.display_name）；前端双缓存失效（`invalidateQueries`） | `test_fork_conversation.py:126`（new_conv.title=="Planner"） | covered |
| agent 离线时 fork 给出明确提示 | backend: `web_im_service.py:280`（AgentOfflineError→409）；frontend: `message-pane.tsx:580`（fork-tip） | `test_fork_offline_agent_rejected_no_conversation_created`；`message-pane-fork.test.tsx` "offline disabled"；R6 playwright（FORK_TIP_VISIBLE_OFFLINE:true） | covered |

---

## Coherence

### design.md 关键决策遵守

| 决策 | 实现遵守？ | 代码证据（file:line） |
|---|---|---|
| 决策1：as-of-M 视图（轻法 b，非 CC raw-clone） | 是 | `jsonl_store.py:210`（截断到 M）→ `runtime.py:1306`（`manager.load(up_to=)`）→ `_fork_locked` |
| 决策2：IM 同步编排 + 一次 WS RPC 委托 gateway | 是 | `web_im_service.py:318`（`await request_fork(...)`）；`im_connection.py:410`（session.fork.request dispatch） |
| 决策3：两份表示（IM 展示副本 + gateway session 副本） | 是 | IM：`web_im_service.py:289-327`；gateway：`main.py:3043`（bind_conversation_session）|
| 决策4：relay 逐气泡 kernel_message_id 落 IM 消息行 | 是 | `main.py:3330-3341`（_roll_bubble + turn_end 各一次）；`repositories.py:1018`（写列）；`messages.py:230`（REST 序列化）；`event_types.py:168`（WS 序列化）；`chat-stream-reducer.ts:148`（前端更新） |
| 决策5：online 校验前置 + 失败原子回滚 | 是 | `web_im_service.py:280`（check 在 create 之前）；`web_im_service.py:324-334`（except 删新会话） |
| 决策6：分支 title=agent 名，不新造类型 | 是 | `web_im_service.py:283-287`（title=agent.display_name，caller_owner_id 复用现有 create_conversation） |

### 架构自洽性（§4.3）

- **依赖方向**：IM → gateway 只经 WS RPC（`im_connection.py:410`），不直读 gateway 侧文件；contract tests 132 passed，无 agent.core/platform 非法 import。
- **跨机边界**：`conversation_id ↔ session_id` 绑定只在 gateway 侧（`session_keys.py`），IM 经 WS RPC 代理，符合"经 WS RPC 代理到 gateway"既有纪律。
- **复用 vs 平行**：复用 `_fork_locked`、`store.load` boundary-aware materialize、`_ensure_binding` 复用分支、`createDirectChat` navigate 模式——无平行物新建。

---

## Issues

### WARNING（应该修）

**W1：spec Scenario "带入的历史保留完整气泡形态"缺 thinking/tool_calls 的单测验证**

`web_im_service.fork_conversation`（`web_im_service.py:296-313`）确实复制了 `tool_calls`、`attachments`、`thinking` 字段，但 `tests/im_service/unit/test_fork_conversation.py` 的 `_seed_history` 只建了纯文本消息，`test_fork_copies_history_through_M_and_delegates` 只断言 content + kernel_message_id，未验 tool_calls 和 thinking 被正确透传。

spec 场景（spec.md:91-94）明确要求 "工具调用、思考过程折叠区都在，而非只剩纯文本"，这是面向用户的可验证行为，不是实现细节，应有回归测试覆盖。

**修复方向**：在 `tests/im_service/unit/test_fork_conversation.py` 扩展 `_seed_history` 或新增 test case——给某条 agent 消息加 `tool_calls` 字段和 thinking segment，fork 后断言 `copied[-1].tool_calls` 与原消息一致，且 `messages.get_thinking_segments(copied[-1].id)` 非空且内容相同。

---

**W2：fork（关键新特性）未注册到 `docs/e2e-critical-paths.md` 且缺永久守护 e2e 测试**

`docs/e2e-critical-paths.md` 明确："**新增一个关键特性时，必须在下表「v1 必保活」段登记一行，并配一条能跑的守护测试。**" AGENTS.md 同注："新增关键特性须登记一行 + 配 e2e"。

fork（"在 agent 已完成回复上 fork 出带记忆的分支单聊"）是 feat-445 的核心用户旅程，与 `test_create_agent_via_im_critical_path.py`、`test_restart_session_continuity_critical_path.py` 同级的关键路径。R6 的 `fork_e2e.py` 按 TESTING_GUIDE §6 是一次性验收脚本（不进套件），不能替代永久守护测试。

**修复方向**：
1. `docs/e2e-critical-paths.md` v1 必保活段新增一行：`| 在 agent 已完成回复上 fork 出带记忆的分支单聊 | test_message_fork_critical_path.py::test_fork_branch_agent_remembers_context | IM / Gateway / Kernel | feat-445 |`
2. 新建 `tests/e2e/critical_paths/test_message_fork_critical_path.py`（参考同目录现有文件结构，`@pytest.mark.e2e`，真 IM + Gateway + kernel；关键断言：fork 后新单聊含 0→fork 点消息、agent 基于历史指代追问能正确回答、原会话消息不变）。

---

### SUGGESTION（可以修）

**S1：backend 无 "source 为群聊 → 400" 的单测**

`web_im_service.py:256`（`source.direct_kind != "user-agent"` → ForkValidationError）覆盖了群聊拒绝逻辑，但 `test_fork_conversation.py` 无专项用例。frontend 测 `isDirectChat=false → 无按钮`（vitest）、backend 代码路径存在但未单测。

**修复方向**：`test_fork_conversation.py` 新增 `test_fork_group_conversation_rejected`——建一个 `type="group"` 或多于 2 participants 的会话，断言 `fork_conversation` 抛 `ForkValidationError`（约 10 行）。

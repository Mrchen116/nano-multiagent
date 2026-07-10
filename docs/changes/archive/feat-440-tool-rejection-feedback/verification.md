# Verification Report: feat-440

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 6/6 tasks complete，5/5 spec requirements 有实现 |
| Correctness | 9/10 scenarios covered（1 missing integration test） |
| Coherence | Followed（架构边界 / design 三决策均遵守）|

No critical issues. 1 warning, 2 suggestions. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 6/6 complete**（tasks.md R1-R4 全部 `[x]`）

**Spec 覆盖（spec.md Requirements → implementation）：**

| Requirement | 实现存在 |
|---|---|
| 主会话用户拒绝回传语义化反馈（含理由/无理由两 Scenario） | ✓ |
| 策略自动拦截回传语义化反馈 | ✓ |
| subagent 工具拒绝回传区分于主会话 | ✓ |
| IM 权限卡常驻选填理由输入框 | ✓ |
| 允许类决策忽略理由框 | ✓ |

**全局测试**: `pytest -m "not e2e"` → 2998 passed, 1 skipped（与本 unit 无关）。

---

## Correctness

### Requirement: 主会话用户拒绝回传语义化反馈

| Scenario | 实现（file:line） | 测试 | 状态 |
|---|---|---|---|
| 用户直接拒绝、未填理由 | `tool_executor.py:247-254` (`build_reject_message(approval="user_deny", reason="")`) | `test_streaming_tool_executor.py::test_user_deny_without_reason_yields_reject_message` | covered |
| 用户拒绝并填写了理由 | `tool_executor.py:237-252`（提取 `details["reason"]`，喂入 `build_reject_message`）| `test_streaming_tool_executor.py::test_user_deny_with_reason_yields_with_reason_prefix` | covered |

### Requirement: 策略自动拦截回传语义化反馈

| Scenario | 实现（file:line） | 测试 | 状态 |
|---|---|---|---|
| 安全策略/分类器自动拦下工具调用 | `tool_executor.py:247-254` (`approval=None` 路径 → `auto_reject_message(reason)`) | `test_streaming_tool_executor.py::test_auto_block_yields_auto_reject_message` | covered |

### Requirement: subagent 工具拒绝回传区分于主会话

| Scenario | 实现（file:line） | 测试 | 状态 |
|---|---|---|---|
| subagent 非白名单工具（synthetic error 路径） | `tool_executor.py:157-174` (`build_reject_message(approval=None, reason=None, is_subagent=True)`) | `test_streaming_tool_executor.py::test_non_allowlisted_tool_yields_subagent_reject_message` | covered |
| subagent 白名单内工具被 gate ToolError 拒（row 1b） | `tool_executor.py:248-252` (`is_subagent=self._tool_execution_allowlist is not None`) | 无 tool_executor 集成测试（仅 `test_reject_messages.py::test_subagent_takes_precedence` 覆盖 helper 层） | **WARNING** |

### Requirement: IM 权限卡常驻选填理由输入框

| Scenario | 实现（file:line） | 测试 | 状态 |
|---|---|---|---|
| 待决权限卡展示理由输入框 | `permission-card.tsx:165-174`（`<textarea data-testid="permission-reason-input">`） | `permission-card.test.tsx`（"renders a persistent optional reason input"） | covered |
| 用户拒绝并填理由 — deny POST 带 reason | `permission-card.tsx:103-104`（`trimmedReason ? { reason: trimmedReason } : {}`） | `permission-card.test.tsx`（"includes the typed reason in the POST body when denying"） | covered |
| 理由框为空可正常做任意决策 | `permission-card.tsx:103-104`（trimmed 空不带 reason 键） | `permission-card.test.tsx`（"omits reason from the POST body when the input is left empty"） | covered |
| 选允许类决策忽略理由框 | 后端 allow 路径不进 reject 文本构造，`response.reason` 无消费 | `permission-card.test.tsx`（"still resolves an allow decision even with reason text present"） | covered |

### build_reject_message 选择表四行映射

| Row | is_subagent | approval | reason | 返回 | 测试 |
|---|---|---|---|---|---|
| 1a | True | None | None（synthetic error） | SUBAGENT_REJECT_MESSAGE | `test_subagent_takes_precedence` + `test_non_allowlisted_tool_yields_subagent_reject_message` |
| 1b | True | user_deny\|None | any（gate ToolError 在 subagent 里） | SUBAGENT_REJECT_MESSAGE | 仅 `test_subagent_takes_precedence(approval="user_deny", reason="x", is_subagent=True)` 覆盖 helper 层；**无 tool_executor 集成测试** |
| 2 | False | user_deny | 非空 | REJECT_WITH_REASON_PREFIX + reason | `test_user_deny_with_reason_yields_with_reason_prefix` |
| 3 | False | user_deny | 空/None | REJECT_MESSAGE | `test_user_deny_without_reason_yields_reject_message` |
| 4 | False | None | any | auto_reject_message(reason) | `test_auto_block_yields_auto_reject_message` |

### CC 文本本地化三点

| 本地化点 | 实现 | 测试断言 | 状态 |
|---|---|---|---|
| `new_string` → `newText` | `reject_messages.py:31,38,46` | `test_new_string_is_localized_to_newText` | ✓ |
| 无 settings/Bash(...) 规则尾句 | `auto_reject_message` 只含 `_AUTO_REJECT_PREFIX + reason + DENIAL_WORKAROUND_GUIDANCE`，无附加句 | `test_auto_reject_has_no_settings_rule_hint` | ✓ |
| 不实现 DONT_ASK 变体 | 未实现，module docstring 显式标注 (`reject_messages.py:17`) | — | ✓ |
| 不实现 SUBAGENT_WITH_REASON 变体 | 未实现，docstring 标注死路径（`reject_messages.py:23-25`） | — | ✓ |

---

## Coherence

### Decision 1：拒绝文本统一在 tool_executor 构造，subagent 两路径合并为 SUBAGENT_REJECT

**遵守**。

- 非白名单 synthetic error：`tool_executor.py:162-170` 调 `build_reject_message(approval=None, reason=None, is_subagent=True)`。
- ToolError catch 分支：`tool_executor.py:247-252` 调 `build_reject_message(..., is_subagent=self._tool_execution_allowlist is not None)`。
- `loop._serialize_tool_result_content` 未改，原样透传 `result.error`（未引入新挂字段）。

### Decision 2：reject_messages.py 落 core，CC 文本逐字照搬 + 私有名词本地化

**遵守**。

- `src/agent/core/agent/reject_messages.py` 新建；无任何 product 包（coding_cli / personal_assistant / IM）import 它，架构边界清洁。
- 常量主体逐字 CC（`REJECT_MESSAGE`/`REJECT_MESSAGE_WITH_REASON_PREFIX`/`SUBAGENT_REJECT_MESSAGE`/`DENIAL_WORKAROUND_GUIDANCE` 均有逐字测试断言）。
- `auto_reject_message` 合并为单一带 reason 模板（无 CC 的无理由分支），设计决策描述与实现一致。

### Decision 3：IM 拒绝理由只补两端，复用既有 reason 全链路

**遵守**。

- 改动仅 4 处（设计声明的收敛点）：
  1. `permission-card.tsx` 加理由框 + POST 带 reason。
  2. `messages.py:422`（`SubmitPermissionDecisionRequest.reason`）。
  3. `gateway_handler.py:283-310`（`push_permission_response` 加 reason 参数 + frame payload）。
  4. `tool_executor.py:237-241`（提取 `details["reason"]` 喂 `build_reject_message`）。
- `PermissionResponse.reason` / `kernel.submit_permission_decision(reason=)` / PA handler `body.get("reason")` / gate `response.reason` 既有字段全程复用，无新增并行字段。

### 架构自洽性

- `reject_messages.py` 纯 `core` 模块，无反向依赖 `platform`。
- IM 不调用 `agent`，reason 通过 WS 帧透传，无跨进程直接文件访问。
- `personal_assistant` / `coding_cli` 不 import `agent.core` 内部。
- `tests/contract/` 全通过（2998 passed 含 contract tests）。

---

## Issues

### WARNING

**W1 — subagent ToolError 路径（row 1b）缺 tool_executor 集成测试**

- 背景：`build_reject_message` 选择表 row 1b 是「subagent 上下文（allowlist active）+ 白名单内工具被 gate ToolError 拒」→ SUBAGENT_REJECT。此路径经 `tool_executor.py:248-252` 处理（`is_subagent = self._tool_execution_allowlist is not None = True`），逻辑正确，但无对应 `test_streaming_tool_executor.py` 集成测试。
- 影响：helper 层 `test_subagent_takes_precedence(approval="user_deny", reason="x", is_subagent=True)` 确认了 helper 正确；但若 tool_executor 的 `is_subagent` 信号提取逻辑将来被错改，当前测试套件不会捕捉到。
- 修复：在 `tests/unit/test_streaming_tool_executor.py` 行 638 之后加一个测试：

  ```python
  @pytest.mark.asyncio
  async def test_gate_denied_allowlisted_tool_in_subagent_yields_subagent_reject() -> None:
      """An allowlisted tool whose registry.execute() raises ToolError(blocked_by_hook)
      inside a subagent context → SUBAGENT_REJECT_MESSAGE (row 1b of design table)."""
      from agent.core.agent.reject_messages import SUBAGENT_REJECT_MESSAGE

      registry = _BlockingRegistry(
          {"blocked_by_hook": True, "reason": "fail-closed", "reason_code": "denied", "approval": None}
      )
      registry.register(_FakeTool(name="edit"))
      # edit IS in allowlist, so it passes _is_execution_denied; ToolError comes from registry
      executor = StreamingToolExecutor(registry, tool_execution_allowlist=("edit",))

      executor.add_tool(_call("edit"))
      results = await _drain(executor)

      assert len(results) == 1
      assert results[0].error == SUBAGENT_REJECT_MESSAGE
  ```

---

### SUGGESTION

**S1 — 前端允许类测试未断言 POST body 内容**

- `permission-card.test.tsx:463` 的 "still resolves an allow decision even with reason text present" 只验证 `onResolved` 被调，未断言 POST body 内容（允许决策实际携带了 reason 字段到后端，后端忽略）。
- spec Scenario"允许类决策忽略理由框"只要求"不产生可观察影响"，当前测试已充分覆盖可观察行为。但测试名描述的是"backend ignores it"，读者无法从测试本身确认 POST body 的实际内容。
- 可选改进：在该测试中追加断言，验证 POST body 或仅断言 `onResolved` 被调用（现状），均合理。低优先级。

**S2 — `auto_reject_message("")` 产生 "Reason: . " 文本**

- `tool_executor.py:254`：`auto_reject_message(reason or "")` 在 reason 为 None/空时输出 `"Permission for this action has been denied. Reason: . " + DENIAL_WORKAROUND_GUIDANCE`。
- 设计声明"本项目所有 auto block 都携带 reason 串"，该边界情况被认为不可达，但无防御性处理。
- 可选改进：`tool_executor.py:254` 改为 `auto_reject_message(block_reason or "policy block")` 或在 `auto_reject_message` 内加 `if not reason: return "Permission for this action has been denied. " + DENIAL_WORKAROUND_GUIDANCE`，避免 "Reason: ." 泄漏。

---

No critical issues. 1 warning, 2 suggestions. Ready for PR (with noted improvements).

---

# Round 2 — feat-440-M2 fix 复验

> M2 commits: 56744242..a37a7f3d（经合并 20a4c835 收入 unit/feat-440）

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 6/7 tasks checked（见下注）；全测试树实际通过 |
| Correctness | Round 1 W1/S1/S2 全部关闭 |
| Coherence | F6 解耦架构自洽 |

**3006 passed, 1 skipped**（pytest -m "not e2e"）；前端 vitest **490 passed**（60 files）。

> 注：tasks.md 末项 `- [ ] 全测试树 -m "not e2e" + 前端 vitest 全绿` 未勾选（记账疏漏），
> 测试实际全绿。无功能缺陷，仅需后续 tasks.md 补勾。

---

## F1 — gate deny reason 改 `or ""`（design Row 3 可达性修复）

**状态：CLOSED**

- 实现：`auto_mode_gate.py`（F1 修后），deny 分支 `"reason": response.reason or ""`，去除 `"user denied"` 占位串。
- 测试：`test_auto_mode_gate_hook.py::TestHandleAskApprovalSignal::test_deny_without_reason_yields_empty_reason` 经真 `_handle_ask`（mock permission channel 返回 deny + reason=""）断言 `result.get("reason") == ""`（显式堵 "user denied" 占位），并验 `approval == "user_deny"`。
- design §选择表 Row 3（bare user_deny → REJECT_MESSAGE）现实路径成立。

---

## F2 — auto_reject_message 空 reason guard（关闭 Round 1 S2）

**状态：CLOSED**

- 实现：`reject_messages.py`，`_AUTO_REJECT_PREFIX` 拆分为 `_AUTO_REJECT_DENIED` + `reason_clause = f"Reason: {reason}. " if reason else ""`；`auto_reject_message` 返回 `f"{_AUTO_REJECT_DENIED}{reason_clause}{DENIAL_WORKAROUND_GUIDANCE}"`。
- 测试：`test_reject_messages.py::TestAutoRejectMessage::test_auto_reject_empty_reason_omits_reason_clause` 断言 `"Reason:" not in msg`；`test_auto_reject_when_no_approval_empty_reason` 经 `build_reject_message(approval=None, reason="", is_subagent=False)` 同断言。

---

## F3 — IM 后端 strip reason、纯空白归一化为 None（关闭 Round 1 S1）

**状态：CLOSED**

- 实现：`messages.py:submit_permission_decision`，`normalized_reason = payload.reason.strip() if payload.reason is not None else None`，`reason=normalized_reason or None`。
- 测试：
  - `test_permission_streaming.py::test_submit_deny_whitespace_only_reason_normalized_to_none`：POST reason="   " → `push_permission_response` 收到 `reason is None`。
  - `test_submit_deny_reason_is_stripped`：POST reason="  先别动  " → `reason == "先别动"`。
- 两用例均通过 TestClient 真发请求，非 mock 输入断言。

---

## F4 — 前端仅 deny 决策带 reason（design Q4）

**状态：CLOSED**

- 实现：`permission-card.tsx`，`carriesReason = option.id === "deny" && trimmedReason.length > 0`；POST body spread 改为 `...(carriesReason ? { reason: trimmedReason } : {})`。Allow 类恒不带 reason，失败 deny 后 reason state 残留但被 decision 守卫拦截。
- 测试（permission-card.test.tsx）：
  - `"omits reason from an allow decision even with reason text present"` — 断言 allow POST body `"reason" in body === false`。
  - `"does not carry a stale reason onto a later allow after a failed deny"` — deny 失败后 allow 的 POST body 无 reason 键。
- Round 1 S1（仅断言 `onResolved` 未验 body）因测试改名 + 追加 body 断言而关闭。

---

## F5 — subagent 白名单内工具被 gate 拒集成测试（关闭 Round 1 W1）

**状态：CLOSED**

- 新增测试：`test_streaming_tool_executor.py::test_subagent_allowlisted_tool_gate_blocked_yields_subagent_reject`：`_BlockingRegistry(approval="user_deny")` + `tool_execution_allowlist=("edit",)` + `is_fork_sidechain=True`，edit 白名单内 → 进 `registry.execute` → gate ToolError → 断言 `results[0].error == SUBAGENT_REJECT_MESSAGE`，`reason_code == "denied"`。
- 覆盖 design 选择表 row 1b（白名单内工具被 gate 拒也落 SUBAGENT），Round 1 W1 路径完整锁定回归。

---

## F6 — is_subagent 改用显式 is_fork_sidechain 信号，与 allowlist 解耦

**状态：CLOSED**

- 实现三点：
  1. `context_fork.py`：fork 构造点显式传 `is_fork_sidechain=True` 进 `loop.run`。
  2. `loop.py`：新增 `is_fork_sidechain: bool = False` 参数，透传给 `StreamingToolExecutor`。
  3. `tool_executor.py`：`_is_fork_sidechain` 独立字段；两处 `build_reject_message(is_subagent=...)` 改用 `self._is_fork_sidechain`，与 `_tool_execution_allowlist` 解耦。
- 主会话默认 `is_fork_sidechain=False`，fork 是唯一显式 True 的构造点，allowlist 回归纯执行裁决职责。
- 测试：
  - `test_main_session_with_allowlist_user_deny_stays_main_reject`：allowlist active 但 `is_fork_sidechain=False` → `REJECT_MESSAGE`（非 SUBAGENT），验证主会话不受 allowlist 污染。
  - `test_fork_sidechain_flag_drives_subagent_reject_without_allowlist`：仅 `is_fork_sidechain=True`（无 allowlist）→ `SUBAGENT_REJECT_MESSAGE`，验证 fork flag 独立驱动。
  - 两用例均通过，解耦正确，主会话默认 False，loop 透传无误。

---

## Round 2 Issues

无新增问题。Round 1 全部遗留（W1/S1/S2）已关闭。

---

All Round 2 checks passed. Ready for PR.

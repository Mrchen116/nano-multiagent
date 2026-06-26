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

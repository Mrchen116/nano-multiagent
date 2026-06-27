# feat-440-M2 — Progress

> 启动报信（§2.5）: 已读 spec + design（三决策 + 选择表 + 决策 2/3）+ M1 progress + 7 改动文件 + 现有测试。基线绿（reject_messages/streaming_tool_executor/auto_mode_gate_hook/gateway_handler 90 passed）。范围与 design M2 行一致，无意图歧义。F6 解耦方案已与 team-lead 同步。开始按 R1-R6 实施。

### R1 — F1: bare-deny 走错模板（CRITICAL）

- Context: gate `_handle_ask` 的 deny 分支 `response.reason or "user denied"` 把空理由伪造成 "user denied"，使 build_reject_message reason 永不为空，design §选择表 Row 3（user_deny + 空 reason → REJECT_MESSAGE）事实不可达，LLM 收到 `...the user said:\nuser denied` 而非简洁 REJECT_MESSAGE。M1 测试盲点：`test_user_deny_without_reason_yields_reject_message` 直接往 `_BlockingRegistry` 注入 details["reason"]=""，绕过 gate 兜底，单测绿但真实路径错。
- Decision: gate deny 分支改 `response.reason or ""`（保持 str，下游 `details.get("reason")` + isinstance(str) 守卫依赖 str，不用 None）。补 gate 层测试 `test_deny_without_reason_yields_empty_reason`：经真 `_handle_ask`（mock request_permission 返回 deny + reason=""）断言 payload["reason"] == ""（非 "user denied"），堵 reason="" 直注盲点。
- Rationale: 根因在 gate 占位串，治本在 gate；选择表 Row 3 因此真实可达。
- Evidence:
  - Tests: `pytest tests/unit/test_auto_mode_gate_hook.py` → 20 passed（含新增 gate 层测试，红→绿）。
  - Entry: gate 层真实路径（`_handle_ask` 经 mock permission channel）；端到端真栈拒后 LLM 行为归 reviewer 轨。
  - Frontend/Browser/E2E/Visual: N/A
- Rollback: revert R1 C2（gate 改回占位串即恢复旧错误行为）。
- Commits: C1=test 红测, C2=fix, C3=本提交。ruff 通过。

### R2 — F2: auto_reject_message 空 reason guard（verifier S2）

- Context: `auto_reject_message(reason)` 用 `f"...Reason: {reason}. ..."`，reason 为空时产出语法损坏 `Reason: . IMPORTANT...`。build_reject_message row 4 在 reason 空时也会触发（`auto_reject_message(reason or "")`）。
- Decision: reason 为空时省略 `Reason: <r>. ` 子句，只保留 `Permission for this action has been denied. ` + DENIAL_WORKAROUND_GUIDANCE；`reason_clause = f"Reason: {reason}. " if reason else ""`。补单测 `test_auto_reject_empty_reason_omits_reason_clause` + `test_auto_reject_when_no_approval_empty_reason`。
- Rationale: 空 reason 的自动拒文本仍须语法正确；治本在 helper 文本构造。
- Evidence:
  - Tests: `pytest tests/unit/test_reject_messages.py` → 13 passed（红→绿）。
  - Entry/Frontend/Browser/E2E/Visual: N/A（纯逻辑 helper）。
- Rollback: revert R2 C2。
- Commits: C1=test, C2=fix, C3=本提交。ruff 通过。

### R3 — F6: is_subagent 与 tool_execution_allowlist 解耦（altitude）

- Context: tool_executor 用 `self._tool_execution_allowlist is not None` 推断 is_subagent — 实现偶合：将来主会话若引入 sandbox allowlist，主会话用户 Deny 会被误判 is_subagent=True、收到 SUBAGENT_REJECT（语义反转）。
- Decision: 给 StreamingToolExecutor 加显式 `is_fork_sidechain: bool=False`，经 `loop.run(is_fork_sidechain=)` → `context_fork.execute` 在 fork 构造点显式传 True；两处 build_reject_message 的 is_subagent 改用 `self._is_fork_sidechain`；`_is_execution_denied` 仍用 allowlist 保留执行裁决职责（两职责解耦）。主会话默认 False。
- Rationale: 单一调用链（context_fork→loop.run→executor），fork 是唯一显式 True 的点。allowlist 回归纯执行裁决，reject 措辞由独立 fork 信号驱动。M1 的 `test_non_allowlisted_tool_yields_subagent_reject_message` 依赖旧偶合，更新为显式传 is_fork_sidechain=True（fork 构造点现实）。
- Evidence:
  - Tests: `pytest tests/unit/test_streaming_tool_executor.py` → 22 passed；新增 `test_main_session_with_allowlist_user_deny_stays_main_reject`（allowlist 但非 fork → REJECT 主会话）+ `test_fork_sidechain_flag_drives_subagent_reject_without_allowlist`（显式 flag 单独驱动 SUBAGENT）。`pytest -k "context_fork or loop"` 69 passed（无调用点回归）。
  - Entry/Frontend/Browser/E2E/Visual: N/A（内核逻辑）。
- Rollback: revert R3 C2（三文件 + 测试一起）。
- Commits: C1=test, C2=refactor, C3=本提交。ruff 通过。

### R4 — F5: subagent 白名单内工具被 gate 拒集成测试（verifier W1）

- Context: M1 只测了非白名单 synthetic-error 分支（不进 registry），漏测「白名单内工具被 gate（hook block）拒」的 ToolError catch 分支（row 1b）。
- Decision: 补 `test_subagent_allowlisted_tool_gate_blocked_yields_subagent_reject`：`_BlockingRegistry` + `tool_execution_allowlist=("edit",)` + `is_fork_sidechain=True`，edit 在白名单 → 进 registry.execute → 抛 gate ToolError → row 1 SUBAGENT_REJECT（断言文本 + reason_code 徽标仍透传）。该路径在 F6 后即正确，本测试锁定回归。
- Rationale: 覆盖 design 选择表 row 1b（白名单内工具被 gate 拒也落 SUBAGENT）；此前无测试守护。
- Evidence:
  - Tests: 该用例 passed（覆盖 catch 分支 is_fork_sidechain → SUBAGENT）。
  - Entry/Frontend/Browser/E2E/Visual: N/A。
- Rollback: revert R4（仅测试）。
- Commits: 单 commit（test，覆盖性，§FL ② 轻量化：自包含覆盖测试，behavior 已由 R3 实现保证正确）。

### R5 — F3: IM 后端 reason 空白裁剪（verifier S1）

- Context: 非前端/直连 API 发 reason="   "（纯空白）会原样透传进 LLM 文本（gateway_handler 的 `reason or ""` 视空白为真值，保留）。
- Decision: 在 HTTP 边界 `submit_permission_decision` 端点 strip：`normalized_reason = payload.reason.strip() if not None`，`reason=normalized_reason or None`（strip 后空视作未提供 → None）。补 `test_submit_deny_whitespace_only_reason_normalized_to_none` + `test_submit_deny_reason_is_stripped`。
- Rationale: HTTP 边界是不可信输入入口，治本在边界裁剪；前端虽已 trim，后端不能信任。
- Evidence:
  - Tests: `pytest tests/unit/IM/test_permission_streaming.py` → 17 passed（红→绿，TestClient 真发 POST 断言 push_permission_response 收到的 reason）。
  - Entry: HTTP TestClient 真请求。Frontend/Browser/E2E/Visual: N/A（后端）。
- Rollback: revert R5 C2。
- Commits: C1=test, C2=fix, C3=本提交。ruff 通过。

### R6 — F4: 前端仅 deny 决策带 reason（verifier S1 + 前端缺口）

- Context: M1 任何决策只要理由框非空就带 reason。spec Q4 要求允许类忽略理由框；且失败的 deny 后 reason state 残留，会被后续 allow 误带。
- Decision: `handleChoice` 加 `carriesReason = option.id === "deny" && trimmedReason.length > 0` 守卫，仅 deny 且非空时带 reason；allow 类决策恒不带，失败 deny 后再 allow 也不带（reason state 残留但 decision 守卫拦住）。前端测试断言 deny POST body 含 reason、allow POST body 不含、失败后 allow 不含。
- Rationale: reason 语义属 deny；根因在「不分决策类型一律带」，治本在按 decision 门控。
- Evidence:
  - Tests: `npx vitest run permission-card.test.tsx` → 21 passed（红→绿；含 allow 不带 reason + 失败 deny 后 allow 不带）。`npm run build`（tsc+vite）通过无类型错误。
  - Frontend State Matrix: default（deny 带/allow 不带）✓ / error（失败 deny 后 allow 不带）✓ / submitting（既有 disabled 不回归）✓；其余沿用 M1 已验收布局 N/A。
  - Browser QA: 真实浏览器（playwright-cli 隔离实例，因 gstack browse daemon 被并发会话占用 §0.11）。真 vite dev 挂载真实 PermissionCard + 记录 POST body 的 fetchFn。观察：①卡片渲染正常（reason textbox + 4 按钮）；②键入「先别动」点 Deny → `POST[0] {decision:deny, reason:"先别动"}`；③理由框填「should be ignored」点 Allow once → `POST[1] {decision:allow_once}`（无 reason key）。console 仅 favicon.ico 404（无关），无卡片相关 error。截图 scratchpad/feat440-m2-card-browser.png。
  - E2E/Regression: 组件测试落库回归；端到端真栈走查归 reviewer 轨。
  - Visual/Interaction: 见截图，布局与 M1 验收一致（本 fix 不改视觉）。
- Rollback: revert R6 C2。临时 harness（_feat440m2_harness.tsx/.html）验收后已删除，未入库。
- Commits: C1=test, C2=fix, C3=本提交。

## 收尾

- 全测试树 `-m "not e2e"` + 前端 vitest 全绿证据见末次 push 前 commit。
- §0.10 浏览器验收：F4 经 playwright-cli 隔离实例真栈验证（gstack browse daemon 被并发会话长时间占用，§0.11 不抢占他会话 daemon，改用隔离 playwright）。

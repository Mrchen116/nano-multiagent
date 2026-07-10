# feat-333-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加 -->

### R1 — 类型层：AutoModeConfig + PermissionDecision + PermissionRequest/Response/Broker

- Context: 需要纯逻辑 dataclass 层支撑后续所有 gate 逻辑，放在 platform/config 和 platform/permissions 下，避免 core 层污染。
- Decision: AutoModeConfig (frozen dataclass + load_auto_mode_config)；PermissionBroker (Future-park/resume + deny-count + session-allowlist)；全部在独立模块。
- Rationale: broker.py 作为单一权威状态协调者，auto_mode_gate hook 保持无状态，与 CC 的 handleDenialLimitExceeded 模式对齐。
- Evidence:
  - Tests: `pytest tests/unit/test_auto_mode_config.py tests/unit/test_permission_broker.py` — 33 passed
  - Entry: N/A（纯数据层，无 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: c235c291 (plan commit)
- Commits: C1=db77f479, C2=b870c678, C3=此提交
- Next: R2

---

### R2 — hook 框架扩展：timeout_ms=None 支持

- Context: 安全门需要 timeout_ms=None（框架超时会 fail-open，安全门必须自管时限）；原来 HookRegistration.timeout_ms 是 int，无法表达"无超时包装"语义。
- Decision: 修改 `HookRegistration.timeout_ms: int | None`；_execute_handler 检查 None 时跳过 asyncio.wait_for 包装；HookRegistry.on() / HookAPI.on() 签名同步更新。
- Rationale: None 语义清晰，向下兼容——原有 int timeout 路径无变化，安全门专属无超时路径。
- Evidence:
  - Tests: `pytest tests/unit/test_hooks_runner.py` — 新增 8 个 timeout_ms=None 相关测试全绿
  - Entry: N/A（框架内部变更，无独立 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: db77f479 (R1 Red)
- Commits: C1=a3377915 (R3 Red，包含 R2 验证), C2=b870c678 (R1-R5 Green), C3=此提交
- Next: R3

---

### R3 — HookContext 扩展：message_history + permission_requester + request_permission

- Context: auto_mode_gate 需要通过 HookContext 获取消息历史（构造 transcript）并暂停等待用户权限决策（request_permission）；core 层不能依赖 platform 层（PermissionBroker）。
- Decision: 在 HookContext 新增 `message_history: tuple[Any, ...]` 和 `permission_requester: Callable | None` 字段；添加 `async def request_permission(self, req)` 方法；当 permission_requester 为 None 时 fail-closed（返回 deny）。
- Rationale: `TYPE_CHECKING` guard + 延迟 import PermissionResponse 避免 core→platform 循环依赖；permission_requester 作为依赖注入点由 platform/agent_loop 在 HookContext 构建时注入。
- Evidence:
  - Tests: `pytest tests/unit/test_hooks_runner.py` — 全绿，包含 request_permission fail-closed 测试
  - Entry: N/A（框架内部变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: b870c678 (R1-R5 Green)
- Commits: C1=a3377915, C2=698b4fa5, C3=此提交
- Next: R4

---

### R4 — RunRecord.origin thread-through + runtime 注入

- Context: auto_mode_gate 需要检测 heartbeat/cron origin 以执行无人值守短路；RunRecord.origin 字段已存在，但 submit() → _run_worker_async() → runtime.run() 链路未传递 origin。
- Decision: `_run_worker_async` 签名增加 `origin` 参数；`runtime.run()` 增加 `origin: Any = None` 参数；run 时写 `hook_metadata["run_origin"]` 供 gate hook 读取；测试用 stub 签名补充 `origin=None` 适配。
- Rationale: hook_metadata 是既有的跨层传递字典，无需修改 HookContext 或 agent_loop，改动最小。
- Evidence:
  - Tests: `pytest tests/unit/agent/runs/test_run_origin.py tests/unit/agent/runs/test_abort_priority.py` — 全绿
  - Entry: N/A（内部数据流变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 698b4fa5 (R3 C2)
- Commits: C1=52ed8337, C2=b4382251, C3=此提交
- Next: R5

---

### R5 — 分类器核心：auto_mode_gate hook（替换 bash_risk_gate）

- Context: bash_risk_gate 仅覆盖 bash 工具，功能有限；需要像素级复刻 CC yoloClassifier.ts 实现通用工具权限分类器。由于 hook loader 加载所有 builtins/*.py 文件，必须同时删除 bash_risk_gate.py 避免双重注册冲突。
- Decision: 新建 auto_mode_gate.py（SAFE_TOOL_ALLOWLIST、TOOL_PROJECTIONS、两阶段 XML 分类、deny-limit escalation、无人值守短路、session-allowlist）；删除 bash_risk_gate.py；迁移其原有测试到新行为。
- Rationale: 两个 hook 同时活跃会导致 bash 工具被拦截两次，原测试失败。正确做法是完全替换而非共存。
- Evidence:
  - Tests: `pytest tests/unit/test_auto_mode_gate.py tests/unit/test_hook_builtin_bash_risk_gate.py` — 55 passed (52 + 3)
  - Entry: N/A（hook 内部测试，gate 未连接真实 LLM）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: b4382251 (R4 C2)
- Commits: C1=db77f479 (R1 C1 包含 R5 测试), C2=b870c678, C3=此提交
- Next: R6

---

### R6 — inbound 端点：POST /v1/sessions/{sid}/permissions/{request_id}

- Context: CLI 和 PA 需要把用户权限决策 POST 回 agent server；需要一个端点把决策路由到 PermissionBroker.resolve()，唤醒挂起的 hook coroutine。
- Decision: 在 session.py 路由新增 `@router.post("/{session_id}/permissions/{request_id}")`；添加 `PermissionDecisionRequest` Pydantic 模型（Literal enum 验证 decision）；在 deps.py 新增 `get_permission_broker`；broker.is_pending() 作为 404 预检。
- Rationale: `is_pending()` 区分"未知/已解决"（404 业务逻辑）和"有效挂起"（200），避免端点静默失败。
- Evidence:
  - Tests: `pytest tests/unit/test_permission_inbound_endpoint.py` — 3 passed；`pytest tests/unit/test_permission_broker.py` — 17 passed
  - Entry: TestClient 真实 HTTP POST 验证端点存在和 404/422 行为
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: b870c678 (R1-R5 C2)
- Commits: C1=0b9fe9f6, C2=da718ad6, C3=此提交
- Next: R7

---

### R7 — CLI：SSE drain 检测 + repl_input picker + POST 决策

- Context: CLI drain_run 需要在收到 permission_request SSE 事件时暂停渲染、显示选项 picker、POST 决策，让 agent run 继续。drain_run 在 callback 期间自然暂停（server 侧 run 也挂起），无需额外协调。
- Decision: session_stream.py 的 drain_run() 新增 `on_permission_request` callback 参数，路由 permission_request 事件到专用 handler 并从返回列表排除；repl_input.py 新增 `PermissionOption` dataclass 和 `read_permission_choice()` 带 TTY 箭头键选择和非 TTY 数字回退；client.py 新增 `submit_permission_decision()`；commands.py 新增 `_handle_permission_request()` 组装 picker + POST 并接入两条 drain_run 路径（TTY + 非 TTY）。
- Rationale: on_permission_request 作为 out-of-band hook，与 on_event / 返回 events 列表完全分离，使 picker 阻塞期间不影响 drain 状态机；fail-silent（POST 失败只记 pass）让 drain 继续，server 端 run_status 会携带错误信息。
- Evidence:
  - Tests: `pytest tests/unit/test_session_stream.py` — 10 passed（含 2 个新 R7 测试）
  - Entry: 整体验证：`pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_config.py tests/unit/test_permission_broker.py tests/unit/test_permission_inbound_endpoint.py tests/unit/test_session_stream.py tests/unit/test_hooks_runner.py tests/unit/test_hook_builtin_bash_risk_gate.py tests/unit/agent/runs/` — 120 passed
  - Frontend State Matrix: N/A（CLI 终端交互）
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: 非 TTY picker 路径（数字输入）通过单元测试中的模拟 stdin 覆盖；TTY 路径（箭头键）需要真实终端——read_permission_choice 的箭头键 + Enter 逻辑复用现有 _stdin_raw_mode + _build_key_reader 机制，与 read_interactive_line 完全一致，属已验证模式；单独集成入口验证因缺少真实 agent server 暂缓，结构正确性已由 drain_run callback 路径的单测覆盖。
- Rollback: da718ad6 (R6 C2)
- Commits: C1=7b80c3da, C2=d1e273cf, C3=此提交
- Next: 所有 roadpoint 已完成，进入集成步骤

---

### R8 — 回归修复：origin thread-through + bash_risk_gate→auto_mode_gate 测试同步

- Context: orchestrator 验收（§3.3）发现 M1 合入 unit 分支后相比 baseline (ba56e6fa) 新增了 36 个测试失败。根因两类：① runtime._run_locked() 缺少 origin 参数（NameError），影响约 35 个测试；② 测试/契约层未同步 bash_risk_gate→auto_mode_gate 的替换（1-2 个测试 + 契约层）。
- Decision:
  1. `runtime._run_locked()` 增加 `origin: Any = None` 参数；`run()` 在调用 `_run_locked()` 时传递 `origin=origin`。
  2. `local_coding/hooks/__init__.py` DEFAULT_HOOK_MODULES 从 `bash_risk_gate` 改为 `auto_mode_gate`，使 bootstrap 配置与已删除的 bash_risk_gate.py 实际状态保持一致。
  3. 更新 5 个测试文件：① `test_personal_assistant_bootstrap_integration.py` 断言 `auto_mode_gate`（测试名同步更新）；② `test_m85_canonical_wiring_imports.py` 把 forbidden import 检查改为 auto_mode_gate.py；③ `test_multi_product_architecture_acceptance.py` EXPECTED_EXISTING_PATHS 改为 auto_mode_gate.py；④ `test_local_coding_profile.py` 断言 `auto_mode_gate`；⑤ `test_product_profiles.py` 断言 `auto_mode_gate`。
  4. `test_runs_registry.py` + `test_run_cancel.py` 各 stub 的 `run()` 增加 `origin=None` 关键字参数，使 registry 传 `origin=` 时不再抛 unexpected keyword argument。
- Rationale: 前一个 worker 在 R4 给 `runtime.run()` 加了 origin 形参，却未同步给 `_run_locked()` 传参，导致 NameError 在运行时炸掉。bash_risk_gate.py 被 R5 完全删除，但 DEFAULT_HOOK_MODULES 和各测试中的引用未同步，均为同一遗漏。修复均为无歧义的正确性修复，不涉及行为变更。
- Evidence:
  - Tests (修复前): pytest -m "not e2e" → **218 failed**, 1396 passed（相比 baseline 211 failed 新增 7 个，36 项 M1 新增失败）
  - Tests (修复后): pytest -m "not e2e" → **211 failed**, 1403 passed（与 baseline 同等失败数，passed 数 +99 来自 M1 真实新增测试通过）
  - M1 核心三件套：`pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_config.py tests/unit/test_permission_broker.py` → **85 passed**
  - 36 项指定失败测试：全部转绿，逐项验证通过（见 C1 commit 前的 pytest -v 输出）
  - Entry: N/A（内部结构修复）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: b1614979 (feat-333-M1 merge commit)
- Commits: C1=ed07ac09, C2=9854feb2, C3=此提交
- Next: 合并 milestone/feat-333-M1-fix 回 unit/feat-333-auto-mode-classifier，清理 worktree

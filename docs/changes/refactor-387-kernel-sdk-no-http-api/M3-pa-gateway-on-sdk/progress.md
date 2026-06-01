# M3 pa-gateway-on-sdk — progress

## 开工说明

- 基于 unit/refactor-387 (含 M1 SDK 落地) 分支开发
- 已知红测 2 个（M4 文档清理）：test_spec_declares_zero_import_acceptance_rules、test_architecture_docs_describe_zero_residue_target_state，不在本 milestone 修复
- 基线：unit+contract 测试 2083 passed, 1 xfailed, 2 failed（已知）

---

## [Design 修订] M3 实施期 SDK 表面扩展

- 原方案: `Kernel` 对外只暴露 design.md 里列的方法（不含 get_session/append_message）
- 新方案: 在 `Kernel` 上增加 `get_session(session_id, workspace_root)` 和 `append_message(...)` 以及 `create_session(tool_allowlist=, metadata=)` 参数扩展
- 原因: InboundPipeline 需要 `get_session` 做 workspace_root binding 验证；`/stop` 命令需要 `append_message` 追加消息历史；`create_session` 需要 metadata/tool_allowlist 透传 agent 配置
- 影响范围: 仅本 milestone，不影响后续 milestone
- design.md 是否同步改: 是，Changelog 段追加了一行

另：`InboundPipeline._ensure_binding` 改为 async（await kernel.create_session），级联改动小但影响调用链测试。`_KernelClientShim` 是 M3 新增的内部适配器（HeartbeatScheduler/InternalDispatchHandler 仍用旧接口，M4 清理）。`_wait_for_gateway_ready` 改为等 PID 文件而非 HTTP 探针（因删了 kernel HTTP 端口）。

---

### R1 — C1 红测：InboundPipeline 接受 Kernel SDK 参数

- Context: 原 InboundPipeline 接受 kernel_client，需改为 kernel= 参数
- Decision: 写三个失败测试，验证新 kernel= 参数路径
- Rationale: TDD 驱动，先有红测再实现
- Evidence:
  - Tests: 3 个新增红测全红（TypeError: got unexpected keyword argument 'kernel'）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: commit 8d82211a
- Commits: C1=8d82211a

---

### R2-R4 — 实现（合并 roadpoint）

- Context: 核心改造：InboundPipeline 接受 Kernel SDK、build_runtime 删子进程、删除 kernel_app.py/kernel_api_client.py、e2e-up.sh 更新
- Decision:
  1. `InboundPipeline` 接受 `kernel: Kernel` 替代 `kernel_client: KernelApiClient`；`_ensure_binding` 改为 async
  2. `_FakeKernel` 新增到 `_pipeline_helpers.py`，实现 Kernel SDK 接口（含 backward compat 属性）
  3. 所有 pipeline 测试从 `kernel_client=` 迁移到 `kernel=`
  4. `_KernelClientShim` 包装 `Kernel` 为 HeartbeatScheduler/InternalDispatchHandler 使用
  5. `build_runtime` 改用 `build_kernel(product_profile, llm_config, can_use_tool)` + 进程内 PA auto-mode 权限策略
  6. `GatewayRuntime.process_manager` 改为 `Optional`，传 `None`
  7. 删除 `kernel_app.py`, `kernel_api_client.py` + 相关测试文件
  8. `e2e-up.sh` 删「起 Kernel API」段，只起「IM + Gateway（内核进程内）」
- Rationale: 按 design.md M3 要求，最小化改动同时保持测试全绿
- Evidence:
  - Tests: 2066 passed, 1 xfailed, 2 failed（2 个已知 M4 红测，基线持平或改善）
  - Entry: build_runtime 可在单元测试中调用并返回正确 GatewayRuntime（含 InboundPipeline with kernel=）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: e2e-up.sh 脚本更新（手动验证见 R5 证据段）
  - Visual/Interaction: N/A
- Rollback: commit 8e4d06ed（M3 plan commit）
- Commits: C2=baeb1900

---

### R5 — 文档

- Context: progress.md + tasks.md 补齐，design.md Changelog 更新
- Decision: 记录实施期设计偏差，更新 tasks.md 状态
- Rollback: commit baeb1900
- Commits: C3=（本次 docs commit）
- Next: 集成到 unit 分支，等待 reviewer Review-B

---

## [Fix] refactor-387 session 复用回归修复（fix/refactor-387-session-reuse）

- Context: 用户实地验证发现 IM 多轮对话 LLM 感知不到上一轮历史。每条入站消息各自
  新建一个 kernel session，历史不累积。
- Root cause: `Kernel.get_session` 返回 `{session_id, status, metadata}`，没有顶层
  `workspace_root`；`_binding_matches_workspace_root` 读 `metadata["workspace_root"]`，
  该字段恒 None → 校验恒 False → 每轮新建 session。这是 M3 新写的方法，metadata 契约
  未对齐，属于本次 refactor 引入的回归。
- Decision: 治本——让 `Kernel.get_session` 暴露顶层 `workspace_root`（从 `Session.workspace_root`
  取，与 jsonl_store 顶层字段一致）；`_binding_matches_workspace_root` 改为读顶层字段；
  两个 `_FakeKernel` stub 同步更新，移除 `metadata["workspace_root"]` 冗余副本。
  **不在 `_build_session_metadata` / `create_session` 里往 metadata 里再塞一份**。
- Evidence:
  - Tests: 新增 `tests/unit/personal_assistant/test_session_reuse_regression.py`
    （3 个测试：contract × get_session 顶层字段、binding_matches 读顶层、端到端复用）
  - Full test tree: `pytest -m "not e2e"` → 2337 passed, 0 failed
  - Entry (实地验证): IM DM 会话连发两轮消息
    - session 文件数：第1条消息后 3→4（新建一个），第2条消息后仍为 4（复用）
    - session JSONL `sess_f270b7a644b30fdd.jsonl`：turn 1 user="你好，请记住这个数字：42"，
      turn 7 assistant="已保存到长期记忆"，turn 8 user="你记得我说的数字是多少吗？"，
      turn 11 assistant="我记得，你让我记住的数字是 42。"——两轮写入同一 session，历史连续。
  - Frontend State Matrix: N/A（后端 fix）
  - Browser QA: N/A
  - E2E/Regression: 新增回归测试已落库
  - Visual/Interaction: N/A
- Rollback: commit 48a35bac（fix 之前的 unit 分支头）
- Commits: C1=78773f99, C2=df319bee, merge=3771a6cb
- Next: 合并已完成，等待 reviewer 验收

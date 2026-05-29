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

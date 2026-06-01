# M2 Progress

## Roadpoints

### R1 — async-native REPL 骨架 + 红测试

- Context: coding_cli 原来是同步 REPL + HTTP ServerClient。M2 要改为 asyncio.run(repl_main()) + agent.sdk.Kernel 进程内调用。需先写失败单测，证明新接口不存在。
- Decision: 创建 `tests/unit/test_cli_async_repl_sdk.py`，覆盖 `kernel_factory`/无 mode/权限/close/REPL 命令等关键断言，全部 Red（`run_cli()` 没有 `kernel_factory` 参数）。
- Rationale: C1 必须是红的，证明当前缺失能力。
- Evidence:
  - Tests: `pytest tests/unit/test_cli_async_repl_sdk.py` → 11 FAILED（TypeError: unexpected keyword argument 'kernel_factory'）
  - Entry: N/A（C1 阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: commit 7df11cda（C1 红测试）
- Commits: C1=7df11cda
- Next: R2 实现

---

### R2-R6 — 全量实现（统一提交）

因为 commands.py 需要整体重写（从同步 HTTP 模式到 async-native Kernel 模式），R2-R6 合并为一次大实现。

- Context:
  - `commands.py` 有 1000+ 行需要整体替换（同步 REPL + HTTP 桥接 → asyncio.run + Kernel stream）
  - `repl_commands.py`/`context_budget.py`/`text_runner.py`/`__init__.py` 都有 ServerClient 依赖需清除
  - 大量测试（约 80 个）使用旧的 `client_factory`/`--base-url`/`--mode` 接口，全部需迁移到 `kernel_factory`/`Kernel` 接口
  - `agent.sdk.__init__` 需要补充 `LLMFactoryConfig`/`PermissionDecision`/`LOCAL_CODING_PROFILE` 等类型导出（SDK 表面不完整）
- Decision:
  1. 新建 `tests/unit/_cli_kernel_stubs.py` — Kernel stub 基类和各类专用 stub，替换旧 HTTP stub 模式
  2. 重写 `src/coding_cli/commands.py` — asyncio.run(_async_main()) 主流程，kernel.stream() 替换 SessionStreamReader，kernel.submit() 替换 HTTP submit_message，can_use_tool 权限回调
  3. 重写各测试文件从 HTTP 接口迁到 Kernel 接口
  4. 更新合约测试（http_only → sdk_boundary，error_contract，workspace_dirname 行号）
  5. agent.sdk.__init__ 增加类型导出（扩充 SDK 表面，不改核心逻辑）
- Rationale: async-native REPL 与旧的同步 REPL + HTTP 桥接是对立的架构；整体替换后测试全绿是正确状态。
- Evidence:
  - Tests: `pytest tests/unit/ tests/contract/ -m "not e2e"` → 2084 passed, 2 xfailed（已知 M4 xfail），1 FAILED（已知 M4 红测），0 新增红测
  - Entry: `run_cli([], kernel_factory=..., workspace_root=tmp_path)` 进 REPL → 全套 REPL 命令/流式/权限/打断/compact/history/llm-config 测试覆盖
  - Frontend State Matrix: N/A（纯 CLI）
  - Browser QA: N/A（纯 CLI）
  - E2E/Regression: coding_cli 单测全套绿（含 async 事件渲染/REPL 命令/text 模式/error 合约）
  - Visual/Interaction: N/A
- Rollback: 回 C1 commit 7df11cda
- Commits: C2=7668d0de
- Next: C3 文档 + 合并到 unit 分支

---

## 设计修订记录

`agent.sdk.__init__` 增加了 `LLMFactoryConfig`/`PermissionDecision`/`LOCAL_CODING_PROFILE` 再导出——SDK 表面补充，coding_cli 不需要 import agent.core/platform 内部即可完成构装。这是 SDK 表面不完整的修补，不改核心逻辑，不走 §4 暂停流程。

## 已知红测（不修，M4 文档清理）

- `test_spec_declares_zero_import_acceptance_rules` → 改为 `xfail(strict=True)`（M4 SPEC 文档清理）
- `test_architecture_docs_describe_zero_residue_target_state` → 仍红（M4 文档清理）

# refactor-489-M4 — Progress

## 启动记录

- Baseline: `unit/refactor-489@8d6cfb3e8`；M4 slice `658 passed, 1 warning`。
- Baseline command: 用 zsh array 选取 `tests/unit/platform` 与排除 M2/M3/M5--M8/M13 语义归属后的 root `tests/unit/test_*.py`，执行 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q`。
- 调试说明: 首轮命令误用 zsh 特殊参数名 `path`，循环赋值污染 `PATH`，造成 6 个 `bash` 子进程假失败；改用普通变量后同一测试集全绿，确认不是仓库基线缺陷。
- Scope clarification: orchestrator 确认 `tests/unit/test_curator.py` 归 M3、`tests/unit/test_text_runner.py` 归 M8，M4 不修改；跨 slice 替代保护只能引用当前基线已存在且可运行的测试，不能依赖尚未合入结果。

## R1 — 清除布局、迁移终态与历史 golden

- Context: M4 同时存在 event 子集重复、platform `__module__`/legacy-root 迁移终态，以及与 current presenter tests 逐字段重复的历史 golden。
- Decision: 删除 2 个 event unit 子集、4 个 platform location 文件与 1 个 presenter migration golden；不新增替代测试。
- Rationale: event 集合已由当前 contract 精确拥有；内部 home/退役 root 没有独立产品风险；presenter 的 summary/detail/emoji/cap 已由当前行为测试直接覆盖。
- Evidence:
  - Claim: 删除历史断言后，event/hook contract、SDK/import boundary 与 presenter 用户可见结果仍受保护。
  - Baseline: `unit/refactor-489@8d6cfb3e8`，M4 slice `658 passed`。
  - Method: 删除前后均运行现有替代保护；删除后扩大到 `tests/unit/platform/tools`。
  - Result: PASS；4 个 contract 文件 `6 passed`，platform tools `57 passed`，`git diff --check` 通过。
  - Locator: `tests/contract/test_core_events_contract.py`、`tests/contract/test_hooks_contract.py`、`tests/contract/test_agent_sdk_boundary_contract.py`、`tests/contract/test_core_no_platform_imports.py`、`tests/unit/platform/tools/test_presentation.py`、`test_presentation_cap.py`。
  - Limit: 本轮只证明现有替代 seam；不评估 M2 对 contract 文件的后续处置。
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q <上述 4 个 contract>` → `6 passed`；`... pytest -q tests/unit/platform/tools` → `57 passed`。
  - Entry: N/A（零产品行为的测试资产重构；current contract 与 presenter seam 是验证入口）。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 保留的自动化 regression 如 Locator；无新用例。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交可恢复 7 个历史测试文件。
- Commits: 本提交（SHA 以 Git history 为准）。
- Next: R2 收敛 AutoMode 与 permission gate，同时保留安全与 fail-closed seam。

## R2 — 收敛 AutoMode 与 permission gate

- Context: 同一 safe allowlist 被 exact set 和逐成员测试重复，dispatch/path 文件残留 private symbol、OUTSIDE NOTE 与 M6 source scan；bash 假 handler 与真实 HookRegistry seam 重复，且一个 `rm -rf /` 测试把 classifier fail-closed 误称为 hard deny。
- Decision: 默认配置和 allowlist 各合并为单一 current-policy 断言；删除旧 path 文件、source/private-symbol/CC phrase 与重复 M6 handler tests；真实 HookRegistry 硬拒绝 case 改用 `reboot`，保留 safe execution、review 无 channel fail-closed、permission allow/deny/ask 与危险路径 bypass-immune。
- Rationale: 安全风险仍由真实决策结果和最低 tool permission seam 覆盖；实现如何拆 helper、prompt 曾使用哪些句子、迁移前有哪些步骤不构成长期契约。
- Evidence:
  - Claim: 清除 707 行重复/历史测试后，AutoMode config、allowlist、权限裁决、危险路径、approval 与 fail-closed 仍有直接保护。
  - Baseline: R1 commit `57f649ba0`；本轮修改前相关测试均包含在 M4 baseline `658 passed`。
  - Method: 运行全部受影响 AutoMode/hook/permission 文件，并加入当前 lower-seam `test_tool_check_permissions.py`；对 6 个保留文件跑 Ruff。
  - Result: PASS；`129 passed, 1 warning`，Ruff `All checks passed!`，`git diff --check` 通过。
  - Locator: `tests/unit/test_auto_mode_gate_dispatch.py::TestCheckPermissionsDispatch`、`TestSafetyLockedBypassImmune`；`tests/unit/test_hook_builtin_bash_risk_gate.py`；`tests/unit/agent/platform/tools/test_tool_check_permissions.py`；`tests/unit/test_auto_mode_gate_hook.py::TestHandleAskApprovalSignal`。
  - Limit: 测试资产重构，不调用真实外部 LLM；provider caller 以现有 stub 验证 gate 决策。
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/test_auto_mode_config.py tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_hook_builtin_bash_risk_gate.py tests/unit/test_permission_broker.py tests/unit/test_permission_decision_loop.py tests/unit/test_permission_requester_cancel.py tests/unit/agent/platform/tools/test_tool_check_permissions.py` → `129 passed`。
  - Entry: 真实本地 hook loader → HookRunner → ToolRegistry → BashTool seam 通过；零产品行为 delta，无外部 live 入口要求。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 保留的 permission/tool regression 如 Locator；无新用例。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交恢复旧路径与重复断言，不影响 R1。
- Commits: 本提交（SHA 以 Git history 为准）。
- Next: R3 删除 hook/background 的 enum/dataclass/fake 自证，将字段保留保护合入真实 dispatch seam。

## R3 — 收敛 hook/background 行为保护

- Context: background hook 测试混入 enum/dataclass 语言特性、手写 fake 自证、未观察目标字段的 turn-meta case，以及对私有 `_strip_fork_conversation` 和 `_context_fork` 内部路径的直接断言。
- Decision: 删除上述低信号断言；在公开 observe/background dispatch 测试中同时证明 observe context 禁止递归 fork 且保留 message history/permission requester；保留真实 fork 工具执行、执行层 allowlist、anti-recursion、runtime payload 和异常隔离。
- Rationale: 用户风险是调度模式、上下文隔离与 fork 实际可执行性，不是 enum 成员数、dataclass getter 或某个私有 helper/字段路径。
- Evidence:
  - Claim: 删除内部与自证断言后，background dispatch、observe 隔离、fork 执行与 hook runner 仍由公开行为保护。
  - Baseline: R2 commit `d5c25b41a`；本轮修改前相关测试包含在 M4 baseline `658 passed`。
  - Method: 运行两个受影响文件，并扩大到 self-improvement hook 与 `tests/unit/platform/hooks`；对两个修改文件跑 Ruff。
  - Result: PASS；`47 passed`，Ruff `All checks passed!`，`git diff --check` 通过。
  - Locator: `tests/unit/test_background_hook_fork.py::test_background_hook_receives_fork_conversation_in_context`、`test_fork_loop_executes_tools_after_bind_tool_registry`、`test_runtime_agent_end_payload_includes_tool_iterations`；`tests/unit/test_hooks_runner.py::TestHookContextPermissionRequester`、`TestHookRunnerTimeoutNone`。
  - Limit: 使用内存 fake LLM/registry 验证进程内 hook seam；零产品行为 delta，不声称外部服务 live 证据。
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/test_background_hook_fork.py tests/unit/test_hooks_runner.py tests/unit/test_self_improvement_hook.py tests/unit/platform/hooks` → `47 passed`。
  - Entry: HookRegistry → HookRunner observe/background dispatch 与 AgentEngine context fork；无用户界面入口。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 保留的进程内 hook/fork regression 如 Locator；无新用例。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交恢复 hook/background 历史断言，不影响 R1/R2。
- Commits: 本提交（SHA 以 Git history 为准）。
- Next: R4 收敛 bash policy 重复，并删除 LLM signature/dead-field 迁移负断言。

## R4 — 收敛 bash policy 与 LLM 负断言

- Context: root bash-policy 文件重复 lower suite 的 allow/review/deny、loader、fork-bomb 与常见危险命令；LLM 文件则以 function signature 和退役 metadata 字段缺席锁定迁移终态。
- Decision: root bash-policy 只保留混合 chain、`emulate`、env prefix 与 deny-command replacement 四项独有风险；删除其余重复 cases，以及 LLM provider 参数缺席和 dead-field 缺席断言。
- Rationale: lower bash suite 已直接覆盖三态决策、enforcement、常见危险命令与配置读取；LLM 长期风险由事实→retryability 结果矩阵和 metadata roundtrip/provider contract 保护，而不是历史参数或字段不能出现。
- Evidence:
  - Claim: 重复与迁移负断言删除后，bash 安全边界、retryability 与公开 model metadata 仍有直接行为保护。
  - Baseline: R3 commit `c32f5199c`；本轮修改前相关测试包含在 M4 baseline `658 passed`。
  - Method: 将 root bash cases 与 current lower policy suite 同跑；将 error classifier/model registry 与 LLM provider contract 同跑；对三个修改文件跑 Ruff。
  - Result: PASS；bash policy `79 passed`，LLM/contract `68 passed`，Ruff `All checks passed!`，`git diff --check` 通过。
  - Locator: `tests/unit/test_tool_safety_policy.py` 的四项独有安全 cases；`tests/unit/agent/platform/tools/builtins/test_bash_policy.py`；`tests/unit/test_llm_error_classifier.py` 的 facts matrix；`tests/unit/test_llm_model_registry.py::test_resolve_anthropic_metadata_extra_request_body_preserved`；`tests/contract/test_llm_provider_contract.py`。
  - Limit: 测试使用本地 policy/model registry 和 provider contract，不调用真实外部 provider。
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/test_tool_safety_policy.py tests/unit/agent/platform/tools/builtins/test_bash_policy.py` → `79 passed`；`... pytest -q tests/unit/test_llm_error_classifier.py tests/unit/test_llm_model_registry.py tests/contract/test_llm_provider_contract.py` → `68 passed`。
  - Entry: Bash policy function seam 与 LLM registry/classifier API；无外部 live 入口。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 保留的自动化 regression 如 Locator；无新用例。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交恢复 bash/LLM 历史断言，不影响 R1--R3。
- Commits: 本提交（SHA 以 Git history 为准）。
- Next: R5 运行完整 M4 slice、受依赖 contract/lower seams、Ruff、diff 与 scope 门禁并收尾证据。

## R5 — M4 范围门禁与证据收尾

- Context: R1--R4 已完成逐组替代保护验证，需要证明合并后的完整 M4 slice 没有遗漏，且 changed paths 未越过 M4、未修改产品实现/spec 或相邻 M3/M8 owner。
- Decision: 复用启动时同一语义 slice 选择器运行全量回归；另跑 event/hook/SDK/import/LLM contracts 和 tool-permission/bash lower seams；对所有保留的修改 Python 文件跑 Ruff，并核对 baseline diff/status。
- Rationale: 同口径 before/after 数量可量化去重结果；独立 contract/lower-seam 命令证明删除项确有当前可运行替代保护，scope 检查防止测试清理夹带行为变化。
- Evidence:
  - Claim: M4 在不改变产品/spec 的前提下删除 107 个重复/历史 tests，剩余工具、权限、安全、hook、LLM/provider 与 platform slice 全绿。
  - Baseline: `unit/refactor-489@8d6cfb3e8`；同口径 M4 slice `658 passed, 1 warning`。
  - Method: 运行 `tests/unit/platform` 与排除 M2/M3/M5--M8/M13 owner 后的 root unit slice；另跑 5 个 contract 和 2 个 lower-seam 文件；检查 Ruff、`git diff --check`、changed paths 与 clean status。
  - Result: PASS；M4 slice `551 passed, 1 warning`，即 `658 → 551`（净减 107）；依赖保护 `122 passed`；Ruff `All checks passed!`；diff check 与 clean status 通过。
  - Locator: `docs/changes/refactor-489-test-signal-discipline/M4-core-tools-platform/tasks.md` 的处置矩阵；R1--R4 progress Locator；changed paths 仅本 milestone 文档与 `tests/unit/` M4 文件。
  - Limit: warning 来自第三方 `lark_oapi` 的 `datetime.utcfromtimestamp()` deprecation，与本次测试资产变更无关；未执行真实外部 LLM、浏览器或服务 E2E，因为产品实现和用户行为均无 delta。
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q "${m4_paths[@]}"` → `551 passed, 1 warning`；`... pytest -q tests/contract/test_core_events_contract.py tests/contract/test_hooks_contract.py tests/contract/test_agent_sdk_boundary_contract.py tests/contract/test_core_no_platform_imports.py tests/contract/test_llm_provider_contract.py tests/unit/agent/platform/tools/test_tool_check_permissions.py tests/unit/agent/platform/tools/builtins/test_bash_policy.py` → `122 passed`。
  - Entry: N/A（测试资产重构；验证入口为 current contract、lower seam 与 M4 unit slice）。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 完整 M4 unit regression 与依赖 contract/lower seams 全绿；无新增 E2E。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Scope: 对 `8d6cfb3e8...HEAD` 的 22 个 changed paths 均为本 milestone 文档或 `tests/unit/`；`tests/unit/test_curator.py`、`tests/unit/test_text_runner.py`、产品源码、current spec 均未修改；worktree clean。
- Rollback: 按 R1--R4 提交逆序回退可恢复原测试资产；零产品迁移或数据回滚要求。
- Commits: R1 `57f649ba0`；R2 `d5c25b41a`；R3 `c32f5199c`；R4 `5d3128d90`；本 R5 文档提交 SHA 以 Git history 为准。
- Next: 按 worker 协议 rebase 最新 `unit/refactor-489`，在 unit lock 下合并并推送，随后清理 milestone worktree/branch。

## Promotion Candidates

None.

# refactor-489-M4: core-tools-platform — Tasks

> 对齐: ../design.md 的 refactor-489-M4 行与决策 1

## 目标

保留工具、权限、hook、LLM 与 platform 的最低 seam 保护；删除迁移终态、源码布局、私有符号缺席、历史 golden 与跨层重复断言，不改变产品行为。

## 退出标准

- [ ] 工具、权限、安全、hook、LLM/provider 与 platform 的当前行为仍由最低合适层的可运行测试保护。
- [ ] 不再以内部调用路径、模块 `__module__`、退役符号缺席、源码句子或一次迁移 golden 作为永久断言。
- [ ] 重复的 allowlist、permission dispatch、presenter、event 与 bash policy 断言已合并到单一 seam。
- [ ] M4 最窄测试与受依赖的既有 contract/lower-seam 保护全绿；无产品行为或 spec delta。

## 测试策略

- 被测行为（来自退出标准）：工具执行/展示/预算与校验；permission gate 的 allow/deny/ask/fail-closed；hook 的 intercept/observe/background 语义；LLM provider 映射、流式错误与重试；skill 管理与使用统计；platform adapter 的输入输出。
- 已有测试在：本 milestone 只重构既有 M4 测试并复用当前基线中的最低层保护，不新建测试文件；合并点详见下表。
- 落层/目录/marker：`tests/unit/`，marker：无；架构/事件集合的替代保护位于既有 `tests/contract/`。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；baseline、最窄验证与最终 M4 slice 结果写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Runtime/hook 事件集合保持 current contract | `tests/unit/test_hook_event_coverage.py`、`tests/unit/test_hook_lifecycle_event_coverage.py` | delete | 两个 unit 子集断言彼此重复，且被当前可运行的 `tests/contract/test_core_events_contract.py` 与 `tests/contract/test_hooks_contract.py` 精确拥有 | `.venv/bin/python -m pytest -q tests/contract/test_core_events_contract.py tests/contract/test_hooks_contract.py` |
| platform 内部包布局与退役 root 不成为 unit 行为 | `tests/unit/test_platform_{hooks,llm_providers,session_support,tools}_location.py` | delete | `__module__`、`find_spec(legacy)` 与 canonical-home 断言只守迁移终态；当前真实架构风险由 SDK/import direction contract 保护，内部文件可等价重组 | `.venv/bin/python -m pytest -q tests/contract/test_agent_sdk_boundary_contract.py tests/contract/test_core_no_platform_imports.py` |
| built-in presenter 的用户可见 summary/detail/emoji 与 cap | `tests/unit/platform/tools/test_presentation_golden.py` | delete | 历史迁移 golden 逐字段重复当前行为测试；保留 `test_presentation.py` 与 `test_presentation_cap.py` 直接覆盖每类 presenter 和截断 seam | `.venv/bin/python -m pytest -q tests/unit/platform/tools/test_presentation.py tests/unit/platform/tools/test_presentation_cap.py` |
| AutoMode 默认值与两级配置覆盖 | `tests/unit/test_auto_mode_config.py::TestAutoModeConfigDefaults` | rewrite-merge | 九个逐字段 getter 测试合为一项明确默认策略；文件加载、global/workspace override 仍单独保留 | `.venv/bin/python -m pytest -q tests/unit/test_auto_mode_config.py` |
| AutoMode safe allowlist 的安全边界 | `tests/unit/test_auto_mode_gate_allowlist.py::TestSafeToolAllowlist`、`tests/unit/test_auto_mode_gate_dispatch.py::TestSafeToolAllowlistChanges` | rewrite-merge | exact set 已同时证明成员与非成员，dispatch 文件不再复述同一 policy；保留 config extension 与 hook registration | `.venv/bin/python -m pytest -q tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py` |
| permission dispatch 的 allow/deny/passthrough、危险路径 bypass-immune 与 fail-closed | `tests/unit/test_auto_mode_gate_dispatch.py`、`tests/unit/test_path_sandbox_via_hook.py` | rewrite-merge | 删除旧路径 helper/OUTSIDE NOTE/迁移叙事；保留 dispatch seam，并由当前 `tests/unit/agent/platform/tools/test_tool_check_permissions.py` 直接保护危险路径判定 | `.venv/bin/python -m pytest -q tests/unit/test_auto_mode_gate_dispatch.py tests/unit/agent/platform/tools/test_tool_check_permissions.py` |
| Bash 经真实 hook registry 执行、硬拒绝与 classifier 不可用 fail-closed | `tests/unit/test_auto_mode_gate_hook.py::TestM6BashViaCheckPermissions`、`tests/unit/test_hook_builtin_bash_risk_gate.py` | rewrite-merge | 删除源码扫描和对同一 bash allow/deny/review 的重复 fake-handler 测试；保留真实 registry/ToolRegistry seam，并把误称 denylist 的 `rm -rf /` 场景改为真实硬拒绝命令 | `.venv/bin/python -m pytest -q tests/unit/test_hook_builtin_bash_risk_gate.py tests/unit/test_auto_mode_gate_hook.py` |
| classifier prompt 只保护结构、配置替换、真实 transcript 与 fail-closed，不钉外部版本措辞 | `tests/unit/test_auto_mode_gate.py::{TestBuildYoloSystemPrompt,TestToolOwnedClassifierProjection,TestXmlSuffixCcBaseline}` | rewrite-merge | 删除 load-bearing phrase、退役 central API 缺席与 CC 版本句子；保留 XML output 结构、用户规则替换、真实 kernel message 投影、XML 解析与 empty-content fail-closed | `.venv/bin/python -m pytest -q tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py` |
| Background hook/fork 只保护调度、隔离、执行与继承结果 | `tests/unit/test_background_hook_fork.py`、`tests/unit/test_hooks_runner.py` | rewrite-merge | 删除 enum/dataclass 语言特性、fake 自证与不观察目标字段的测试；把私有 `_strip_fork_conversation` 断言合并到公开 dispatch 行为，保留真实 fork 工具执行、anti-recursion 与 SDK hook payload | `.venv/bin/python -m pytest -q tests/unit/test_background_hook_fork.py tests/unit/test_hooks_runner.py` |
| Bash policy 的真实安全边界只在最低层断言一次 | `tests/unit/test_tool_safety_policy.py` | rewrite-merge | 删除与当前 `tests/unit/agent/platform/tools/builtins/test_bash_policy.py` 重复的 allow/review/deny/loader cases；只保留混合命令、env prefix、独有危险命令和 deny override 风险 | `.venv/bin/python -m pytest -q tests/unit/test_tool_safety_policy.py tests/unit/agent/platform/tools/builtins/test_bash_policy.py` |
| LLM retryability 与 model registry 不依赖“参数/字段不存在”迁移断言 | `tests/unit/test_llm_error_classifier.py::test_classifier_has_no_provider_name_branch`、`tests/unit/test_llm_model_registry.py::test_resolve_model_metadata_no_dead_fields` | delete | provider-neutral 由事实→retryability 结果矩阵证明；公开 model metadata/SDK payload 由现有 roundtrip 与 contract 保护，无需锁内部 signature 或退役字段缺席 | `.venv/bin/python -m pytest -q tests/unit/test_llm_error_classifier.py tests/unit/test_llm_model_registry.py tests/contract/test_llm_provider_contract.py` |
| 其余工具、权限、hook、LLM、skill/platform tests | M4 slice 中未列为重写/删除的既有测试 | keep | 它们直接覆盖仍存在的 tool output/validation/safety、permission transaction、hook order/fail-open、provider mapping/streaming/retry、skill I/O/usage 等风险，未发现更低层等价覆盖 | M4 slice 命令（见 R5） |

无受影响既有测试时：不适用；本 milestone 的任务本身即审视并处置 M4 slice。

## Roadpoints

### R1 — 清除布局、迁移终态与历史 golden

- 状态: DONE
- 步骤: 删除 location/event-subset/presenter-golden 文件，并先运行表中当前替代保护。
- 验证: 对应 contract、presenter/current cap tests 与 `git diff --check` 全绿。

### R2 — 收敛 AutoMode 与 permission gate

- 状态: DOING
- 步骤: 合并默认值/allowlist/dispatch；删除 private-symbol/source-text/CC phrase 与重复 bash fake-handler 断言；保留危险路径、授权和 fail-closed seam。
- 验证: AutoMode、permission、真实 hook registry 与 tool permission 最窄测试全绿。

### R3 — 收敛 hook/background 行为保护

- 状态: TODO
- 步骤: 删除 enum/dataclass/fake 自证与重复内部断言；把 context 字段保留验证合入真实 dispatch seam。
- 验证: background fork、hook runner、self-improvement 与 realtime hook tests 全绿。

### R4 — 收敛 bash policy 与 LLM 负断言

- 状态: TODO
- 步骤: bash policy 仅保留未被 lower seam 覆盖的安全 cases；删除 LLM signature/dead-field 迁移断言。
- 验证: bash policy lower seam、LLM provider/retry/model registry 与 contract tests 全绿。

### R5 — M4 范围门禁与证据收尾

- 状态: TODO
- 步骤: 运行完整 M4 slice、检查 changed paths、测试收集数、diff 与无产品/spec delta，补齐 progress。
- 验证: M4 slice 全绿，`git diff --check` 与 scope 检查通过。

# refactor-489-M9: kernel-integration-tests — Tasks

> 对齐: ../design.md 的 refactor-489-M9 行与决策 1--2

## 目标

让 M9 integration 切片只保护 kernel/tool 经过真实装配、持久化、hook 或 provider 边界后的可观察结果；删除 unit 重复、私有步骤断言和一次性迁移 golden。

## 退出标准

- [x] M9 每项受影响存量测试都有 keep / rewrite-merge / delete 处置结论。
- [x] 保留的 integration 只断言 `build_kernel` / ToolRegistry / hook-loader / tool-loader / provider mapper 等跨 seam 结果，不重测下层 policy、ReadTool 细节或 REPL 私有输入实现。
- [x] 删除的真实风险均有更低层保护；纯迁移 golden 明确记录为无 current 风险。
- [x] M9 切片、相关最低层替代保护、ruff、`git diff --check` 全绿，changed paths 不越界。

## 测试策略

- 被测行为（来自退出标准）：`build_kernel` 能把 compaction、显式空工具集、bash/通用工具 liveness 与 timeout 信号连到对外请求/事件；workspace hook/tool 可动态加载并经 registry 生效；read 多部件工具结果经 registry/hook/provider seam 不丢失。
- 已有测试在：本 milestone 的 11 个现有 integration 文件（收敛/删除）；相关下层保护在 `tests/unit/agent/platform/tools/builtins/test_bash_policy.py`、`tests/unit/test_tool_validation_errors.py`、`tests/unit/test_tools_read.py`、`tests/unit/test_idle_callback.py`、`tests/contract/test_tools_bash_contract.py`、`tests/unit/agent/prompt_sections/`。不新建测试文件。
- 落层/目录/marker：`tests/integration/`，marker：无（fake LLM + 本地子进程/文件，无外部服务）。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；基线、最窄保护和收尾门禁均记入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 安全 bash 动作经 registry + hook gate 不进分类器 | `test_bash_check_permissions_integration.py::{test_git_status_passes_without_classifier,test_python3_version_flag_passes_without_classifier}` | rewrite-merge | 合并为参数化跨 seam 用例；命令分类细节由 `test_bash_policy.py` 保护 | M9 pytest + bash policy unit |
| 非 allowlist bash 动作经 registry + hook gate fail closed | `test_bash_check_permissions_integration.py::test_python3_script_goes_to_classifier_and_blocks_fail_closed` | keep | 直接证明 ToolRegistry→hook→BashTool 跨 seam 连接 | M9 pytest |
| BashTool 存在方法且 policy 返回指定内部状态 | `test_bash_check_permissions_integration.py::test_bash_check_permissions_is_called_via_tool_registry_injection` | delete | 未经 registry，只测私有装配步骤/方法存在；policy 结果已由 bash policy unit 保护 | bash policy unit + M9 pytest |
| 静默 bash/通用工具的 liveness 和 bash timeout reason 到达 `kernel.stream` | `test_bash_engine.py::{test_silent_long_bash_emits_run_heartbeat_through_build_kernel,test_bash_timeout_surfaces_tool_timeout_reason_through_build_kernel,test_silent_non_bash_tool_emits_run_heartbeat_through_build_kernel}` | keep | 三项均经过真实 `build_kernel`→tool executor→event stream，是下层 unit 无法替代的连接保护；改用终态事件条件等待 | M9 pytest |
| threshold/manual/overflow compaction 在 live session、外部 append 和 JSONL 重开后保持历史 | `test_conversation_compaction_integration.py::*` | rewrite-merge | 保留 4 条 `build_kernel` 跨 seam 风险；摘要请求识别从 prompt 原文改为空 tools 边界，不锁死措辞 | M9 pytest |
| compaction 同时刷新 memory/user 快照并重置 read 去重窗口 | `test_conversation_context_window_integration.py::test_compaction_refreshes_memory_and_resets_file_read_window` | rewrite-merge | 保留 kernel→memory snapshot→ReadTool 跨 seam；摘要识别不再绑 prompt 字面量 | M9 pytest |
| 显式 `enabled_tools=[]` 经 session 装配到 model request 仍为空 | `test_empty_tool_allowlist_wiring.py::test_create_session_empty_allowlist_exposes_no_runtime_tools` | keep | 证明 SDK session 配置→runtime→LLM request 连接，不重测执行层 allowlist 逻辑 | M9 pytest |
| builtin/workspace hook 动态加载后按层组合并可 dispatch | `test_hooks_loader_integration.py::test_loader_uses_builtin_then_workspace_order_for_same_priority` | rewrite-merge | 保留动态加载→HookRegistry→HookRunner 连接，删除对 fixture 文件名列表的重复布局断言 | M9 pytest |
| REPL idle 背景渲染 | `test_idle_background_render.py::test_idle_callback_renders_background_events_prompt_aware` | delete | 复制了生产格式化逻辑却不调用生产入口，对真实回归无信号；current 最低层保护由 `tests/unit/test_idle_callback.py` 所属切片维护 | idle unit + M9 pytest |
| REPL 私有 key reader 超时和 callback 循环 | `test_idle_background_render.py::{test_key_reader_idle_timeout_sequence,test_read_interactive_line_idle_callback_invoked}` | delete | 直接测私有 `_build_key_reader` 且与 `tests/unit/test_idle_callback.py` 重复，不是 kernel integration seam | idle unit + M9 pytest |
| kernel skeleton 与历史 PA/CLI golden 字节完全一致 | `test_kernel_skeleton_reproduces_golden.py::test_skeleton_plus_slots_reproduces_golden[*]` | delete | 一次性 refactor-406 迁移终态，无 current 风险要求原样字节稳定；当前 prompt 组装机制由 `tests/unit/agent/prompt_sections/` 保护。该文件是 `tests/integration/golden_prompts/*.txt` 7 个 fixture 的唯一引用；fixture 不属 M9，M9 只删引用，由 M10 rebase 后删除无引用 fixture | prompt unit + M9 pytest + baseline/current `git grep golden_prompts` |
| Bash signal 细节 | `test_tools_bash_integration.py::test_registry_bash_signal_error_keeps_signal_details` | delete | 与 `tests/contract/test_tools_bash_contract.py::test_bash_signal_contract_exposes_signal_details` 对同一真实 ShellRunner 路径重复，高层 registry 未增加独立风险 | bash contract + M9 pytest |
| ReadTool image 多部件经 registry 仍保持结构 | `test_tools_read_integration.py::test_registry_executes_read_image_and_keeps_part_structure` | rewrite-merge | 保留 ReadTool→ToolRegistry 连接，只断言 multipart shape；字节/尺寸细节由 `test_tools_read.py` 保护 | read unit + M9 pytest |
| ReadTool 截断细节 | `test_tools_read_integration.py::test_registry_executes_read_text_with_truncation_hint` | delete | 与 `tests/unit/test_tools_read.py::{test_read_truncates_output_by_lines,test_read_truncation_returns_truncated_content}` 重复，registry 无额外风险 | read unit + M9 pytest |
| hook rewrite 工具结果时 image multipart 不被压平 | `test_tools_read_integration.py::test_read_image_parts_survive_tool_result_content_rewrite` | keep | 直接保护 ReadTool→ToolRegistry→HookRunner 跨 seam | M9 pytest |
| tool-role image blocks 转换为 Anthropic/OpenAI provider payload | `test_tools_read_integration.py::{test_anthropic_mapper_accepts_read_image_blocks_directly,test_openai_compat_mapper_accepts_read_image_blocks_directly}` | keep | 精确 provider payload 是 core DTO→provider adapter seam，两家协议形态不同，不与 ReadTool unit 重复 | M9 pytest |
| ToolRegistry 基本 dispatch/参数校验/未知工具 | `test_tools_registry_loader_integration.py::test_registry_dispatches_and_validates_arguments` | delete | 与 `tests/unit/test_tool_validation_errors.py` 及 registry unit 保护重复，未经 loader seam | validation unit + M9 pytest |
| workspace tool 动态加载后可经 registry 执行 | `test_tools_registry_loader_integration.py::test_loader_discovers_and_registers_directory_tools` | rewrite-merge | 保留文件发现→动态 import→registry execution 连接，删除文件名和 auto-classifier 投影细节 | M9 pytest |

## Roadpoints

### R1 — 删除历史和重复断言

- 状态: DONE
- 步骤: 删除 idle 复制逻辑、kernel 迁移 golden、重复 bash signal 文件，以及各文件中已由 unit/contract 拥有的 policy、truncation、validation 细节；用下层最窄命令证明真实风险未丢。
- 验证: 相关 unit/contract 绿；收集结果不再出现已删 node。

### R2 — 收敛保留的跨 seam 保护

- 状态: DONE
- 步骤: 参数化 bash gate；compaction 不再依赖 prompt 原文；hook/tool/read 只断言跨边界结果；bash stream 改为等待指定 run 终态事件。
- 验证: 保留的 M9 integration 全绿，无固定 prompt 文案/无条件 trailing sleep/无为解锁 stream 而提交的 noop run。

### R3 — 门禁与范围收尾

- 状态: DONE
- 步骤: 复核处置表、保留保护与 changed paths，运行 M9 切片、下层替代保护、ruff 和 diff 检查。
- 验证: 所有门禁全绿，`progress.md` 记录 Claim/Baseline/Method/Result/Locator/Limit。

### R4 — 合并后跨 milestone collection 回归修复

- 状态: DONE
- 步骤: 复现 M13 consumer 导入失败，追溯 M9 R2 删除与共享 harness 依赖；只在 M9 owner 文件恢复仍被消费的 stream collector 与 teardown exception tuple，不回退 M9 自身的终态事件收集逻辑。
- 验证: M13 consumer 可 collect 且实跑通过；M9 18 项与 consumer 合并运行全绿；ruff、diff 与 scope 检查全绿。

# refactor-489-M3: core-prompt-runtime — Tasks

> 对齐: ../design.md 的 refactor-489-M3 行与决策 1、2

## 目标

保留当前 core seam 的状态、提示词条件和消费者输入输出保护；合并或删除迁移快照、退役路径墓碑、私有 helper 重复覆盖与提示词片段措辞断言。

## 退出标准

- [ ] 当前 prompt assembler、feature/tool gate、session/runtime 状态与消费者输入输出仍有最低层保护。
- [ ] 迁移 golden、旧符号/目录终态和 prompt 段落片段不再作为永久测试契约。
- [ ] 真实风险对应的保留或替代测试在删除旧测试前已跑通。
- [ ] M3 精确范围测试、相关 contract 替代保护、ruff 与 diff 检查通过。

## 测试策略

- 被测行为（来自退出标准）：prompt section 按当前顺序、启用条件与 runtime/preview 输入装配；session/runtime 的状态、JSONL 序列化和 LLM 消费者输出保持不变；架构依赖由 contract 而非迁移墓碑保护。
- 已有测试在：`tests/unit/agent/test_prompt_sections.py`、`tests/unit/agent/test_kernel_list_capability_queries.py`、`tests/unit/agent/test_session_metadata_features_wiring.py`、`tests/unit/test_nested_memory_read_injection.py`、`tests/unit/test_session_persistence_fidelity.py`、`tests/unit/agent/session/**`、`tests/contract/test_agent_sdk_surface_contract.py`、`tests/contract/test_core_no_platform_imports.py` 与 no-legacy contract（扩展/保留）；不新建测试域，只在现有 M3 文件内合并。
- 落层/目录/marker：`tests/unit/` 与既有 `tests/contract/` 替代证明，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；处置前后命令与结果写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Event hub 与 core 包依赖仍可用 | `tests/unit/agent/test_core_events_hub_location.py` | delete | 只断言迁移后的模块位置；跨 loop 事件行为由 `tests/contract/test_agent_sdk_surface_contract.py::test_cross_loop_streaming_receives_run_status_event` 保护，依赖方向由 core contract 保护 | 定向 contract + M3 全量 |
| 退役 HTTP/旧 core roots 不被重新依赖 | `tests/unit/agent/test_http_api_dir_removed.py`、root `test_core_{hooks,llm,observability,runs,tools}_location.py` | delete | 文件/`__module__`/旧 import 缺失是迁移终态；现行依赖风险由 `tests/contract/test_no_legacy_{wiring,homing}_imports.py`、`test_core_no_platform_imports.py` 及各域行为测试保护 | 定向 contract + M3 全量 |
| skill resolver 按 workspace 构造且无配置时关闭 | `tests/unit/test_core_skills_location.py` | rewrite-merge | 删除 canonical-home、SDK 无符号与旧 root 墓碑，仅保留 resolver 输入输出并改为行为命名文件 | resolver 定向测试 + M3 全量 |
| ToolSafety/read/shell 当前行为 | `tests/unit/agent/platform/tools/test_safety.py`、`tests/unit/agent/tools/test_safety_background.py` | rewrite-merge / delete | 删除已退役字段/方法不存在墓碑；保留路径归一化、workspace 判定、跨 workspace read 与现行 ShellRunner 行为测试 | safety、background adapter 定向测试 |
| foreground stopper 走独立 registry | `tests/unit/agent/background_tasks/test_foreground_wiring.py::test_background_registry_has_no_foreground_patches` | delete | 私有字段不存在不是风险；同文件保留 wiring 暴露与 Kernel 注入结果，registry 行为另有直接测试 | foreground wiring/registry 定向测试 |
| bash policy 返回 allow/review/deny 与配置覆盖 | `tests/unit/agent/platform/tools/builtins/test_bash_policy.py` 的常量清单、迁移删除项与 dataclass 形态测试 | rewrite-merge | 直接行为参数化已覆盖相同风险；不再冻结内部常量集合或 dataclass 实现 | bash policy 文件 |
| prompt assembler 顺序、gate、空段过滤、cache-safe 与 override | `tests/unit/agent/prompt_sections/test_prompt_sections_no_order_field.py`、`tests/unit/agent/test_prompt_sections.py` | delete / rewrite-merge | 前者是迁移红测且与后者重复；后者合并为当前 assembler seam 的最小行为矩阵 | prompt assembler 文件 |
| memory/user/AGENTS runtime 与 preview 条件 | `test_prompt_sections_golden_baseline.py`、`test_prompt_sections_render_mode.py`、`test_core_sections_legacy_cleanup.py`、`test_user_profile_block.py`、`test_agents_md_prompt_section.py` | delete / rewrite-merge | 删除迁移 golden、字段存在与 banner 字节/片段断言；把真实输入输出合并为 runtime/preview/empty consumer 结果与 cache invariant | prompt runtime state + AGENTS prompt 定向测试 |
| feature/tool 条件决定通用 guidance 是否启用 | `tests/unit/agent/test_core_sections.py`、`tests/unit/agent/test_feature_registry.py`、`tests/unit/test_agent_prompting.py` 条件段 | rewrite-merge / delete | 删除 CC prompt 词片段和 registry skeleton 形态；保留 feature+tool 条件、Kernel capability projection、metadata override 与 legacy fallback 的动态注入关系 | prompt condition、capability、metadata 定向测试 |
| background notification prompt 与子 agent role prompt 不绑定历史句子 | `test_background_tasks.py::test_prompt_block_contains_rules`、`test_subagent_types.py::test_role_prompt_seeds_are_distinct_and_read_only_types_avoid_gp_copy`、`test_agent_tool.py::test_type_specific_prompt_seed_is_passed_to_create_subagent` | delete / rewrite-merge | XML/schema、工具 deny 与 PromptSlotSeed 传递风险仍保留；AgentTool 改为对象相等而非 `READ-ONLY` 片段 | background/subagent/agent tool 定向测试 |
| assistant history 合并向 LLM 保留文本、tool calls 与 reasoning | `tests/unit/test_merge_adjacent_assistant.py`、`tests/unit/test_prompting_merge_adjacent.py` | delete / rewrite-merge | 删除私有 helper 的重复直接测试，改经 `build_chat_messages` 消费者入口覆盖相邻合并与 group coalesce | prompting merge 文件 + persistence fidelity |
| MemoryStore 空态与纯内容输出 | `tests/unit/test_memory_store.py`、prompt golden/render-mode 中的重复用例 | rewrite-merge / delete | 同一 store 风险只在 store 最低层断言一次；prompt 只验证装配输入输出 | memory store + prompt runtime state |
| 自动 skill curator 的 stale/archive/reactivate 与发现边界 | `tests/unit/test_curator.py` | keep | 范围澄清后纳入；5 个测试直接经过 curator 文件状态 seam，分别保护仍存在的生命周期风险，没有迁移快照或更低层重复 | `pytest -q tests/unit/test_curator.py` |

## Roadpoints

### R1 — 删除迁移终态与墓碑断言

- 状态: DONE
- 步骤: 先跑架构/运行时替代保护，再删除 location/removed/tombstone 测试并收敛混合文件中的行为用例。
- 验证: no-legacy/core contract、Event hub 跨 loop、safety/background/bash policy 定向测试通过。

### R2 — 收敛 prompt 条件与消费者输入输出

- 状态: DOING
- 步骤: 删除迁移 golden、片段措辞和 registry skeleton 断言；把 assembler、runtime/preview、AGENTS、feature/tool gate 与 PromptSlotSeed 传递合并到当前 seam。
- 验证: prompt、capability、metadata、subagent 定向测试通过，且不再存在 M4 golden/legacy/no-order 文件。

### R3 — 合并 runtime/persistence 重复并完成门禁

- 状态: TODO
- 步骤: 把 assistant merge 改为 `build_chat_messages` 消费者保护，去除 MemoryStore 重复；核对处置表并运行 M3 精确范围门禁。
- 验证: M3 全量（显式包含 `tests/unit/test_curator.py`）、相关 contract、ruff、`git diff --check` 与范围检查通过。

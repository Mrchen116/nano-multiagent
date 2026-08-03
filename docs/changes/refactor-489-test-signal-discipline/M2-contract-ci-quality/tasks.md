# refactor-489-M2: contract-ci-quality — Tasks

> 对齐: ../design.md

## 目标

让 contract 与 CI/quality gate 只因当前公开协议、真实依赖、文档结构或可执行质量规则变化而失败；移除迁移终态、私有源码步骤、历史整句和行号白名单产生的噪声。

## 退出标准

- [ ] 每项受影响的 contract/quality gate 都有 keep、rewrite-merge 或 delete 处置及最低层保护说明。
- [ ] 保留的架构检查通过 AST 验证真实 import 依赖，或验证 current 文档/构建结构，不绑定已删除符号、历史目录树或迁移终态。
- [ ] 被删除测试曾对应的真实风险，已由当前公开 seam 的 unit/integration/contract/E2E 保护，或已确认没有长期风险。
- [ ] 指定切片 pytest、docs-check、ruff/format 与 hook 入口全部通过；无产品行为或 spec delta。

## 测试策略

- 被测行为（来自退出标准）：跨包与内核分层 import 边界；SDK/schema/序列化公开契约；change workflow、docs catalog、测试命名/大小和 CI/hook 的可执行质量规则。
- 已有测试在：`tests/contract/**`、`tests/unit/test_docs_check.py`、`tests/unit/test_agents_md_loader.py`、`tests/unit/test_change_spec_author_next_unit_id.py`（改写/保留）；不新建产品测试，仅新增 contract 内共享 AST helper。
- 落层/目录/marker：`tests/contract/` 与 `tests/unit/`，marker：无。
- 可选依赖 importorskip：无；本切片使用 dev 依赖与 Git 工作树。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；命令结果写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 产品只经 `agent.sdk` 接触内核，顶层包与内核层依赖方向正确 | `test_agent_sdk_boundary_contract.py`、`test_cli_sdk_only_contract.py`、`test_core_no_platform_imports.py`、`test_platform_no_sdk_imports.py` | rewrite-merge | 保留 current `SPEC.md` / kernel spec 的真实 import seam；用共享 AST import 解析替代正则、源码片段和重复扫描 | 四个 contract 文件 + hook 入口 |
| `agent.sdk` 公开 export、DTO/schema、LLM/provider、tool/hook 与 Kernel 公共行为 | `test_agent_sdk_surface_*`、`test_{core_types,core_events,llm_interfaces,llm_provider,compaction,hooks,hook_integration,tools_*,kernel_sdk_behavior,sdk_kernel_wiring,sdk_two_layer_assembly,tool_gate_coverage,skill_commands,system_prompt,cli_error,bg_origin_constant}_*.py` | keep | 直接调用公开对象或协议序列化 seam；精确字段/文本仅用于 schema、wire payload 或明确公开 API | 对应 contract pytest |
| capability wire payload 的字段、顺序、默认值和 skill location | `test_capability_payload_baseline.py` | rewrite-merge | 风险仍是当前 node/agent capability 协议；去除“迁移前 baseline”叙事，保留受控环境下的协议精确断言 | capability contract pytest |
| 个人助手包进入构建产物 | `test_personal_assistant_package_contract.py`、`test_personal_assistant_main_contract.py` | rewrite-merge | 用 setuptools 实际发现结果保护可安装包；删除入口文件路径、私有 factory/lifecycle 源码布局断言 | package contract pytest |
| CLI 与 PA 的 cron/heartbeat 产品隔离 | `test_cron_coding_cli_isolation.py`、`test_agent_sdk_surface_contract.py` 的 cron-negative tests | rewrite-merge | 保留两产品 factory 的可观察 tool/prompt 结果；删除 `cron.py` 文件位置和“名称中不得含 cron”的迁移终态扫描 | cron isolation pytest |
| 已完成包重命名、旧 import/目录和 session aggregate 切换 | `test_multi_product_architecture.py`、`test_no_legacy_homing_imports.py`、`test_no_legacy_wiring_imports.py`、`test_session_aggregate_architecture.py` | delete | 只验证迁移终态、已删路径/符号或私有 `_engine`；真实跨包依赖由 AST contract，session 行为由 session unit/integration 与 SDK contract 保护 | 替代 contract + session focused tests |
| PA/IM 内部 owner、module/file layout 和前端单 WebSocket 实现 | `test_gateway_inbound_ownership_contract.py`、`test_im_gateway_seam_contract.py`、`test_im_persistence_seam_contract.py`、`test_im_frontend_user_stream_ownership.py` | delete | 源码字符串、私有调用、类/文件位置是实现步骤；Gateway/IM/前端行为在所属 unit/integration/E2E/Vitest seam 保护 | 相关已有行为测试收集证据 + contract suite |
| workspace dirname 不被新增硬编码 | `test_no_hardcoded_workspace_dirname.py` | delete | 行号白名单随无关编辑漂移，且所称单一 owner 与当前代码不成立；真实 workspace 路径行为由产品/config/session tests 保护 | 搜索 current owners + scoped suite |
| change workflow 的 optional review、同 reviewer Gate 2 与 selected gates 同步 | `test_change_workflow_documentation_contract.py` | rewrite-merge | workflow 文档是 current seam；改为按 Markdown section/table 语义核对，避免固定整句 | 单文件 contract pytest |
| PR body 中 unit 文档链接固定到 PR head | `test_change_skill_archive_contract.py` | rewrite-merge | 保留真实渲染风险；提取所有 change-unit Markdown link 验证绝对 blob 形态，不固定模板恰有五个链接 | 单文件 contract pytest |
| docs-check 维护 current 路由、spec index、E2E catalog 与 bootstrap | `scripts/docs_check.py`、`tests/unit/test_docs_check.py`、`scripts/docs-check` | rewrite-merge | 保留结构与 pytest node 可收集性；E2E catalog 不再依赖标题措辞或重复 prose count | docs-check unit + CLI |
| 新测试文件命名与 400 行上限 | `test_test_naming_and_size_contract.py`、`.github/workflows/ci.yml` | rewrite-merge | 保留 M1 current 质量规则；CI 获取完整 base history，比较失败大声报错，不再因缺 `origin/main` 静默放行 | 单文件 contract + invalid-base negative run |
| 编辑 Python 后的 ruff 与架构快速反馈 | `.claude/hooks/ruff-guardrail.py`、`pyproject.toml` | rewrite-merge | 保留 ruff/timeout/current lint 配置，并让 hook 覆盖全部 current import 方向 contract | hook JSON 入口 + ruff |
| 全套 pytest 的模型注册初始化与共享 inbound graph | `tests/conftest.py`、`tests/helpers/**` | keep | 是实际测试 harness seam，不固定迁移终态；本 milestone 不改变其行为 | scoped pytest 与 collection |
| AGENTS loader 与 unit-id allocator | `test_agents_md_loader.py`、`test_change_spec_author_next_unit_id.py` | keep | 直接运行 parser/git/worktree/并发公开脚本行为，属于最低 unit seam | 两个 unit 文件 pytest |

前端 UI：N/A。Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — Contract 架构 seam 收敛

- 状态：TODO
- 步骤：先确认保留的当前行为保护；新增共享 AST import helper，改写跨包/层级 contract；删除迁移终态和私有源码/目录扫描；把 capability/package/cron/SDK 断言改成 current seam。
- 验证：受影响 contract 文件最窄 pytest；替代保护 focused pytest；ruff/format。

### R2 — CI 与 quality gate 收敛

- 状态：TODO
- 步骤：改写 workflow/template/docs catalog/test-file gate 为结构或可执行规则；让 CI base 可用且失败不静默；扩充 hook 的 current import 边界反馈。
- 验证：quality contract、`test_docs_check.py`、`./scripts/docs-check`、invalid-base negative run、hook JSON 入口、ruff/format。

### R3 — 切片回归与证据闭环

- 状态：TODO
- 步骤：核对处置表、tracked scope 与 diff；运行完整 M2 pytest/docs/ruff/hook 门禁并记录 limits；完成可回退提交与集成准备。
- 验证：完整 M2 命令、`git diff --check`、无越界路径。

# refactor-406-M2 — Progress

## 启动对齐（§2.5）

- worktree 从 `origin/unit/refactor-406`（HEAD e96eac26，含 M1 全部成果）切，分支 `milestone/refactor-406-M2`。
- 已读：design 全文（决策 4 能力查询 / 决策 7 精确名单 / 风险 2 payload 漂移 / Milestones M2 行 / Reviewer 矩阵 R-CFG/R-GW）、M1 progress（_M1_TEMP 名单确切位置）、delta-spec、reporter 实现、`kernel.list_*` 实现 + DTO。
- 基线：`pytest -m "not e2e"` 2744 passed / 2 skipped 全绿；surface guard + boundary contract 6 passed。
- orchestrator 确认投影方案正确（决策 4「Kernel 报中立事实、Gateway 投影产品语义」）：
  - i18n（label_i18n/help_i18n）**全归 Gateway 投影**（含内核两条 memory/skill），不进内核 DTO（i18n 是产品「文案」，违反中立判据）。
  - kernel list_features() 只报 key/default_on/requires_tool（中立事实，内核两条）；4 条 feature 的 i18n + heartbeat/cron 两条整条 + tools default_on 划分 + available 计算全由 Gateway 投影自管。

## R1 — capability payload 基线 fixture（漂移防线，已 push）

- Context: design 风险 2（capability payload 漂移）是 M2 最高风险——reporter 数据源整体替换为 `kernel.list_*` + Gateway 投影。先录基线再切。
- Decision: 新建 `tests/contract/test_capability_payload_baseline.py`，受控环境（conftest 固定 model registry + 受控 HOME 隔离 skill 全局/compat root + 受控 workspace 种已知 skill）固化重构前 payload 形状为可执行基线，跨机可复现。
- Evidence: commit 3fede227。3 个断言：node.capabilities / agent.capabilities.resolve / node.register flags。
- Commits: C1=3fede227（基线录制，单 commit）。

## R2 — reporter 数据源换 kernel.list_* + Gateway 投影（进行中）

- Context: design 决策 4——reporter 不再消费 SDK 转发的 registry/resolver/profile/feature registry 自建磁盘布局，改调 `kernel.list_models/list_tools/list_features/list_skills` 中立查询 + Gateway 自己投影。
- Decision（落点）:
  1. 新建 `src/personal_assistant/reporter/capability_projection.py`（Gateway 投影层，产品语义真相）：
     - `PA_DEFAULT_TOOL_IDS` / `PA_OPTIONAL_TOOL_IDS`：tools default_on 划分，逐字 port 自 PERSONAL_ASSISTANT_PROFILE。
     - `FEATURE_PROJECTIONS`：4 条 feature 的 key/label_i18n/help_i18n/default_on/requires_tool（声明顺序），逐字 port 自 FEATURE_REGISTRY；含 heartbeat/cron 两条产品 toggle。
     - `project_tools(tool_infos)`：投影 tool pills + default_on；**description 固定 ""**（保 payload 逐字段不变，见漂移点1）。
     - `project_features(tool_allowlist)`：4 条 feature 投影 + available 计算（node 级=None→全 True；agent 级=按 allowlist）。
  2. `reporter/upstream_reporter.py`：三个 capability 函数加 `kernel` 参数，数据源换 kernel.list_*：
     - `build_runtime_capabilities(kernel)` / `build_node_capabilities_payload(kernel)` / `build_agent_capabilities_payload(kernel, *, workspace_root, tool_allowlist)`。
     - 删 `_repo_root`/`_product_root`/`_build_skill_capability_entries`/`_build_tool_names`/`_build_model_names`；删 SDK 旧导出 import（get_default_model/get_default_provider/list_provider_models/list_supported_providers/default_skill_search_roots/SkillRegistry/ConfigResolver/PERSONAL_ASSISTANT_PROFILE/FEATURE_REGISTRY）。
  3. 调用点注入 kernel：`main.py`（reporter 构造 + agent_capabilities_provider 闭包 + 新增 node_capabilities_provider 闭包）；`ws/im_connection.py`（node.capabilities.resolve 改走注入的 `node_capabilities_provider`，不再 import 模块函数，WS 层 kernel-agnostic）。

### 查询字段 ↔ payload 字段映射表（design 决策 4 风险硬要求）

| payload 字段 | 来源 | 投影逻辑 |
|---|---|---|
| `models` | `kernel.list_models()` → ModelInfo.name | `_dedupe_preserve_order`（保序去重，复现旧 payload 顺序） |
| `platform_default_model` | `kernel.list_models()` 里 `is_default=True` 的项 | 取首个 is_default 的 name |
| `tools[].name` | Gateway 自管（PA_DEFAULT_TOOL_IDS + PA_OPTIONAL_TOOL_IDS） | 名单 port 自 PROFILE default/optional tool ids，顺序复现 |
| `tools[].description` | **Gateway 固定 ""** | 旧 payload 历来空串；kernel.list_tools 有真 description 但不投影（见漂移点1） |
| `tools[].default_on` | Gateway 自管划分 | default_tool_ids→True / optional_tool_ids→False |
| `skills[].name/description` | `kernel.list_skills(workspace_root)` → SkillInfo | per-workspace discovery（决策 4）；**root 不全，见漂移点2 阻塞** |
| `features[].key/default_on/requires_tool` | 中立事实（内核两条经 list_features 印证；4 条由 FEATURE_PROJECTIONS port） | Gateway 自管 4 条（含 heartbeat/cron 产品 toggle） |
| `features[].label_i18n/help_i18n` | **Gateway 自管**（FEATURE_PROJECTIONS） | i18n 是产品文案，不进内核 DTO（orchestrator 确认） |
| `features[].available` | Gateway 计算 | node 级全 True；agent 级 requires_tool∈tool_allowlist |
| `relay/send_message/config_sync` flags | ReporterCapabilities 默认（产品自管） | 不变 |
| `default_system_prompt` | 固定 ""（feat-379-M5 ISSUE-4） | 不变 |

### 基线 fixture 暴露的 2 个真实漂移点

- **漂移点1：tools description（已自决修复）**：旧 reporter `_build_tool_names` 硬编码 `description: ""`；`kernel.list_tools()` 返真实工具 description。`project_tools` 保持 ""（design 风险2 逐字段不变；IM tool-pill 历来空 description，展示真实 description 是 payload 变更、超出 behavior-preserving 边界、另开 unit）。**models/tools/features/flags 现全部逐字段绿。**
- **漂移点2：skills search root 不全（M1 遗留架构 gap，已 SendMessage orchestrator 求拍板，未收口）**：
  - 旧 reporter PA skill search root = 4 类：workspace `<ws>/.nanoassistant/skills` + global `~/.nanoassistant/skills` + compat `~/.claude/skills` + `~/.codex/skills`（39 真实 skill 主要来自 compat `~/.claude/skills`）。
  - M1 `kernel.list_skills` 用 `_WorkspaceDirnameSkillResolver`（kernel.py:464）**只有 workspace 一类 root**——漏 global + 2 compat。受控 HOME 实测旧报 5 / 新报 2。违反 payload 逐字段不变硬契约 + 影响 R-CFG-1/2（用户 IM 创建 Agent 看到的 skill 集缩水）。
  - 基线 fixture 已把此钉成可执行红测（models/tools/features 绿、skills 红精确指出漏的 3 个 global/compat skill）。
  - **方案（orchestrator 已批准，已实现）**：`build_kernel(skill_search_roots: tuple[Path,...] = ())`（用户级共享 skill root，部署常量，build 作用域；workspace root 仍由 workspace_config_dirname 约定派生）；PA 工厂 `build_pa_kernel` 传 PA 3 个 user-level root（`PA_SKILL_SEARCH_ROOTS` 常量，逐字 port 自 PROFILE global_config_home + compat_skill_roots，顺序 global→compat-claude→compat-codex）；coding_cli 不传。内核 `_WorkspaceDirnameSkillResolver` 加 `extra_roots`，`user_skill_roots()` 返回 `(workspace root,) + extra_roots` 去重保序，复刻旧 reporter 4 类 root 顺序。
  - **落点**：kernel.py（build_kernel / _build_kernel_base / Kernel.__init__ 加 skill_search_roots + _WorkspaceDirnameSkillResolver extra_roots + list_skills 传入）；product.py（PA_SKILL_SEARCH_ROOTS 常量 + build_pa_kernel 传入）。
  - **orchestrator nail-down「顺序+dedup 逐字节」**：由基线 fixture hard guard（skills 顺序+dedup 与旧 reporter 一致，红即停）。
  - **已修复**：基线 fixture 4 类 payload（models/tools/features/skills/flags）全逐字段绿。

### R2 受影响测试更新（已完成）

- `_im_connection_helpers.py`：加 `_build_test_kernel(repo_root)`（conftest payload + build_pa_kernel 构造真 kernel），`_minimal_reporter` 改用它。
- `test_gateway_upstream_reporter.py`：capability 测试加 kernel；删 `_build_tool_names` 测试（已删），重定向到 `build_node_capabilities_payload(kernel)['tools']` + `capability_projection.FEATURE_PROJECTIONS`。
- `test_capabilities_tools_format.py`：整体重写，测 `capability_projection.project_tools`（含 description 固定 "" 不变量断言）+ node payload tools 格式。
- `test_gateway_im_auth.py` / `test_gateway_im_relay.py`：本地 `_minimal_reporter` / reporter 构造加 kernel。
- `test_no_hardcoded_workspace_dirname.py`：whitelist 行号锚定 kernel.py 122→131（skill_search_roots param + docstring 位移）。
- ruff format 收 M1 遗留 format 债（cron_service_registry/cron/web_fetch/dto/kernel/test_sdk_kernel_wiring/test_sdk_two_layer_assembly/test_presentation_golden 8 文件），CI 绿前提。
- `test_skills_workspace_with_resolver.py` / `test_tool_loader_with_resolver.py` / `test_hook_loader_with_resolver.py`：grep 命中 `product_root` 是函数名子串，测 core/platform 内部 API 的 product_root 参数——**不依赖 reporter**，归 R3（products/ 解散评估）。

### delta-spec 同步（已写）

- kernel delta-spec：build_kernel 签名行补 `skill_search_roots=()`；「Kernel 提供单项中立能力查询」Requirement 补 list_skills 合并语义（workspace root + 部署 root 去重保序）+ 新 Scenario「部署级共享 skill 根叠加在每 workspace 根之上」。

- Evidence（R2 完成）:
  - 基线 fixture 4 类 payload 逐字段全绿（3 passed）；全 personal_assistant 单测 580 passed/1 skipped；contract 134 passed；kernel list_* 4 passed；**全测试树 not e2e 2747 passed/2 skipped 零回归**；ruff check + format 全仓干净。

## R3 — 撤旧导出 + products 解散 + 决策7 最终闸（进行中）

### R3a — 撤 SDK 旧导出 + 决策7 最终闸（已完成，push commit 62070cee）

- **撤 SDK 公共导出**（`agent/sdk/__init__.py`）：SkillRegistry/ConfigResolver/default_skill_search_roots/FEATURE_REGISTRY/model registry 列表函数全家（init_model_registry/get_default_model/get_default_provider/list_provider_models/list_supported_providers）+ LLMFactoryConfig/LLMConfigPayload/LLMModelPayload/LLMProviderPayload + LOCAL_CODING_PROFILE/PERSONAL_ASSISTANT_PROFILE 全撤。
- **src/ 消费者迁移（撤导出前置）**：
  - `dto.py` 加 SDK-owned `LLMConfig.from_catalog`（providers→LLMProvider/LLMModel）+ `from_json`（解析 gateway-style catalog JSON），消费者不依赖内部 wire-payload 类型。
  - `coding_cli/commands.py`：`_build_llm_config_payload`→`_build_cli_llm_config`，用 from_json/from_catalog 构 LLMConfig，不再 import LLMConfigPayload 全家。
  - `personal_assistant/config/local_store.py`：LLM config wire schema 改 **PA-owned** dataclass（LLMConfigPayload/Model/Provider，复刻原字段语义——base_url Optional、extra_request_body None-when-absent——保 config.yaml round-trip byte-identical），不再从 agent.sdk import；`config.llm` 经 duck-typed `LLMConfig.from_payload` 流入 build_kernel 不变（K2.6 thinking extra_request_body 保留）。
  - `main.py`：删冗余 `init_model_registry(config.llm)`（build_kernel 内部已 init，决策5 消化 footgun）。
- **决策7 三道闸最终闸**（surface guard）：`EXPECTED_SURFACE` 钉死为最终 curated 面（22 符号），删 `_M1_TEMP_REPORTER_EXPORTS` + `_M1_TEMP_PROFILES` 豁免组，仅剩永久豁免（C1 RunOrigin/PermissionDecision/TERMINAL_RUN_STATUSES + 决策12 ToolPresenter/Event + CanUseToolFn typing alias）。三道闸（精确名单 + 所有权 + 无 stale 豁免）全绿。
- whitelist 行号锚定更新：commands.py 1144/1145→1146/1147（函数替换净+2行）。
- Evidence：全树 not e2e 2747 passed/2 skipped 零回归；ruff check + format 干净；分支零 e2e 产物。

### R3b — products/ 物理解散（评估完，进行中）

- **生产零依赖取证**：`bootstrap_product` 零生产调用；`ConfigResolver(profile=)` 只剩 2 处构造——bootstrap.py（死）+ kernel.py:1005 legacy 分支（M1 R7 删 legacy build_kernel 路径后 `build_resolver._profile` 永远 None，死分支）。新 2 层路径用 `_WorkspaceDirnameSkillResolver`（鸭子 ConfigResolverLike Protocol）。ProductProfile/ConfigResolver(profile=)/bootstrap_product 在新路径全是 legacy 死代码。
- **范围**：删 `agent/products/` + `platform/products/` 垫片 + `platform/product.py` + bootstrap_product + kernel.py 死分支；~30 个测试 import `agent.products` 内部需逐个分类（含 risk-1 prompt golden 3 个：test_full_system_prompt_byte_identical/test_kernel_skeleton_reproduces_golden/test_prompt_sections_golden，重定向到 src/personal_assistant/ 副本 + 逐字节复验守 risk-1）。
- **risk-1 golden 防线锚点（orchestrator 钉死，已核实非循环）**：
  - golden 期望值 = `tests/integration/golden_prompts/*.txt`（M1 R1 commit 00cbd5b8 录的**重构前冻结快照**，literal 文件），**不是** live import 段。`test_kernel_skeleton_reproduces_golden`：`actual`=skeleton + src 生产工厂 slots 渲染，`expected`=冻结 .txt。渲染侧换 src/、期望侧锚冻结原文 → **非 src-vs-src 循环**。
  - **migration 断言（删 products 前一次性验，已绿）**：src/ 生产段 == products/ 原文段**逐字节**——PA 7 段 + LC 3 段全 MATCH，证明 R6 copy 忠实。
  - 结论：fc63e226 golden 重定向对 risk-1 零风险。
- **ConfigResolver 去留（orchestrator 拍板）**：legacy 死分支删（fc63e226）；ConfigResolver 具体类零生产消费者→整删 + loader 注解改 ConfigResolverLike；ConfigResolverLike Protocol 保留。
- **chat_history**：M1 已 `hooks=[]` 弃用、inbound_pipeline 无替代 = 生产行为已不存在，删 hook+test。**标记**：M1 R6 弃用（非 M2 引入），意外丢失需新 unit 恢复（DONE 高亮）。
- **状态**：migration 断言绿，开始系统删 src + ~32 测试分类。

## R4 — live 实测 R-CFG-1/2/3/4 + R-GW-1/2（待 R2/R3 收口）

（待做）

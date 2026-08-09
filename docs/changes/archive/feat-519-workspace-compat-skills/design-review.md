# Design Review: feat-519-workspace-compat-skills

## Round 1

### Metadata

- reviewer: `/root/feat_519_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 恒为 full；从 spec、design、四份 delta-spec、prototype 与两个 milestone 建立完整 inventory，并从 CLI/Gateway/IM 生产入口正向追 current code 与 canonical specs。`
- started_at: `2026-08-10T00:11:52+08:00`
- completed_at: `2026-08-10T00:18:42+08:00`
- duration: `6m50s`

### Verdict

Issues Found — 4 CRITICAL / 2 WARNING

### Coverage

- 首文档：`spec.md` v1；逐条覆盖 5 项澄清、5 段用户场景、12 个验收 Scenario、4 项非目标。
- 设计：`design.md` 全文；逐条核 26 项现状/约束/复用/历史断言、6 个编号决策、接口与数据流、风险回退、runbook 与 2 个 milestone。
- 契约增量：`specs/{cli,gateway,im,kernel}/*.md` 全部 Requirement/Scenario；逐条对照对应 canonical area，并额外追到同一语义的 `kernel/sdk-boundary.md`、`gateway/external-channels.md`。
- 原型：`prototype.html` 的桌面/窄屏布局、三态分组控制、单项 pill、保存反馈及声明覆盖状态。
- 生产 grounding：CLI `run_cli → build_cli_kernel → agent.sdk.build_kernel`；PA `compose_gateway → build_pa_kernel → agent.sdk.build_kernel`；Gateway capability resolve、IM WS/REST 转发、Agent create/detail selector、session runtime projection、SlashPicker，以及 Feishu/Lark/`skill_created` 配置写回路径。

### 现状断言核实台账

| ID | 现状断言 | 本轮独立证据与结论 |
|---|---|---|
| A1 | PA 为一个 workspace root 叠加三项共享 roots | 成立：`src/personal_assistant/product.py:40-52,418-427`；SDK 当前只接一个 `workspace_config_dirname`，见 `src/agent/sdk/kernel.py:230-242,311-318`。 |
| A2 | CLI 仅有原生 workspace root、`~/.nanocode` 与 `~/.codex` | 成立：`src/coding_cli/product.py:30-43,144-153`；生产入口由 `src/coding_cli/commands.py:295-321` 调该 factory。 |
| A3 | `make_skill_resolver()` 同源供 list/preview/runtime | 成立：helper 在 `src/agent/core/skills/discovery.py:53-84`；生产调用分别见 `src/agent/sdk/kernel.py:1880-1889,2201-2211` 与 `src/agent/core/agent/runtime.py:1010-1021`。 |
| A4 | Skill 工具另行拼 roots | 成立：`src/agent/core/skills/root_resolver.py:55-104`；`skill_view` 与 `skill_manage` 分别经 `src/agent/platform/tools/builtins/skill_view.py:205-220`、`skill_manage.py:356-385` 调用。 |
| A5 | Registry 按 root 顺序、metadata name 首项胜出，最终按 name 排序 | 成立：`src/agent/core/skills/registry.py:41-58,64-81`。 |
| A6 | PA capability 只有 location/default_on、无稳定来源字段 | 成立：`src/personal_assistant/reporter/upstream_reporter.py:124-154`。 |
| A7 | 当前 selector 有三组、以 path/default_on 猜来源且无分组操作 | 成立：`src/IM/frontend/src/features/settings/agents/skill-source-selector.tsx:10-23,49-69,89-120`。 |
| A8 | create/detail 共用 selector 与同一 `string[]` draft | 成立：create 见 `agent-create-page.tsx:932-946`，detail 见 `agent-detail-page.tsx:1828-1841`。 |
| A9 | PA 空 skills 被投影成 SDK `None` | 成立：`src/personal_assistant/gateway/session_composition.py:58-74,85-90`。 |
| A10 | IM profile/SQLite、Gateway YAML/operation 当前只携 names | 成立：`src/IM/domain/models.py:104-125`、`src/IM/infra/db.py:54-71`、`src/personal_assistant/config/local_store.py:167-214`、`src/personal_assistant/gateway/agent_config_sync.py:78-124,796-825`。 |
| A11 | SlashPicker 空 whitelist 解释成全部 capability Skill | 成立：`src/IM/frontend/src/features/chat/components/slash-candidates.ts:38-51`，生产消费见 `chat-workspace-page.tsx:407`。 |
| A12 | node capability 当前会把 repo root 当 workspace fallback | 成立：node projection 调 `_skills_from_kernel(..., None)`，见 `upstream_reporter.py:157-173`；`Kernel.list_skills(None)` 回退 `_repo_root`，见 `agent/sdk/kernel.py:1862-1888`。 |
| A13 | 产品只经 SDK、IM 不调 agent、core 不反依赖 platform | 成立：`SPEC.md:115-124,148-161`；本次落点组合符合该方向。 |
| A14 | Agent Workspace 由 Gateway owning node 解析 | 成立：生产 provider 在 `src/personal_assistant/gateway/composition.py:624-640`；IM current 契约在 `docs/specs/im/agents-nodes.md:346-352` 明示只转发。 |
| A15 | Skill name 是 allowlist 身份，Registry root order 是同名权威 | 成立：Registry 证据同 A5；IM/Gateway 配置只存 names，见 A10。 |
| A16 | `skill_manage` 原生 workspace root 负责写，extra roots 只读 | 成立：`src/agent/core/skills/root_resolver.py:85-103` 与 `skill_manage.py:356-385`。 |
| A17 | 新运行配置只在后续新回复采用 | 成立：生产 admission 在 `src/personal_assistant/gateway/session_run_coordinator.py:1200-1256` 先投影完整 snapshot 再 reconfigure。 |
| A18 | 缺失 root 被跳过，无效内容沿用 Registry parser | 成立：`src/agent/core/skills/registry.py:41-58,113-161`；新增目录无需另建容错分支。 |
| A19 | 共享 `make_skill_resolver()` 是 list/preview/runtime 的正确收敛点 | 成立：A3；且符合 `SPEC.md:120-122` 的 core/sdk 依赖方向。 |
| A20 | `ResolvedSkillRoots` 已分离 writer 与 search roots | 成立：`src/agent/core/skills/root_resolver.py:17-39,92-103`。 |
| A21 | Gateway→IM 已有 location 投影链 | 成立：Gateway `upstream_reporter.py:135-154`，IM 类型/转发 `src/IM/api/routes/agents.py:132-147,646-677`。 |
| A22 | Selector 是 create/detail 的共用 draft seam | 成立：A8。 |
| A23 | 当前 UI 是窄画布、卡片、11px 标题与紧凑 pills | 成立：selector `skill-source-selector.tsx:72-120` 与 create/detail 实际挂载点 A8；原型保持同类密度。 |
| A24 | bugfix-431 将 resolver helper 下沉 core 并要求同源 | 成立：历史设计 `docs/changes/archive/bugfix-431-runtime-skill-resolution/design.md:90-126`，current code 见 A3。 |
| A25 | feat-430 透传 location，names 仍是启用身份 | 成立：历史设计 `docs/changes/archive/feat-430-im-slash-skill-picker/design.md:97-110,139-160`，current code 见 A10/A11/A21。 |
| A26 | PA 已有 Claude/Codex 全局兼容 roots | 成立：`src/personal_assistant/product.py:40-52`。 |

### 决策核实台账

| 决策 | 拍死/歧义/自洽/spec 驱动 | 结论与证据 |
|---|---|---|
| D1 有序 workspace layout | 目录序列、两个产品顺序、旧 consumer fallback 均已拍死；不把品牌写进 core | 通过。直接覆盖 `spec.md:49-79` 的发现与优先级；现有单目录限制见 A1-A4。 |
| D2 读取统一 builder、写入保持原生 | reader/writer 边界明确，且延续 bugfix-431 | 通过。A3/A4/A20 证明共享 seam 与当前分叉；设计未引入反向依赖。 |
| D3 Gateway 输出 `source_group` | 三个值、root 映射、旧 payload fallback、`default_on` 含义均明确 | 通过设计本身；但 IM delta 无法正确替换 canonical，见 R1-C3。 |
| D4 `default_discovery` / `explicit_allowlist` | 字段名、枚举、legacy 映射、运行时投影与保存时点大体拍死 | **不通过**：生产中仍有不经普通配置页的 Skill allowlist 写路径，mode 如何保留/转换没有决策，见 R1-C1。 |
| D5 分组标题三态微交互 | 作用集合、草稿、不可见 name、桌面/移动与 a11y 均明确 | 架构决策通过；prototype 未覆盖其依赖的 default-discovery 状态，见 R1-W1。 |
| D6 node 只查 shared roots | node/agent 两种调用语义、创建后权威入口与不新增跨机扫描 API 已拍死 | 通过。A12 证明当前误用；独立 `list_shared_skills()` 比可空 workspace/布尔开关更清楚。 |

### spec 约束逐条台账

| 约束 | design 落点 | 结论 |
|---|---|---|
| Q1 两产品支持三个指定兼容根 | D1、PA/CLI layout、M1 | 覆盖。 |
| Q2 统一来源优先级、首项胜出 | D1/D2、Registry 不变 | 覆盖。 |
| Q3 PA 显式选择后下一轮生效；CLI 新会话发现 | D4 数据流、M1 reviewer 轨 | 覆盖；D4 的旁路写者仍有缺口（R1-C1）。 |
| Q4 缺失/空/无有效 Skill 沿用既有行为 | 现状 A18、风险表、M1 | 覆盖。 |
| Q5 分组批量选择、保留单项、克制视觉 | D5、prototype、M2 | 覆盖；缺 default mode 原型态（R1-W1）。 |
| 用户场景 1：同项目不复制 Skill | D1 两产品 layout | 覆盖。 |
| 用户场景 2：PA 候选、保存、下一轮且不静默扩宽显式选择 | D3/D4、主时序 | 覆盖。 |
| 用户场景 3：CLI 同批兼容 Skill 与可预测覆盖 | D1/D2 | 覆盖。 |
| 用户场景 4：按来源整组操作且不笨重 | D5/prototype | 覆盖。 |
| 用户场景 5：目录缺失/空仍正常 | Registry skip、风险表 | 覆盖。 |
| R1-S1 PA 工作区/主目录兼容候选 | D1/D3、Gateway delta | 覆盖。 |
| R1-S2 CLI 工作区/主目录兼容候选 | D1、CLI delta | 覆盖。 |
| R1-S3 原生与既有兼容来源保持 | D1 追加布局、旧 consumer fallback | 覆盖。 |
| R2-S1 PA 同名优先级且 UI/runtime 同版 | D1/D2、PA 时序 | 覆盖。 |
| R2-S2 CLI 同名优先级 | D1/D2 | 覆盖。 |
| R3-S1 新兼容 Skill 不扩宽已有显式选择 | D4 legacy/explicit 规则 | 覆盖。 |
| R3-S2 保存后下一轮使用且保留聊天历史 | D4、session admission、M1 | 覆盖。 |
| R4-S1 分组批量后仍可单项调 | D5、M2 | 覆盖。 |
| R4-S2 三态如实反映草稿/运行边界 | D4/D5 | 覆盖；default mode 原型证据不足（R1-W1）。 |
| R4-S3 桌面/移动自然融入 | D5、prototype、M2 | 覆盖。 |
| R5-S1 缺兼容目录不失败 | Registry skip、M1 | 覆盖。 |
| R5-S2 无有效 Skill 不误报失败 | 现状 A18、风险表 | 覆盖。 |
| N1 不迁移/复制/改写 Skill | D1/D2 只读 roots、writer 固定 | 不越界。 |
| N2 不改格式/权限/skill_view/显式选择边界 | Registry 不变、D2/D4 | 不越界；mode 旁路必须补齐才能实际守住。 |
| N3 不发现其他 Claude/Codex 资源 | workspace dirnames 只派生 `skills` | 不越界。 |
| N4 控件细节在 design 阶段决定 | D5/prototype | 合规。 |

### delta-spec 逐条台账

| Delta 条目 | canonical 对账 / THEN 可观察性 | 结论 |
|---|---|---|
| CLI MODIFIED `CLI 自有装配定义产品 prompt、工具集合和扩展目录` | 标题命中 `docs/specs/cli/product-integration.md:20`；新根与优先级可观察 | **不完整**：静默删掉原 Scenario，见 R1-C4。 |
| CLI Scenario：Claude/Codex workspace Skill | 用户从 CLI 启动可观察候选 | 合格。 |
| CLI Scenario：用户主目录 Claude Skill | 用户可观察覆盖结果 | 合格。 |
| CLI Scenario：workspace/全局扩展纳入 | 保留原 Scenario，且未改 tools/hooks | 合格。 |
| CLI Scenario：缺失可选目录 | 启动与其他 roots 可观察 | 合格。 |
| Gateway ADDED：有序兼容 roots | canonical 尚无同义 Requirement；PA capability/runtime/skill_view 是产品可观察行为 | 合格。 |
| Gateway Scenarios：workspace candidate / 同名一致 / 缺目录 / node 仅全局 | 均以 IM/Gateway 消费者可观察结果书写 | 合格。 |
| Gateway ADDED：默认发现与显式空 | 行为确为新增，但会改变现有“空 allowlist 默认发现”契约 | 条目自身可观察；还须 MODIFIED 既有冲突项并拍死旁路写者，见 R1-C1。 |
| Gateway Scenarios：显式清空 / 旧空升级 | 用户下一轮与升级行为可观察 | 合格。 |
| IM MODIFIED：`agent 能力的 skills 项携带 location 与来源分组` | canonical 中该文字不是 Requirement，而是父 Requirement 下的 Scenario（`docs/specs/im/agents-nodes.md:346-384`） | **无法归并**，见 R1-C3。 |
| IM Scenarios：来源信息 / 旧节点降级 | 浏览器可观察，字段为可选 | 内容合格；锚点不合格。 |
| IM ADDED：按来源分组批量选择 | 三态、单项、保存边界与窄屏均可观察 | 合格。 |
| IM Scenarios：批量后单项 / 批量取消三态 / 窄屏 | 均为 UI 可观察结果 | 合格。 |
| IM ADDED：配置 API 表达 selection mode | API 与页面/回复行为可观察 | 合格；与 R1-C1 的旁路写回语义需补齐。 |
| IM Scenario：显式空页面/回复一致 | 用户可观察 | 合格。 |
| Kernel MODIFIED：preview/list/runtime/skill_view 同源 | 标题未精确命中 canonical `docs/specs/kernel/skills.md:117`，且另一个 canonical root 契约未改 | **无法一致归并**，见 R1-C2。 |
| Kernel Scenario：多个 workspace dirs 四路径一致 | SDK consumer 视角，names/location 可观察 | 合格。 |
| Kernel Scenario：preview/runtime 一致 | 忠实保留原行为 | 合格。 |
| Kernel Scenario：未传 `workspace_config_dirname` 则空 | 与 current code `build_kernel()` 默认 `.nano` 冲突 | **不成立**，并入 R1-C2。 |
| Kernel Scenario：`list_skills` 携 location | 忠实保留原行为 | 合格。 |
| Kernel ADDED：兼容读取不改 writer root | SDK consumer 经 tool 读写结果可观察 | 合格。 |
| Kernel Scenario：读兼容、写原生 | SDK consumer 视角正确 | 合格。 |
| Kernel ADDED：无真实 workspace 只查 shared roots | SDK consumer 的返回集合可观察 | 合格。 |
| Kernel Scenario：prospective Agent 不含 repo skill | SDK consumer 视角正确 | 合格。 |

### Milestone 台账

| Milestone | 垂直价值 / 范围 / 两轨退出 | 结论 |
|---|---|---|
| feat-519-M1 `skill-root-layout` | 能独立交付 PA/CLI 兼容发现、同名一致、显式空与新建页候选修正；reviewer/worker 两轨齐 | 价值垂直，但范围还缺 selection-mode 旁路写者；见 R1-C1。 |
| feat-519-M2 `grouped-skill-selection` | 能独立交付分组批量 UX；两轨齐，且依赖 M1 后串行 | 范围可验；多 milestone 拆分未给硬触发证据，见 R1-W2。 |

### 整体判断

- 上层可读性：核心思路、总图和六条一句话决策能把 root layout、来源投影、selection mode 与分组 UI 串起来；没有被实现步骤淹没。
- 接口与数据流：主链 `Gateway capability → IM → selector → config apply → next turn` 闭合；但 Skill allowlist 还有 Feishu activation、bundle reconciliation、`skill_created` 等现存写回支线，D4 未闭合。
- 完整性：标题、对齐、branch、Changelog、风险与 runbook 齐全；prototype 的“覆盖 default discovery”声明与文件实物不一致。
- 命名：`workspace_skill_dirnames`、`skills_selection_mode`、`source_group` 在 design 内一致。

### 架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 归属 | 有序 root layout 放在 product composition 输入、纯 root builder 放 core、UI source projection 放 PA Gateway，符合 `SPEC.md:115-124,148-161`。selection mode 归 Agent 配置也正确；问题是它必须成为所有 allowlist mutation 的同一配置事实，现方案只画主保存链，遗漏现存写回支线（R1-C1）。长期代价是每增一个 Skill 自动启用来源就再次复活 empty/non-empty 猜测。 |
| 该不该存在 | 删除 `workspace_skill_dirnames` 会迫使 PA/CLI 把动态 workspace root 伪装成静态 roots；删除 `list_shared_skills()` 会继续让 node capability 借 repo root。两者都隐藏了真实不同的调用意图，不是空包装。`source_group` 删除后前端继续复制 path 规则，维护税更高。无新增 Issue。 |
| 深还是浅 | shared root builder 用一个输入隐藏四条 reader 的路径拼装；`list_shared_skills()` 用明确方法名隐藏“无 workspace”的特殊根集合；`source_group` 让浏览器不懂文件系统。接口均比被隐藏实现更简单。无新增 Issue。 |
| 治本还是补丁 | D1/D2 治 root 漂移，D4 用显式 mode 治 empty sentinel，而非禁止取消最后一项，方向正确。若不把 Feishu/bundle/skill-created 等写者纳入同一状态机，D4 会退化成只修配置页主链的补丁，具体债务见 R1-C1。 |

### Issues

- [R1-C1][CRITICAL] [现状分析 / 决策 4 / 接口与数据流 / feat-519-M1] `skills_selection_mode` 没有覆盖当前真实存在的 Skill allowlist 写回支线，因而“全链路携带意图”尚未形成可实施契约。Managed Feishu 激活会调用 `ensure_agent_skills_enabled()`（`src/personal_assistant/gateway/managed_channel_control.py:150-154`），它与 `skill_created` 都进入 `_enable_skills_for_agent()`（`agent_config_sync.py:961-1008,1021-1053`），再通过一个会重写完整 Agent config、当前只携 names 的 `_patch_agent_skills()`（`1062-1098`）回写 IM；静态 Feishu bundle 还有独立 YAML mutation（`src/personal_assistant/config/local_store.py:688-721`）。现有 canonical 同时规定非空 Feishu allowlist 会自动补 Lark bundle、空 allowlist 保持 default discovery（`docs/specs/gateway/agent-capabilities.md:265-290`；managed channel 入口还见 `docs/specs/gateway/external-channels.md:341-345`），而新 gateway delta 又声明 explicit empty。设计必须拍死这些自动写者遇到 absent/default/explicit-nonempty/explicit-empty 时是否保留 mode、何时把 default 转 explicit、`skill_created` 是否加入刚创建的 name，并把受影响 canonical area 和 M1 范围列全。否则两个 worker 都可“合理地”让旁路 PATCH 丢 mode、把显式空重新解释成默认发现，或让新建 Skill 永久不可见；配置页、SlashPicker 与真实回复会再次分裂。

- [R1-C2][CRITICAL] [kernel delta-spec / 决策 1、2、6] kernel `MODIFIED` 不能替换 current canonical，且保留了一个与 current code 相反的 Scenario。delta 标题是“preview、list_skills、运行时注入与 skill_view…”，canonical 标题却是“preview、list_skills 与运行时注入…”（`docs/specs/kernel/skills.md:117`）；本仓归并规则只按同名 Requirement 替换（`docs/specs/CONTRIBUTING.md:149-155`）。同时 `docs/specs/kernel/sdk-boundary.md:120-136` 仍把 `list_skills` 固定为单个 `<workspace_config_dirname>/skills + skill_search_roots`，没有 delta 修改 `workspace_skill_dirnames` / `list_shared_skills()`。更直接地，delta 的“未传 workspace_config_dirname → 技能为空”与 current `build_kernel()` 将省略值转为 `.nano`（`src/agent/sdk/kernel.py:230-242,311-318`）相反，resolver 会照常派生 `.nano/skills`（`src/agent/core/skills/discovery.py:53-84`）。不改会导致 orchestrator 归并后旧新 Requirement 并存、SDK 边界仍描述旧接口，worker 甚至可能为满足错误 Scenario 改坏外部 consumer 的现有默认。应保持原 Requirement 标题或显式 REMOVED+ADDED，补 `sdk-boundary.md` 的精确 MODIFIED，并先对 current `.nano` 默认作 drift 裁决。

- [R1-C3][CRITICAL] [IM delta-spec / 决策 3] IM 的 `MODIFIED Requirement` 没有 canonical 锚点。current `docs/specs/im/agents-nodes.md:346-384` 中“agent 能力的 skills 项携带 location”是父 Requirement“节点 runtime 能力按需向在线网关解析…”下的一个 Scenario，不是 Requirement；current Scenario 还写着前端按不同 path 分开展示同名 Skill（`382-384`），与本设计的 per-Agent first-name-wins 相反。按 `docs/specs/CONTRIBUTING.md:151-155`，现 delta 只会成为新增孤立条目，不能移除/改写旧 Scenario。下游归并会留下“低优先级同名不下发”和“同名不同路径分开展示”两份冲突 truth。应 MODIFIED 完整父 Requirement 并忠实保留其余模型/features/default-workspace Scenarios，或先把该 capability Scenario 合法拆成独立 Requirement 后再精确变更。

- [R1-C4][CRITICAL] [CLI delta-spec] CLI 的 `MODIFIED Requirement` 静默删除了 canonical 的 `Scenario: CLI 装配保持在产品包`（`docs/specs/cli/product-integration.md:20-33`），而 MODIFIED 必须提供修改后的完整条目（`docs/specs/CONTRIBUTING.md:133-143`）。本 unit 没有需求移除“CLI 只由 product factory 装配、内核不识别产品 profile”的契约；设计和代码反而继续依赖它（`src/coding_cli/commands.py:295-321`、`src/coding_cli/product.py:121-155`）。不改会让归并过程无声删掉仍成立的架构场景，后续 change 无法从 canonical 读到该边界。把该原 Scenario 原样保留在 MODIFIED 完整条目中。

- [R1-W1][WARNING] [前端原型 / 决策 4、5] design 声明 prototype 覆盖“默认发现提示”（`design.md:252-255`），但 prototype 只渲染固定“已自定义选择”（`prototype.html:126-140`），脚本也只有一个 `selected` Set 与 dirty/save 状态（`143-203`），没有 `default_discovery` 的视觉状态或“首次单项/分组编辑转 explicit”的交互。这个状态不是装饰：它是用户区分“当前发现全部”与“显式选中若干/零项”的唯一解释。若留给 worker 猜，create/detail 可能一个显示全亮、另一个显示 0 项，或三态计数让用户误以为默认发现已经被保存成 explicit。补一个 default-discovery 原型状态及其第一次编辑后的转换，并把 must-match/验收投影写清。

- [R1-W2][WARNING] [Milestones] 两个 milestone 都是可观察垂直价值，且串行依赖本身没有并行冲突；但 design 没有给出多 milestone 命中“可真并行且无交集 / 超单 worker 窗口 / 必须分阶段验证”哪一项硬触发。M1 已横跨 agent、PA、CLI、IM、Gateway 与 frontend helper，M2 又回到 PA capability/IM schema/frontend，存在同一能力链的二次接续。若不补理由，orchestrator 会承担一次无证据的交棒和重复上下文恢复。应明确以“单 worker 上下文窗口”或“必须先验证 selection/root 契约再做 prototype UI”等事实举证，并划清共有文件归属；举证不了则收敛为单 M1。

### Recommendations

- [R1-R1] 保留 `list_shared_skills()` 这个意图明确的 API；不要退回 `list_skills(None)` 或布尔参数。修订重点应放在 canonical 锚点与 selection-mode 状态机闭合，而不是推翻 root-layout 主架构。
- [R1-R2] 在修 delta 时顺手记录两处 current drift：kernel 的“省略 workspace_config_dirname 则空”和 IM 单 Agent “同名不同 location 分开展示”均与实际代码不一致；先裁决预期，再让本 unit 的 delta 成为唯一可归并目标。

### Author Resolutions

| Issue | Disposition | Evidence |
|---|---|---|
| R1-C1 | 接受并修正 | `design.md` 的现状分析、决策 4 状态表、M1 scope 已覆盖 managed/static Feishu bundle、`skill_created`、IM config operation 和本地 YAML 写回；`specs/gateway/agent-capabilities.md` 以完整 `PA 内置 skill 启动自举` MODIFIED 条目和新增 selection-mode 条目定义 absent/default/explicit-nonempty/explicit-empty 行为。 |
| R1-C2 | 接受并修正 | `specs/kernel/skills.md` 使用 canonical Requirement 原标题并保留 `.nano` 默认；新增 `specs/kernel/sdk-boundary.md` 完整修改 SDK 查询契约，声明 `workspace_skill_dirnames` 与 `list_shared_skills()`。 |
| R1-C3 | 接受并修正 | `specs/im/agents-nodes.md` 完整修改 canonical 父 Requirement，保留 features/models/reasoning/default-workspace 场景，并裁决单 Agent 内同名首项胜出、多 Agent SlashPicker 仍可按 location 区分。 |
| R1-C4 | 接受并修正 | `specs/cli/product-integration.md` 恢复 `CLI 装配保持在产品包` 原场景。 |
| R1-W1 | 接受并修正 | `prototype.html` 现在以 default discovery 为初态，首次分组或单项操作切换 explicit；`design.md` 的 must-match 原型契约同步要求该状态转换。 |
| R1-W2 | 接受并修正 | 两个 milestone 收敛为单个 `feat-519-M1 workspace-skills-selection` 端到端垂直切片，并合并全部 reviewer/worker 退出标准。 |
| R1-R1 | 接受 | 保留意图明确的 `Kernel.list_shared_skills()`，并补齐 canonical SDK boundary。 |
| R1-R2 | 接受 | `design.md` 新增 Current drift 裁决，明确 SDK `.nano` 默认和单 Agent 同名覆盖的目标状态。 |

## Round 2

### Metadata

- reviewer: `/root/feat_519_design_reviewer`
- review_mode: `full`
- mode_reason: `作者修订了共享 SDK 契约、Gateway Skill allowlist 自动写回状态机、完整 MODIFIED canonical 条目与 milestone 边界，属于核心跨模块接口和共享契约的高风险变化；因此从 closure 升级为 full，重建全部五类承重原子并重跑四角度架构进攻。`
- started_at: `2026-08-10T00:34:58+08:00`
- completed_at: `2026-08-10T00:42:44+08:00`
- duration: `7m46s`

### Verdict

Issues Found — 0 CRITICAL / 1 WARNING

### Coverage

- 首文档：`spec.md` v1；逐条复核 5 项澄清、5 段用户场景、12 个验收 Scenario 与 4 项非目标。
- 设计：`design.md` 全文；逐条核 29 项现状/约束/复用/历史/drift 断言、6 个编号决策、接口与数据流、风险回退、runbook 和单一 milestone。
- 契约增量：`specs/{cli,gateway,im,kernel}/*.md` 五份文件全部 Requirement/Scenario；逐项对照 `docs/specs/` 的精确 Requirement 标题和完整原 Scenario，并复核 `gateway/external-channels.md` 的显式非空 allowlist 边界。
- 原型：`prototype.html` 的 default-discovery 初态、首次单项/分组操作转 explicit、三态分组控制、显式 0 项保存反馈、桌面/窄屏样式和 ARIA 状态。
- 生产 grounding：从 PA/CLI product factory 正向追到 `agent.sdk.build_kernel`、core resolver 与 skill tools；从 Gateway capability、managed/static Feishu、`skill_created` 和 config operation 入口追到 IM profile/SQLite、Gateway YAML、session projection 与 SlashPicker。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 补齐 Gateway 自动写回支线、状态表、delta 与 M1 | managed Feishu 入口、static YAML、`skill_created`、`_patch_agent_skills()` 和 config operation 已进入设计状态机及单 M1；Gateway delta 也完整修改现有内置 Skill Requirement。但 legacy non-empty 的 mode 持久化时点仍有两句冲突，见 R2-W1。 | reopened_as_R2-W1 |
| R1-C2 | 修正 kernel 标题、`.nano` drift，新增 SDK-boundary delta | `specs/kernel/skills.md:5` 精确命中 canonical 标题；`specs/kernel/sdk-boundary.md:5` 精确命中 SDK 查询 Requirement，且保留原场景并增加 `list_shared_skills()`；`.nano` 裁决与 `build_kernel()` 当前默认一致。 | closed |
| R1-C3 | 完整 MODIFIED IM 父 Requirement 并裁决同名 drift | `specs/im/agents-nodes.md:5-45` 完整保留 features/provider/reasoning/default-workspace 场景，修改 location 场景并新增旧节点降级；单 Agent first-root-wins 与 Registry current code 一致。 | closed |
| R1-C4 | 恢复 CLI 原场景 | `specs/cli/product-integration.md:11-13` 原样保留“CLI 装配保持在产品包”，其余原场景也仍在。 | closed |
| R1-W1 | 原型增加 default→explicit | `prototype.html:130-141,151-164,169-214` 初态为 default 且所有当前候选有效选中；首次 pill/group 操作先转 explicit，再改变集合，保存 0 项也有明确反馈。 | closed |
| R1-W2 | 收敛为单 M1 | `design.md:324-328` 只保留 `feat-519-M1 workspace-skills-selection`，reviewer/worker 两轨覆盖完整端到端链；实际 skeleton 只有该 milestone 的 `.gitkeep` 会进入版本控制。 | closed |
| R1-R1 | 保留 `list_shared_skills()` | 独立 API 同时出现在 D6、SDK 接口表、两份 kernel delta 和 M1，未退回 `list_skills(None)`/布尔参数。 | adopted |
| R1-R2 | 记录两处 current drift 裁决 | `design.md:54-57` 明确保留 SDK `.nano` 实现事实，并把单 Agent 同名裁决为 Registry 首项胜出、多 Agent SlashPicker 才按 location 区分。 | adopted |

### 现状断言核实台账

| ID | 现状断言 | 本轮独立证据与结论 |
|---|---|---|
| A1 | PA 为一个 workspace root 叠加三项共享 roots | 成立：`src/personal_assistant/product.py:40-52,418-427`；生产 composition 仍调用该 factory。 |
| A2 | CLI 只有原生 workspace、`~/.nanocode` 与 `~/.codex` Skill roots | 成立：`src/coding_cli/product.py:30-43,143-154`。 |
| A3 | `make_skill_resolver()` 是 list/preview/runtime 共用构造入口 | 成立：helper 在 `src/agent/core/skills/discovery.py:53-84`；SDK list/preview 调用见 `src/agent/sdk/kernel.py:1873-1889,2193-2211`，runtime 由同一 build 参数注入 engine（`730-741`）。 |
| A4 | Skill tools 仍独立重建 roots | 成立：`src/agent/core/skills/root_resolver.py:55-104`，writer/search roots 在这里另行构造。 |
| A5 | Registry 按 root 扫描、metadata name 首项胜出并按 name 排序 | 成立：`src/agent/core/skills/registry.py:41-58,64-81`。 |
| A6 | PA capability 只有 location/default_on、无 `source_group` | 成立：`src/personal_assistant/reporter/upstream_reporter.py:135-154`。 |
| A7 | 当前 selector 以 path/default_on 猜三组，只有单 pill 操作 | 成立：`src/IM/frontend/src/features/settings/agents/skill-source-selector.tsx:10-23,49-69,89-120`。 |
| A8 | create/detail 共用 selector 和 `string[]` draft | 成立：生产挂载点仍为 `agent-create-page.tsx:932-946` 与 `agent-detail-page.tsx:1828-1841`。 |
| A9 | Gateway 空 skills 被投影成 SDK `None` | 成立：`src/personal_assistant/gateway/session_composition.py:58-74,85-90`。 |
| A10 | IM profile/SQLite、Gateway YAML/operation/live payload 目前只携 names | 成立：`src/IM/domain/models.py:104-125`、`src/IM/infra/repositories/agents.py:130-185`、`src/personal_assistant/config/local_store.py:167-214,800-818`、`src/personal_assistant/gateway/agent_config_sync.py:78-110,812-825,1347-1365`。 |
| A11 | SlashPicker 把空 whitelist 当全部 capabilities | 成立：`src/IM/frontend/src/features/chat/components/slash-candidates.ts:38-51`，生产消费在 `chat-workspace-page.tsx:407`。 |
| A12 | allowlist 有 managed/static Feishu 与 `skill_created` 三类自动写回支线 | 成立：managed 入口 `managed_channel_control.py:150-154`；`skill_created` 入口与共用 mutation 在 `agent_config_sync.py:961-1053`；静态 YAML mutation 在 `config/local_store.py:688-721`，IM mirror 的静态 bundle 分支在 `agent_config_sync.py:1115-1138`。 |
| A13 | node capability 把 repo root 当 workspace fallback | 成立：node projection 调 `_skills_from_kernel(..., None)`（`upstream_reporter.py:157-173`），`Kernel.list_skills(None)` 回退 `_repo_root`（`agent/sdk/kernel.py:1862-1888`）。 |
| A14 | 产品只能经 SDK，IM 不调 agent，core 不反依赖 platform | 成立：`SPEC.md:115-124,148-161`；新 layout 仍由 product 传入 SDK/core。 |
| A15 | Agent Workspace 由 owning Gateway 解析 | 成立：current IM canonical `docs/specs/im/agents-nodes.md:346-352` 与 Gateway agent capability 调用链一致。 |
| A16 | Skill name 是 allowlist 身份，root order 是同名权威 | 成立：配置存 names 见 A10；first-root-wins 见 A5。 |
| A17 | `skill_manage` 原生 workspace root 写入、extra roots 只读 | 成立：`src/agent/core/skills/root_resolver.py:85-103` 把 `agent_root` 固定为 writer，同时追加 extra roots 到 registry。 |
| A18 | 保存配置不打断当前回复，后续 admission 才投影新配置 | 成立：`docs/specs/gateway/agent-capabilities.md:48-74` 是 current contract，session projection 从 captured snapshot 生成完整 runtime（`session_composition.py:45-74`）。 |
| A19 | 缺失 root 自然跳过，无效条目沿用现有 parser | 成立：`src/agent/core/skills/registry.py:41-58,64-81`；没有需要兼容目录专属的错误分支。 |
| A20 | `make_skill_resolver()` 是扩展读取路径的现成收敛点 | 成立：A3，且位于 core、未形成 core→sdk 反向依赖（`discovery.py:26-28,60-63`）。 |
| A21 | `ResolvedSkillRoots` 已分离 writer 与 search roots | 成立：`src/agent/core/skills/root_resolver.py:17-39,92-103`。 |
| A22 | Gateway→IM 已透传 location，适合增补来源字段 | 成立：Gateway 投影 `upstream_reporter.py:135-154`；current IM capability 父契约在 `docs/specs/im/agents-nodes.md:346-384`。 |
| A23 | `SkillSourceSelector` 是 create/detail 共用 draft seam | 成立：A8；组件回调只更新同一 selected names（`skill-source-selector.tsx:25-35,67-70`）。 |
| A24 | 当前 Agent 配置使用紧凑卡片/11px 标题/pill | 成立：`skill-source-selector.tsx:72-120`；prototype 沿用同一信息密度。 |
| A25 | bugfix-431 已把 resolver 构造下沉 core 以消除读取漂移 | 成立：current helper 注释与调用链见 A3/A20；未新造 product 专属 resolver。 |
| A26 | feat-430 保持 names 为启用身份、location 为展示/聚合信息 | 成立：current SlashPicker 先按 whitelist name 过滤，再按 location 聚合（`slash-candidates.ts:38-89`）。 |
| A27 | PA 已支持 `~/.claude`/`~/.codex` 全局兼容 roots | 成立：`src/personal_assistant/product.py:40-52`。 |
| A28 | canonical 的“省略 workspace_config_dirname 则空”与 SDK current `.nano` 默认 drift | 成立：canonical 旧文在 `docs/specs/kernel/skills.md:126-129`，生产 `build_kernel()` 在 `src/agent/sdk/kernel.py:230-242,311-318` 注入 `.nano`。 |
| A29 | canonical 的单 Agent 同名多 location 展示与 Registry current 首项胜出 drift | 成立：旧 canonical `docs/specs/im/agents-nodes.md:382-384` 对比 Registry `src/agent/core/skills/registry.py:41-58`；多 Agent SlashPicker 的 location 聚合另见 A26。 |

### 决策核实台账

| 决策 | 拍死/歧义/自洽/spec 驱动 | 结论与证据 |
|---|---|---|
| D1 有序 workspace layout | 两产品精确顺序、旧 consumer fallback、产品/core 归属均拍死 | 通过。覆盖 `spec.md:49-79`，且现有单目录限制由 A1-A4 证实。 |
| D2 所有 reader 共用 sequence、writer 固定原生 root | list/preview/runtime/view 与 manage writer 的边界明确 | 通过。复用 A3/A4/A21 的现成 seam，没有改变写入目标或格式。 |
| D3 Gateway 输出结构化 `source_group` | 三值映射、location/default_on 关系与旧节点 fallback 明确 | 通过。PA 投影字段、IM 透传、selector consumer 均闭合。 |
| D4 `default_discovery` / `explicit_allowlist` | 字段、枚举、legacy 映射、各持久边界、session/SlashPicker 与自动 writer 状态表均已出现 | 状态覆盖已完整，但 legacy non-empty 自动 mutation 是否持久化 mode 与同节迁移规则矛盾，见 R2-W1。 |
| D5 分组标题三态微交互 | 作用于当前可见组、保留不可见 names、草稿/保存边界和 a11y 已拍死 | 通过。prototype 实物覆盖 default/explicit、none/partial/all 与 pill 联动。 |
| D6 node 仅查 shared roots | 调用意图、API 名、创建后 agent-level 权威入口和回退均明确 | 通过。A13 证明需修 current fallback；独立 `list_shared_skills()` 不是假抽象。 |

### spec 约束逐条台账

| 约束 | design 落点 | 结论 |
|---|---|---|
| Q1 两产品支持三个指定兼容根 | D1、两产品 layout、M1 | 覆盖。 |
| Q2 统一优先级、首项胜出 | D1/D2、Registry 保持 | 覆盖。 |
| Q3 PA 显式选择后下一轮生效；CLI 新会话发现 | D4 主流程、M1 两轨 | 覆盖。 |
| Q4 缺失/空/无效条目沿用现有行为 | A19、风险表、M1 | 覆盖。 |
| Q5 分组批量、保留单项、视觉克制 | D5、prototype、M1 | 覆盖。 |
| 用户场景 1：同项目无需复制 Skill | D1 两产品 workspace roots | 覆盖。 |
| 用户场景 2：PA 候选/保存/下一轮且显式选择不静默扩宽 | D3/D4、主时序 | 覆盖。 |
| 用户场景 3：CLI 同批兼容 Skill 与可预测覆盖 | D1/D2、CLI delta | 覆盖。 |
| 用户场景 4：整组操作且不笨重 | D5、prototype | 覆盖。 |
| 用户场景 5：目录缺失/空仍正常 | A19、风险表 | 覆盖。 |
| R1-S1 PA 工作区/主目录兼容候选 | D1/D3、Gateway delta | 覆盖。 |
| R1-S2 CLI 工作区/主目录兼容候选 | D1、CLI delta | 覆盖。 |
| R1-S3 原生与既有兼容来源保持 | D1 追加布局、旧 consumer fallback | 覆盖。 |
| R2-S1 PA 同名最优先来源且 UI/runtime 同版 | D1/D2、PA 时序 | 覆盖。 |
| R2-S2 CLI 同名最优先来源 | D1/D2 | 覆盖。 |
| R3-S1 新兼容 Skill 不扩宽已有显式选择 | D4 explicit 规则 | 覆盖。 |
| R3-S2 保存后下一轮使用并保留聊天历史 | D4、session admission、M1 | 覆盖。 |
| R4-S1 分组批量后仍可单项调整 | D5、prototype、M1 | 覆盖。 |
| R4-S2 三态如实反映草稿/运行边界 | D4/D5、prototype | 覆盖。 |
| R4-S3 桌面/移动自然融入 | D5、prototype responsive CSS、M1 | 覆盖。 |
| R5-S1 缺兼容目录不失败 | Registry skip、M1 | 覆盖。 |
| R5-S2 无有效 Skill 不误报失败 | A19、风险表 | 覆盖。 |
| N1 不迁移/复制/改写 Skill | D1/D2 只读 roots、writer 固定 | 不越界。 |
| N2 不改格式/工具权限/skill_view 行为或绕过显式选择 | Registry/工具行为保持，D2/D4 只改 roots 与 selection intent | 不越界。 |
| N3 不发现其他 Claude/Codex 资源 | layout 目录只派生 `skills` | 不越界。 |
| N4 控件细节在 design 阶段决定 | D5/prototype | 合规。 |

### delta-spec 逐条台账

| Delta 条目 | canonical 对账 / Scenario 完整性 / 可观察性 | 结论 |
|---|---|---|
| CLI MODIFIED `CLI 自有装配定义产品 prompt、工具集合和扩展目录` | 精确命中 `docs/specs/cli/product-integration.md:20`；完整保留两个原 Scenario，并新增 workspace/global Claude 与缺失目录场景；THEN 均为 CLI consumer 可观察集合/启动结果 | 合格。 |
| Gateway MODIFIED `PA 内置 skill 启动自举` | 精确命中 `docs/specs/gateway/agent-capabilities.md:224`；10 个原场景全部保留或按 mode 完整改写，另拆出 explicit-empty 场景；与 `external-channels.md:341-345` 的 explicit non-empty 边界一致 | 合格；设计文字仍有 R2-W1 的持久化时点歧义。 |
| Gateway ADDED `PA Agent 从有序的工作区与全局 Claude/Codex 兼容根发现 Skill` | current canonical 无同义 Requirement；4 个场景覆盖 agent capability/runtime/view、同名、缺失目录和 node shared-only，均为 PA/IM 可观察结果 | 合格。 |
| Gateway ADDED `PA Agent 配置区分默认发现与显式空 Skill 选择` | 新增选择意图契约；4 个场景覆盖 explicit empty、legacy empty、自动 writeback 和 `skill_created`，THEN 为下一轮/持久配置可观察结果 | 合格；与 D4 状态表一致。 |
| IM MODIFIED `节点 runtime 能力按需向在线网关解析,不入库快照` | 精确命中 `docs/specs/im/agents-nodes.md:346`；原 features/provider/reasoning/default-workspace 六类内容全部保留，location 场景按 drift 裁决修改并新增旧 payload 降级 | 合格。 |
| IM ADDED `Agent 配置页可按 Skill 来源分组批量调整选择` | 3 个 UI 场景覆盖批量后单项、三态/保存边界与窄屏；THEN 全为浏览器可观察结果 | 合格。 |
| IM ADDED `配置 API 表达默认 Skill discovery 与显式 allowlist 的不同意图` | 与现有 Agent 配置 Requirement 平行补充新字段语义，不与旧条目冲突；显式空页面/下一轮场景可观察 | 合格。 |
| Kernel MODIFIED `同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致` | 精确命中 `docs/specs/kernel/skills.md:117`；3 个原场景均保留/按 `.nano` current drift 修正，新增多 workspace roots 场景，并把 `skill_view` 纳入同源结果 | 合格。 |
| Kernel ADDED `Skill 管理写入不因兼容读取 root 改变目标目录` | 新增 SDK consumer 读/写结果契约；不写内部函数调用断言 | 合格。 |
| Kernel ADDED `SDK 消费者可在没有真实 workspace 时只查询共享 Skill roots` | 与 node prospective-Agent 需求对应，返回集合是 SDK consumer 可观察结果 | 合格。 |
| Kernel SDK MODIFIED `Kernel 提供单项中立能力查询` | 精确命中 `docs/specs/kernel/sdk-boundary.md:120`；原 3 个场景全部保留/扩展，新增 `list_shared_skills()` 场景，完整声明 workspace layout→shared roots 顺序 | 合格。 |

### Milestone 台账

| Milestone | 垂直价值 / 范围 / 两轨退出 | 结论 |
|---|---|---|
| feat-519-M1 `workspace-skills-selection` | 单一端到端切片覆盖 agent/SDK、PA/CLI roots、IM/Gateway mode 持久链、全部自动 Skill 写者、capability/source group、create/detail/SlashPicker、原型与测试；reviewer 轨覆盖真实产品价值，worker 轨覆盖同源解析、全状态恢复和 a11y | 单 M1 合格，无横切拆分、并行碰撞或重复交棒；只有 D4 文句冲突需先消歧（R2-W1）。 |

### 整体判断

- 上层可读性：核心综述、总图和六条一句话决策能直接串起 root layout、来源投影、selection mode、分组 UI 与 prospective-Agent 查询；没有被逐步实现细节淹没。
- 接口与数据流：`product → SDK/core resolver → capability → IM selector → config operation/YAML → next turn/SlashPicker` 主链闭合；managed/static Feishu 与 `skill_created` 支线也已进入同一状态表。
- 常规完整性：标题、对齐、branch、Changelog、风险/回退、真栈 runbook、prototype 契约和单 M1 齐全；五份 delta 均可按 current 归并规则落入精确 canonical anchor。
- 唯一剩余歧义是 legacy non-empty 的自动写回是否允许成为 mode 的首次持久化；它不会推翻架构，但必须在 worker 开始前统一一句话契约。

### 架构进攻

| 角度 | 主动攻击与结论 |
|---|---|
| 归属 | 有序 workspace layout 由 PA/CLI 产品声明、root sequence 由 core 解析、SDK 暴露中立查询、PA Gateway 投影来源、IM 只持久化/透传配置，组合后仍符合 `platform → core`、`sdk → core + platform` 与产品只 import SDK 的红线。selection mode 放在 Agent 配置并贯穿 IM/Gateway 而非塞进 Kernel，也避免内核理解产品持久化。无错放层；R2-W1 是同一 owner 内的迁移措辞冲突。 |
| 该不该存在 | 删除 `workspace_skill_dirnames` 会让动态 workspace roots 再次被伪装成 build-time shared roots；删除 `list_shared_skills()` 会保留 repo-root prospective-Agent 泄漏；删除 `source_group` 会让浏览器永久复制路径品牌规则。三者都隐藏真实不同意图，并非一处实现套假接口。无新增 Issue。 |
| 深还是浅 | 一个 root-sequence builder 收敛 list/preview/runtime/view/tool 的多处拼装；`list_shared_skills()` 以无参数方法隐藏 shared-only registry；`source_group` 把文件系统分类从前端移回 owning Gateway。接口均显著小于被隐藏规则，且复用现有 resolver/Registry/配置 operation，没有第二套持久化通道。无新增 Issue。 |
| 治本还是补丁 | D1/D2 治动态 root 与 reader 漂移，D4 治 empty-list sentinel，D6 治 node-level repo fallback；自动 writeback 也已纳入状态机而非给页面单独打补丁。若不消除 R2-W1，长期代价是 legacy non-empty 配置在 IM DB/YAML/receipt 中出现两种同语义表示，后续 writer 会继续猜迁移时点；除此之外未发现临时兼容层冒充长期方案。 |

### Issues

- [R2-W1][WARNING] [决策 4：迁移与自动写回状态机] legacy absent + non-empty 配置的 mode 首次持久化时点仍自相矛盾。迁移规则写“只在用户成功保存新配置时持久化明确 mode”（`design.md:168`），但同节状态表要求 managed/static Feishu 或 `skill_created` 更新 legacy non-empty names 后结果为 explicit（`design.md:175-183`），并进一步要求 `_patch_agent_skills()` 与静态 YAML mutation “保留或显式设置” mode（`design.md:185`）；Gateway delta 也要求自动写回显式携带 mode（`specs/gateway/agent-capabilities.md:120-129`）。不改时，worker 可合理地选择“自动 names mutation 后仍保留 absent”或“把 effective explicit 固化”，导致 IM DB、Gateway YAML、operation fingerprint/receipt 对同一次调和产生不同 durable shape，恢复与测试无法共享唯一预期。请拍死为其中一个规则；按现有状态表的整体方向，最小修正是把第 2 条改成“无配置写入时不做 eager migration；任一成功 names mutation/用户保存都持久化当时的 effective mode”。

### Recommendations

- [R2-R1] 只消除 R2-W1 的一句话冲突，不需要改 root-layout、`list_shared_skills()`、delta 架构或重新拆 milestone；修订后复核可采用 closure mode。

### Author Resolutions

| Issue | Disposition | Evidence |
|---|---|---|
| R2-W1 | 接受并修正 | `design.md` 决策 4 的迁移规则现明确：无配置写入时不做 eager migration；用户保存或任一自动 writer 成功修改 names 时，都把当时的 effective mode 一并持久化。该规则与同节状态表、Gateway delta 及 operation/YAML 持久边界一致。 |
| R2-R1 | 接受 | 未改 root-layout、`list_shared_skills()`、delta 架构或 milestone，仅消除持久化时点冲突。 |

## Round 3

### Metadata

- reviewer: `/root/feat_519_design_reviewer`
- review_mode: `closure`
- mode_reason: `R2 后的受审语义变化可封闭为决策 4 第 2 条的一处措辞消歧；它不改变状态表、跨模块接口、delta-spec、prototype 或 milestone，因此仅复核 R2-W1 closure 与直接一致性证据。`
- started_at: `2026-08-10T00:43:50+08:00`
- completed_at: `2026-08-10T00:44:30+08:00`
- duration: `40s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-W1 | 无配置写入不 eager migrate；用户保存或自动 writer 成功修改 names 时持久化 effective mode | 已闭环：`design.md:168` 现在明确区分“无写入保持 absent”与“发生用户保存/names mutation 时持久化”。这与状态表中 legacy absent + empty 不物化、legacy absent + non-empty 发生 mutation 后成为 explicit、default 不物化、explicit 保持 mode 的各行（`design.md:175-185`）一致，也与 Gateway delta 的自动写回携带 mode、`skill_created` 按当前 mode 更新（`specs/gateway/agent-capabilities.md:120-129`）一致。worker 不再需要猜 IM DB、Gateway YAML 或 operation receipt 的 durable shape。 | closed |
| R2-R1 | 不改其他架构，只做最小消歧 | 已核：当前修订没有改变 root-layout、`list_shared_skills()`、delta 契约、prototype 或单 M1；Round 2 的完整台账仍有效。 | adopted |

### Issues

None.

### Recommendations

None. Gate 2 已达到 `Approved — 0 CRITICAL / 0 WARNING`，可进入 `change-orchestrator`。

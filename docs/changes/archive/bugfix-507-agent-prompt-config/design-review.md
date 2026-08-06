# Design Review: bugfix-507-agent-prompt-config

> **Superseded.** 本记录审查的是“迁移旧文本到 Custom Instructions”的旧设计；用户随后
> 明确要求不兼容旧版本。它只保留为决策变更的历史证据，不能作为当前 Gate 2 结论。

## Round 1

### Metadata

- reviewer: `/root/bugfix_507_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 requires a complete independent review.`
- started_at: `2026-08-06T15:02:22+08:00`
- completed_at: `2026-08-06T15:08:31+08:00`
- duration: `6m 09s`

### Verdict

Issues Found — 2 CRITICAL / 0 WARNING

### Coverage

- Inputs read in full: `incident.md`, `design.md`, both delta-specs, current IM/Gateway specs, kernel prompt spec, spec contribution rules, and the applicable topology constraints in `SPEC.md`.
- Production paths traced from IM HTTP/WS wiring through the actual Gateway config-sync, local YAML, prompt factory, session runtime, preview, and conversation relay paths. This was not limited to the files named by the design: the static Gateway registration persistence path was also traced.
- Full inventory checked: 10 current-state assertions, 5 decisions, 3 incident requirements / 5 scenarios, 2 clarifications, 3 non-goals, 3 delta entries, and 2 milestones.

### 核实台账

#### 现状断言

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| A1 IM profile 有两个字段 | `AgentProfile` 同时声明 `system_prompt` / `custom_prompt`，repository 的读写 SQL 也同时映射它们：`src/IM/domain/models.py:105-130`、`src/IM/infra/repositories/agents.py:24-35`、`259-339`。 | 成立 |
| A2 IM API/create/live merge 仍公开 legacy | 响应和 PATCH request 都含 `system_prompt`，live merge 同样读取它；node create 也接受并转发它：`src/IM/api/routes/agents.py:26-71`、`208-260`、`410-443`、`src/IM/api/routes/nodes.py:78-90`、`252-307`。 | 成立 |
| A3 SQLite schema/migration 仍保存 legacy | 新 schema 含两个 prompt 列，现有 migration 只补列且未做收敛：`src/IM/infra/db.py:35-67`、`611-666`。 | 成立 |
| A4 Gateway YAML 是双字段的真实存储实现 | 类型、parser、serializer 都读写 `system_prompt` 与 `custom_prompt`：`src/personal_assistant/config/local_store.py:164-220`、`775-845`、`1063-1188`。 | 成立 |
| A5 config.sync 的真实数据流 | WS `config.sync` 只通知 `{agent_id, profile_version}`：`src/IM/ws/gateway/control.py:84-92`；Gateway 随后拉 `GET .../config?source=mirror`：`src/personal_assistant/config/sync_client.py:40-52`、`src/personal_assistant/gateway/agent_config_sync.py:635-643`，解码后先写 YAML 再发布 live catalog：`518-578`、`580-614`。 | 成立；design 的“sync body 携带 profile”表述不符合实际，见 R1-C1 |
| A6 运行时真正采用 legacy 在前 | `prompt_for()` 从 Agent 配置读两字段，并依次生成 `pa.system_prompt_override` 与 `pa.user_custom`：`src/personal_assistant/product.py:289-350`；运行时 `project_agent_runtime()` 以此 factory 建 PromptSlots：`src/personal_assistant/gateway/session_composition.py:38-66`。 | 成立 |
| A7 preview 与 runtime 的分叉来源 | preview 的 imaginary agent 只赋 `custom_prompt` 后调用同一个 `prompt_for()`：`src/personal_assistant/gateway/composition.py:132-167`；前端也只送 draft custom/features/tools/skills：`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:142-157`。 | 成立 |
| A8 conversation provenance 复制 legacy 正文 | conversation 表、snapshot 和建表 INSERT 都含 `config_system_prompt`：`src/IM/infra/db.py:35-52`、`src/IM/infra/repositories/conversations.py:23-30`、`123-147`、`834-877`。 | 成立 |
| A9 relay 的 legacy snapshot 非 prompt payload 必需 | relay payload 只投影 profile version：`src/IM/application/relay_service.py:102-122`，但选择逻辑仍查询/比较 `config_system_prompt` 与 profile `system_prompt`：`363-480`、`628-632`。 | 成立；移除正文、保留 id/version 的方向正确 |
| A10 Kernel override 与 PA profile 分层 | core 在 hook override、frozen session prompt 和 sections 间独立决策：`src/agent/core/agent/runtime.py:438-489`；产品仍仅能经 `agent.sdk`，且 IM/PA 不互 import：`SPEC.md:156-161`。 | 成立 |

#### 决策

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| D1 custom_prompt 为唯一公开接口 | 与 incident 的唯一可见入口不变量一致（`incident.md:95-106`），也切中当前双字段实际路径 A1-A6；但缺少 Gateway-first bootstrap 的归属规则，不能无歧义实施。 | R1-C1 |
| D2 双持久边界合并且幂等 | 四种合并表保住了当前 `legacy -> custom` 顺序（`src/personal_assistant/product.py:342-350`），但没有定义 local YAML 迁移如何进入 IM 权威 profile，且 `load_local_config()` 本身不回写文件（`src/personal_assistant/config/local_store.py:568-611`）。 | R1-C1 |
| D3 stable preview | 复用现有 `prompt_for()` + SDK preview 是最短同源路径，且与 kernel 的 same-PromptSlots 契约一致：`docs/specs/kernel/prompts.md:35-54`。 | 成立 |
| D4 删除 prompt provenance 正文 | 当前 relay payload 不消费该正文（A9）；仅保留 agent id/version 不改变路由语义并减少敏感副本。 | 成立 |
| D5 两个 vertical milestones | D1/D2 明定删除公共 profile/API/config 字段，但 M1 与 M2 对这同一 cutover 的归属重叠，M2 也没有独立用户价值。 | R1-C2 |

#### Incident 约束、澄清与非目标

| 原子 | 对齐检查 | 结论 |
|---|---|---|
| Q1 / 专属说明唯一可见 | D1 的目标正确，但 R1-C1 未封闭 static-YAML 到 IM 的首次收敛。 | R1-C1 |
| Q2 / 独立完成 full bugfix | unit 有 incident、design、deltas 与 milestones，流程形状具备。 | 成立 |
| R1 新建/编辑无第二入口 | D1、IM delta modified requirement 覆盖；切断 live snapshot 与 config sync 需在同一可交付 slice 落定。 | R1-C2 |
| R2 保存仅影响该 Agent 的下一新回复 | Gateway delta 保留 complete runtime / history 语义：`specs/gateway/agent-capabilities.md:7-33`。 | 成立 |
| R3 preview 含 saved/draft stable config | D3、IM delta added requirement 已覆盖，并使用现有同源 factory。 | 成立 |
| R4 preview 明示 runtime exclusions | D3 与 IM delta `44-47` 覆盖；现有 i18n 也已有群聊/记忆排除文案：`src/IM/frontend/src/i18n/en.json:381-384`。 | 成立 |
| R5 legacy 有效说明升级后可审阅且不重复 | 合并表覆盖 DB/YAML already-known dual value；Gateway-first empty-IM bootstrap 未覆盖。 | R1-C1 |
| 非目标：不改公共 PA/群聊/记忆/模型提示 | D1-D4 保留 sections factory与 runtime-only tail，未引入这些改动。 | 成立 |
| 非目标：保留 Kernel 内部 override | D1 与 D4 只切 product profile，A10 确认其路径独立。 | 成立 |
| 非目标：不新建角色 UI | D3 只调整既有 preview / i18n，测试策略也明确不新增 UI。 | 成立 |

#### Delta-spec

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| IM MODIFIED `Agent 配置中心...` | 精确替换 canonical 同名 Requirement；保留其既有场景并增加 consumer-observable 的字段不出现语义，目标 area 正确：`docs/specs/im/agents-nodes.md:11-55`。 | 成立 |
| IM ADDED `Agent 专属说明...` | 是新、稳定且用户可观察的契约；Scenario 无内部实现符号，覆盖空值、preview、迁移顺序：delta `36-53`。 | 成立 |
| Gateway MODIFIED `Agent 运行能力更新...` | 精确替换 canonical 同名 Requirement，消费者是 Gateway/用户，明确 custom 为追加段、不能走 Kernel override；现有完整配置语义未被静默删减：`docs/specs/gateway/agent-capabilities.md:47-89`。 | 成立 |

#### Milestone

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| M1-visible-custom-cutover | 有 IM→Gateway→next reply 的用户旅程和双轨退出标准，但范围包含 API/profile/config sync/local store 的 field migration。 | 与 M2 重叠，R1-C2 |
| M2-legacy-retirement | conversation provenance 清理可随 M1 同做；表中又写 public profile/Gateway protocol retire，与 M1 和 D1 重叠。它是 M1 完整性前提的清理层而非可独立发布的垂直体验。 | R1-C2 |

### 架构进攻

| 角度 | 独立判断 | 结论 |
|---|---|---|
| 归属 | 将 profile 迁移放 SQLite/YAML persistence，而不是 UI/HTTP handler，归属正确；但 Gateway-first 注册时 IM 的 first-seen profile 才是后续 sync 权威，必须定义它如何收到迁移后的 canonical 值。当前 register 仅传 workspace/skills/tools：`src/personal_assistant/reporter/upstream_reporter.py:245-276`、`src/IM/ws/gateway/sessions.py:273-330`。 | R1-C1 |
| 该不该存在 | 复用 `prompt_for()`，不新建 preview assembler；不需要为这次修复增加抽象层。 | 通过 |
| 深/浅 | 单个 local canonicalization helper 可同时服务 YAML parser 和 mirror HTTP decoder，能集中顺序/幂等规则；前提是明确谁调用、何时持久化、谁可覆盖谁。否则 helper 只把复杂度藏在两条未定义的同步路径后。 | R1-C1 |
| 治本/补丁 | 从持久化/API/runtime 链移除 legacy，而非仅隐藏前端，是治本；但把公共合同删除和 provenance 清理分到重叠 M1/M2 会让 worker 在中间态猜测，不能作为安全 cutover。 | R1-C2 |

### Issues

- [R1-C1][CRITICAL] [决策 1/2；接口与数据流；数据迁移、兼容与回退] Gateway YAML legacy 的迁移没有定义首次接入空 IM 时的权威来源、传输和持久化顺序，且把真实的“通知后 mirror pull”误写为携带 profile 的 `config.sync` body。当前 Gateway 注册只上报 agent id/workspace/skills/tools，IM 对首次 agent 自行生成 `system_prompt`、`custom_prompt=None`（`src/personal_assistant/reporter/upstream_reporter.py:245-276`; `src/IM/ws/gateway/sessions.py:273-330`; `src/IM/infra/gateway_persistence.py:150-192`）。紧接着 Gateway 会以该 IM mirror 覆盖并持久化本地 config（`src/personal_assistant/gateway/agent_config_sync.py:462-504`, `580-614`, `635-643`）。因此，一个只在旧 YAML 中有有效 `system_prompt` 的既有 Agent，在新 Gateway 连接空 IM 后可能被空/默认 profile 覆盖，违背 incident 的升级不丢约束场景；而 `load_local_config()` 不自行保存，也不能兑现文中“load 后写回 canonical”的承诺（`src/personal_assistant/config/local_store.py:568-611`）。不改，下游 worker 会各自猜是 IM、YAML 还是首次 sync 胜出，造成角色丢失、重复或永远留在 legacy 文件。

- [R1-C2][CRITICAL] [决策 5；Milestones M1/M2] 两个 milestone 对同一个 public-contract cutover 互相矛盾、范围交叠。D1 要从 AgentProfile、create/update API、config.sync、AgentWorkspaceConfig 和 runtime projection 删除字段（design `74-80`）；M1 已把 IM API/profile migration 与 Gateway config/sync/local store 纳入范围（`176`），M2 又声明删除“公共 profile 和 Gateway 配置协议中遗留的 legacy 存储/字段”（`118-121`, `177`）。M1 的“空输入无额外 profile 人设”和可信 preview 不可能在仍可由 public/live/config-sync 入口复活 legacy 的情况下完成；M2 则只剩 removal cleanup，不能独立交付用户价值。 不改，orchestrator 无法给 worker 无冲突的文件边界和验收门：M1 可能留下能复活的字段，或 M2 被迫重改 M1 已交付的同一 contract。

### Recommendations

- [R1-R1] 先修 R1-C1：在 design 中明确三种迁移输入的同一 precedence/terminal owner（既有 IM SQLite、旧 Gateway YAML、旧 IM mirror），并补 Gateway-first/empty-IM 的 canonical seed 或一次性上送/确认流程；规定 migration 成功后立即写回 YAML 的调用点。增加覆盖“旧 YAML nonempty + 空 IM 首次 register/reconcile + 重启”的跨进程验收，连同 both-text 顺序和重试幂等一起断言。
- [R1-R2] 先修 R1-C2：要么收敛为一个端到端 M1（profile/API/sync/runtime/preview/provenance/physical migration 同次关闭），要么明确 M1 已永久切断所有公开/runtime ingress，M2 仅做无 contract 重叠且确有独立可观察价值的 legacy-data retirement；重写两者范围、退出标准和依赖后再复审。

### Author Resolutions

| Issue | Resolution | Evidence / changed atoms |
|---|---|---|
| R1-C1 | Accepted. 明确 `config.sync` 是通知、mirror GET 是 profile 传输；新增 `node.register.agent_custom_prompts` 作为 empty-IM / first-seen 的唯一 canonical seed。IM existing profile 持续权威，Gateway old YAML 在 load 时只转为内存 canonical 值，成功 reconcile/persist 才写回 YAML。 | `design.md` 决策 2、接口与数据流、数据迁移、测试策略、M1；IM delta 新增 first-register Scenario。 |
| R1-C2 | Accepted. 删除 M2，将 profile/API/storage/runtime/preview/provenance 一次性收敛为 M1 atomic cutover；worker 可在 M1 内按 roadpoint 实施。 | `design.md` 决策 5、Milestones、风险表；删除 `M2-legacy-retirement/` 空目录。 |

## Round 2

### Metadata

- reviewer: `/root/bugfix_507_design_reviewer`
- review_mode: `full`
- mode_reason: `R1-C1 changes the cross-process node.register data flow and ownership; R1-C2 changes the shared public-contract milestone boundary. Both require a full re-check of all load-bearing atoms and all architecture attack angles.`
- started_at: `2026-08-06T15:16:07+08:00`
- completed_at: `2026-08-06T15:17:52+08:00`
- duration: `1m 45s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- Inputs read in full: current `incident.md`, revised `design.md`, both revised delta-specs, and Round 1 including the author resolutions.
- Re-traced the production registration-before-reconcile path, not merely the proposed field name: `UpstreamReporter.send_register()` builds the frame before the post-ACK `ConnectionReadyCoordinator` invokes `reconcile_all_agents()` (`src/personal_assistant/reporter/upstream_reporter.py:245-276`; `src/personal_assistant/ws/im_connection.py:412-424`; `src/personal_assistant/gateway/connection_ready.py:69-110`).
- Full inventory checked: 10 current-state assertions, 5 decisions, 3 incident requirements / 3 user scenarios / 2 clarifications / 3 non-goals, 3 delta entries, and the single M1 milestone.

### 核实台账

#### 现状断言

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| A1 IM profile 双 prompt 字段 | `AgentProfile` 与 repository 映射仍同时有 `system_prompt` / `custom_prompt`：`src/IM/domain/models.py:105-130`、`src/IM/infra/repositories/agents.py:24-35`、`259-339`。 | 成立；M1 的 profile/schema 收敛必要。 |
| A2 API/live merge 公开 legacy | Agent create/read/update、live merge 及 node create 当前仍读取或返回 `system_prompt`：`src/IM/api/routes/agents.py:26-71`、`208-260`、`410-443`、`src/IM/api/routes/nodes.py:78-90`、`252-307`。 | 成立；D1/M1 覆盖完整。 |
| A3 SQLite 仍保存 legacy | profile 与 conversation schema 均仍有 legacy 正文，现有迁移只做补列：`src/IM/infra/db.py:35-67`、`611-666`。 | 成立；D2/D4 的同次 migration 有事实基础。 |
| A4 Gateway YAML 是真实双字段存储 | 类型、parser、serializer 都处理两个字段：`src/personal_assistant/config/local_store.py:164-220`、`775-845`、`1063-1188`。 | 成立；D2 定义了唯一的 YAML canonicalization 点。 |
| A5 sync 是通知后 mirror pull | `config.sync` 只携带 `agent_id` / `profile_version`：`src/IM/ws/gateway/control.py:84-92`；Gateway notification handler 再触发 fetch：`src/personal_assistant/config/sync_client.py:40-52`，mirror GET / decode / persist 在 `src/personal_assistant/gateway/agent_config_sync.py:518-605`、`635-643`。 | 成立；修订后的 design 与实际协议一致。 |
| A6 runtime 当前 legacy 在前 | `prompt_for()` 当前先投影 profile `system_prompt`，再追加 `custom_prompt`：`src/personal_assistant/product.py:289-350`；session projection 使用这份 factory：`src/personal_assistant/gateway/session_composition.py:38-66`。 | 成立；D1 明确只保留 `pa.user_custom`。 |
| A7 preview/runtime 来源当前分叉 | preview imaginary Agent 只赋 `custom_prompt` 后调用同一 factory：`src/personal_assistant/gateway/composition.py:132-167`；设置页也只提交 draft custom/config：`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:142-157`。 | 成立；D3 的同源收敛命中根因。 |
| A8 conversation provenance 复制 legacy 正文 | conversation schema、snapshot 与写入查询仍含 `config_system_prompt`：`src/IM/infra/db.py:35-52`、`src/IM/infra/repositories/conversations.py:23-30`、`123-147`、`834-877`。 | 成立；D4/M1 将其与 profile migration 一起关闭。 |
| A9 relay 不需要 prompt 正文 | relay payload 只投影 profile version，而选择逻辑仍比较 legacy snapshot：`src/IM/application/relay_service.py:102-122`、`363-480`、`628-632`。 | 成立；D4 保留 id/version、删除正文不会改变路由目标。 |
| A10 Kernel override 独立于 PA profile | Kernel 继续自行处理 hook override、frozen session 和 sections：`src/agent/core/agent/runtime.py:438-489`；产品边界仍禁止 PA/IM 反向耦合：`SPEC.md:156-161`。 | 成立；不触碰 Kernel 是正确非目标。 |

#### 决策

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| D1 唯一公开字段 | 设计明确同时删除 profile、HTTP、live snapshot、sync、本地类型和 runtime projection 的 legacy ingress（`design.md:76-82`, `134-139`），并保留只读 capability `default_system_prompt`。这与 A1-A6 和 incident 的唯一入口不变量相符。 | 成立。 |
| D2 迁移、所有权与 seed | 合并表保持 A6 的历史顺序（`design.md:84-95`）。修订精确定义 existing IM profile 权威、load 仅在内存规范化、first-seen 才接受 `agent_custom_prompts`，且 seed 非空、不能覆盖 existing profile（`design.md:97-107`, `167-173`）。现有注册确在 reconcile 前发生，且 persistence 已有 first-seen workspace/skills/tools 模式（`src/IM/ws/gateway/sessions.py:273-330`; `src/IM/infra/gateway_persistence.py:141-193`）。 | 成立。 |
| D3 stable preview | 保留当前唯一 `prompt_for()` factory，明确 preview 边界及文案（`design.md:109-115`）；Kernel spec 已规定 preview 与同一 PromptSlots source 对齐：`docs/specs/kernel/prompts.md:35-54`。 | 成立。 |
| D4 provenance 收敛 | 设计只移除不参与 relay payload 的正文，同时保留 agent id/version（`design.md:117-122`），与 A8-A9 的真实职责吻合。 | 成立。 |
| D5 单一原子 M1 | 设计禁止将“不可见”与“不可执行/不能复活”拆开（`design.md:124-130`）；Milestones 中现在只有一个包含所有 ingress、migration、preview 和 provenance 的 M1（`design.md:184-188`）。 | 成立；无横切拆分或范围交叠。 |

#### Incident 约束、澄清与非目标

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| Q1 唯一公开入口 | incident 要求可见 Custom Instructions 是唯一改变专属人设的公开配置（`incident.md:23-27`, `95-106`）；D1/D2 和 IM delta 共同封住 API、sync、runtime 及 first-register 入口。 | 覆盖且不冲突。 |
| Q2 Full bugfix | incident 授权独立完成 Full bugfix（`incident.md:29-31`）；unit 具备 incident、design、两份 delta 和可实施的单 M1。 | 覆盖。 |
| 场景 1 配置即真实 | 空值没有 hidden profile 人设、更新只在对应 Agent 下一轮采用的落点分别在 IM/Gateway delta（IM delta `40-42`; Gateway delta `21-29`）。 | 覆盖。 |
| 场景 2 preview 可检查 | D3、IM delta 的 saved/draft preview 和 runtime exclusions（IM delta `44-47`）保留既有不模拟 runtime 的边界。 | 覆盖。 |
| 场景 3 已有 Agent 不丢约束 | 四种合并表、existing-owner precedence、empty-IM first-register seed、幂等/重启测试共同覆盖（`design.md:86-107`, `175-181`; IM delta `49-59`）。 | 覆盖。 |
| 非目标：公共 PA / 群聊 / 记忆 / 模型提示词 | D1-D3 只收 profile source，stable preview 明确不模拟 runtime（`design.md:72`, `109-115`）。 | 未越界。 |
| 非目标：Kernel 内部 override | D1/D4 不连 profile 至 Kernel override，且测试策略保留 core regression（`design.md:76-82`, `180`）。 | 未越界。 |
| 非目标：不新建角色 UI | 前端范围仅既有设置页/preview 文案（`design.md:175-182`），未引入团队编辑器。 | 未越界。 |

#### Delta-spec

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| IM MODIFIED 既有 Agent 配置 Requirement | 精确锚定 canonical 同名 Requirement，保留乐观锁、next-reply、live merge 与 heartbeat scenarios，并把公开 profile 字段语义收敛为 custom（`docs/specs/im/agents-nodes.md:11-55`; delta `specs/im/agents-nodes.md:7-32`）。 | 用法和覆盖正确。 |
| IM ADDED 专属说明 / preview / upgrade Requirement | 新增的用户可观察 contract 覆盖空值、saved/draft preview、legacy 顺序和 empty-IM first registration；Scenario 的 THEN 没有内部符号（delta `specs/im/agents-nodes.md:36-59`）。 | 覆盖正确。 |
| Gateway MODIFIED 完整运行配置 Requirement | 精确替换 canonical 同名 Requirement，保持既有聊天历史、next reply 和失败不混配的语义，同时声明 profile custom 只能是追加段（`docs/specs/gateway/agent-capabilities.md:47-89`; delta `specs/gateway/agent-capabilities.md:7-33`）。 | 用法和消费者视角正确。 |

#### Milestone

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| M1-visible-custom-cutover | Scope 一次包含 IM profile/API/schema/conversation、register seed、Gateway store/sync/live、PA projection、preview、UI 和 cross-process test；reviewer 轨逐项映射用户旅程，worker 轨列 migration / precedence / API / sync / relay / E2E / Kernel checks（`design.md:184-188`）。 | 原子、可验、无缺口。 |

### 架构进攻

| 角度 | 独立判断 | 结论 |
|---|---|---|
| 归属 | IM persistence 负责 existing profile 的终态所有权；Gateway YAML loader 只负责把本地 legacy 规范化；现有 WS registration boundary 负责 Gateway-first seed。没有让 UI、HTTP handler 或 Kernel 管迁移。 | 通过。 |
| 该不该存在 | `agent_custom_prompts` 是扩展已有 first-seen `node.register` seed，而非新 RPC 或同步服务；一个局部 canonicalization helper 被 YAML 与 old mirror 共同复用。删除其中任何一项会重新引入空 IM 丢值或两套合并逻辑。 | 通过。 |
| 深/浅 | 公共 sync 仍是小的 notification-only envelope，完整 profile 仍由 mirror GET 单一取得；seed 只解决建立 authority 前那一个不可由 GET 回答的初值，不把整份 profile 重复塞进每次通知。 | 通过。 |
| 治本/补丁 | M1 从 schema/API/register/sync/runtime/preview/conversation 的全部可复活入口切断 legacy，不是仅隐藏前端；已有 IM owner 与 Gateway-first 的分歧也由明确 precedence 消除。 | 通过。 |

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | `config.sync` 改为准确的 notification + mirror GET 表述；以 `node.register.agent_custom_prompts` seed 解决 empty-IM first-seen；existing profile 保持 IM 权威。 | 数据流、三个来源的 precedence、YAML 写回时机、跨进程 seed/reconcile/restart 验收均已明确（`design.md:97-107`, `134-139`, `167-181`），并与实际 register-before-reconcile 调用顺序及 existing-only persistence seam 相符。 | closed |
| R1-C2 | 删除 M2，形成一个 atomic cutover M1。 | 设计只剩 M1；它含原 M1/M2 所有 contract ingress 与 two-track exit criteria（`design.md:124-130`, `184-188`）。 | closed |

### Issues

None.

### Recommendations

None. The unit may proceed to `change-orchestrator`.

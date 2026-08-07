# Design Review: feat-515-agent-workspace-root-selection

## Round 1

### Metadata

- reviewer: `/root/feat_515_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 必须完整审查；本 unit 首次进入 Gate 2，涉及 Browser → IM → Gateway 的创建协议和 node-local filesystem authority。`
- started_at: `2026-08-07T16:44:00+08:00`
- completed_at: `2026-08-07T16:51:45+08:00`
- duration: `7m45s`

### Verdict

Issues Found — 2 CRITICAL / 2 WARNING

### Coverage

- 输入：`spec.md`、`design.md`、两个 delta-spec、`prototype.html`，以及 IM/Gateway current specs 和生产调用路径。
- 现状路径从 `/settings/agents/new` 的 mutation，追至 `nodes.create_node_agent()`、`GatewayControl`、`IMConnectionManager`，再到 `IMAgentConfigSync.handle_agent_create()`；Gateway 的实际 wiring 是 `composition.py:602-627`。
- 已逐条核对现状断言、五项关键决策、spec 的四个 requirement/全部 scenario 与澄清、两个 delta-spec requirement 和唯一 M1；并从归属、必要性、接口深度、治本性四个角度攻击方案。

### 承重原子台账

| 类别 | 原子 | 结论与独立证据 |
|---|---|---|
| 现状 | 创建页当前丢弃 workspace root | 成立。`normalizeDraft()` 强制 `workspace_root: null`，尽管 request type 已含该字段：`src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:43-55`；提交调用 `createNodeAgent()`：`:401-420,481-491`。 |
| 现状 | IM 仅 owner-scope 后转发，成功才落 profile | 成立。节点门禁、向 Gateway 发起创建、取成功 root 并随后 `create_profile()` 位于 `src/IM/api/routes/nodes.py:237-320`。 |
| 现状 | 当前 WS create 回包不能表达业务拒绝 | 成立。Gateway 端将 handler payload 原样放进 `agent`：`src/personal_assistant/ws/im_connection.py:1034-1051`；IM 端只取 `agent` 字典给 waiter：`src/IM/ws/gateway/control.py:582-599`。 |
| 现状 | Gateway config sync 是生产创建收口 | 成立。production wiring 注入 `im_config_sync_client.handle_agent_create`：`src/personal_assistant/gateway/composition.py:602-627`；该 handler 当前确定 root、初始化、持久化和发布：`src/personal_assistant/gateway/agent_config_sync.py:162-258`。 |
| 现状 | 更新不改 workspace root | 成立。服务层 update 方法没有该参数且明确说明 immutable：`src/IM/application/config_service.py:175-219`；已创建页的 root input 为 disabled：`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1845-1858`。 |
| 约束 | IM 不应访问 node-local filesystem，Gateway local config 是 runtime authority | 成立且和 current spec 一致：`docs/specs/IM/agents-nodes.md:130-144`、`docs/specs/gateway/service-lifecycle.md:77-84`；runtime resolver 也只读 local agents：`src/personal_assistant/gateway/workspace_authority.py:14-34`。 |
| 约束 | 已有目录初始化不覆盖，但当前 helper 会创建缺失初始文件/父级 | 成立。`ensure_workspace_defaults()` 的 `mkdir(parents=True)` 和“existing files left untouched”在 `src/personal_assistant/config/local_store.py:108-146`；设计正确地把它移到确认后。 |
| 约束 | UI 卡片、草稿保护与移动布局可复用 | 成立。创建页是现有 panel/card 流程并含 blocker：`agent-create-page.tsx:481-645`；卡片及 720px 双列规则在 `src/IM/frontend/src/styles/global.css:856-925`。 |
| 决策 1 | 单次 create 请求承担 non-mutating existing-dir check，确认后重试 | 方向成立。它把真实节点重查留在创建边界，避免引入会陈旧的远端 preflight；`confirm_existing_workspace` 的 request/response 分支与顺序图一致（`design.md:83-92,147-190`）。 |
| 决策 2 | 默认只交给 Gateway，自定义 root 只在节点 canonicalize | 成立，且符合跨机 authority。Gateway 已在本地展开及 resolve 显式 root：`agent_config_sync.py:170-180`。但其 IM mirror 收口未闭合，见 R1-C1。 |
| 决策 3 | canonical root 以 local config 实施同节点唯一性 | 归属成立、无额外跨节点索引是正确的。`RuntimeConfigOwner.persist()` 对 config 更新串行且持久化成功后才发布：`src/personal_assistant/config/local_store.py:332-370`。错误是缺少 default 标识的持久化设计，见 R1-C2；不影响这项唯一性归属本身。 |
| 决策 4 | 缺 parent 拒绝、existing directory 需确认、file target 拒绝 | 完整覆盖用户需求，且和 helper 副作用顺序自洽（`design.md:115-128`）。确认前不调用 helper 充分避免了 existing-dir 首次提交写入 `.nanoassistant`。 |
| 决策 5 | structured outcome 映射为 409/422，成功才建 profile | 业务分层正确且接口字段完整（`design.md:130-160`）。现有前端 error parser 只识别 string detail（`im-agent-config-api.ts:374-407`），因此 M1 必须按设计扩展 code parsing；该边界已在 M1 worker exit criterion 中覆盖。 |
| spec 约束 | 默认/自定义新目录/无效父目录 | 覆盖。决策 2、4，接口 code 表和 M1 #2/#3 分别给出落点（`design.md:94-128,153-160,269`）。 |
| spec 约束 | existing directory 须先提醒后确认 | 覆盖。决策 1/4、sequence、原型 notice 和 M1 #4 一致（`design.md:83-89,165-190,220-224,269`）。 |
| spec 约束 | 同节点唯一、跨节点同字符串不冲突 | 覆盖。决策 3、并发边界和两个 delta specs 一致（`design.md:104-113,193-200`；`specs/IM/agents-nodes.md:42-49`；`specs/gateway/service-lifecycle.md:30-37`）。 |
| spec 约束 | 创建后不编辑/迁移 | 覆盖且没有越界。决策、UX 原型和 M1 都只新增 create card；已有页保持展示-only（`design.md:27-37,204-206,269`）。 |
| delta-spec | IM modified requirement | 语义上应使用 MODIFIED，且保留了原 node ownership、404/409/503 与 immutable scenario；新增 custom、confirmation、unique scenarios 都是消费者可观察结果。`specs/IM/agents-nodes.md:3-60`。默认 `workspace_is_default == true` 不能由设计实现，见 R1-C2。 |
| delta-spec | Gateway modified requirement | 使用 MODIFIED 正确，保留默认 create/runtime-local authority，并以 Gateway 对外 observable outcomes 写场景，没有把内部函数名放进 THEN。`specs/gateway/service-lifecycle.md:3-45`。 |
| milestone | 单 M1 是垂直切片 | 成立。页面、HTTP/WS、node filesystem 是同一创建协议的 producer/consumer，拆成横切 milestone 会制造假并行；M1 同时给出 reviewer 与 worker 两轨退出标准（`design.md:262-269`）。 |

### 架构进攻

| 角度 | 结果 |
|---|---|
| 归属 | Workspace existence、canonicalization、占用检查和初始化归 Gateway 是正确分层；IM 不新增远端 filesystem 抽象或数据库全局索引。R1-C1 说明 IM 的镜像/read path 仍必须完整去除 host-local reinterpretation。 |
| 该不该存在 | 不新增 preflight endpoint 是更深的设计：单一 create outcome 既避免 TOCTOU，又没有为了一处调用包装虚构策略层。新增 `confirm_existing_workspace` 是本需求的必要协议状态。 |
| 深/浅 | `agent.created.error` 扩展复用既有 request correlation，而不是加一套平行 RPC，接口足以覆盖 Browser/IM/Gateway 三方。稳定 `code` 与文案 `detail` 分离使 UI 不依赖字符串匹配。 |
| 治本/补丁 | node-local canonical comparison 对符号链接/`..` 同样生效，避免仅在 UI 禁用或按字面字符串查重的补丁。默认根的 source/mirror 身份没有被共同建模，留下的长远代价是 API/详情页持续错误分类，见 R1-C2。 |

### Issues

- [R1-C1][CRITICAL] [现状分析“ConfigService” / 决策 2、5 / 数据流]: 设计只要求收窄 `ConfigService.normalize_workspace_root()`，却没有拍死所有 IM-side root 读取与转发的语义。生产响应和后续 RPC 实际走 `ConfigService.workspace_root_for_profile()`，它仍对 stored root 调用本机 `Path(...).resolve()`（`src/IM/application/config_service.py:221-249`），`to_agent_config_response()`、能力、cron、heartbeat 等接口都使用它（`src/IM/api/routes/agents.py:178-195,368-372,749-809,890-894`）。因此 worker 若按文档只改 normalize，Gateway 已 canonical 的远端路径仍会在 IM host 被重解释，违反 `design.md:137-138` 和跨机 authority；详情显示或下发的路径可能不再是 node canonical P。设计必须明确一个唯一的 IM mirror accessor：对 Gateway-returned absolute root 不做 `expanduser/resolve`，并列出所有 response/RPC consumers 迁到它，同时把相关 current-code drift 记录进现状分析。

- [R1-C2][CRITICAL] [决策 2、3 / HTTP success interface / IM delta 默认场景]: 默认目录的身份在设计中不可恢复。Browser 只发送 `workspace_root: null`，Gateway success 仅回 `workspace_root`（`design.md:94-99,147-151`），IM profile 当前也只存 path；但 delta-spec 要求 default 创建后 `workspace_is_default == true`（`specs/IM/agents-nodes.md:10-16`）。当前计算把 root 与 **IM host** 的 hard-coded `~/nano-assistant/workspace/<agent_id>` 比较（`src/IM/domain/models.py:8-41`，由 `ConfigService.workspace_is_default_for_profile()` 调用：`config_service.py:227-230`）。Gateway 的 default factory 可使用 node `workspace_base`（`src/personal_assistant/config/local_store.py:149-163`），所以跨机或配置过 base 的默认 root 会被错误标为 custom；未来 GET/detail 也没有字段推导出它原本是 default。设计必须决定并写清 default/custom provenance 如何由 Gateway 回传并在 IM mirror 持久化/响应（或明确废除/重定义 `workspace_is_default`），再将它补入 wire contract、migration/compatibility、delta spec 和测试。否则 worker 无法同时满足默认模式和已写入的 API scenario。

- [R1-W1][WARNING] [Runbook / M1 reviewer #3]: Runbook 要求验“不同节点同字符串路径”，但只提供一套 `e2e-up.sh` 的单节点启动命令（`design.md:248-260`）。current 脚本确实只生成一个 `NODE_ID` / 一份 Gateway config（`scripts/e2e-up.sh:349-366`），且 design 只笼统说“使用两个各自隔离的 Gateway config”，没有给第二节点如何接入同一 IM、如何获得独立 node ID/workspace、以及怎样清理的可执行步骤。照此实施/验收会跳过 user requirement 的关键反例，或误启动第二个隔离 IM。请在 runbook 给出受控的第二 Gateway 命令/配置生成方式与验证步骤，或把可复现的 multi-node contract/integration test 指定为该 scenario 的主验证并说明真栈补充范围。

- [R1-W2][WARNING] [Runbook Vite 行]: Vite 启动命令引用未定义的 `$VITE_PORT`（`design.md:251`）。canonical runtime guide 在启动前使用 `scripts/free-ports.sh 1` 分配它（`docs/development/worktree-runtime.md:127-140`）。不改则 reviewer 不能照抄运行客户端验收命令，可能占用默认端口或直接因空参数失败；补上该变量来源和 reviewer 自己的 Vite PID/cleanup 范式即可。

### Recommendations

- [R1-R1] 在修正 R1-C1/C2 后，把 `workspace_root` 的“Gateway canonical display/routing value”与 `workspace_is_default` 的 provenance 放进同一小节/接口表，避免再次由 IM 主机路径推导 node-local 事实。
- [R1-R2] 现有 prototype 清晰呈现 confirmation 和 conflict 状态；修订后可保留其布局，只需使文案明确“确认后会补齐缺失 Agent 初始文件”，这已和 `ensure_workspace_defaults()` 的真实行为对齐。

### Author Resolutions

- [R1-C1] accepted — 现状分析明确记录 `workspace_root_for_profile()` 和 node prompt preview 的 IM-host drift；设计新增“Root 镜像与 provenance”小节，规定 Gateway root 为 opaque value、统一 accessor 覆盖 config/list、capabilities、preview、cron、skill usage 与 heartbeat，并把新建前 preview 的候选根解析交还 Gateway。
- [R1-C2] accepted — Gateway local config、`agent.created`、`node.register` 和 IM profile 共同携带 `workspace_is_default`。新增 nullable IM migration、legacy compatibility 与不覆盖既有 provenance 的规则；公开 response 直接返回镜像值，不再比较 IM managed path。
- [R1-W1] accepted — Runbook 增加一套可照抄的第二 Gateway config/进程启动、同字符串路径验证和停止命令，明确它只验证 logical node scope、不在共享测试目录运行 Agent。
- [R1-W2] accepted — Vite 启动命令先以 `scripts/free-ports.sh 1` 分配 `VITE_PORT`。

## Round 2

### Metadata

- reviewer: `/root/feat_515_design_reviewer`
- review_mode: `full`
- mode_reason: `Round 1 的两个 CRITICAL 都引入了跨进程 wire 字段、Gateway/IM 双端持久化、SQLite migration、node.register seed 和下行 preview 数据流；这是共享契约与核心边界的高风险变化，不能用 delta/closure 继承 R1 台账。`
- started_at: `2026-08-07T16:53:00+08:00`
- completed_at: `2026-08-07T17:03:34+08:00`
- duration: `10m34s`

### Verdict

Approved — 0 CRITICAL / 1 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | Gateway root 变为 opaque mirror value，统一 accessor 并把 creation preview 的候选 root 交回 Gateway | `design.md:113-116,152-156,180-203` 明确 preview、HTTP response 与每一个 node RPC 不再走 IM-host `resolve()`；current drift 的真实落点仍可在 `src/IM/application/config_service.py:221-249`、`src/IM/api/routes/nodes.py:194-205` 复现，修订方案准确覆盖。 | closed |
| R1-C2 | Gateway 生产并持久化 provenance，`agent.created`/`node.register` seed 与 nullable IM mirror 同步 | `design.md:101-111,180-197` 给出 source-of-truth、legacy/null 策略和回放不覆盖规则；current `workspace_is_default` 的 IM-host path comparison 在 `src/IM/domain/models.py:8-41`，Gateway default 可来自 `workspace_base` 在 `src/personal_assistant/config/local_store.py:149-163`，修订已消除这个错误推导。 | closed |
| R1-W1 | 增加同一 IM 下第二 Gateway 的隔离配置、启动、验证和停止步骤 | `design.md:302-359` 给出可执行命令。其 `--foreground --auto-bind` 用法和 current `scripts/e2e-up.sh:301-321`、`src/personal_assistant/main.py:45-108` 一致；第二 node id/workspace 也被显式隔离。 | closed |
| R1-W2 | Vite 先申请空闲端口 | `design.md:292-300` 使用 `scripts/free-ports.sh 1`，与 canonical guide `docs/development/worktree-runtime.md:127-140` 一致。 | closed |

### Coverage

- 输入：修订后的 `spec.md`、`design.md`、两个 delta-spec、`prototype.html`、Round 1 及 Author Resolutions；对照 IM/Gateway current specs 与生产 wiring。
- 重追 Browser create → `nodes.create_node_agent()` → `GatewayControl` → `IMConnectionManager` → `IMAgentConfigSync.handle_agent_create()`；另追 `node.register` → `GatewayNodePersistence.register()` 与 Gateway config-sync reload 路径。
- 全量复核本轮有效的现状断言、五项决策、spec 的四个 requirement/全部 scenario/澄清、两个 delta-spec 条目和 M1，并重新执行四个架构进攻角度。

### 承重原子台账

| 类别 | 原子 | 本轮结论与独立证据 |
|---|---|---|
| 现状 | 创建表单已有 root 类型却强制发送 null | 成立：`src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:43-55,401-420`。设计的 default/custom 表单状态和 `null` default 语义准确覆盖。 |
| 现状 | IM create 路由成功后才建 profile，WS 回包当前没有业务 error | 成立：`src/IM/api/routes/nodes.py:237-320` 与 `src/IM/ws/gateway/control.py:582-599`。新增 typed outcome 在 `design.md:145-178` 覆盖成功、409 与 422。 |
| 现状 | Gateway handler 是真实的 workspace/本地 config 收口 | 成立：production wiring `src/personal_assistant/gateway/composition.py:602-627`；当前创建副作用顺序 `agent_config_sync.py:162-258`。设计仍将 parent、existing confirmation、unique 与 initialization 放在此处，没有把 node filesystem 推给 IM。 |
| 现状 | root 仍在 IM host 被 re-resolve，node preview 由 IM 派生 root | 成立：`src/IM/application/config_service.py:221-249`、`src/IM/api/routes/nodes.py:194-205`。opaque accessor + node-resolved preview 的收口明确列在 `design.md:113-116,152-156,199-203`。 |
| 现状 | local config / register 种子是 Gateway workspace truth | 成立：runtime local-only resolver `src/personal_assistant/gateway/workspace_authority.py:14-34`，register workspace map 的 producer/consumer `src/personal_assistant/reporter/upstream_reporter.py:238-270`、`src/IM/ws/gateway/sessions.py:273-330`、`src/IM/infra/gateway_persistence.py:99-190`。新 provenance map 归到这条既有路径，归属正确。 |
| 现状 | profile update 与详情页均不允许 root 编辑 | 成立：`src/IM/application/config_service.py:175-219`、`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1845-1858`。修订没有增加 root migration/edit 行为。 |
| 决策 1 | 单 create request 先零副作用确认，再同 payload 重试 | 成立且自洽：`design.md:88-97,205-234`；仍避免 remote preflight/TOCTOU。 |
| 决策 2 | Gateway 分配 default/custom root 并生产 provenance；preview 同样由 node 解析 | 成立：`design.md:99-116` 在 root、bool、node preview 上都有明确 producer，未依赖 IM 路径猜测。 |
| 决策 3 | canonical root 仅在同一 Gateway local config 中查重 | 成立：`design.md:118-128,236-243`；`RuntimeConfigOwner.persist()` 的 serialize-after-durable-write 语义由 `src/personal_assistant/config/local_store.py:332-370` 佐证。 |
| 决策 4 | custom parent、file target、existing directory 与 initialization 次序 | 成立：`design.md:130-143` 完整覆盖；`ensure_workspace_defaults()` 会 mkdir parents 且不覆写文件的真实语义在 `src/personal_assistant/config/local_store.py:108-146`，设计已把它置于 confirmation 后。 |
| 决策 5 | typed rejection、opaque root 及 success-only IM profile | 成立：`design.md:145-156` 与 wire table 兼容当前 `agent.created` correlation；root 与 provenance 同源的 persistence rule 见下一项。 |
| 决策/接口 | root 与 provenance 共同持久化、register only fills null、legacy 保守 fallback | 成立：`design.md:180-203` 明确 Gateway producer、IM nullable mirror、legacy migration、首次 register 和 non-overwrite。现有 `AgentProfile`/SQLite 没有此列（`src/IM/domain/models.py:104-129`、`src/IM/infra/db.py:53-67,645-700`），故 schema migration 是必要增量而非冗余抽象。 |
| spec 约束 | default/custom new path、parent invalid、existing confirm、node-local uniqueness、immutable root | 均有落点：`design.md:88-178,236-243`，并在 M1 reviewer/worker 两轨再投影。没有恢复已有 Agent 的编辑或迁移。 |
| delta-spec | IM modified requirement | 使用 MODIFIED 正确，保留原 node owner/online/404/409/503 行为；新增 root/provenance round-trip scenario 是消费者可观察契约，`specs/IM/agents-nodes.md:3-58`。 |
| delta-spec | Gateway modified requirement | 使用 MODIFIED 正确，保持 local runtime authority 并把 default/custom provenance 作为 IM 可观察回包/注册事实，`specs/gateway/service-lifecycle.md:3-46`。无实现层断言泄漏到 THEN。 |
| milestone | 一个端到端 M1 | 成立：同一 request wire 的 Browser、IM、Gateway 不可横切拆分；M1 的 user/reviewer 和 implementation/worker exit criteria 都可验证，`design.md:361-368`。R2-W1 是唯一新增 UI 验收投影不一致。 |

### 架构进攻

| 角度 | 结果 |
|---|---|
| 归属 | 路径解析、占用与 source 生产在 Gateway；IM 只 mirror/route，符合 IM/Gateway 可跨机和 local config truth。新增 nullable mirror column 是保存跨进程来源所需的最小持久化，不引入反向依赖。 |
| 该不该存在 | provenance bool 不可由 node-independent path 可靠推导，是保留已有 API boolean 正确语义的必要字段。复用 agent.created/register 而不增加预检或 provenance API，避免多余控制面。 |
| 深/浅 | `workspace_root`+`workspace_is_default` 作为不可拆分 pair 把复杂度收在 one accessor / one origin，而不是让每个 response 重复 path comparison。preview 的 node-side candidate resolution同样复用 factory，而非再建 directory-check service。 |
| 治本/补丁 | legacy null 明确承认不可恢复的历史信息，register 只补 null，避免用 IM host 路径伪造答案或将新字段反写到 Gateway authority。第二 Gateway runbook 基于实际现有 launcher，不是假设平行 e2e runner。 |

### Issues

- [R2-W1][WARNING] [M1 reviewer exit #2 / 原型对齐契约]: M1 新增“详情标为 default/custom”（`design.md:368`），但这不是 spec 要求，现有详情页只以 disabled input 展示 root（`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1845-1879`），原型也只承诺显示固定路径、没有 default/custom 标签或 must-match 行（`prototype.html:35-54`；`design.md:259-267`）。不改会让 worker 为满足 reviewer exit criterion 自行决定新增标签的文案、位置和移动端表现，造成未设计的 UI 扩张。请二选一：从 M1 #2 移除“详情标为 default/custom”，保留 API/provenance 自动化验证；或在原型和原型对齐契约中明确该标签的视觉与状态。

### Recommendations

- [R2-R1] R2-W1 仅是收口已有验收文字的局部修正，不影响 API/provenance 架构；修复后可用 closure mode 复审。

### Author Resolutions

- [R2-W1] accepted — 从 M1 的详情页验收删除未设计的 default/custom 标签，保留当前原型和 current UI 所承诺的“显示固定 root、不可编辑”。default/custom provenance 继续作为创建响应与自动化契约验证，不新增用户界面。

## Round 3

### Metadata

- reviewer: `/root/feat_515_design_reviewer`
- review_mode: `closure`
- mode_reason: `作者只删除了 R2-W1 指出的未定义详情页标签要求；没有改变 root/provenance wire、持久化、行为或原型契约，影响可封闭在 M1 reviewer exit #2。`
- started_at: `2026-08-07T17:06:00+08:00`
- completed_at: `2026-08-07T17:08:28+08:00`
- duration: `2m28s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-W1 | 从 M1 删除未设计的详情页 default/custom 标签；保留固定 root、不可编辑及 API/provenance 自动化验证。 | 修订后的 M1 #2 只要求详情显示固定 root、已有 Agent 页面无修改/迁移操作，并将 default/custom 限定为 API 成功场景的 provenance（`design.md:368`）。这与首文档的“可看到 P、无修改或迁移操作”（`spec.md:75-80`）、原型的“详情页将显示节点分配的固定路径”（`prototype.html:54`）和 current 详情页只读 root input（`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1845-1858`）一致；原型 must-match 表也没有遗漏的详情页标签状态（`design.md:259-267`）。 | closed |

### Issues

- None.

### Recommendations

- None; R2-W1 已闭环，可进入实施。

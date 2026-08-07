# Design 评审：refactor-483-web-agent-config-form-model

> 评审对象：`motivation.md` v2、`design.md` v2、`prototype.html`
> 评审方式：fresh full-pass；从生产路由正向追 create/detail → IM HTTP DTO → Gateway
> capability/config owner，并以真实浏览器渲染原型。未把作者文档中的引用当作事实证据。

**结论**：Issues Found

当前抽取 pure form model、保留 create/edit lifecycle owner、共享 Behavior view 但不共享 endpoint
的总方向是合理的；单 M1 也符合“两页同时切到一个 rule authority”的原子迁移要求。但现在仍有
4 个会直接误导 worker/reviewer 的 CRITICAL：真实 HTTP create/update 契约没有闭合、required-tool
联动与 auto provenance 自相冲突、原型的 must-match 基线不是当前详情页/移动 edit、Runbook 没有
可取得的第二 node/capability fixture。另有 3 个需要拍死的 WARNING。

## 核实台账

### 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| create/detail 是生产真实入口 | 从 React router 正向追页面 | ✓ `/settings/agents/new`、`/settings/agents/:agentId` 分别直接装配 `AgentCreatePage`、`AgentDetailPage`，node 下的新建入口也复用 create page（`src/IM/frontend/src/app/router.tsx:43-69`）。 |
| create 同时拥有 draft/default、normalize/validate、capability default 与 submit | 读生产 controller | ✓ create 本地解析 missing feature default（`agent-create-page.tsx:71-80`）、初始化 DTO-as-state（`:83-96`）、用 ref heuristic 写入 capability defaults（`:325-399`）、直接闭包当前 node 发 mutation（`:401-420`）。 |
| detail 把 API DTO 直接当 draft，并重复共同规则 | 读生产 controller | ✓ `type AgentConfigFormState = AgentConfig` 且重复 normalize/validate/effective feature（`agent-detail-page.tsx:32-74`）。 |
| allowlist/text/model normalization 规则 | 对照两页实现与 payload builder | ✓ allowlist trim/去空/首次 dedupe，text trim，blank model → `null`；create 与 detail 当前各有一份实现（`agent-create-page.tsx:20-58`、`agent-detail-page.tsx:34-53`）。 |
| feature missing/default/explicit false | 追实际表达式 | ✓ 两页都用 `draftFeatures?.[key] ?? default_on`；`false` 不会被 `??` 吃掉（`agent-create-page.tsx:71-80`、`agent-detail-page.tsx:63-74`）。 |
| feature/tool 三向联动 | 追两页事件处理 | ✓ 开启只追加该 `requires_tool`、关闭不删 tool；显式移除 tool 会把所有依赖 feature 写 false（create `agent-create-page.tsx:644-704`；detail `agent-detail-page.tsx:1722-1739,1844-1857`）。 |
| edit 显式空 tool allowlist 是存储真值 | 对照 UI 与 canonical | ✓ detail selector直接消费 `draft.tool_allowlist`，不会用 capability default 回填；canonical 明确空名单全不亮且保存刷新保持（`docs/specs/im/agents-nodes.md:375-389`）。 |
| create defaults 只在未编辑时随 capability 初始化 | 追 refs/effect | ✓ 当前用 `skillsEditedRef/toolsEditedRef` 与 auto-default 快照阻止显式选择（包括 `[]`）被覆盖（`agent-create-page.tsx:325-399,676-704`）；切 node 重置为 auto。现实现没有 epoch，设计补 epoch 是有效治本方向。 |
| heartbeat/cron enable 属于 features，cadence/edit-only 不属于共同 core | 追详情渲染 | ✓ feature toggle写 `features`；heartbeat cadence card仍是 detail-only（`agent-detail-page.tsx:1722-1765`）。但当前 card visibility 直接读 raw `draft.features?.heartbeat`（`:1751-1756`），所以设计要求统一读 effective map 有真实落点。 |
| create/edit preview endpoint 不同 | 追 client API | ✓ create 调 node preview、edit 调 agent preview（`im-agent-config-api.ts:618-667`）；shared view不应猜 endpoint。 |
| preview 当前没有 late-response owner | 追两个 `fetchPreview` | ✗ 两页都只有 debounce timer；已经发出的请求没有 abort/request epoch，较旧响应可在较新请求后写 `previewText/error/loading`（`agent-create-page.tsx:119-160`、`agent-detail-page.tsx:125-166`）。设计 D8 新建 preview controllers 却没有拍死该 lifecycle，见 WARNING-2。 |
| detail dirty/refetch 会覆盖未保存 draft | 追 React Query cache 与 WS consumer | ✓ detail 对任意 `detailQuery.data` 变化都 `setDraft`（`agent-detail-page.tsx:1352-1367`），dirty 又用整个 normalized DTO 的 JSON（`:1371-1384`）；status WS 会原地改 detail-state 的 `config.node_status`（`agent-status-ws-consumer.ts:54-63`），足以触发覆盖。 |
| late create/save 会跨 activation 写当前页面 | 追 mutation callbacks | ✓ create success无 node/session guard即 cache+navigate（`agent-create-page.tsx:401-419`）；detail success无 agent activation guard即 setDraft/cache（`agent-detail-page.tsx:1390-1423`）。D7 的 activation epoch 有真实问题驱动。 |
| capability snapshot 的生产权威来源 | 从 Gateway composition 正向追 | ✓ production wiring 把 node/agent providers接到 `build_*_capabilities_payload`（`src/personal_assistant/gateway/composition.py:548-575`）；Gateway projection明示产品语义 owner并投影 features/defaults（`src/personal_assistant/reporter/capability_projection.py:1-25,79-112,154-190`），IM只按需透传（`docs/specs/im/agents-nodes.md:234-260`）。前端不应复制 registry。 |
| capability option 的“稳定 identity” | 对照 canonical 与 selector | △ canonical要求同名不同 location 的 skill 分开展示（`docs/specs/im/agents-nodes.md:258-260`），当前 selector也按 location 分组但 payload选择仍按 name（`skill-source-selector.tsx:10-67`）。D4 未定义 skill/tool/model 各自的 dedupe identity，见 WARNING-3。 |
| create API DTO 与 form payload 可 round-trip | 对照 TS client、Pydantic DTO、route 与 persistence | ✗ TS `NodeAgentCreateRequest`声明并发送 `features/custom_prompt`（`im-agent-config-api.ts:130-144,496-500`），但真实 `CreateNodeAgentRequest`没有这两字段（`src/IM/api/routes/nodes.py:78-90`），route发给 Gateway及 `ConfigService.create_profile`也均未携带/落库（`:252-307`；`src/IM/application/config_service.py:77-124`）。Pydantic原子探针确认两字段被丢弃，见 CRITICAL-1。 |
| edit “字段 absent 且 untouched → omit → server keeps existing” | 对照 request model与route | ✗ client注释/设计认为 omit preserves（`im-agent-config-api.ts:150-165`；design D2），但后端 `features` 是 `default_factory=dict`（`src/IM/api/routes/agents.py:52-71`），route无条件传 `payload.features`（`:410-444`）；省略会变 `{}` 而不是 preserve。response也总物化 `features` 为 dict（`:181-205`）。见 CRITICAL-1。 |
| 详情页当前视觉/生命周期范围 | 追真实 JSX | ✓ 详情页除共同 cards 外还有 Overview/Config/Channels/Skills/Sessions tabs（`agent-detail-page.tsx:1616-1657`）、heartbeat/cron、Workspace card（`:1894-1929`）和 desktop rail（`:1977-1983`）。这与原型 claimed baseline 不一致，见 CRITICAL-3。 |
| Claude Code 对照方向 | 读本机参考源码 | ✓ CC把原始 settings经 schema投影到 `SettingsJson`并单独 merge/cache（`claude-code/src/utils/settings/settings.ts:178-226,309-367,645-668`），provider registry独立加载/校验/合并（`claude-code/src/services/providerRegistry/loader.ts:68-103,130-158`）。用它支持“稳定配置 model 与 capability catalog 分权”是合理类比；文档也没有声称存在等价 UI。 |

### 编号决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| D1：共同 core draft + create/edit session extensions | 查边界是否包含真实交集、是否越界 | ✓ common fields与两页重叠一致；identity/runtime metadata、heartbeat cadence、cron/channel/diagnostics留在入口 extension，避免万能表单。 |
| D2：显式 DTO adapters/projectors | 查真实接口闭合、presence语义 | ✗ client-side分层方向正确，但 create后端会丢字段、update omit会物化 `{}`；因此“API DTO ↔ form ↔ payload round-trip”和 field presence contract并不成立。见 CRITICAL-1。 |
| D3：selection provenance + capability epoch | 模拟 node switch/refetch/user edit | ✗ node/epoch guard与 explicit `[]`合理；但 `toggleFeature`追加 required tool时没有规定 tools provenance从 `auto` 变 `explicit`。随后同 node capability refetch可按 D3.3 以 defaults替换 tools，留下 `feature=true`、required tool缺失。见 CRITICAL-2。 |
| D4：immutable capability snapshot | 查 authority、unknown/orphan、identity | △ snapshot作为输入且保留 unknown/orphan正确；“stable identity”未按 skill/tool/model拍死，存在 canonical skill location 回归分歧。见 WARNING-3。 |
| D5：pure transitions | 对照当前三向联动与不变量 | ✗ transition本身覆盖 on/off/remove，但和 D3 provenance的组合缺口会破坏“feature on ⇒ required tool在 allowlist”。见 CRITICAL-2。 |
| D6：semantic dirty | 查 comparison语义与生命周期 | ✓ 排除 readonly metadata/provenance、保留 field/key presence、blank model等价、success rebase，均直接修复当前 JSON DTO comparison；payload顺序仍独立保留。 |
| D7：page controllers拥有 async lifecycle | 枚举 activation/refetch/save/create late paths | ✓ node/agent activation、dirty refetch、late create/save/query和 matching success commit都已拍死，且直接覆盖当前真实 race。preview请求不在此契约，另见 WARNING-2。 |
| D8：共享 Behavior view，不共享 endpoint | 查接口归属与数据流出口 | △ shared view无 I/O、两入口各自选 endpoint正确；但 preview controller没有 request identity/latest-wins契约，worker对新 owner仍需猜。见 WARNING-2。 |

### motivation/spec 约束

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 澄清：作者自主完成，仅最终确认 | 查 design 是否留下必须由用户拍板的 TBD | ✓ 无 TBD/A-or-B；需修订项都可由 design author根据已给不变量自行闭合。 |
| 澄清：不以文件大小为拆分理由 | 查抽象驱动力 | ✓ unit由两页重复业务规则与 ownership drift驱动，不是机械拆巨石。 |
| 目标：API config ↔ draft ↔ submit payload 单一投影 | 查端到端 DTO/route/persistence | ✗ client model只能统一浏览器侧，真实 create/update contract未闭合。见 CRITICAL-1。 |
| 目标：normalization/validation/dirty 单一 authority | 查 D1/D2/D6与M1 | ✓ pure model + simultaneous migration + duplicate helper deletion覆盖。 |
| 目标：missing/false、auto/explicit-empty、feature/tool约束 | 查 D3-D5组合 | ✗ 三态与 explicit empty建模充分，但 required-tool 与 auto provenance组合缺口破坏约束。见 CRITICAL-2。 |
| Req 创建 Agent 保持 | 查 defaults/validation/payload/success/error/navigate | △ controller职责和测试轴覆盖大部；真实 custom feature/prompt创建目前被服务端丢弃，design必须明确是要“如实保留缺陷”还是补契约，不能称 round-trip。见 CRITICAL-1。 |
| Req 编辑 Agent 保持 | 查 initial/dirty/payload/feedback | ✓ D2/D6/D7覆盖；HTTP presence语义例外并入 CRITICAL-1。 |
| Req capability 约束保持 | 查 options/linkage/explicit empty/persistence | ✗ D3+D5组合缺口；另有 stable identity歧义。见 CRITICAL-2、WARNING-3。 |
| Req 当前 UI 保持 | 把 prototype与真实 1440/375页面对照 | ✗ prototype缺详情 tabs、heartbeat/cron、Workspace、真实移动 edit，并含 mobile sidebar CSS错误，不能作为这条 Requirement 的 must-match依据。见 CRITICAL-3。 |
| 影响范围：不改 HTTP/Gateway schema/视觉 | 查代码和 prototype | △ Gateway schema确实不需改，视觉目标也是 no-delta；但 HTTP事实与 form-model承诺冲突，必须选择补 HTTP contract、前置独立 bugfix，或明确降级目标。见 CRITICAL-1。 |

### delta-spec / canonical 对账

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| kernel：no spec delta | 查是否改变 kernel consumer behavior | ✓ model/view/controller重构不触及 kernel。 |
| IM：no HTTP/schema/product delta | 查 create/update DTO与持久化语义 | ✗ 如果目标是文档声称的 create/edit round-trip，则必须改 IM；如果坚持 no-delta，则必须明确当前 create drop/update materialization事实并收窄验收承诺。当前写法两者都占。见 CRITICAL-1。 |
| Gateway：no config/capability delta | 查真实 capability owner | ✓ 继续消费 Gateway snapshot、不复制 registry，生产 provider与现有 schema均不变。 |
| CLI：no spec delta | 查依赖面 | ✓ 无 CLI 路径。 |
| current required-tool canonical 是否与 no-delta一致 | 对照 canonical、代码与历史用户拍板 | ✗ 当前代码和原始决策都是“关 feature 不删 tool”（两页代码见上；`docs/changes/archive/feat-379-system-prompt-sections/spec.md:63-71`），但 canonical 写“停用 cron 则 cron tool随之移出”（`docs/specs/gateway/agent-capabilities.md:107-110`）。design没有报告 drift。见 WARNING-1。 |

### 前端原型、Runbook 与 Milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| prototype：Create cards + actions must-match | 本地浏览器渲染 create/invalid | ✓ 原型有 create header、Identity/Behavior/Access cards、上下 actions与validation状态，足以表达该局部 no-delta基线。 |
| prototype：Detail sidebar/header/cards must-match | 本地浏览器渲染 detail/constraint并对照生产 JSX | ✗ 原型只有三张共同 cards，没有详情 tabs、heartbeat/cron、Workspace或其他 detail-only结构，却声称覆盖“当前 detail 页面结构”（design `:277-297`）。见 CRITICAL-3。 |
| prototype：Feature/tool linkage must-match | 切换 constraint状态、对照当前联动 | ✓ 可见 required tool结果；但这是静态示例，不替代 D3+D5 state-machine测试。 |
| prototype：Mobile 两入口 create/edit must-match | 本地浏览器切 mobile，检查 DOM/CSS | ✗ mobile mode无 create/edit子状态，且 `body[data-mode="mobile"] .topbar,.body[data-mode="mobile"] .sidebar` 的第二 selector写错（`prototype.html:104-116`），实跑 sidebar仍显示；`.edit-only`又被一律隐藏，无法验 mobile edit。见 CRITICAL-3。 |
| prototype：示例数据 may-adapt | 查是否把示例当 contract | ✓ milestone允许真实 API 数据替换。 |
| Runbook：服务起停/健康检查 | 检查命令与 required journey前置 | ✗ 起停命令可执行，但 health check只证 IM OpenAPI，不证明 Gateway connected/capability可用；required journey又要求第二 node或 capability fixture，却没有来源、创建方式、资源路径或 availability check（design `:327-341`）。见 CRITICAL-4。 |
| M1：单一原子切换 | 查垂直性、范围交集、两轨退出 | △ 单 M1理由成立且 reviewer/worker双轨齐；但退出依赖不真实的 prototype #2/#4、不可取得的第二 node fixture以及尚未闭合的 payload round-trip，修完 CRITICAL 后才能派发。 |

### 整体性质

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 给人看的上层架构是否直观 | 只读总览、图和决策标题 | ✓ before/after、数据流、owner边界清楚；没有被实现步骤淹没。 |
| 接口与数据流是否闭合 | 从每个 DTO source追到 payload/persistence/response | ✗ frontend model → IM create/update在 presence与字段集合上断裂；preview async也无 latest-result owner。 |
| 常规自洽/风险/回退 | 查命名、图、风险与回退 | △ 命名/图/单M1一致；“API/持久数据无变化”的回退描述与 round-trip目标冲突，原型/Runbook风险未闭合。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | pure form model、page controllers、Gateway capability projection | ✓ 归属正确：配置语义集中在 settings feature的 pure module，路由/React Query/endpoint留在 page controller，Gateway继续拥有产品 capability语义；没有形成 frontend→Gateway内部或 core→product反向依赖。 |
| 该不该存在 | `agent-config-form-model.ts` 与 `AgentBehaviorFields` | ✓ 删除测试通过：删除 pure model会把 normalize/presence/linkage/dirty重新散回两页；删除 shared Behavior会保留两份同构交互。设计也拒绝通用 form framework与万能 detail state，没有为假想多态造 factory/protocol。 |
| 深还是浅 | session/transitions/projections边界 | ✓ model用一组 typed intent隐藏 missing/default、provenance、payload与dirty复杂度，接口明显小于两页现有实现；shared view不吸收 endpoint，是深度与就近性的合理平衡。 |
| 治本还是补丁 | “前端 pure model 即可统一 API config ↔ payload” | ✗ 只统一 TS DTO会继续掩盖 IM create丢字段与 update omit物化 `{}`；长期代价是 client snapshot测试长期为绿、用户持久化仍错，下一字段继续在两端 schema漂移。需在本 unit、显式前置 bugfix或收窄契约三者中拍死一条，见 CRITICAL-1。 |

## Issues

- [CRITICAL] [决策 2 / motivation 目标 / IM no-delta]：真实 HTTP contract 没有闭合。
  前端 `NodeAgentCreateRequest` 会发送 `features/custom_prompt`，但 IM Pydantic create DTO、Gateway
  create payload和 `ConfigService.create_profile`均没有它们；原子验证显示输入后 `model_dump()`
  完全丢弃两字段。edit 的 `features` 省略也会被后端 `default_factory=dict` 变成 `{}`，不是设计写的
  “untouched → omit → preserve”。不改时，worker能让 pure model/snapshot tests全绿，却继续把创建页
  custom feature/prompt静默丢掉，并实现一个服务端不支持的 field-presence contract。作者必须在 Gate 2
  前拍死并全篇对齐一种方案：
  1. 根治：把 create DTO → Gateway frame → IM profile persistence/response 补齐，并让 update按
     `model_fields_set` 区分 absent/present empty；补 IM delta/canonical与真实 HTTP contract tests；
  2. 独立 bugfix前置：给本 unit加明确 dependency，完成后再实施；
  3. 坚持纯 no-delta：明确记录现有 drop/materialization，删除“持久 round-trip/preserve”的错误承诺，
     测试只声称浏览器 request projection保持现状。不能继续同时声称 no HTTP delta和端到端 round-trip。

- [CRITICAL] [决策 3 + 决策 5]：`toggleFeature` 添加 required tool 后，tools provenance 是否变
  `explicit` 没有定义。按当前字面，create tools仍可保持 `auto`，下一次同 node capability refetch
  会用 `default_on` tools替换它，造成 `feature=true` 但 `requires_tool` 缺失，直接违反 motivation
  的 capability不变量。把契约改成二选一且加矩阵测试：要么 feature toggle追加 tool时将 tools
  selection provenance切为 explicit；要么把 auto defaults与 required-tool overlay分别建模，并在每次
  snapshot应用后重建 invariant。测试必须包含“auto初态 → 开 requires-tool feature → same-node refetch/
  late capability → required tool仍在”。

- [CRITICAL] [前端原型 / UI Requirement / M1退出标准]：`prototype.html` 不是它声称的当前
  detail/mobile must-match基线。真实详情页有五个 section tabs、heartbeat/cron、Workspace和 desktop
  rail；原型 detail只剩三张共同 cards。mobile只有一个 create-like状态，隐藏全部 `.edit-only`，并因
  `prototype.html:105` selector错误仍显示 sidebar。按当前 M1，worker/reviewer“匹配原型 #2/#4”仍可让
  当前详情/移动 edit发生回归。请用真实当前页面重建/补齐 detail clean/dirty 与 375 create/edit状态，
  修正 selector，并把每个 must-match行指向可直接打开的明确 state/anchor；若刻意不模拟某 detail-only
  区域，就从“覆盖当前 detail结构”与 must-match中移除，改为明确以生产现状截图/组件为 authority。

- [CRITICAL] [Runbook for Reviewer / M1 reviewer退出]：required journey要求快速切第二 node或切换
  capability fixture，但 Runbook只写“另准备”，没有可获得来源/路径/创建命令/检查命令；
  `curl "$IM_URL/openapi.json"`也只证明 IM活着，不证明 Gateway connected或 snapshot满足
  default-tool/requires-tool/two-tools/model前置。下游 reviewer在标准 `e2e-up.sh` 单 node环境无法执行
  必验旅程，只能静默降级。请写出已存在资源的精确来源与 availability check（至少验证两个可切 node，
  或一个确定可操纵且等价的 capability fixture），并用 authenticated nodes/capabilities检查证明
  Gateway connected与 snapshot字段满足；若资源尚不存在，Gate 2前先实现它，不能把创建责任留给 worker
  的“验收证据记录”。

- [WARNING] [delta-spec / canonical drift]：design与当前代码/原始用户拍板都采用“取消 feature不删
  tool”，但 `docs/specs/gateway/agent-capabilities.md:107-110` 仍写“停用 cron则 tool随之移出”。
  不处理时 worker与 reviewer面对两个 authority会作相反判断。把它在现状分析标为 pre-existing drift，
  并明确由哪份 current contract胜出；若以已验证代码/原始 spec为准，随 unit修正 canonical wording
  （这是纠漂，不是产品行为 delta），同时保留“移 tool → feature false”的另一方向。

- [WARNING] [决策 8 / 规则测试矩阵 async]：新 preview controllers没有定义 concurrent request
  的 latest-wins/activation规则。当前实现已经能让旧 node/agent/draft响应覆盖新 preview，抽取 owner时
  两个 worker可能分别保留或修复。给 preview请求加入 `{activation, previewEpoch}` 或 abort contract：
  只有当前 activation的最新 request可写 text/error/loading；把 node/agent切换、rapid edits、关闭后迟到
  三类加入 async矩阵。endpoint选择仍分别由 create/edit controller拥有。

- [WARNING] [决策 4]：`trim、去空、按 stable identity dedupe`没有定义三类 option的 identity。
  tool/model按 name去重与 skill按 `(name, normalized location)`保留展示是不同契约；若一律按 name，
  会违反 canonical“同名不同 location 分开展示”。请在 capability snapshot接口拍死每类 identity，
  同时说明 payload仍是 name list、unknown selection如何合成 orphan option，并加同名不同 location
  的 adapter/view test。

## Recommendations

- 在 M1 worker矩阵里保留真实 API contract test，不能只 mock `createNodeAgent` 断言 TS object；当前
  `tests/im_service/contract/test_agent_create_contract.py` 会通过但没有发送/断言 create
  `features/custom_prompt`，正是该 drift 未被发现的原因。
- `owner_id: ""` 是当前 create client常量，而 IM route又把它直接传给 profile persistence
  （`agent-create-page.tsx:83-96`、`src/IM/api/routes/nodes.py:280-283`）。它不属于本次 blocker，
  但 D2 的“保持当前 create contract的值”可改为明确常量与 owner authority，避免 worker误以为
  browser负责可信 owner。

## 本轮验证证据

- frontend focused baseline：
  `npm run test -- --run agent-create.test.tsx agent-detail-page.test.tsx agent-tools-pill.test.tsx im-agent-config-api.test.ts`
  → 4 files / 49 tests passed（现有 React `act`/storage/query warnings，无失败）。
- backend focused baseline：
  `.venv/bin/python -m pytest -q tests/im_service/contract/test_agent_create_contract.py tests/im_service/contract/test_agent_config_contract.py`
  → 13 passed。
- Pydantic原子探针：
  `CreateNodeAgentRequest.model_validate({...features,custom_prompt...}).model_dump()` 不含两字段；
  `UpdateAgentConfigRequest` 省略 features 后 `features == {}` 且 `model_fields_set` 不含 features。
- `prototype.html` 通过本地 HTTP + Playwright实跑 create/invalid/detail/constraint/mobile；浏览器与
  临时服务已关闭，生成的本轮临时产物已清理。

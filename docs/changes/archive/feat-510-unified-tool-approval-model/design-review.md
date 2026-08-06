# Design Review: feat-510-unified-tool-approval-model

## Round 1

### Metadata

- reviewer: `/root/feat_510_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 恒为 full；从首文档、两份 delta-spec、M1 骨架、current canonical、生产装配/运行路径与 Related refactor-476 独立重建证据。`
- started_at: `2026-08-06T17:50:48+08:00`
- completed_at: `2026-08-06T18:01:16+08:00`
- duration: `10m28s`

### Verdict

Issues Found — 2 CRITICAL / 2 WARNING

方案的主数据流成立：PA 启动 snapshot 经唯一 SDK 装配 seam 把可选模型交给同一 Kernel，
`auto_mode_gate` 的两次 `HookContext.call_model()` 已有显式 model 与 provider 路由能力，正常 run
model 不会因此改变。但当前 delta inventory 漏掉一份被公开接口直接修改的 canonical，Gateway
delta 又漏掉 PA 自身的运行失败契约；此外，Related refactor-476 的 builtin dependency seam 与本
方案的 registry state seam 尚未收口，Runbook 还给出了实际不存在的 IM health endpoint。修正前
不应进入 `change-orchestrator`。

### Coverage

- 首文档：`spec.md` 全文，含 6 条澄清、4 个 Requirement、7 个 Scenario、范围与非目标。
- 设计：`design.md` 全文，含现状/约束/可复用能力/历史、7 条决策、接口数据流、风险回退、
  Runbook 与单一 M1。
- delta-spec：`specs/gateway/agent-capabilities.md`、`specs/kernel/runs.md` 全文；并逐项对照
  `docs/specs/gateway/agent-capabilities.md`、`docs/specs/kernel/runs.md`、
  `docs/specs/kernel/sdk-boundary.md`、`docs/specs/kernel/model-runtime.md`。
- 生产正向路径：`process_lifecycle._default_build_runtime → compose_gateway → build_pa_kernel →
  agent.sdk.build_kernel → build_hook_registry → auto_mode_gate → HookContext.call_model →
  AgentEngine._call_hook_model → provider client`；另核 Web/外部消息、heartbeat、cron、context
  fork/subagent 均复用该 Kernel/engine。
- Related：读取 `refactor-476-permission-transaction-owner` 当前 design/delta/review，区分其尚未
  落入生产代码的目标 seam 与本轮 current-code 事实。
- M1 骨架：`M1-impl/.gitkeep` 是唯一文件，符合设计阶段空骨架约定。

### 核实台账

#### 1. 现状断言、约束、复用能力与历史

| 原子 | 独立核实动作 | 结论 + 证据 |
|---|---|---|
| 现状 1：PA `llm` payload 只有 default/catalog，parse/save 在 local store | 读 DTO、parser 与 serializer，而非只核 design 引行 | 成立。`LLMConfigPayload` 当前仅有 `default_model/providers`（`src/personal_assistant/config/local_store.py:48-58`）；serializer 在 `:893-921` 写完整 `llm`，parser 在 `:986-1060` 建 catalog 并硬校验 default。 |
| 现状 2：Gateway 启动把 PA catalog 转 SDK `LLMConfig` 并装配唯一 Kernel | 从生产 lifecycle 正向追 composition | 成立。生产 lifecycle 调 `compose_gateway(config)`（`src/personal_assistant/gateway/process_lifecycle.py:824-828`）；composition 在 `:194` 转 DTO、`:210-215` 只调用一次 `build_pa_kernel`。 |
| 现状 3：Web/外部/heartbeat/cron 共用该 Kernel | 查各入口真实持有者，而非推断“同进程即相同” | 成立。Web/外部 run coordinator 收 `kernel`（`src/personal_assistant/gateway/composition.py:516-524`）；heartbeat 经同一 `kernel_shim`（`:578-590`）；cron 同时收相同 `kernel/kernel_shim`（`:280-289`）；最终 runtime 也持该 Kernel（`:656-669`）。 |
| 现状 4：派生运行共用 hook model caller | 追 context fork/subagent wiring | 成立。context fork 从 parent `HookContext` replace，保留 `model_caller`（`src/agent/core/agent/context_fork.py:213-249`）；subagent runner 复用同一 engine graph 且继承 parent run model（`src/agent/platform/tools/builtins/agent.py:343-361,409-416`）。 |
| 现状 5：`build_kernel` 是产品唯一装配入口 | 查两产品生产工厂与 contract | 成立。PA 只在 `build_pa_kernel` 调 SDK（`src/personal_assistant/product.py:381-434`），CLI 同样调 SDK（`src/coding_cli/product.py:121-154`）；产品越界由 `tests/contract/test_agent_sdk_boundary_contract.py:50-63` 拦截。 |
| 现状 6：auto gate 是仓内自动分类唯一模型调用方 | 全仓搜索 `.call_model(` 并读两个调用点 | 成立。生产源码仅 `auto_mode_gate.py:466,511` 调 `HookContext.call_model`；两处分别是 stage 1/stage 2（`:435-535`）。 |
| 现状 7：Hook model 已支持显式 model 与 provider 路由 | 追 DTO→context→runtime→client | 成立。`HookModelCall.model` 在 `src/agent/core/hooks/context.py:25-39`；context 原样传入（`:190-226`）；runtime 优先 `call.model`，再 run/default，并经 `provider_of` 选 client（`src/agent/core/agent/runtime.py:1463-1512`）。 |
| 现状 8：显式模型失败不会换模型 | 查异常前是否存在二次 model 解析/备用请求 | 成立。一次 `_call_hook_model` 固定局部 `model` 后生成同一 request（`runtime.py:1480-1512`）；auto gate 捕获 timeout/exception/不可解析并返回 ask，未再次调用其他 model（`auto_mode_gate.py:464-505,509-534`）。 |
| 约束 1：产品只 import SDK；依赖为 platform→core、sdk→core+platform | 对照顶层权威与 contract | 成立。`SPEC.md:113-124` 明确唯一 SDK 面与三层方向；产品 import guard 见 `tests/contract/test_agent_sdk_boundary_contract.py:35-63`。设计的 PA→SDK 参数与 SDK→platform state 未反向穿层。 |
| 约束 2：Kernel 是产品中立库，不恢复 HTTP/profile | 对照顶层架构与设计新增面 | 成立。`SPEC.md:62-85,113-124` 固定进程内库与无产品对象；新增参数对三类 SDK 消费者同构，不含 PA DTO/import。 |
| 约束 3：`llm.providers` 是 PA 注册表，错配启动失败 | 查 current parser 与 registry | 成立。PA 已用同一 catalog 校验 default/agent model（`local_store.py:1053-1060,1072-1124`）；registry 的未知 model 反查 fail loud（`src/agent/core/llm/model_registry.py:154-169`）。 |
| 约束 4：只改自动分类，不改规则/人工审批/unattended/正常 run | 逐段追 gate 分支与 run model 数据流 | 成立。静态/safe/tool-decision 分支在分类前返回（`auto_mode_gate.py:819-908`），分类只在 `:935-998`；正常/heartbeat/cron submit model 仍由产品按 Agent 解析（`src/personal_assistant/gateway/kernel_client.py:189-218`）。 |
| 约束 5：字段随 Gateway 进程 snapshot 生效 | 查 config owner 与 composition 的读取时机 | 成立。`compose_gateway` 只在构造期从 immutable config 生成 `LLMConfig`（`composition.py:172-215`），当前无 LLM file watcher/reconfigure path；正常重启重新走 lifecycle→composition。 |
| 复用 1：`HookModelCall.model` 与现有 provider 路由 | 查真实调用链 | 成立，证据同现状 7；无需新增 client/engine 分支。 |
| 复用 2：HookRegistry extension state 是 per-registry | 查 registry 存储与实例构造 | 成立。每个 `HookRegistry` 有实例级 `_extension_state` 与 lock（`src/agent/core/hooks/registry.py:20-27,123-142`）；每次 build 新建 registry（`src/agent/platform/hooks/loader.py:54-82`）。 |
| 复用 3：session_events/session_usage 已用该 state | 读 setter/getter，不接受 design 类比本身 | 成立。event publisher factory 通过 registry state 注入/读取（`src/agent/platform/hooks/session_events.py:12-37`）；usage reader 同样（`src/agent/platform/hooks/session_usage.py:10-49`）。 |
| 改动落点：只给 auto gate 两阶段调用传 model | 全仓 model call 搜索 + gate 分支检查 | 成立且是最窄 current-code 落点；两次调用位于 `auto_mode_gate.py:464-518`，其他普通模型请求不经过该函数。 |
| 不用 AutoModeConfig loader | 核 loader 所有权与生命周期 | 成立。该 loader 明确读 global/workspace `auto_mode` 段（`src/agent/platform/config/auto_mode.py:1-9,59-103`），并承载 allow/deny/unattended 策略（`:39-56`），不是 PA 顶层 Gateway catalog snapshot。 |
| 不用 session/per-Agent metadata | 查 Gateway 共享图与 current model 配置 | 成立。Gateway 只有一个 Kernel（上证）；per-Agent model 每轮解析（`kernel_client.py:198-218`），把统一选择复制进 session/Agent 会制造额外覆盖语义。 |
| 不把字段放 SDK `LLMConfig` | 对照 DTO 当前职责 | 成立。`LLMConfig` 明确是 catalog+connection+default（`src/agent/sdk/dto.py:107-137`）；自动权限分类策略不是连接/catalog 元数据。 |
| 历史 382：PA catalog/硬校验/重启语义 | 用 current code 复核历史结论 | 成立；current parser/serializer/composition 证据见现状 1/2/约束 3/5。 |
| 历史 406：唯一 SDK 装配 seam | 用 current code/contract 复核 | 成立；`build_kernel` 是公开 composition root（`src/agent/sdk/kernel.py:229-302`），两产品调用证据见现状 5。 |
| 历史 429：per-run model 与 hook 显式优先级 | 用 current runtime 复核 | 成立。Gateway 每轮传 resolved model（`kernel_client.py:198-218`），hook 显式优先级在 `runtime.py:1486-1493`。 |
| Related 476：权限事务所有权正交但可能同文件冲突 | 读 active related design，并与 current 区分 | 部分成立。权限 transaction 与 model 选择语义正交；但 related design 已明确计划把 builtin 依赖改为 `BuiltinHookDependencies` trusted injection（`docs/changes/refactor-476-permission-transaction-owner/design.md:126-136`），与本设计 D3 的 registry-state 注入不是单纯文本冲突，见 R1-W1。 |

#### 2. 编号决策

| 决策 | 四问核实 | 结论 + 证据 |
|---|---|---|
| D1 `llm.tool_approval_model` 可选字段 | 已拍死字段名、None/空串、catalog 校验、错误内容和 save round-trip；由 PA 配置场景驱动 | 成立。PA authoritative config 文档当前把持久 LLM 字段放在同一 `llm` 段（`docs/operations/gateway.md:5-44`）；parser/save seam 真实存在（`local_store.py:893-921,986-1060`）。 |
| D2 SDK 新增 build-scoped 参数、不进 `LLMConfig` | 参数、合法集合、from_env 语义、PA/CLI caller均拍死 | 设计本身成立；`LLMConfig.from_env()` 确实是无 catalog 单模型（`src/agent/sdk/dto.py:145-173`），`_init_model_registry_from_llm_config` 同样合成单模型目录（`src/agent/sdk/kernel.py:327-359`）。但这是公开装配契约变化，delta 漏项见 R1-C1。 |
| D3 选择存 HookRegistry state | current-code 下 setter/getter、build-only 生命周期与读取方闭合 | current main 可实现：registry state per-instance（`registry.py:20-27,123-142`），builtin setup 持有 `HookAPI`，其 `get_state` 直达同一 registry（`:145-191`；loader `src/agent/platform/hooks/loader.py:122-147`）。与 Related 476 的最终 seam 未拍死，见 R1-W1。 |
| D4 只给 stage 1/2 显式 model | 两阶段一致、None 回落、普通 run 不变 | 成立。两个唯一 call site 在 `auto_mode_gate.py:464-518`；runtime 优先级在 `runtime.py:1486-1493`；普通 submit 独立传 Agent model（`kernel_client.py:198-218`）。 |
| D5 失败沿用 fail-closed、不换模型 | provider retry 与 gate 失败分支均有确定语义 | 成立。retry 包在同一个 client/request 外层，而 gate 捕获后直接形成 ask（`auto_mode_gate.py:479-505,523-534,979-998`），没有 C→A/B 的第二分类入口。 |
| D6 只随 Gateway 重启切换 | 生命周期、不可热更、disk/runtime 分离明确 | 成立。composition 只读启动 snapshot（`composition.py:172-215`）；设计未新增 setter/watch/reconfigure。 |
| D7 以真实 request.model 验收 | 可观察锚与概率措辞分离，A→C→A/B→C→B 及失败禁备用均可确定断言 | 成立。provider request 的 model 由 runtime 写入 `LLMGenerateRequest`（`runtime.py:1497-1512`）；已有 E2E 也采用确定副作用/协议锚而非模型措辞（`tests/e2e/critical_paths/test_permission_approval_critical_path.py:10-18,93-165`）。 |

决策之间未发现互相矛盾；D1/D2 的双层校验分别承担 PA 字段错误与通用 SDK precondition，不是
无驱动重复防御。D3 的问题是与 Related unit 的未来装配 seam 未收口，而非 current main 无法实现。

#### 3. spec 约束

| spec 原子 | design 落点与独立核实 | 状态 |
|---|---|---|
| Q1：产品目标限 PA；Kernel 支持显式/复用两模式 | D1/D2/D4；CLI 不传（design `:125-126`），current CLI 唯一 build caller位于 `src/coding_cli/product.py:144-154` | covered |
| Q2：PA 未配置继续复用 Agent model | D1 `None` + D4 `call_model(model=None)`；runtime 的 run/default回落真实存在（`runtime.py:1486-1493`） | covered |
| Q3：未注册值拒绝启动、明确报错 | D1 PA parser + D2 SDK precondition；PA current hard-validation pattern在 `local_store.py:1053-1060` | covered |
| Q4：专用模型只做自动分类 | D4；全仓仅 gate 有 `ctx.call_model` 两处，正常 submit path独立 | covered |
| Q5：运行失败不回退 | D5；gate异常直接 ask，证据 `auto_mode_gate.py:479-505,523-534,979-998` | covered |
| Q6：配置随 Gateway 重启生效 | D6；生产启动 snapshot证据 `composition.py:172-215` | covered |
| Req 1：PA 可统一指定分类模型 | D1-D4 + 单 M1 | covered |
| Scenario：Agent A/B 分类共用 C | D7 `A→C→A/B→C→B`；M1 reviewer/worker exit均有请求序列锚 | covered |
| Scenario：Web/外部/heartbeat/cron/派生来源统一 | 架构总览 + D3/D4；生产共用 Kernel/parent HookContext 证据见现状 3/4；M1 要求不同 run origin测试 | covered |
| Scenario：分类 C 不改变正常 A | D4/D7；normal submit与 hook side-call 是两条独立 model入口 | covered |
| Req 2：未指定保持现有行为 | D1/D4 | covered |
| Scenario：省略字段时 A/B 分别复用 | D7 复用模式 `A→A→A/B→B→B`，M1 exit明确 | covered |
| Req 3：显式模型真实生效且不静默降级 | D1/D2/D5 | covered at design；Gateway delta不完整，见 R1-C2 |
| Scenario：未注册值拒绝启动 | D1/D2；M1 reviewer/worker均覆盖 | covered |
| Scenario：C 超时/失败不改用 A/其他，进入既有处理 | D5/D7；M1 exit有“无 A/B 备用分类 + 既有人工/unattended” | covered at design；Gateway delta漏项，见 R1-C2 |
| Req 4：随 Gateway 重启切换 | D6 | covered |
| Scenario：运行中 C，重启后 D | D6；M1 reviewer exit明确 C→D before/after restart | covered |
| 范围：PA 字段、所有来源、两 Kernel 模式、校验/不回退/重启 | D1-D7 + M1原子覆盖 | covered |
| 非目标：不改 CLI model选择 | CLI省略参数；current caller `src/coding_cli/product.py:144-154` 无需产品改动 | respected |
| 非目标：无 per-Agent覆盖/UI/普通模型改变 | 字段只在 PA顶层；D3 build-scoped；D4不改 submit；无 IM/frontend seam | respected |
| 非目标：不改规则/prompt/卡片/unattended/热更 | D4-D6；AutoModeConfig与UI/protocol不在接口表/M1代码范围 | respected |

#### 4. delta-spec

| delta 原子 | canonical 对账 | 结论 |
|---|---|---|
| gateway ADDED Requirement：统一选择分类模型 | current `agent-capabilities.md` 7条 Requirement 中没有同义条目；与既有“正常回复每轮 Agent model”并行（`docs/specs/gateway/agent-capabilities.md:14-45`） | ADDED 用法正确，target语义合适 |
| gateway Scenario：A/B 分类共用 C且正常 run不变 | 对应 spec Req1两个场景；THEN 是运维者/用户可观察模型路由结果，无内部函数名 | valid |
| gateway Scenario：省略时 A/B复用 | 对应 spec Req2；不修改既有 normal model requirement | valid |
| gateway Scenario：未注册拒启动 | 对应 spec Req3配置场景；运维者可观察 | valid |
| gateway Scenario：C→D重启才生效 | 对应 spec Req4 | valid |
| gateway 运行失败/不降级条目 | 首文档 `spec.md:66-77` 要求这是 PA 对外行为，但 gateway delta `:5-31` 无该 Scenario | missing，R1-C2 |
| kernel ADDED Requirement：consumer build时指定分类模型 | current `runs.md` 已有权限交互与自动动作描述（`docs/specs/kernel/runs.md:122-162`），没有模型选择契约；新增而非替换旧 Scenario | ADDED 用法正确 |
| kernel Scenario：显式 C只用于分类 | SDK consumer视角，结果可经 recording client观察；无内部符号断言 | valid |
| kernel Scenario：未选择复用 run A | 对应两模式 | valid |
| kernel Scenario：显式 model必须注册 | SDK build precondition，是库消费者可观察错误 | valid |
| kernel Scenario：失败不改用 A/其他并进入既有处理 | SDK consumer可观察请求/permission事件，无实现层 THEN | valid |
| kernel public `build_kernel(tool_approval_model=...)` | canonical `sdk-boundary.md:47-68` 逐字枚举 build surface；本 unit没有 `specs/kernel/sdk-boundary.md` MODIFIED delta | missing，R1-C1 |
| IM no spec delta | 不改 IM wire/UI/持久化；permission事件保持原状 | correct |
| CLI no spec delta | CLI caller省略新 optional参数，现有行为不变 | correct |

#### 5. Milestone

| Milestone | 核实 | 结论 + 证据 |
|---|---|---|
| M1 PA统一工具审批模型 | 单一垂直切片，无并行文件交集；范围从 config→SDK→gate→真栈，reviewer/worker两轨均有确定锚；骨架仅 `.gitkeep` | 结构正确。`M1-impl/.gitkeep` 存在且无预填 tasks/progress。它继承 R1-C1/R1-C2 的契约缺口与 R1-W2 的错误 health check，当前不能派发；无需拆 M2。 |

### 整体判断

- **人的上层视图**：架构总览、两张图和每条决策首句足以直接理解“PA启动选择→SDK
  build-scoped 注入→auto gate显式 model→runtime provider路由；normal run不变”，没有被 grounding
  淹没。
- **接口/数据流**：启动、分类、成功、失败、None fallback 与重启生命周期闭合；唯一未闭的是契约
  文档流——公开 SDK surface 和 PA failure behavior 未完整进入 delta inventory。
- **命名/自洽**：`tool_approval_model`、`HookModelCall.model`、`auto_mode_gate` 与 M1 命名一致；无
  TBD、模板注释或悬而未决二选一。Changelog 可空，不构成实施歧义。
- **风险/回退**：parse/save、stage 1/2、normal model、多 provider 与同文件冲突均有对应措施；旧
  parser 确实会忽略未知 `llm` key。Runbook 的起停参数存在，但 IM health URL 错误，见 R1-W2。
- **常驻服务**：给出了 e2e-up/down 与 restart语义；`scripts/e2e-up.sh` 当前明确以
  `/openapi.json` 探 IM ready（`:246-253`），不是 `/health`。

### 架构进攻

| 角度 | 攻击对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | PA字段、SDK参数、platform hook选择、core runtime路由 | PA拥有配置、SDK拥有消费者装配、platform builtin拥有策略读取、core只执行通用显式 model，依赖方向自然。唯一风险是 Related 476 已规划 trusted builtin deps，而 D3 固定走 extension-state；若两条 seam并存，builtin build依赖将形成两个注入协议，见 R1-W1。 |
| 该不该存在 | 新 SDK参数、tool-approval state窄模块、PA payload字段 | 删除 SDK参数则 PA只能越界或复制到 session；删除 PA字段则无法配置；窄 state模块隐藏共享 key，避免 SDK import builtin。current main下均有真实接缝，不是为假想多态新增 factory/Protocol。若 476 的 `BuiltinHookDependencies` 先落地，应删除测试反转为复用该 seam，而不是继续新建 state协议。 |
| 深还是浅 | `build_kernel(tool_approval_model)` 与 state helper | public参数把“注册校验+per-Kernel共享+只影响分类”压成一个选择，调用方比实现简单；runtime现有 explicit model/provider路由足够深，没有重造 client。真正的浅点不在代码抽象，而在 delta inventory：公开装配签名变了却不修改精确列签名的 canonical，长期产生两份不一致的 API truth，见 R1-C1。 |
| 治本还是补丁 | 统一模型选择与失败行为 | 方案把选择放在 Gateway唯一 build snapshot，并在唯一分类调用点显式路由，正面解决“每 Agent模型漂移”，没有按入口打补丁或构造 fallback链。Gateway delta漏写失败语义会让长期产品契约仍可被回退实现侵蚀，见 R1-C2。 |

### Issues

- [R1-C1][CRITICAL] **[delta-spec / 决策 2] 新增 public `build_kernel` 参数，却遗漏
  `specs/kernel/sdk-boundary.md` 的 MODIFIED delta。** Current canonical 在
  `docs/specs/kernel/sdk-boundary.md:47-58` 逐字枚举完整 `build_kernel(...)` 装配表面；D2 又明确
  把 `tool_approval_model` 定义为该 public seam 的新参数（design `:106-126`）。只把行为 ADDED
  到 `runs.md` 后，归并得到的 canonical 会同时声称“消费者可传这个参数”和“公开装配签名没有
  这个参数”。Related refactor-476 还在同一 Requirement 上增加另一参数（其 delta
  `specs/kernel/sdk-boundary.md:83-103`），所以按任一合并顺序都不能靠收尾时顺手补一句解决。
  不改会使 worker/verifier没有一份可归并的最终 SDK surface，后续 canonical与 contract测试各走
  各的。请新增完整 MODIFIED delta：以实施时最新 canonical/476结果为底，保留原 Requirement与
  全部 Scenario，只加入 `tool_approval_model` 的 optional参数、注册校验、None复用与产品中立语义。

- [R1-C2][CRITICAL] **[gateway delta / spec Requirement 3] PA运行期专用模型失败“不降级”没有
  进入 Gateway canonical 增量。** 首文档 `spec.md:66-77` 把“C超时/失败时不改用Agent/其他
  模型，值守转显式审批、无人值守遵守既有 fallback”列为 PA Requirement；design D5/M1也以此
  为验收行为。但 gateway delta `specs/gateway/agent-capabilities.md:5-31` 只有统一、缺省、非法
  配置和重启四个 Scenario，完全没有运行失败场景。Kernel delta能约束通用 SDK consumer，不能
  代替 `docs/specs/gateway/` 对 PA 运维者/终端用户行为的权威；该包入口也明确消费者包含运维者与
  各 IM 用户（`docs/specs/gateway/spec.md:5-13`）。不改时，unit归并后 PA canonical允许将来
  静默引入 C→A fallback或改变失败后的用户可见路径，verifier也无法对 Gateway delta逐条对账。
  请在现有 gateway ADDED Requirement 中补一个忠实 Scenario，保留“同一 C内 provider retry
  允许，但不换 model；随后走既有值守/unattended分支”。

- [R1-W1][WARNING] **[决策 3 / Related refactor-476] “固定使用 HookRegistry extension state”
  与已知的 trusted builtin dependency seam 没有明确合流规则。** Current main下 D3可实现；但
  related design 已决定 loader通过 `BuiltinHookDependencies(permission_policy_state=broker)` 只向
  canonical builtin `auto_mode_gate.setup(...)` 注入 build dependency，并明确避免 service locator
  （`docs/changes/refactor-476-permission-transaction-owner/design.md:126-136`）。feat-510 的风险段
  只写“按最新主干解冲突”，同时 D3又要求新增独立 state module，worker若在476之后执行只能猜：
  扩展 `BuiltinHookDependencies`，还是保留第二套 registry key/getter。后者长期让同一 builtin 的
  build-scoped依赖分散到 explicit deps与隐式state两种协议，每次 loader/override调整都要双维护。
  请在 D3 写条件式最终边界：若476 seam已落地，`tool_approval_model` 成为同一 trusted builtin
  dependency bundle的字段并删除本 unit state helper；若未落地，才采用当前 registry-state方案，
  且476后续迁移时必须收为单 seam。不要让 worker临场改架构。

- [R1-W2][WARNING] **[Runbook for Reviewer] IM健康检查指向不存在的 `/health`。** Design
  `:255-257` 要 reviewer 执行 `curl -fsS "$IM_URL/health"`；但当前 `e2e-up.sh` 明确说明 IM没有
  dedicated health endpoint，并以 `/openapi.json` 判 ready（`scripts/e2e-up.sh:246-253`），仓内
 真实栈E2E也检查该路径（`tests/e2e/test_worktree_stack_lifecycle_e2e.py:93`）。不改会让健康的
  隔离栈在验收第一步被误判失败，reviewer转而排查不存在的服务故障。请把健康检查改成
  `curl -fsS "$IM_URL/openapi.json"`，并继续单独核目标 node online 与 recording stub端口。

### Recommendations

- [R1-R1] 保留单一 M1；问题是契约 inventory 与两个 seam/命令需收口，不是需要再做横切拆分。
- [R1-R2] M1“运维文档”范围显式点名 authoritative `docs/operations/gateway.md`（其
  `:5-44` 已拥有持久 Gateway LLM配置），只在 README保留最小示例，避免 worker在多个入口复制
  完整字段说明。
- [R1-R3] 修订后先由原 design author补两份 delta/两处边界，再唤醒同一 reviewer做 delta模式；
  若 refactor-476 的核心 injection seam在此期间发生变化，应升级为 full。

### 本轮只读核验

- 未修改 `spec.md`、`design.md`、delta-spec、M1骨架或产品代码；未 commit。
- 执行了 production source/canonical/related-history 的只读路径追踪与全仓 call-site搜索。
- 未运行产品旅程或实现测试；本阶段只审设计，当前阻断项均可由静态契约与真实装配路径确定。

### Author Resolutions

- R1-C1: accepted。新增 `specs/kernel/sdk-boundary.md` 的完整 MODIFIED Requirement，保留
  current canonical 全部 Scenario，并把 optional public 参数、catalog 校验、None 语义和产品
  中立性投影到可归并契约；`design.md` delta inventory 同步登记该 target，并规定若 476 先
  归并，必须以最新 canonical 重写完整 MODIFIED 条目、同时保留两边参数与 Scenario。
- R1-C2: accepted。在 Gateway delta 的同一 ADDED Requirement 中补入专用模型失败场景，明确
  同一模型既有重试允许，但禁止改用 Agent/其他模型，随后沿用值守与 unattended 分支。
- R1-W1: accepted。决策 3 改为单一 trusted builtin dependency seam，并给出基于实施分支的
  确定规则：已有 476 bundle 就直接扩展；尚未落地才使用 registry-state bridge，后落地的 476
  必须迁移并删除 bridge；禁止 bundle 与 state 两条协议并存。图、接口表、风险和 M1 退出标准
  已同步。
- R1-W2: accepted。Runbook 健康检查改为仓库真实使用的 `GET /openapi.json`。
- R1-R2: accepted。M1 范围显式点名 authoritative `docs/operations/gateway.md`，不要求在
  README 复制完整可选字段说明。

## Round 2

### Metadata

- reviewer: `/root/feat_510_design_reviewer`
- review_mode: `full`
- mode_reason: `本轮不仅补证据/措辞，还新增完整 public SDK MODIFIED contract，并把核心 builtin dependency 从固定 registry-state 改为随 refactor-476 基线切换的双时序架构；这同时触及共享 SDK 表面、跨模块注入边界和 milestone 退出标准，按规则升级为 full，重建五类台账并重跑四角度架构进攻。`
- started_at: `2026-08-06T18:05:12+08:00`
- completed_at: `2026-08-06T18:12:04+08:00`
- duration: `6m52s`

### Verdict

Issues Found — 0 CRITICAL / 1 WARNING

R1 的两项契约缺口和错误健康检查均已实质关闭，新增 SDK MODIFIED delta 也忠实保留了 current
canonical 的原 Requirement 与全部 Scenario。统一模型的产品数据流、失败语义、重启语义和单一
M1 仍然成立。剩余问题集中在 D3 修订新增的架构承诺：文档把 current-main 的 registry-state
bridge 也称为“只给 canonical builtin”的 trusted dependency，但真实 HookAPI state 通道没有这条
访问隔离；同时数据流图和 D6 仍把两种基线都写成 registry state。公开行为可实现，然而 worker
无法同时满足当前 M1 的“独占依赖”退出标准与 bridge 机制，需先把这条边界说真、说一致。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 新增完整 `specs/kernel/sdk-boundary.md` MODIFIED Requirement，并规定与 476 的归并顺序 | 新 delta 保留 canonical 的 build/create 两层说明与原 4 个 Scenario（current `docs/specs/kernel/sdk-boundary.md:47-76`；delta `:5-43`），新增参数/None/非法值 3 个 Scenario（delta `:45-57`）；design `:243-246` 又要求 476 先归并时以最新 canonical 重写并保留双方参数/Scenario | closed |
| R1-C2 | Gateway delta 补专用模型失败且不换模型场景 | 新 Scenario 明确同一 C 的既有重试可用、不得改用 A/其他模型，并保留值守审批与 unattended fallback（`specs/gateway/agent-capabilities.md:26-30`），与首文档 `spec.md:66-77` 一致 | closed |
| R1-W1 | D3 改为单一 trusted builtin dependency，并按 476 是否存在选择 bundle 或 bridge | 原问题要求的合流/删除规则已补齐（design `:128-144,258-261`），不再允许两套协议并存；但新写下的“bridge 也只给 canonical builtin”与 current HookAPI 能力不一致，作为新问题 R2-W1 单列 | closed |
| R1-W2 | Runbook 改用 `/openapi.json` | design `:273-275` 已使用仓库真实 readiness endpoint，与 `scripts/e2e-up.sh:246-253` 及 `tests/e2e/test_worktree_stack_lifecycle_e2e.py:93` 一致 | closed |

R1-R2 也已采纳：M1 范围现明确点名 authoritative `docs/operations/gateway.md`（design `:286-288`）。

### Coverage

- 首文档：`spec.md` 全文，逐条复核 6 条澄清、4 个 Requirement、7 个 Scenario、范围与非目标；
  首文档本轮未改，但其所有约束均重新投影到修订后的设计与三份 delta。
- 设计：`design.md` 全文，含 5 组现状/约束/复用/历史断言、7 条决策、两张数据流图、6 个接口
  seam、3 个 delta target、6 项风险/回退、Runbook 与单一 M1。
- delta-spec：完整读取 gateway `agent-capabilities.md`、kernel `runs.md` 和新增 kernel
  `sdk-boundary.md`；逐条对照 current canonical 及 Related 476 对同名 SDK Requirement 的 MODIFIED
  delta，核 ADDED/MODIFIED 用法、原 Scenario 保留与 THEN 消费者可观察性。
- 生产正向路径：重新核 `process_lifecycle → compose_gateway → build_pa_kernel →
  agent.sdk.build_kernel → hook loader/registry → auto_mode_gate → HookContext.call_model →
  AgentEngine._call_hook_model → provider client`；另核 Web/外部、heartbeat、cron、context fork 与
  subagent 仍共用同一 Kernel/engine。
- Related/并发基线：重新读取 refactor-476 的 `BuiltinHookDependencies` 目标边界和其 SDK delta，
  并在 current source 搜索确认 `BuiltinHookDependencies` 尚不存在、现行 loader 给各来源同一种
  concrete `HookAPI`。
- M1 骨架：仍只有 `.gitkeep`；不把设计期空目录误报为问题。

### 核实台账

#### 1. 现状断言、约束、复用能力与历史

| 原子 | 独立核实动作 | 结论 + 证据 |
|---|---|---|
| PA `llm` 当前只有 default/catalog，local store 负责 parse/save/校验 | 重读 payload、serializer、parser 与 Agent model 校验 | 成立。`LLMConfigPayload` 当前仅含 `default_model/providers`（`src/personal_assistant/config/local_store.py:48-58`）；完整 `llm` 写回在 `:893-921`，catalog/default 与 Agent model 校验在 `:986-1124`。 |
| Gateway 启动 snapshot 转 SDK `LLMConfig` 并只装配一个 Kernel | 从生产 lifecycle 正向追到 composition | 成立。lifecycle 调 `compose_gateway(config)`（`src/personal_assistant/gateway/process_lifecycle.py:824-828`）；composition 在 `:194` 转 DTO、`:210-215` 唯一一次调用 `build_pa_kernel`。 |
| Web/外部、heartbeat、cron 使用同一 Kernel | 分别追真实 constructor 参数 | 成立。run coordinator 收同一 `kernel`（`composition.py:516-524`），heartbeat 收同一 shim/kernel（`:578-595`），cron 收同一 kernel/shim（`:280-289`），最终 runtime 也持它（`:656-669`）。 |
| Agent 派生运行不会另造 Kernel/model caller | 追 fork 与 builtin agent runner | 成立。context fork 保留 parent `HookContext.model_caller`（`src/agent/core/agent/context_fork.py:213-249`）；subagent 复用同一 engine graph并继承 parent run model（`src/agent/platform/tools/builtins/agent.py:343-361,409-416`）。 |
| `build_kernel` 是产品唯一可用装配 seam | 查 PA/CLI caller和 boundary contract | 成立。PA/CLI 都经 SDK factory（`src/personal_assistant/product.py:381-434`；`src/coding_cli/product.py:121-154`）；产品 import guard在 `tests/contract/test_agent_sdk_boundary_contract.py:35-63`。 |
| auto gate 是生产自动分类唯一 hook-model 调用方 | 全仓搜索 `.call_model(` 并读调用上下文 | 成立。生产源码只有 `auto_mode_gate.py:466,511` 两处，分别位于 stage 1/2（`:435-535`）。 |
| hook model 已支持显式 model 和跨 provider 路由 | 追 call DTO→context→runtime→client | 成立。`HookModelCall.model`/传递在 `src/agent/core/hooks/context.py:25-39,190-226`；runtime按 explicit→run→default取值并用 `provider_of` 选 client（`src/agent/core/agent/runtime.py:1463-1512`）。 |
| 显式调用失败不会自动改模型 | 检查一次请求后的所有 catch/fallback分支 | 成立。runtime固定一次 request.model（`runtime.py:1480-1512`）；gate timeout/error/parse failure直接返回 ask，未发备用模型请求（`auto_mode_gate.py:464-540,979-998`）。 |
| 产品/内核分层与产品中立约束 | 对照顶层架构和 import guard | 成立。`SPEC.md:113-124` 固定 PA/CLI只依赖 SDK及 core/platform方向；本设计新增的是中立 SDK参数，没有 PA DTO进入 core。 |
| 注册值应在 Gateway启动期失败 | 查 current PA catalog validator与 model registry | 成立。现有 default/Agent model均在 parse期对 catalog硬校验（`local_store.py:1053-1060,1072-1124`），同一位置可承载新字段级错误。 |
| 改动只触及自动分类，不改静态规则/人工审批/normal run | 读 gate先行分支及 Gateway submit model入口 | 成立。静态/safe/tool-decision路径在分类前返回（`auto_mode_gate.py:819-908`），分类仅在 `:935-998`；正常 run model由 `kernel_client.py:189-218` 独立解析并提交。 |
| PA顶层 LLM配置按进程 snapshot生效 | 查 composition与是否存在 watcher/reconfigure | 成立。composition仅在构造期从 config生成 LLM/Kernel（`composition.py:172-215`）；本设计未新增 runtime setter或 watcher。 |
| extension state 是 per-registry 可复用能力 | 读存储、构造和现有用户 | 成立。state保存在每个 `HookRegistry`实例（`src/agent/core/hooks/registry.py:20-27,123-142`）；session event/usage均以此注入build-scoped reader（`src/agent/platform/hooks/session_events.py:12-37`；`session_usage.py:10-49`）。但它是共享state通道，不自带 trusted-caller隔离，见R2-W1。 |
| AutoModeConfig workspace loader不适合拥有 PA统一选择 | 查其输入和职责 | 成立。loader读 global/workspace `auto_mode`（`src/agent/platform/config/auto_mode.py:1-9,59-103`），数据是allow/deny/unattended策略（`:39-56`），不是Gateway LLM catalog。 |
| session/per-Agent metadata不适合build-scoped统一值 | 对照共享Kernel和per-run model | 成立。Gateway共享一个Kernel；Agent model是每轮输入（`kernel_client.py:198-218`）。复制统一选择会制造无spec驱动的per-Agent覆盖和旧session漂移。 |
| SDK `LLMConfig`只描述catalog/connection/default | 重读DTO及from_env | 成立。职责在 `src/agent/sdk/dto.py:107-173`；审批分类策略由独立build参数承载更符合所有权。 |
| 历史382/406/429可继续作为current前提 | 用当前代码而非历史文本复核 | 成立。local store/composition、唯一SDK build与runtime explicit model优先级分别由上述现状证据确认。 |
| Related476语义正交但共享装配/hook seam | 对照其design和delta | 成立。476把人工权限状态放进 `BuiltinHookDependencies`且只给canonical builtin（`docs/changes/refactor-476-permission-transaction-owner/design.md:126-136`），同时MODIFIED同一SDK Requirement增加`permission_interaction_port`（其delta `:83-103`）；本unit必须处理合并顺序。 |

#### 2. 编号决策

| 决策 | 四问核实 | 结论 + 证据 |
|---|---|---|
| D1 `llm.tool_approval_model`可选字段 | 字段名、None/空串、catalog错误和round-trip均拍死；归属由PA配置场景驱动 | 成立。持久Gateway LLM配置的authoritative入口是 `docs/operations/gateway.md:5-44`，真实parse/save seam在 `local_store.py:893-921,986-1060`。 |
| D2 public `build_kernel`新增build-scoped参数 | 参数合法集合、from_env单模型、PA透传和CLI省略均拍死；不把产品策略塞进连接DTO | 成立。from_env无catalog时只合成`llm.model`（`src/agent/sdk/kernel.py:305-359`）；新增MODIFIED delta已补齐公开表面（本unit sdk delta `:5-57`）。 |
| D3 统一为一条builtin dependency seam，按476基线选择bundle/bridge | 选择条件、迁移者与禁止并存均明确；再核两种实现是否都满足同一不变量 | 部分成立。current main确无`BuiltinHookDependencies`，bridge可传值；476目标bundle也可传值。但bridge经所有hook都拿到的concrete `HookAPI.get_state`读取，不能兑现“workspace/product hook不得获得/ canonical builtin独占”这一trusted不变量（`registry.py:145-191`；`loader.py:122-147,160-176`），见R2-W1。 |
| D4 仅stage1/2传可选model | 两调用点、None回落、normal run不变均无歧义 | 成立。两处call site在 `auto_mode_gate.py:464-518`；runtime回落在 `runtime.py:1486-1493`；normal submit独立。 |
| D5失败沿用fail-closed且绝不换模型 | 同模型retry边界、ask/attended/unattended后果均拍死 | 成立。gate错误转ask（`auto_mode_gate.py:479-540`），最终ask按run origin进入显式审批或unattended fallback（`:979-998`），没有第二分类入口。 |
| D6只随Gateway重启切换 | 生命周期决策成立；核不同依赖基线的措辞一致性 | 行为成立；但 `design.md:169` 只写“运行中registry state”，对476 bundle基线不准确，和同段“文件不被运行中Kernel监听”的真正不变量可拆开表达，纳入R2-W1。 |
| D7以真实request.model验收 | 请求序列与失败禁备用均可确定断言，不靠模型自然语言 | 成立。runtime把chosen model写进`LLMGenerateRequest`（`runtime.py:1497-1512`）；M1对A/B/C序列、failure与restart均给出双轨退出锚（design `:286-288`）。 |

D1/D2双层校验分别负责PA字段错误和所有SDK消费者的precondition，不是无需求驱动的重复防御；
D3外的六条决策之间未发现矛盾、待定项或越出spec的产品行为。

#### 3. spec约束

| spec原子 | design落点与独立核实 | 状态 |
|---|---|---|
| Q1：目标限PA；Kernel支持显式/复用 | D1/D2/D4；CLI省略参数且current caller只经SDK（`src/coding_cli/product.py:121-154`） | covered |
| Q2：PA省略时复用Agent model | D1 None + D4 `call_model(model=None)`；runtime真实回落到run model（`runtime.py:1486-1493`） | covered |
| Q3：未注册值拒绝启动 | D1 PA parser + D2 SDK precondition；M1含字段名/非法值验收 | covered |
| Q4：专用模型只做自动权限分类 | D4；全仓只有gate两处hook-model调用，normal submit路径独立 | covered |
| Q5：运行失败不改用其他模型 | D5/D7；Gateway与Kernel delta都已有不回退Scenario | covered |
| Q6：修改后重启才切换 | D6；M1有C→D重启前后验收 | covered |
| Req1：PA可统一指定自动分类模型 | D1-D4 + M1完整垂直路径 | covered |
| Req1 Scenario A/B统一用C | D7与M1记录`A→C→A`/`B→C→B` | covered |
| Req1 Scenario所有PA来源 | 共享Kernel图+D3/D4；生产Web/外部/heartbeat/cron/fork证据见现状台账 | covered |
| Req1 Scenario C不改变normal A/B | D4；hook side-call和normal submit是独立model入口 | covered |
| Req2：未配置保持现有行为 | D1/D4；None明确走current run model | covered |
| Req2 Scenario A/B分别复用 | D7复用序列与M1 reviewer退出标准均明确 | covered |
| Req3：显式选择真实生效且不静默降级 | D1/D2/D5 | covered |
| Req3 Scenario未注册拒启动 | D1/D2、两层错误语义和M1均覆盖 | covered |
| Req3 Scenario C不可用时不换model并走既有权限失败处理 | D5/D7、Gateway delta `:26-30`、Kernel delta `:26-30` | covered |
| Req4：随Gateway重启切换 | D6 | covered |
| Req4 Scenario运行中C、重启后D | D6/D7与M1真栈验收 | covered |
| 范围：PA字段、所有来源、两Kernel模式、校验/失败/重启 | D1-D7与M1均有落点 | covered |
| 非目标：不改CLI、无per-Agent覆盖/UI/normal model改变 | CLI省略；字段只在PA顶层；无frontend/IM seam；D4不改submit | respected |
| 非目标：不改规则/prompt/卡片/unattended、无热更新 | D4-D6复用现有分支；接口表/M1无这些改动 | respected |

#### 4. delta-spec

| delta原子 | canonical对账/可观察性 | 结论 |
|---|---|---|
| Gateway ADDED Requirement：统一选择模型 | current `docs/specs/gateway/agent-capabilities.md:14-45`只有normal Agent model等既有能力，无同义Requirement | ADDED正确，target最窄 |
| Gateway Scenario：A/B分类共用C且normal不变 | 对应spec Req1；运维者可从recording请求与最终run观察 | valid |
| Gateway Scenario：省略字段A/B分别复用 | 对应spec Req2；不顶替current normal model Requirement | valid |
| Gateway Scenario：未注册值拒启动 | 对应spec Req3配置错误；错误为运维者可观察 | valid |
| Gateway Scenario：C失败不换A/其他并走既有处理 | 新增条目 `:26-30` 忠实覆盖spec `:73-77`；THEN无内部函数/日志断言 | valid，R1-C2 closed |
| Gateway Scenario：C→D重启生效 | 对应spec Req4 | valid |
| Kernel runs ADDED Requirement：consumer可指定分类模型且不降级 | current `docs/specs/kernel/runs.md:122-162`描述权限行为但无分类model选择 | ADDED正确，consumer视角正确 |
| Kernel runs Scenario：显式C仅用于分类 | 可由SDK consumer recording client观察C与normal A | valid |
| Kernel runs Scenario：None复用run A | 对应两模式且不修改既有per-run contract | valid |
| Kernel runs Scenario：显式model须注册 | build失败是SDK consumer可观察precondition | valid |
| Kernel runs Scenario：失败不改A/其他并进入既有处理 | 请求与permission结果可观察，无内部符号THEN | valid |
| Kernel SDK MODIFIED Requirement：完整build/create两层表面 | 精确锚current同名Requirement；原文语义与4个Scenario全部保留（canonical `:47-76`；delta `:5-43`） | MODIFIED正确，R1-C1 closed |
| SDK Scenario：应用零前置装配 | 从canonical忠实保留 | valid |
| SDK Scenario：三应用同构 | 从canonical忠实保留，新增参数仍产品中立 | valid |
| SDK Scenario：工具目录共享/会话子集 | 从canonical忠实保留 | valid |
| SDK Scenario：Kernel稳定方法集 | 从canonical忠实保留，未借MODIFIED删API | valid |
| SDK Scenario：registered C成功 | consumer视角、结果为build成功/中立 | valid |
| SDK Scenario：None/省略成功 | consumer视角；未把内部state写入THEN | valid |
| SDK Scenario：unregistered X在runtime/background前拒绝 | consumer可观察启动边界；未断言内部函数调用 | valid |
| IM/CLI no spec delta | 不改IM wire/UI/持久化，CLI省略optional参数 | correct |

Related 476 若先归并会改变同名MODIFIED基底；design `:243-246` 已把“保留双方参数和全部Scenario”
写成M1硬规则，避免任一delta静默覆盖另一unit的public interface。

#### 5. Milestone

| Milestone | 核实 | 结论 + 证据 |
|---|---|---|
| M1 PA统一工具审批模型 | 单一垂直切片从config→SDK→builtin gate→真实请求；无横切拆分/并行碰撞；reviewer轨逐条引用所有用户场景，worker轨覆盖parse/save、两stage、SDK contract、注入seam、recording E2E和静态门禁；范围明确含`docs/operations/gateway.md`；骨架仅`.gitkeep` | 拆分正确、两轨可验。唯一阻碍是“canonical builtin独占依赖”在registry bridge基线下没有可实现的判定边界，见R2-W1；无需增加M2。 |

### 整体判断

- **人的上层视图**：总览仍能直接读出“PA配置→唯一SDK build→builtin gate显式C→runtime按provider
  路由；normal A/B不变”。D3的两种实施基线已经有确定选择规则，但总览下方的sequence和D6仍用了
  只适用于bridge的state名称，造成一个局部架构承诺不一致。
- **接口/数据流**：PA parse/save/compose、SDK precondition、builtin分类、成功/失败、None与restart
  路径均闭合；三份delta现在覆盖所有对外变化。断裂只在“trusted/exclusive”这一内部依赖属性，而非
  用户模型路由。
- **常规完整性**：无TBD/模板残留；字段、参数、模型序列、failure和restart命名一致；风险均有测试或
  合并规则。Runbook包含可执行起停、真实health endpoint、node/stub readiness和隔离真栈pytest命令。
- **风险/回退**：config round-trip、stage2、多provider、normal model、476冲突和代码revert都有对应
  策略；没有新增运行时自动降级或热更开关。

### 架构进攻

| 角度 | 攻击对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | PA字段、SDK参数、platform builtin依赖、core路由 | 字段由PA拥有、consumer策略经SDK装配、platform builtin消费、core只执行通用显式model，符合`PA→SDK→platform/core`方向。D3 bundle分支的trusted依赖也自然归loader；bridge分支却把“仅canonical可得”建立在共享HookAPI state上，访问边界名不副实，见R2-W1。 |
| 该不该存在 | public参数、PA payload字段、registry bridge/BuiltinHookDependencies | public参数和PA字段均不可删，否则只能越界或复制到session。current main复用existing state是最小实现；476已存在时复用bundle避免第二套helper。条件分支本身有真实并发基线驱动，不是假想多态；但bridge不应被包装成安全/独占抽象，否则worker会为证明它而加脆弱caller检查。 |
| 深还是浅 | `build_kernel(tool_approval_model)`、窄state helper、recording fixture | public参数把注册校验、per-Kernel生命周期与分类专用性藏在一个选择后，接口明显比实现简单；runtime provider路由和recording fixture均复用既有能力。state helper集中key能减少拼写漂移，但无法把共享state变成trusted injection；把它写成“exclusive”只会增加名义抽象而不增加隔离。 |
| 治本还是补丁 | 统一模型选择、476并发处理、失败行为 | 在唯一build和唯一分类call site解决模型漂移是治本；不按Web/heartbeat/cron分别打补丁，也不造C→A fallback。基线选择/后续删除bridge有明确偿还者，临时路径不冒充永久双协议；当前需要修的是对bridge能力的过强承诺，不是另造第四条seam。 |

### Issues

- [R2-W1][WARNING] **[决策3 / 接口表 / M1退出标准] registry-state bridge无法兑现文档新承诺的
  “trusted且canonical builtin独占”依赖边界，两种基线在正文其他位置也仍被写成同一种state协议。**
  D3先要求workspace/product同名hook不得获得该build-scoped值，并把最终seam定义为只向canonical
  builtin注入（design `:128-136`）；接口表和M1又要求“只给canonical builtin/断言独占”（`:233,288`）。
  但current-main分支指定的bridge经`HookRegistry` extension state实现（`:137-140`），真实loader向
  builtin、product、workspace模块传的是同一种concrete `HookAPI`（`src/agent/platform/hooks/loader.py:122-147,160-176`），而该对象对所有来源都暴露无identity校验的`get_state`（`src/agent/core/hooks/registry.py:145-191`）。窄helper可以集中key，却不能形成访问隔离。反过来，sequence仍写SDK必然“写入hook state”，D6也只描述“运行中registry state”（design `:169,197`），又不适用于476 bundle分支。不改时，current-main worker要么为满足“独占”退出标准发明脆弱的source/private-field校验，要么擅自把它解释成“只有builtin按约定读取”；若476先落地，另一个worker还可能按图继续写state。请在design层二选一拍死：若“不可被非canonical hook获得”是真正架构不变量，就不要用共享state bridge，缺476时也引入同一trusted bundle；若按当前需求采用最小bridge，则如实写成“canonical builtin是唯一预期reader，但state不是访问控制边界”，把M1测试改为断言仅有一条model-selection协议/只有canonical gate消费，并把D6与sequence改成基线中立的`builtin dependency`措辞。spec并未要求把模型id当secret，后者更符合当前最小范围。

### Recommendations

- [R2-R1] 保留单一M1和现有public SDK/PA契约；R2-W1只需让依赖能力、图和退出标准讲同一件事，不应借机扩成权限hook框架重构。
- [R2-R2] 修订后可由同一reviewer走`closure`：只需核D3、sequence、D6、接口表和M1断言是否对同一bridge/bundle不变量达成一致；除非作者改成在feat-510内新建完整`BuiltinHookDependencies`架构，才升级`delta/full`。

### 本轮只读核验

- 除向本文件末尾追加Round 2外，未修改`spec.md`、`design.md`、delta-spec、M1骨架或产品代码；未commit。
- 未运行产品旅程或实现测试；本阶段只审设计。生产代码、canonical、Related unit和runbook均以只读方式核验。

### Author Resolutions

- R2-W1: accepted，选择 reviewer 建议的最小 bridge 语义。D3 不再声称 registry-state bridge
  是访问控制或 canonical builtin 独占通道，而是明确 model id 非 secret、canonical auto gate
  是唯一生产 consumer；共享 state 在已知 key 后技术上可由其他 hook 读取。若 476 bundle 已
  存在则复用其 trusted 注入；否则 bridge 只作为待 476 迁移删除的单一临时协议。sequence、D6、
  接口表、风险和 M1 均改成基线中立的 builtin/model-selection dependency 措辞，worker 断言也
  改为“生产源码只有 auto gate 消费 + bundle/bridge 不并存”，不再要求 bridge 无法提供的访问隔离。

## Round 3

### Metadata

- reviewer: `/root/feat_510_design_reviewer`
- review_mode: `closure`
- mode_reason: `本轮只修订 R2-W1 指出的 bridge 能力表述及其在 sequence、D6、接口表、风险和 M1 的投影；未改变 public SDK/PA 契约、用户行为、delta-spec、数据流或 milestone 拆分，影响边界可封闭，沿用 Round 2 的 full inventory。`
- started_at: `2026-08-06T18:13:58+08:00`
- completed_at: `2026-08-06T18:14:51+0800`
- duration: `0m53s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R2-W1 已实质关闭。设计现在如实区分 current-main bridge 与 476 bundle：前者是非 secret model id
的共享 registry state，不承诺访问隔离；后者才是 canonical builtin 的 trusted 注入。两种基线仍
只允许一条 model-selection 协议，用户行为和 public contract 相同，worker 不再需要猜测或发明
bridge 无法提供的 source-level 访问控制。可以进入 `change-orchestrator`。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-W1 | 选择最小 bridge 语义；去掉 trusted/独占承诺，明确非 secret、唯一生产 consumer 与其他 hook 已知 key 后技术可读；同步 sequence、D6、接口表、风险和 M1 | D3 现明确 model id 非 secret、canonical auto gate 是唯一生产 consumer、bridge 不承诺阻止其他 hook 读取，并只在 476 已存在时使用 trusted bundle（design `:128-147`）；这与 concrete `HookAPI.get_state` 对各 hook source 无访问隔离的现状一致（`src/agent/core/hooks/registry.py:145-191`；`src/agent/platform/hooks/loader.py:122-147,160-176`）。sequence 与 D6 已改为基线中立的 `Kernel-scoped builtin dependency`（design `:170-174,188-209`）；接口表明确 bridge 不承诺访问隔离且两协议不并存（`:228-237`）；风险使用单一 model-selection 协议（`:251-265`）；M1 改为断言生产源码只有 auto gate 消费且 bundle/bridge 不并存（`:288-292`）。全设计搜索中 `trusted` 只再限定 476 bundle，不再修饰 bridge。 | closed |

### Issues

None.

### Recommendations

- [R3-R1] 当前设计已通过 Gate 2，可按单一 M1 交给 `change-orchestrator`；实施分支若已有 476 bundle，就按 D3 复用它，否则采用已写明非访问控制边界的 registry-state bridge。

### 本轮只读核验

- 除向本文件末尾追加 Round 3 外，未修改 `spec.md`、`design.md`、delta-spec、M1 骨架或产品代码；未 commit。
- 本轮为 closure，仅重核 R2-W1、Author Resolution 和其直接改动位置；Round 2 的 full 台账与其余结论未被本轮改动失效。

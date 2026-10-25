# Design Review — bugfix-660-shared-agent-lifecycle

## Round 1

### Metadata

- reviewer: `/root/shared_design_review`（独立 change-design-reviewer）
- target: `incident.md`、`design.md`、`specs/gateway/service-lifecycle.md`、design 中的 `M1-shared-lifecycle` skeleton
- review_mode: full
- mode_reason: Gate 2 首轮；重新确定共享执行所有权、恢复入口及跨模块停止边界，需要全范围审查。
- baseline: Nano `main` / `f00653f1aac14c557daf18b20520a0863fe564da`；DSH 本地参考 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`，同时检查 Nano 安装的 `0.2.1-alpha.1` 公开类型及既有真实 probe。
- started_at: 2026-10-25T22:54:49+08:00
- completed_at: 2026-10-25T22:58:24+08:00
- duration: 3m 35s

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

公开 AgentHandle、原生子树 drain 和 Nano 按产品 Agent 收拢自动入口可以支撑目标方案。设计明确保留 Web/iOS 及持久停用协议，撤销逐普通 Agent OS 进程、control host 与拆分迁移，没有把单次 cancel 或停止整个运行时当作完成条件。本结论只批准设计可实施；不表示尚未实现的共享生命周期或真实产品验收已通过。

### Coverage 与证据

#### 现状、用户约束与职责边界

- 从真实入口 `apps/node/src/main.ts:101`、`runtime-partitions.ts:40` 及 `agent-lifecycle.ts:35` 核对：当前组装确实具有 control host、普通 Agent 独占 partition/home、`agents[0]` 初始化与 host 级 disable。`packages/dsh-integration/src/index.ts:684` 的禁用分支还会全局停 Task/Cron/model/knowledge/workflow，并卸载 loop/subprocess provider。incident 的根因与本地实现一致，不能只改 partition key。
- design 将 Node 的职责限定为持久用户意图、可信路由、状态确认及各 owner admission；DSH integration 持有原生 Session handle 并衔接 Nano 自动驱动；DSH 承担 loop、Session、Job/终端及原生子树生命周期。该分工复用现有能力，没有新增另一套执行循环、进程树管理器或数据搬迁框架。
- 普通 shared + 既有 PA scoped 的目标、5 秒未确认状态、失败不杀共享 host、启用不恢复旧 Task、全部停用仍可管理、生产不部署/不迁移/不发包均已明确。生产版本核对属于 incident 提供的会话证据；本 reviewer 未重新连接生产，未据此执行生产操作。

#### owner 创建、恢复、fork 与子树

- Nano 安装包的公开声明包含 `AgentRegistry.create/resume -> AgentHandle`、`AgentHandle.dispose`、`SessionController.resolveAgent`、`buildForkSeed` 与 `SubagentRuntime.drainContinuableDescendants`；已核对 `packages/dsh-integration/node_modules/@deepseek-ai/` 对应包的 `lib/types`，以及 DSH `packages/core/session/package.json` 的 root/`./fork` exports、`packages/api/session-controller/package.json` 的 root export。方案不需要 private import。
- DSH `packages/core/agent/src/index.ts:95`、`:145`、`:391`、`:410` 与 `packages/core/agent-loop/src/index.ts:518` 表明：factory setup 在发布前完成；dispose 等待 loop/scope 退出、持久写 handle close，移除 registry，并传播聚合失败。可承接“仅清理完成并持久后确认”，无需卸载全局 provider。
- 本地 probe `~/.codex/reports/dsh-session-isolation-20261025/result.json` 记录同 host PID 955：A cancel 后 A 后台 Job 仍在，A handle dispose 后 A shell 收到 SIGTERM、A Agent/Job 移除，B Agent/Job 保持运行。它直接支持 handle 隔离能力；不把该 probe 外推为终端、所有子树与 Nano 产品入口均已验收。后者已进入 M1。
- DSH `packages/subagent/subagent/src/index.ts:340` 的公开 drain 会关闭指定 live parents 下 continuable admission、等待已接纳 materialization 并 child-first 释放 activation handles，其他 parent 不受影响。design 先关闭 Nano admission、等待创建中 root、drain continuable descendants 再释放 root scope 的顺序能够覆盖当前真实 ownership 机制。
- DSH `packages/api/session-controller/src/index.ts:226` 的 public resolver 可被 subclass 覆盖；原生 Schedule 的实际调用在 `packages/schedule/schedule/src/runtime.ts:101`，确实经过该 resolver。Nano 的 `ensure/agent` 在 `index.ts:765`，fork 在 `history.ts:179`；design 明确把 create/fork 也交给 owner，避免误以为只覆盖 resolver 就能拦截 controller 内部的全部创建。
- `NativeHistory.performFork` 目前保存配置 snapshot、operation/idMap、override，并依赖创建期配置绑定；design 明确保留这些语义并仅复用公开 `buildForkSeed` 生成 seed。factory 的 setup 能在发布前 mount preset 与建立 owner 归属，无需复制 DSH fork 算法。

#### 自动入口、共享路由与冷历史

- 已追踪 `CronOwners` 的 per-Agent storage realm 与 `disposeAgent`，TaskExecutionDriver 的事件驱动入口，ModelPolicy/ModelFallback 的续跑及持久取消，KnowledgeRuntime 的 reviews/facts，WorkflowEngine 的 live runs、`stopSession` 与持久 records。当前存在的全局 stopped/cancelPersisted 行为是本次应修改的落点；design 明确要求按 owner 清理、保留 B pending、初始化 bindings/config/lifecycle 后才恢复服务，范围和顺序已收口。
- `RuntimePartitions.scoped/resolve/validateOrigin` 及 main 的 KnowledgeUpdates/WorkflowResults 组装当前依赖 partition 身份。design 第 7 步明确 collection 仍走 scoped port、返回逐条可信 owner 过滤、ACK 不搜其他 owner；普通通知/审批/Session 路由按 Agent 和 lineage 门禁，而不是继续用 partition 的第一个 Agent。该决定覆盖共享后最关键的调用与返回边界。
- 历史只读路径确有可复用实现：`trajectory.ts:172` 在 Session cold 时使用 `sessionQuery.observeSession + controller.page`，live 时才进入 `controller.follow`；`history.ts` 的 export 同样能只读持久 Session。DSH `SessionHistoryController.follow` 的 prepared Session 分支会通过内部 controller promote，且不经过 subclass 的 public resolver（上游 `history.ts:204`、`index.ts:208`）。因此 design 第 6 步的“不调用 resolveAgent/create/resume”应理解为保留 Nano 现有 cold/live 分支，不能把冷历史改成直接 follow。现有路径与设计一致，这不是存活 finding。
- Node 需改变哪些 `agents[0]`/control/host disable 依赖、何时发布各 Agent 状态、host instance 的共享含义均已有决定；没有要求为每个调用编写逐行实施说明。

#### Context Design Review

- mode: Design Review；触发面为 Session 创建/恢复/失效及自动输入的交付时间，非单纯内部重构。
- Consumer: root、原生子 Agent，以及由 Schedule、Task、模型续跑、知识复盘和 Workflow 驱动的 LLM 请求。已追踪可信 binding/parent lineage → preset setup → ConfigurationScopes/ModelPolicy/NativeHistory → inbox/pre-step → 持久 fence 与恢复。
- Before/After: 原创建与恢复经 SessionController，fork 另存历史配置；改后 owner 持有 handle，但 preset、tools/skills/system prompt、cwd、seed、配置 snapshot 和模型路由仍由原服务组装。停用 A 时宿主阻止交付和执行，B 的 Context 保持；启用 A 后新消息恢复既有历史与配置，旧自动 inbox/Task 不随之获得新授权。模型不需要推导或填写宿主 owner/revision。
- 设计用 per-Agent revision/disabledThroughRevision 与 Session fence 保留失效范围，明确绑定在自动消费前可见，并以实际 LLM 日志、root/child 与恢复历史证据进入 M1 退出标准。没有发现来源、权限或恢复语义的设计缺口。
- 本轮未运行真实模型；安装包 API 与 probe 只能证明可行的生命周期基础，不能代替最终 Context 交付验证。实现审查应核对真实组装，产品验收应按 M1 运行代表性任务。

#### delta-spec、M1 与体验验收

- delta 正确锚定 `docs/specs/gateway/service-lifecycle.md:342` 的同名 Requirement；原有停止、自动输入、离线意图、历史管理和外部动作 Scenario 完整保留，仅用共享数据场景替换“旧共享运行数据升级”。顶层拓扑继续归 `SPEC.md`，没有把实现细节散写到 IM/UI spec。
- 与 `docs/specs/im/agents-nodes.md:968` 及 `ios-client.md:124` 的既有真人操作、未确认状态、重新启用和旧任务说明一致。本 unit 没有新视觉/交互设计，本轮未重新渲染页面或运行 iOS；不声称已独立验证当前 UI。M1 已要求真栈 Web 验收保留的完整路径，只有原生 UI 实际变化才扩大 iOS 验收，符合本轮范围。
- 单 M1 同时覆盖 Node 与 integration 的共享接口修改，没有并行文件归属冲突；worker 负责生命周期/Context/自动入口，reviewer 负责用户路径、离线/重启/未确认与管理能力，退出标准能够证明此次范围。Runbook 的参数笔误见非阻断修订建议。

### 历史问题闭环

首轮 full，无既往 review issue 或 Author Resolution。

### Issues

无。

### Recommendations

- **R1-R1 — 修正 Runbook 参数拼写。** `design.md:75` 使用 `--runtime-root`；实际 `scripts/e2e-up.sh:115` 与 `e2e-down.sh:9` 接受 `--wt`，目标临时目录需先存在。建议将两条命令统一改为 `--wt /tmp/nano-bugfix-660` 并保留实际隔离配置交接。作者在评审期间主动指出同一笔误；reviewer 已独立核实脚本。该局部文档修正不改变设计、范围或退出标准，可由作者记录 retained，无需因这处拼写单独触发设计复审。

### Author Resolutions

- Runbook suggestion — accepted：将不存在的 `--runtime-root` 改为实际脚本 `--wt`；脚本负责分配端口与配置。只修执行命令，不改设计语义，R1 retained。
- Cold history recommendation — accepted：保留 NativeTrajectory 的 sessionQuery + page 冷读分支；cold follow 不调用 DSH 会触发 promotion 的 follow。现有设计已要求历史不得激活，实施按该既有边界验证。
- 作者核对 R1、公开接口和实际接线，无实质异议；没有新增架构或范围变化。

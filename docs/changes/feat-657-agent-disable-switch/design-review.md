# feat-657 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review`，独立 reviewer；使用 `change-design-reviewer`，未参与作者产物编写。
- review_mode: `full`
- mode_reason: 首次 Gate 2，覆盖跨进程生命周期、恢复、持久化迁移和 Web/iOS 增量，不能仅作局部 closure。
- started_at: 2026-10-25T16:46:00+08:00（分钟级记录）
- completed_at: 2026-10-25T16:58:01+08:00
- duration: 约 12 分钟，包含本轮内用户反馈修订后的重新走查。
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，HEAD `404b5ef02b9f22537c871c8d91e6195a5f09c6b2`；代码基线为 `b80e6d74d`，随后仅提交本 unit 首文档。开始与结束均检查工作区，保留作者未提交文件。
- reviewed artifacts: `spec.md`、`design.md`、四份 `specs/` delta、`prototype.html`、`design-evidence.md`、`deployment-prompt.md`、M1 表及 `M1-agent-lifecycle/.gitkeep`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

结论针对本轮最终修订稿。每产品 Agent 独立执行进程、先阻断准入再清理、停止确认与意图分离、重新启用不恢复旧工作，都有明确职责和可验证出口。没有要求扩大 DSH 的平台隔离承诺。此结论仅为需求与设计门禁，不表示实现、真实进程停止或生产部署已经完成，也不授权进入实施。

### Coverage 与证据

#### 现有产品组装与架构判断

- 实际读取 `apps/node/src/main.ts:91` 和 `runtime-partitions.ts`：普通 Agent 当前归 `ordinary`，PA 按 binding/epoch 分区；`ordinary` 还承担模型快照、恢复与节点 ready。设计没有把“改分区 key”误当完整交付，明确将管理职责放入零产品 Agent 的 control host，并调整模型广播、配置恢复、健康状态与更新屏障。复用 RuntimePartitions/RuntimeSupervisor 比另造进程路由器合适。
- `packages/dsh-integration/src/client.ts:104` 的启动/恢复与 `:144` 的 shutdown，以及 `index.ts:644` 的 shutdown 是真实执行路径。当前 shutdown 保留 inbox 且串行等待多类 owner；设计单设 disable 原因、先封禁重启和新建、并行发取消及外部截止时间，避免直接复用普通升级停机而保留旧工作。`rpc.ts:26` 的逐行异步 receive 和独立响应派发支持不等待普通业务 handler 的控制请求；JS 执行线程失去响应仍由外层监督处理。
- 对照 `SPEC.md:40` 的依赖方向及 runtime dependency contract：IM 负责真人权限与持久意图，Node/PA 负责产品接收、发送与恢复准入，integration 负责 DSH owner 清理和原生存储。控制面不下沉为模型工具，不让 PA/Channels/IM 持有 DSH 对象；没有 runtime fork、private import、第二套 Agent Loop 或内核 HTTP 服务。新增 control host 有明确的全停用后管理/历史读取用途，不作为产品 Agent 的备用执行通路。
- `apps/im-server/src/control.ts:179` 的 owner/node/space 校验与 `task-graphs.ts:858` 的现有 pause 事务已核实。设计要求抽取共享事务而非伪装真人为 Agent actor，范围和归属正确；`task-graphs.ts:813` 已有真人恢复证据，能够沿用并补充停用代次冻结。
- `packages/personal-assistant/src/external.ts:51` 的直接入站、`:102` 的恢复和 `:198` 的外部发送，以及 `heartbeat.ts`、`task-execution.ts` 的准入点都在设计范围。单靠 IM relay 拦截不能覆盖这些路径，最终方案已同时覆盖本地输入、输出、自动调度与产品副作用，Work/checkpoint/ACK 则继续推进停止事实。

#### DSH 公开能力及用户约束

审查使用本仓锁定安装的 `0.2.1-alpha.1` 公开 package exports、类型声明和 README；没有修改上游或安装产物。

| 能力 | 独立核实与判断 |
|---|---|
| 主执行与后代 | `dsh-agent` 的 `cancel` 默认清 inbox，`whenIdle` 等待 quiescence；公开 AgentHandle 支持 dispose。`dsh-subagent` 的 `drainContinuableDescendants` 明确只覆盖 continuable。设计另行收拢 one-shot、Workflow、knowledge owner，未把单个 descendant 方法当全停保证。 |
| Bash、Job 与 PTY | `dsh-jobs` 公开 `list/kill/wait` 与 owner disposal；`dsh-terminal` 公开 owner list/kill 及 awaited cleanup；`dsh-subprocess` 明确 service disposal 终止所有受管进程并等待退出。取消请求与清理确认分离是必要的。 |
| macOS 边界 | `dsh-subprocess-local/README.md` 明确 fallback 依赖进程组/树/可观察 session，不能回收所有逃逸后代；root exit 不等于完整清理。方案遵守用户“接受 DSH 的设计，不用强求”的决定，保留 stop_unconfirmed，不增加强隔离容器或自制全机扫描守护机制。 |
| 冷 inbox 恢复 | `dsh-agent` 的公开 `Inbox.clear/remove` 是持久取消。实际 `dsh-agent-loop` 的 setupAndPublish 在 maintenance 内 await serial `agent/created`，之后才释放初始化边界；设计的清理屏障有实际接入点，不需要改写原生事件日志。 |
| 冷历史与迁移 | `dsh-session-persistence` 公开 list/stat/open(read)、create/append/flush 和 inheritedEventCount；读 handle 不取得写 ownership。只读 control composition 与一次性迁移可沿公开接口实现。迁移要求保留 lineage、事件序列、附件、Nano domains、Schedule、Work checkpoint/ACK，并对无法归属的数据阻断，未以新进程能启动替代完整性验证。 |

Raft 只读对照了 `agentOrchestrator.ts:12765` 的 manual-stop admission 和 `agentProcessManager.ts:4086` 的 queued-start 取消、stop epoch 使用。设计吸收的是阻断唤醒和过期启动的原则，没有复制其完整 orchestrator，也没有把 Raft 的停止响应当清理证明。

#### 接口、状态与数据流

`desired/revision`、`observed`、`processInstanceId` 分别表达持久意图、应用结果和启动身份；CAS、幂等 request_id、迟到 report 校验、重连全量 snapshot、停止未确认时禁止 enable 已明确。停用先固化资格屏障，Task 暂停投影可重放且不延迟停止指令。旧输入/审批/输出不能在 enable 后改标新代次；独立周期 Schedule 从未来点继续，Task 关联计划仍冻结。离线不新增停机租约，也不把中心写入成功显示为机器已停，符合已收口范围。

#### 前端独立走查与用户反馈闭环

通过独立 Playwright 会话实际打开最新构建基线 `http://127.0.0.1:58300/settings/agents/daily-product`，并点击 Work；未发送消息或触发业务任务。桌面 1440×1000 的紧凑身份头、连续配置区和 390×844 Work 的记录/原生轨迹入口已目视对照。证据：[桌面基线](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/review-baseline-desktop.png)、[窄屏 Work 基线](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/review-baseline-mobile-work.png)。不采用陈旧 dist 图片。

审查进行中，用户明确拒绝作者自加的活动统计。作者解除冻结后删除统计、自造活动列表和 Work 恢复按钮，重新冻结；本 reviewer 在同一 Round 重读相关设计、delta、证据并重新打开原型，没有仅沿用修订前画面。该范围纠正由用户提出，不列作 reviewer 独立发现。

最终实际观察结果：

- 1440×1000：身份、设备、状态与停用动作同处页头；列表目标明确。Work 恢复为现有记录/原生轨迹框架，没有活动数量和自造工作列表。[最终桌面](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/review-final-desktop.png)。
- 连续点击停用→确认停用→重新启用，不出现二次确认。390×844 的停用状态同时保留设备在线信息，320×740 的重新启用提示完整表达旧任务不自动恢复。[390 已停用](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/review-final-disabled-390.png)、[320 重新启用](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/review-final-enabled-320.png)。
- 最终稿重新触发清理失败：320×740 下原因、禁止新工作和重试停止均可读可达；启用不可用。没有用“已停用”替代未确认。[最终失败状态](/Users/czj/Repos/nano-multiagent/output/playwright/feat-657/review-final-failed-320.png)。
- 本轮修订前已实际操作离线→重连、失败→重试、非 owner、配置草稿→切换开关和 iOS 局部方案。作者修订未改变这些状态转换、权限和草稿处理；本轮保留其交互证据，旧截图不作为最终 Work 布局依据。最终原型已重读确认这些逻辑仍在，受影响的桌面/窄屏布局已重新渲染。
- 旧任务明确恢复复用 `src/IM/frontend/src/features/tasks/task-graphs-page.tsx:219` 的既有真人动作。本次不增加 Work 恢复入口。原型没有真实 Task 后端，因此只证明提示和范围决定，具体任务恢复仍由 M1-R3 实施验收。
- iOS 已读取 AgentConfigView 的 Form/Section 和 AgentWorkView 的 List/Section；独立 HTML 局部方案呈现身份→设备→Toggle/状态→按钮，设计决定足以指导既有控件绑定。未运行原生客户端，不声称原生视觉通过；编译/契约测试及按实际平台差异扩大验证的安排合理。

画面事实支持本次增量：用户能在当前身份旁直接停用，读出“尚未确认”与“已停用”的区别，并在启用时看到旧任务保留暂停。未发现需要扩大页面设计的体验问题。最终布局不继承修订前统计。

#### Delta、milestone 与验收前置

- 四份 delta 分别落在 IM Agent 管理、Gateway 生命周期、Gateway Task 和 iOS current target，消费者视角正确。新增 IM `MODIFIED` 锚定现有“离线时统一只读”Requirement，保留原三个 Scenario，只明确独立停用意图/重试例外；不会让下游把紧急开关一起放进配置只读条件。
- 单个 M1 覆盖完整停用闭环，目录仅 `.gitkeep` 符合设计阶段要求。M1-R1～R4 覆盖真实用户结果，W1～W6 覆盖权限/代次、真实 OS 清理、冷恢复、管理能力、迁移与平台差异；must-match 已投影到 R/W 退出标准。没有横切拆出一个可误用的“仅 UI 开关”。
- runbook 给出了隔离 daily 模板的停止、构建、启动、健康检查和角色补充。真实 baseline 已可访问；single-thread、非 owner、受控 Bash/PTY 的构造来源明确，不依赖未落实的生产账号或外部人员。外部 adapter 的迟到/去重用集成测试、共享体验用 Web 的分工合理。
- 一次性迁移仅在实现完成及另获部署授权后执行；plan/apply/verify、静止快照、中断继续、未知归属阻断和禁止旧版忽略 disabled 状态的回退约束完整。未执行迁移或生产操作。

### 历史问题闭环

无前轮 issue。R1 内用户范围纠正及作者修订已按上文复核；没有未解决的 CRITICAL/WARNING，不补造旧 Round 或已不存在的问题编号。

### Issues

无。

### Recommendations

- **R1-R1（非阻断）**：实施首次直接消费 jobs/terminal/subprocess 服务时，将对应锁定版本明确加入 integration 的已声明依赖，并让迁移脚本通过 integration 所属适配层调用公开存储能力。当前公开 exports 已核实存在；这只是落实已有架构红线，不需要新增抽象或扩大本轮设计。

### 验证限制与清理

本轮是设计审查，没有运行停用实现、OS 清理测试、迁移或原生 iOS 验收。截图仅保存在本机忽略目录，不能证明后端行为或性能。独立创建的 `feat657-review`、`feat657-review-revised` 浏览器会话均已关闭；未停止共享 baseline/原型服务。只新增本报告，未修改作者产物或代码、未提交。

### Author Resolutions

- **R1-R1 — accepted**：实施时在 integration 声明实际消费的 DSH 服务依赖，迁移从同一适配边界调用公开能力；属于本文已有依赖红线的落实，不增加抽象。本轮不修改依赖或实施代码，不改变已审架构。
- 作者确认最终修订稿与需求一致；无未解决的实质问题。用户指出的统计及 Work 扩张已删除，并由本轮 reviewer 重新实际走查。受审产物此后无实质修改。

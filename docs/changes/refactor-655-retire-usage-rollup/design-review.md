# refactor-655 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/design655`（独立 change-design-reviewer；未参与本轮设计编写）
- review_mode: `full`
- mode_reason: 首轮 Gate 2，覆盖累计链退役和同一 unit 追加的 Work 持久增量恢复。
- started_at: `2026-10-25T01:18:00+08:00`
- completed_at: `2026-10-25T01:25:00+08:00`
- duration: 约 7 分钟（时间按分钟记录）
- baseline: `main` / `1c9d5583f`；审查当前工作区的 motivation、design、三份 delta、prototype、deployment-prompt 与 M1 骨架。未修改这些文件或产品代码，未提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

删除范围、持久恢复边界和产品不变性已经形成可实施的闭合方案。以下批准是设计门禁结论，未声称真实 DSH 验收、客户端实现或生产部署已完成。

### Coverage 与证据

#### 现状与实际产品接线

- 核对 `apps/node/src/main.ts:120`、`:296`、`:362`、`:407`：实际生产组装同时接入 UsageReports、GlobalAgent 与 WorkSync，启动/重连会触发 usage recovery。设计删除的是这条运行链，WorkSync 与产品 journal 是独立消费者，不能随累计汇总删除。
- `packages/personal-assistant/src/global-agent.ts:293` 的 recoverAll 当前对每个 Global Agent 调 main/reconcile；`:605` 每次从 NodeStore 全历史重新形成 logicalEvents；`:661` 的子执行 cursor/modelVersion 仅内存。`packages/dsh-integration/src/index.ts:401` 的 descendants handler 还先取 live root，并调用 workflow.read。设计明确给出这些真实入口的替代边界，没有仅优化一个未接线 helper。
- `apps/im-server/src/gateway.ts:762`、`src/work.ts:827` 和 `src/schema.sql:100` 分别实现累计入站、查询和建表；当前 specs 中累计接口引用仅落在本轮替换的 auth-tenancy 与 lifecycle 场景。保留旧表、停止新库建表、成套升级的范围一致。
- `src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx:154`、`src/IM/ios/NanoIM/Features/Agents/AgentWorkView.swift:19` 已经围绕保存的记录、最近用量和分页组织界面。Work 与原生轨迹有独立入口，方案保持这一关系。

#### 公共 DSH 边界与跨重启缺口

- 实际安装的 `@deepseek-ai/dsh-session-persistence@0.2.1-alpha.1` 公开 `lib/types/index.d.ts` 声明 stat 返回 header、可选 eventCount/sizeBytes，且不读取完整正文；同文件明确 events append-only、header immutable、revision 仅同一 service instance/session 可比较。JSONL provider 的公开 stat 实现实际返回 sizeBytes；未物化会话可以没有该字段。
- 因此设计第 23、53、94 行使用公开大小/计数及 header 的同一 append-only 对象见证、同实例观察 cut 一致性检查，以及见证缺失时只重查不确定分支，具备当前后端可实施基础。没有把进程 revision 持久化后冒充跨进程指纹，也没有依赖私有路径、文件 inode 或 fork/patch。
- `packages/dsh-integration/src/descendants.ts:64` 现有观察会 flush live session、通过 sessionQuery 取得 own/inherited cut 和 catalog；设计延续该公开 seam，并把 catalog/关系的小型衍生元数据放在 integration 的 storageDomain。PA 仍只通过产品 RPC 消费，未越过 DSH 包边界。
- parent/root 映射本来由 `src/index.ts:202` 的 live parent 链与 usageRoot 提供。设计第 41、55 行明确迁出该依赖，并同时覆盖 session.event、model.changed、父会话卸载和继承 catalog 归属，避免累计模块删除后失去子执行刷新。

#### 处理位置、ACK、逻辑回退与运行义务

- `packages/personal-assistant/src/inbox.ts:341` 的稳定 event_id journal 与 `src/work-sync.ts:112` 的中心 ACK 是既有独立事实。设计第 59–63 行把 Work checkpoint 与产品事实放入同库事务；NodeStore 接收 cursor、Work 处理位置、中心 ACK 三者不混用，覆盖原生落盘→NodeStore→journal→ACK 的窗口。网络回执继续走现有持久义务，不纳入 SQLite 网络事务。
- `global-agent.ts:615`、`presentation.ts:82` 的 logicalEvents 已把多个物理 attempts 映射成逻辑轮次；设计保留开放逻辑 run 的全部 attempts 和 modelVersion 变化重放，完成轮次跳过仅适用于已覆盖事实。`model-fallback.ts:131` 当前在 attach 时才从 domain 装载 runs；设计第 54 行明确要求冷读取持久 ModelRun，避免空内存列表误判。
- `workflow/engine.ts:159` 的 spent 会对冷预算来源执行 sessionQuery.observeSession，`:184` 的 read 会调用 spent。方案明确只为 Work 归属读取持久 run 元数据，预算执行仍用原路径；这项分离是必要的实际读取成本控制。
- `global-agent.ts:293` 同时承担控制、personal 输入、收据和 publication 恢复。设计第 43、52 行以不存在原生新增和待处理输入/控制/审批/交付为延后 ensure 的前提，未用“已 ACK”替代运行义务核对。主子独立 drain 与历史补建不阻塞发送的要求保留现有关键隔离。

#### 用户约束、delta 与 milestone

- motivation 中追加授权与 design 范围一致：同一 unit 交付、Work 工具/统计实时不退化、原始详情按需、完成历史普通重启不正文重建；不增加生产部署授权。design 第 93、109 行诚实保留公开 JSONL 范围读可能全文解码的限制，并分别计量正文获取、原生事件及产品处理量。
- agent-work delta 为 ADDED，保留 current 的工具参数/结果、主子导航、已报告用量和原生轨迹场景。auth-tenancy 的 MODIFIED 完整保留其余身份/成员/资源权限场景，仅退役累计 metrics；lifecycle 的 MODIFIED 保留全部断线恢复场景，只把退役请求替换为 conversation.query。canonical target 正确，没有用 active 方案改写 current。
- 单 M1 的范围跨 integration→PA→IM→客户端状态，但属于同一恢复与产品不变性闭环，不存在并行接口 ownership 冲突；M1 目录仅有 `.gitkeep`，符合设计阶段不预填任务台账的规则。
- 真 DSH、确定计数 provider fixture、主子工具开始/成功/失败、崩溃窗口、普通重启增长历史、变更分支、首次补建及回滚均列入退出条件。Runbook 指向隔离 e2e-up/down，要求和生产身份隔离。部署提示词明确首次 bootstrap 单独记录、保留旧表、成套回滚及一致时间点恢复。

#### 前端体验独立观察

- 本 reviewer 在 IAB 实际打开 `http://127.0.0.1:8655/prototype.html`，以约 1280×720 的桌面画面切换 catching_up、unknown、current、offline 四种状态。状态说明位于切换工具栏下、最近用量上；正在补齐与尚未确认各自说明“已保存内容”，不会阻断阅读工具与统计；current 隐藏提示；offline 只保留一条离线说明并将主执行状态显示为未知。
- 独立查看作者保存的 `/Users/czj/.codex/reports/refactor-655/prototype-narrow.png`：约 319px 下补齐说明自然换行，最近用量和主执行层级仍能辨认。窄屏另外三种状态本轮未重新操作，不把作者记录写成本 reviewer 的实测。
- 对照当前 Web toolbar/callout 与 iOS 首个状态 Section 的源码，新增文字位置已收口，iOS 具体采用现有次要文字层级并规定离线优先；没有以笼统“原生适配”代替位置和信息关系。当前真实产品与原生 iOS 运行画面本轮未启动，完整产品视觉及真实同步反馈留给 M1，不能以本局部原型作为实现验收。

#### 架构判断

原生关系与冷见证由 integration 持有，产品处理 checkpoint 由 PA/InboxStore 持有，网络追平由 WorkSync/IM 持有，是现有职责的直接延伸。复用 journal、ACK、domain 元数据和原生查询，优于另建完整事件仓或保留失去消费者的累计扫描。新增状态只是记录完整性的展示，没有扩成新的调度器或第二套执行循环。当前方案复杂度来自真实崩溃窗口与既有逻辑回退，没有发现会带来具体维护代价的多余抽象。

### 历史问题闭环

首轮审查，无历史 issue 或 Author Resolution。

### Issues

无。

### Recommendations

- **R1-R1（可选实施提醒）**：在实现 design 第 39、61 行的“缺口及开放轮次”投影时，沿用现有跨轮次模型/上下文元数据语义。`presentation.ts:96` 的 modelAt 会向前找 request/header，`:26` 的 context_window 也来自先前 request/context；`tests/store.test.ts:104` 已保护模型 carry-forward。checkpoint 字段是“至少”列表，实施可用很小的有效元数据状态衔接切片，不必恢复全部历史。将“上一轮已提交、下一轮没有重复模型 header”的既有断言带入增量/重启用例，有助于验证方案承诺的不变性；这是既定要求的实施落点提醒，不要求增加完整上下文副本或另设门禁。

### Author Resolutions

- R1-R1: **accepted**。现有 modelAt/tokenUsage 的跨轮次元数据是既有统计语义；实施将用小型有效模型/上下文状态衔接切片，并在处理 checkpoint 重启用例中保护，不增完整原生上下文副本。属于 design 已列持久小型元数据与统计不变性的实施细节，不改变受审接口、范围或 milestone。
- 复核本轮无实质设计问题，接受 Approved；R1 后仅追加本 Author Resolutions，受审产物无实质变化，Gate 2 retained。

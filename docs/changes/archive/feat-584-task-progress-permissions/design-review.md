# feat-584 Design Review

## Round 1

### Metadata

- reviewer: `/root/feat584_design_review`（独立 change-design-reviewer）
- target: `feat-584-task-progress-permissions` 冻结的 spec、design、migration-guidance、五份 delta、prototype、visual-review/截图及 M1 骨架。
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖需求、当前生产组装、关键决定、接口、delta、原型与 milestone。
- started_at: `2026-10-12T20:39:42+08:00`（首个留存浏览器证据时间；前置文档读取未单独计时）
- completed_at: `2026-10-12T20:49:32+08:00`
- duration: 9 分 50 秒（可核对证据时段；不含前置读取）
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，`d9ff73748`。开工确认了 dirty/untracked 状态；没有修改产品代码、其他设计产物或用户既有内容，没有提交。

### Verdict

**Issues Found — 0 CRITICAL / 4 WARNING。**

整体职责与数据流可以在当前 TypeScript IM + PA + DSH 架构中承接；未发现需要新增执行循环、任务调度器或上游私有接口的理由。当前不能放行：原型缺少已分配给自己的任务领取入口和 P2 冲突恢复状态，公开群读取权限还遗漏两个 current 契约的 delta，另有作者已识别的两处断链。

本轮结束前收到审查外的新用户变更：“图里面暂缓不单独一个竖条了吧，归到代办里”。本轮仍审查冻结的六列版本，没有把该变更当成已实现，也不以旧六列行为额外报错。下一轮须核对保留 `paused` 状态、并入待办展示分组、卡片仍标暂缓的受影响产物。

### Coverage 与证据

#### 当前生产路径与架构判断

- **IM 是唯一任务事实源。** 实际入口 `apps/im-server/src/server.ts` 的 `createServer` 装配 Messaging/Gateway/control；`control.ts:904` 注册任务 HTTP，`task-graphs.ts:721` 当前只提供 list/get/activity；`gateway.ts:345` 将 Agent `task_graph.command` 交给同一 `TaskGraphService.execute`。设计新增 HTTP 写入口、统一 actor/ACL/revision 处理的位置正确，没有把规则散落到客户端。
- **身份和会话边界确有现成承接点。** `task-graphs.ts:386-390` 核查 active 真人或注册 Agent、node、owner 公司资格和工具能力；`work.ts:463-585` 查询注册 Agent 的成员会话；`media.ts:49,124,184` 复用 Messaging access。将这些入口收敛到 read/write 分开的会话授权，而非只修改 task list，是必要改动。公开访客读取不自动写成员，不借 owner 管理权限读取私聊，外部影子会话不随内置群默认公开，均与已确认边界一致。
- **通知方案复用了实际持久机制，但正确承认需要改造。** `messaging.ts:428-550` 的现状确实是插入消息、生成 relay 并立即发送，全部离线时返回 503；`gateway.ts:970-984` 重连重放 queued/sent/accepted。D3 要拆出事务内持久化与提交后发送、任务/回执/消息/relay 同事务，并在重投前复核资格；这解决具体双写/离线问题，无需增加第二通知表或通用事件总线。
- **PA 与 DSH 承担输入/执行，IM 不执行任务。** `apps/node/src/main.ts:188-192` 实际装配 SingleThread/GlobalAgent；`global-agent.ts:157-185` 固定绑定 Agent 并经 relay 调任务服务；`agent-config.ts:45-48` 装载 global-mode 和 feature，`global-mode.ts:24-43` 为两种主模式提供 conversations 工具。扩充其 create/join、保留 root 限制，符合现有能力分工。没有以内部 child 自报身份加入公司群的旁路。
- **接收策略与停止语义已核对。** `attention.ts` 使用真实 mentioned_agent_ids/groupReplyPolicy；`single-thread.ts:47-127` 持久接收、followup 及非真人 system 来源；`global-agent.ts:63-97` Inbox 接收/唤醒；两处 `/stop` 继续 `session.cancel`。D5 与 Q33 一致，不恢复历史 Q20–Q22 中已被覆盖的持久停止措辞。
- **持久结构与迁移选择适度。** 当前 task graph 的 500 节点/1000 依赖/100 operations、revision、receipt 与整图校验已有；`db.ts` 仅执行 CREATE IF NOT EXISTS，确需显式迁移。图级 conversation、节点 creator/assignee、读取派生计数和 ACL 后 json_each 符合当前规模；没有证据要求新增节点投影。迁移 guidance 正确区分原始创建事实、一次性归属整理与未知项，不把最近修改人伪装为创建者；备份恢复、旧群 private、保 ID 和无通知洪泛已进入 W4。尚未调查生产数据，不作迁移完成判断。

#### 需求、决定与 milestone

检查了 spec 前置验收标准及 Q1–Q33 最终决定。D1–D6 覆盖固定会话归属、独立身份、共同维护与删除资格、分配/领取分离、六状态、通知对象、父子不自动联动、跨层负责人汇总、软解散历史、一次性迁移和现有 `/stop`。创建者 immutable、领取竞争、改派不改状态、来源群与讨论群分离、删除一次授权覆盖子树、回执重放重新授权均已形成可实施接口。

单一 serial M1 有合理性：权限与数据写入、通知消费者和 Web/iOS 必须一起形成协作旅程；没有人为拆分相互冲突的并行里程碑。骨架仅 `.gitkeep`。P1–P5 均投影到 R1–R5 和 W1–W4；真栈验收包含真人/Agent、always/mention_only、忙闲/离线/重投、ACL、回滚和双端，未将原型当后端通过证据。runbook 指向实际 TypeScript e2e-up，隔离端口/配置/数据/workspace/身份并明确清理；无需生产变更。原生使用可用模拟器、显式 DEVELOPER_DIR 的约束已写明，设计期没有冒称 build、模型调用或物理设备通过。

#### Delta 核对

五份 delta 的 canonical target 正确，修改的主要 Requirement 可与 current 对应；保留了未受影响的 DAG/探索结构、revision、删除授权、认证身份和群治理规则。iOS 通过现有业务/权限一致契约承接，不需要复制全部规则。但公开群读取的影响还落在 `gateway/routing-delivery` 的既有图片 Scenario 和 `im/agent-work` 的来源读取 Scenario，当前 delta 没有收敛，见 R1-W3。auth-tenancy 有两处相对链接未随文件位置调整，见 R1-W4。

#### 独立原型走查

使用专属 Chromium 会话 `feat584-review`，临时只读静态服务 `127.0.0.1:18784`，实际渲染并操作；独立查看了作者的 `evidence/baseline-desktop.png` 与本轮截图。没有启动生产、测试后端或原生 App。浏览器和本轮静态服务均已关闭。

基线来自当前 React 组件加合成 API 数据，只能证明现有布局；其 disconnected 提示不作为产品缺陷。原型保留 teal 视觉、导航、左任务列表、中心内容和桌面右详情；1440/1024 的横向滚动限制在完成情况区域，390 使用纵向状态组和详情 sheet。未见关键按钮被裁切或整页异常横向溢出。身份演示与普通聊天/示例连线的边界已标注。

本轮截图是临时审查证据，位于 `output/playwright/feat-584-review/`，不属于产品产物，不应提交运行缓存：

| 检查 | 实际操作与结论 | 证据 |
|---|---|---|
| P1 层级/宽度 | 1440 根层、1024 工具条换行；根→第二层、根→探索、结构/完成切换、面包屑返回；每层仅直属节点 | `desktop.png`、`medium.png`、`phone-progress.png` |
| P2 详情/编辑 | 390 详情 sheet、编辑结果→待确认可保存；待办改派给当前用户后无领取入口（W1）；冲突恢复无状态（W2） | `phone-detail.png`、`phone-edit.png`、`todo-self-no-claim.png` |
| P2 删除 | 父任务删除弹窗明确本节点加两个后代，共 3 个，取消可返回 | `delete-scope.png` |
| P3 负责人汇总 | Agent B 筛选出现父节点及深层匹配节点，带群/父路径；点击“验证修复后的登录”进入 n2 所在层并选中 n9 | `filter.txt`、`phone-detail.png` |
| P4 公开访客 | 访客的新增禁用；加入后能打开未分配 n3、领取成为小李并置进行中；普通成员没有他人节点删除按钮，范围不可改 | `visitor.txt`、`joined.txt`、`ordinary-settings.png` |
| P4 新建/解散 | 新群表单默认公开；管理员改私密→解散确认→任务历史禁写；原型明确新群后完整导航为背景 | `new-group.png`、`dissolved.png` |
| P5 系统消息 | 改派保存产生一条原/新负责人消息；任务链接返回正确节点；n9 提交待确认后消息包含创建者 A 与父负责人小王 | `notice.png`、`settings.txt` |

原生当前截图尚未采集。本轮接受作者将 HTML 手机画面限为共享信息/操作语义、SwiftUI 控件为 may-adapt 的呈现范围；**不对原生视觉作通过结论**，也不把原型 @ 外观当成真实 mentioned_agent_ids、ACL、离线消费或迁移证据。必要的浏览器交互状态仍须在当前原型可审，不能以“没有后端”豁免 P2（W2）。

### 历史问题闭环

R1 首轮，无历史 issue 或 Author Resolution。本轮冻结产物未被 reviewer 修改。

### Issues

#### R1-W1 — 已分配给当前用户的待办没有领取入口

- **级别：WARNING；状态：open。**
- 位置：`prototype.html:24` 的 `detail()`；对照 `design.md:143` 与 P2（223 行）、spec“分配与领取分离”。
- 实证：以小王身份选择待办 n3「整理发布说明」→调整负责人→小王→保存。详情仍为待办、负责人小王，但只剩编辑/调整负责人/删除，不能“领取并开始”。独立截图 `output/playwright/feat-584-review/todo-self-no-claim.png` 已实际查看。源码仅在 `x.assignee==='未分配'` 时渲染领取按钮，解释了画面。
- 后果：P2 被实施为 must-match 时，别人提前分配给本人的工作反而缺少接手动作；用户只能先取消分配或手工改状态，背离“分配不代表开工、自己可领取已有分配”的约定。
- 修正边界：对未分配或当前主体负责且可领取的节点提供相应入口；非本人已有负责人仍不提供抢占。用待办自有任务走通领取后的状态，保留现有 done→doing 的返工原因规则。

#### R1-W2 — P2 的冲突恢复没有可审查的界面状态

- **级别：WARNING；状态：open。**
- 位置：`design.md:147,223,232`；`prototype.html:31-32`；`evidence/visual-review.md:35-38`。
- 实证：P2 明确将冲突恢复列为 must-match；实际编辑只有标题必填与 done→doing 返工原因校验，所有有效保存直接更新并关闭表单；没有冲突提示、保留草稿、重新读取及明确重试的可操作路径。作者也明确记录未提供冲突模拟。本轮实际打开并提交过手机编辑表单。
- 后果：下游虽知道不能自动覆盖，却无法从 must-match 判断“重读后旧草稿如何保留、如何回到编辑、何时算明确重试”，新的多人编辑关键恢复体验被推迟到实施时决定。
- 修正边界：在独立演示区触发一次合成 revision conflict，展示保存失败仍保留文本→读取最新记录→用户明确重试的界面。无需连接真实后端，也不要求新增自动合并或历史版本。后端原子性仍由 M1 验收。

#### R1-W3 — 公开群读取未覆盖现有图片/Work 来源契约

- **级别：WARNING；状态：open。**
- 位置：本 unit `specs/gateway/routing-delivery.md` 目前只有通知 ADDED；缺少 `specs/im/agent-work.md` 对应 delta；对照 current `docs/specs/gateway/routing-delivery.md:48`、`docs/specs/im/agent-work.md:31`。
- 实证：前者仍规定全局 Agent 发到已有聊天的受保护图片“持同一 URL 的非成员不能读取”；后者规定 Work 来源聊天/附件“仍按成员关系判定，非成员无法读取”。本 unit 新 im/conversations-messages 与 auth-tenancy 已允许 active 公司非成员读取公开群消息和附件，设计 153/164 行也覆盖相同对象。
- 后果：五份 delta 归并后，同一个公开群非成员读取相同来源附件，会同时被 canonical 要求允许与拒绝；实现或验收若沿用 Work/图片条目，可能错误保留成员限定。
- 修正边界：补这两个消费者 Scenario 的最窄 MODIFIED delta，改为当前会话读取资格；私密群/私聊继续拒绝非成员，Work 可见不额外授予来源权利，未改 Scenario 保留。无需放开配置或成员 WS 推送。

#### R1-W4 — auth-tenancy delta 的两个契约引用断链（作者已知待修）

- **级别：WARNING；状态：open。** 文档完整性问题，不涉及新增产品决定。
- 位置：`specs/im/auth-tenancy.md:7` 的 `agent-work.md` 与 `gateway-relay.md`。
- 实证：两链接相对当前 delta 目录解析，但该目录没有对应文件；作者只读 docs-check 已报告本 unit 这两个新增问题，本轮独立确认目标不存在。没有重复扫描或将作者报告的四个无关基线错误归责给本 unit。
- 后果：读者无法沿引用到达 current 的 Work 和机器入口边界，且本 unit 引入 docs-check 失败。
- 修正边界：将链接改到实际 canonical 文件（作者已提出 `../../../../../specs/im/...`），归并时使用 canonical 目录正确相对路径；核对这两个新增错误消失。无需修改无关文档。

### Recommendations

无额外可选架构建议。修复上列有证据的问题即可，不要求增加调度、通用事件总线、节点投影或新权限角色。


### Author Resolutions（Round 1 后）

- **R1-W1 — accepted。** `prototype.html` 的 detail/claim 已允许未分配或分配给当前用户的非进行中任务领取；他人负责人不允许抢占。done→doing 进入要求原因的编辑表单。实际浏览器完成 n3 改派小王→仍待办→领取→doing，证据 `evidence/prototype-self-claim.png`。
- **R1-W2 — accepted。** 独立演示区增加一次合成版本冲突；表单保留草稿，先读取并显示最新描述，之后才提供明确重试。已走通并查看 `evidence/prototype-conflict-retry.png`；不以原型模拟替代后端测试。
- **R1-W3 — accepted。** 增补 `specs/im/agent-work.md` 的完整 MODIFIED Requirement，以及 routing-delivery 图片条目的完整 MODIFIED，保留原有其他 Scenario，来源只按会话读取资格改变，Work 本身不扩权。
- **R1-W4 — accepted。** auth-tenancy 的 Work 引用指向新补的同目录 delta，Gateway relay 引用改为实际 canonical 相对路径；归并时恢复 canonical 相对链接。

审查后用户另有两项明确修订，原话保存在 spec Q34/Q35：暂缓并入待办展示、UI 控件过大和布局需要收紧。已同步 spec/design/task delta/prototype 与当前视觉截图；保留原架构和 M1。新原型默认收起详情、轻量五列与紧凑操作，须复审视觉和相关交互，不能仅沿用 R1 结论。

## Round 2

### Metadata

- reviewer: `/root/feat584_design_review`（与 R1 同一独立 reviewer）
- target: R1 Author Resolutions 后重新冻结的 spec（含 Q34/Q35）、design、migration-guidance、六份 delta、prototype、更新视觉证据与 M1 骨架。
- review_mode: `full`
- mode_reason: 除历史问题修复，还增加 Q34/Q35 用户要求，并实质改变完成情况分组、详情默认状态、筛选与操作入口；需重新覆盖需求与原型，不仅做 closure。
- started_at: `2026-10-12T21:38:08+08:00`
- completed_at: `2026-10-12T21:43:53+08:00`
- duration: 5 分 45 秒。
- checkout: 同一 `main`；本轮确认 `apps/`、`packages/`、`src/` 无 tracked diff。reviewer 仅追加本报告，没有修改冻结产物、产品代码或提交。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

R1 四项均关闭。Q34 已正确实现为六状态、五个展示分组；Q35 的控件和布局修订没有改变包架构或权限决定，新版桌面/手机画面可读、冲突恢复能操作。但按需详情丢失了默认浏览中的根任务操作入口，新增的完成后领取分支没有保存领取者，见 R2-W1/R2-W2。

### Coverage 与证据

#### 需求、设计、契约与架构

- 重新核对 spec 前置需求及 Q33/Q34/Q35、design D1–D6、接口/状态读取/原型契约/Runbook/M1。Q34 只改变呈现：`paused` 仍是独立状态，待办列包含 todo/paused，顶部直属状态数量仍分别计数；没有偷偷转换状态或改变父子联动/通知规则。spec、design 第 5 节和 IM task delta 的描述一致。
- Q35 对应紧凑负责人菜单、轻量列容器、详情按需打开、删除移到更多操作。保留现有全局导航、Tasks 与聊天入口、相同节点和层级数据，没有添加未授权的产品导航或新角色。两处可达性/动作结果问题见 Issues。
- `retained_from: Round 1`：IM 唯一事实源、会话 ACL、真实 actor、事务消息与 relay、PA/DSH 输入处理、`/stop`、迁移及单 M1 的架构证据。理由：本轮生产代码无修改，设计中的对应职责、数据结构、事务与控制语义不变；新 UI 不要求新后端机制。保留整图 JSON、派生计数、公开 DSH 边界和现有执行服务仍适当，不要求重复启动后端验证这些未变结论。
- 六份 delta 已覆盖当前本 unit 涉及的任务、聊天/附件、认证、Work 来源、Agent 工具与路由通知。新增 Work MODIFIED 保留原 Requirement 的其余四个 Scenario；routing 图片 MODIFIED 保留本地/跨机器/路由/离线/失败/普通文本等 Scenario，只将图片读取资格与公开群规则对齐。canonical 尚未提前修改。
- milestone 仍为 serial M1，P1 更新为六状态五组，W3 仍要求三宽度与真实 Web/iOS 对照，R2 要求不丢草稿、各入口同一事实。没有新增未落实的账号/外部租户/硬件前置。Runbook 与原生/后端证据边界沿用 R1；本轮不宣称生产、原生视觉或实现验收通过。

#### 原型独立渲染与交互

使用自己的浏览器会话 `feat584-review-r2` 打开作者提供的只读 `127.0.0.1:49268/prototype.html`，独立渲染 1440×960、1024×900、390×844 并查看本轮图片。结束关闭自己的浏览器，**未关闭作者静态服务**。临时证据位于 `output/playwright/feat-584-review/`，不提交运行缓存。

| 范围 | 本轮证据与结果 |
|---|---|
| 五组与新版布局 | `r2-desktop.png`、`r2-medium.png`、`r2-phone.png`：默认详情收起；轻量五列/手机五组；暂缓 n6 位于待办且标暂缓，直属统计仍区分状态。控件没有恢复旧版的大块列容器。 |
| 自有待办领取 | `r2-self-claim.png`：n3 从未分配改派小王，仍为待办且有领取；点击后 doing。其他负责人节点无抢占入口。 |
| 冲突恢复 | `r2-conflict.txt`、`r2-conflict-retry-phone.png`：模拟冲突保存后草稿保留、保存禁用；读取最新后同时看到新描述与原草稿，再明确“确认重试”成功关闭表单。390 宽度的恢复文案和按钮完整可操作。 |
| 负责人筛选/深链 | `r2-filter.txt`：新版菜单可选 Agent B，显示深层任务及父路径；点击 n9 的结果进入 n2 层级并选中 n9。返回根层后观察到 W1。 |
| 完成后领取 | `r2-rework.txt`：无返工原因被拦；填写原因后保存，实际负责人仍未分配，见 `r2-rework-unassigned.png` 和 W2。 |
| 当前层详情 | `r2-root-no-detail.png`：默认列表与面包屑都只进入层级，根任务无详情/编辑入口；子任务卡片可打开并关闭详情，见 W1。 |

`retained_from: Round 1`：群类型创建/访客加入/管理员切换/解散语义、系统通知回链与删除范围的判断；本轮对应函数和产品契约不变，作者又提供更新后的窄屏表单/设置/消息/历史截图。R2 独立重点覆盖有实质变化的菜单、详情、领取、冲突和三宽度，未将作者截图计为本轮真实后端或原生操作证据。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮独立核验 | 状态 |
|---|---|---|---|
| R1-W1 | accepted：未分配或自有任务可领取，done 转编辑要求返工原因 | 自有待办显示按钮并变 doing；他人负责无抢占入口；done 无原因确实拒绝。原来的“已分配给自己无入口”已修复。修订 done 分支另有领取者丢失问题，独立记为 R2-W2，不改写 R1 结论 | closed |
| R1-W2 | accepted：独立演示区模拟冲突、保留草稿、读取最新、明确重试 | 完整走通并查看 390 截图；草稿保持，读取前不可提交，读取后按钮为“确认重试” | closed |
| R1-W3 | accepted：补 Work 与 routing 图片完整 MODIFIED | 与 current 对照确认保留其他 Scenario，公开群可读、私密/私聊按成员，Work 不额外扩权 | closed |
| R1-W4 | accepted：Work 指向新增同目录 delta，relay 指 canonical | 独立解析两个链接，分别落到实际存在的 unit `specs/im/agent-work.md` 和 `docs/specs/im/gateway-relay.md`。作者报告 docs-check baseline 4/with_unit 4，即零新增；本轮未将其表述为重新运行全仓通过 | closed |

### Issues

#### R2-W1 — 默认浏览缺少当前层根任务的详情入口

- **级别：WARNING；状态：open。**
- 位置：`prototype.html:30-33` 的 `enter/sidebar/detail/render`，design P1/P2 和 Q35 按需详情约定。
- 实证：默认全部负责人列表点击「公开发布准备」及同名面包屑，都调用 `enter()` 并设 `detailOpen=false`。页面 h1 只是标题；当前根节点不属于自己 children，看板只展示后代，所以没有卡片能打开 n1。独立实际点击与截图 `r2-root-no-detail.png` 一致。相反，先筛选 Agent A 再从匹配结果打开根任务可以进入详情，说明默认旅程缺入口而非权限禁用。
- 后果：用户无法在通常的根层浏览中编辑总任务结果/状态、改派或删除总任务，只能猜测筛选绕路；进入一个层级后也不能就地查看当前层任务的身份和结果。这不是 Q35 要求收紧布局所授权的功能删除。
- 修正边界：保留默认收起，只给当前层任务一个明确且紧凑的详情入口（例如可点标题或详情按钮），并在 Web/手机与创建新根后的同一路径可达；不要求恢复常驻侧栏。

#### R2-W2 — 已完成的未分配任务领取后仍没有负责人

- **级别：WARNING；状态：open。**
- 位置：`prototype.html:39,41` 的 `claim()` / `saveEdit()`，对照 design `claim_task`（143 行）。
- 实证：以小王打开已完成 n5「核对发布清单」→负责人改为未分配→“领取并开始”→表单状态预填进行中→空原因保存被拒→填写“需要重新检查发布清单”→保存。结果显示进行中、负责人未分配，见已实际查看的 `r2-rework-unassigned.png`；正常领取应把负责人设为小王。代码 done 分支仅调用 edit 并改 status，保存没有携带领取意图或设置 assignee。
- 后果：用户明确完成了领取流程，任务却仍无人负责；本人负责人汇总会漏掉这项返工，且未产生实际首次分配对应通知。该状态属于设计明确支持的 done→doing 领取路径，不是新的扩展需求。
- 修正边界：返工原因校验通过后，作为同一次领取设置当前主体和 doing；取消/失败时不提前改负责人。若已分配给当前主体，保持该主体；他人负责继续禁止领取。无需新确认层或自动合并。

### Recommendations

无新增可选建议。下一轮只需复核两条修订路径及受影响的入口/宽度，不扩大架构或追逐与本次目标无关的视觉偏好。


### Author Resolutions（Round 2 后）

- **R2-W1 — accepted。** 当前任务标题旁补充轻量“详情”，调用 choose(scope)，根与任意层均可打开；默认仍收起，不恢复常驻详情。已实际从默认根进入编辑，截图 `evidence/prototype-root-detail.png`，主桌面/手机截图已刷新。
- **R2-W2 — accepted。** done 领取进入编辑时保留领取目标，验证返工原因并通过冲突检查后，保存同时将当前用户设为负责人、置 doing；未填原因不落状态或负责人。实际走通 n5 取消负责人→领取→空原因拒绝→填写原因→doing/小王，截图 `evidence/prototype-done-claim.png`。

本次只修两项可复现的交互问题及对应说明/截图，其他架构、需求、delta 与 M1 未变。

## Round 3

### Metadata

- reviewer: `/root/feat584_design_review`（同一独立 reviewer）
- target: R2 Author Resolutions 后冻结的局部原型修订及对应 design/visual-review 说明。
- review_mode: `closure`
- mode_reason: 仅修 R2-W1 当前层详情入口、R2-W2 返工领取主体保存；需求、核心接口、架构、delta 与 milestone 不变，既有证据上下文完整。
- started_at: `2026-10-12T21:45:42+08:00`
- completed_at: `2026-10-12T21:46:30+08:00`
- duration: 48 秒（独立操作与取证时段）。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R2 两项均经独立实际交互关闭；无新增实质问题。此结论是 Gate 2 设计与所选原型范围通过，不表示产品实现、后端权限/投递、迁移或原生视觉已验收。

### Coverage 与保留证据

`retained_from: Round 2`：Q34/Q35、六状态五组、桌面/中间/手机布局、R1 四项闭环，以及需求到 P1–P5/M1 的覆盖。`retained_from: Round 1`：实际 TS IM/PA/DSH 组装、职责和依赖方向、会话授权、事务通知/relay、停止语义、迁移与验收前置。理由：本轮修订只添加 `choose(scope)` 入口和保存前的领取意图，不改变这些已验证决定或证据条件。

本轮使用自己的 Chromium 会话 `feat584-review-r3`，打开作者静态服务 `127.0.0.1:49268`，实际操作 1440×960 与 390×844。独立查看当前层详情、领取结果和手机详情截图；未仅凭作者 Resolution 放行。临时证据位于 `output/playwright/feat-584-review/`。结束关闭自己的浏览器，保留作者服务，未启动生产或修改其他文件。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮独立证据 | 状态 |
|---|---|---|---|
| R2-W1 | accepted：当前标题旁轻量“详情”调用 choose(scope)，默认仍收起 | 从默认根页直接点详情，显示 n1，进入编辑并保存结果“R3 根任务编辑可达”；390 宽度重新打开同一根详情可见保存结果，再进入 n2 层级点详情正确显示 n2。查看 `r3-root-detail.png`、`r3-phone-root.png`、`r3-phone-scope.png`，按钮/编辑/关闭可达，无需筛选绕路 | closed |
| R2-W2 | accepted：claimTarget 保留领取意图，原因与冲突检查后才提交负责人及 doing | n5 已完成→取消分配→领取→空原因保存被拒；取消后独立快照仍为已完成/未分配，创建者 Agent A、结果保留。再次领取并填写返工原因保存，独立截图显示进行中/小王，创建者与结果不变。证据 `r3-rework-invalid.txt`、`r3-cancel-preserved.txt`、`r3-done-claim.png`；源代码确认领取赋值在原因校验与冲突检查之后 | closed |

R1-W1–W4 保持 R2 的 closed，未重新打开；本轮无需重复全仓 docs-check 或后端测试。

### Issues

无未关闭 CRITICAL/WARNING。

### Recommendations

无。可按现有 M1 与真实客户端/PA/DSH 验收前置进入实施，不增加新门禁或可选视觉返工。


### Author Resolutions（Round 3 后）

R3 判真：接受 Approved，无实质异议；R1/R2 全部问题已有独立闭环，不新增可选修订。受审原型、spec、delta 与 milestone 保持不变。审查后仅将 design/visual-review 的状态文字更新为 R3 已通过，属于归档元数据，`retained_from: Round 3`；未改行为、视觉或接口，不另开一轮。

最终格式检查仅清除五份 delta 的多余文件尾空行，内容不变，保留 R3 结论。

## Round 4

### Metadata

- reviewer: `/root/feat584_design_review`（与 R1–R3 同一独立 reviewer）
- target: `main` / `06843ba4a` 的 R3 Approved 基线之后，冻结的 Q36–Q38、design 原型/P5、prototype 及视觉证据。
- review_mode: `delta`
- mode_reason: 新增的是有界的任务页头、示例内容密度与系统消息视觉/交互要求；核心需求语义、架构、权限、共享接口、六份 delta 与 M1 范围未改变。不能仅 closure，但已有基线与历史问题上下文足以保留未变部分，无需 full。
- started_at: `2026-10-12T22:11:37+08:00`
- completed_at: `2026-10-12T22:16:20+08:00`
- duration: 4 分 43 秒（独立浏览器取证至完成核验时段）。
- checkout: `main` / `06843ba4a`；确认 `apps/`、`packages/`、`src/`、unit delta 和 migration-guidance 无 tracked diff。只追加本报告，保留其他 dirty/untracked 内容，不提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

Q36–Q38 在所选原型范围内已落实。独立实际渲染和交互验证没有发现会使实施走偏的未解决问题。本结论是 Gate 2 设计通过，不代表真实后端有效 mention、Agent 接收、原生 App 或生产部署验收。

### Coverage 与证据

#### 变化范围与现状依据

- Q36：标题和祖先路径合为紧凑上下文栏，当前标题不再重复占两块区域；桌面同排呈现群归属/可见性，390 宽度分两行。详情入口保留，未因压缩头部重新引入 R2-W1。
- Q37：代码样例为 3 棵树、32 节点，默认根层实际显示 15 个直属任务；长短标题、无描述、多段描述和长结果均有可达实例。负责人筛选/编辑资格继续引用既定会话授权，没有因为增加示例人物或树而改变权限。
- Q38：独立查看作者的 `baseline-chat-desktop.png`、`baseline-chat-phone.png`，并核对实际组装 `chat-workspace-page.tsx` 使用 `ConversationSidebar` / `MessagePane`，以及 `global.css:1627` 起的 262px 侧栏规则。原型继承会话栏、紧凑群头、本人右侧浅绿气泡、Agent 左侧灰色气泡、底部输入区；手机隐藏全局导航并保留返回/群头/任务入口。系统事件居中且无真人气泡/头像，修改者、任务链接、变化和 @ 可区分。
- 截图来源边界准确：React/Vite 基线由合成 API fixture 渲染，截图断线提示未被当成真实后端成功；本 reviewer 没有把直接访问缺 fixture 的 Vite 当作可用 demo。独立重现的主任务页和 Chat 与作者当前 `prototype-desktop.png`、`prototype-notice.png` 一致；按相同操作生成的改派/结果也与 `prototype-chat-reassigned.png` 的状态语义一致，没有用预置事件冒充本轮操作结果。
- P5 已列出事件消息、修改者、任务链接、有效 @、状态、摘要/展开与手机回链，仍投影到 R5 和 W2/W3。M1 的真实 Web/iOS、三宽度原型对照、PA/DSH 通知验收要求保留。原型的本地文字回显、搜索/过滤背景已注明边界，不据此验收现有完整聊天功能。

#### 独立原型操作

使用自己的 Chromium 会话 `feat584-review-r4`，复用作者静态服务 `127.0.0.1:49268/prototype.html`。独立查看以下截图；DOM 数量/宽度检查仅作补充。临时证据位于 `output/playwright/feat-584-review/`。

| 范围 | 操作、证据与结论 |
|---|---|
| 三宽度任务页 | `r4-desktop.png`、`r4-medium.png`、`r4-task-phone.png`：1440×960、1024×900、390×844 的紧凑上下文、长短卡片和状态分组可读。1024 的溢出限制在看板容器，documentWidth=1024；390 的任务页没有整页横向溢出。 |
| 长描述/详情 | 打开 n12，`r4-long-description.png` 中长标题完整换行，多段描述和分步内容保留，手机 sheet 可读；n4 的空描述仍明确显示。 |
| Chat 对照与预置事件 | `r4-chat-desktop.png`、`r4-chat-phone.png`：现有布局与本次轻量系统事件清楚区分，分配、改派、暂缓、待确认、完成均存在；长标题在手机自然换行。 |
| 实际改派 | 点击 Chat n2 回链进入详情，从 Agent B 改派 Agent A，再进入 Chat；`r4-reassign.png` 显示新增一条“小王…从 @Agent B 改派给 @Agent A”事件，修改者和旧/新负责人完整。 |
| 结果生成与展开 | 手机上编辑 n15 待确认→已完成，再进入 Chat；`r4-generated-phone.png` 显示新事件自动可见，含小王、任务链接、状态、@Agent A 与首段摘要。原有 6 条预置事件加上述改派、此次完成共 8 条，此次结果只新增 1 条。`r4-new-result-expanded.png` 显示同一条事件内展开多段完整结果，群头和输入区仍可用。 |
| 消息回链 | 展开 n4 预置结果并点击任务链接，`r4-expanded-phone.png` / `r4-backlink-phone.png` 证明 390 宽度进入 n4 原任务详情；点击新生成 n15 事件亦进入 n15 详情，未错误跳到另一层或根节点。 |
| 删除后的消息 | 经原型详情“删除任务及子树”确认删除 n15，再点仍保留的事件链接；`r4-deleted-link.png` 显示“任务已删除或无法访问”，没有空白崩溃或伪造新任务。仅操作本 reviewer 的内存示例。 |

浏览器唯一 console error 为静态服务缺 `favicon.ico` 的 404，与设计路径无关。结束已关闭自己的浏览器，**保留作者静态服务**，未启动或停止生产进程。

#### 保留的架构与契约判断

`retained_from: Round 3`：R2-W1/W2 的独立闭环；`retained_from: Round 2`：Q34/Q35、六状态五分组、六份 delta 的完整覆盖；`retained_from: Round 1`：IM 唯一事实源、会话 ACL、真实 actor、事务消息/relay、PA/DSH、停止语义、迁移和验收前置。

保留理由是本轮对应文档与产品代码没有变化，新增内容只是既定字段的 UI 呈现和演示数据。消息视觉应由现有客户端聊天渲染承担，摘要/展开是已有 result 的展示方式；IM 继续产出事件事实和有效 mention，PA 继续复用已有输入处理。无需新增存储、通知服务或第二套任务机制，也未发现借原型样式引入新的跨包依赖。

### 历史问题闭环

R1-W1–W4、R2-W1/W2 均保持 R2/R3 的 **closed**；Author Resolutions 已保留。本轮没有新的历史问题修复请求。Q36 仍有当前层详情入口，通知回链也能打开正确详情；领取赋值、冲突、delta 链接等无相关差异，不机械重复后端或历史整套验证。

### Issues

无未关闭 CRITICAL/WARNING。

### Recommendations

无。按既有 M1 进入实施与真实客户端验收，不追加新的视觉偏好或门禁。


### Author Resolutions（Round 4 后）

接受 R4 Approved，无实质异议。Q36–Q38 的布局、内容与交互已由独立浏览器核对，未修改受审原型或行为。审查后仅更新 design/visual-review 的审查状态文字，`retained_from: Round 4`；新增文档检查把本 unit 全部新增图片作为拟提交文件核验，unit 0 问题，剩余 4 条为其他 dirty 文档引用未跟踪内容的既有问题。未修改或提交那些文件。

## Round 5

### Metadata

- reviewer: `/root/feat584_design_review`（与 R1–R4 同一独立 reviewer）
- target: `main` / `54dd5dc21` 的 R4 Approved 基线后，冻结的 Q39、spec 通知正文、design P5/Chat 呈现、prototype、两张更新消息截图及 visual-review。
- review_mode: `delta`
- mode_reason: Q39 明确撤销消息标签和结果摘要/展开，属于有界呈现要求变化；不是历史 issue closure，也未改变架构、通知对象、接口或 milestone，无需全量复审。
- started_at: `2026-10-12T22:25:27+08:00`
- completed_at: `2026-10-12T22:27:19+08:00`
- duration: 1 分 52 秒（独立差异检查与浏览器取证时段）。
- checkout: `main` / `54dd5dc21`；确认产品代码、unit delta 与 migration-guidance 无 tracked diff。只追加本报告，不提交或修改其他产物。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

Q39 已兑现：通知保留时间、实际修改者、任务链接、变化和 @，不再附标签、摘要或展开；完整结果仍从任务详情读取。Gate 2 通过范围仍限于设计与原型，不表示真实通知投递、有效 mention 或原生实现已验收。

### Coverage 与证据

- **需求及文档闭合。** spec 正文和 Q39、design P5/Chat 段落均明确移除该额外呈现；Q39 显式覆盖 Q38，visual-review 明确旧截图和摘要/展开说明属于历史证据。保留历史问答没有形成两套当前要求。P5 仍映射 R5、W2/W3，结果字段及任务详情契约未变。
- **Raft 引用核验。** 只读 `/Users/czj/Repos/opensource-hub/raft-source` 中 `packages/server/src/routes/tasks.ts:821–838`、`packages/web/src/components/message/MessageItem.tsx:4159–4180`，确认所引任务状态通知正文包含修改者、任务编号/标题、目标状态，system 分支显示时间和正文，没有任务结果摘要/展开。另读 `SystemMessageGroupDisclosure.tsx` 与 `ThreadPanel.tsx:1792–1807` 调用，展开的是 `messageIndexes` 对应的原消息，不是任务 result。此结论只针对这些引用路径，不扩大为 Raft 所有消息都没有展开能力，也不把参考项目作为 Nano 的权限契约。
- **局部实现落点。** 原型预置与新生成事件共用精简后的 `eventRow(body,time)`；移除了结果区 CSS 和 detail 参数，`saveEdit` 继续保存节点 result，只不再把它附加到通知展示对象。事件目标计算、任务链接和数量规则保留。复用现有聊天消息渲染与任务详情即可落实，无需新增数据模型、服务或依赖。
- **独立实际画面。** 使用自己的 Chromium 会话 `feat584-review-r5` 打开作者静态服务，在 1440×960、390×844 看过 `output/playwright/feat-584-review/r5-chat-desktop.png` / `r5-chat-phone.png`：六条预置事件均为时间和变更正文，无“任务动态”逐条标签、摘要或展开；长标题与 @ 在手机可读，现有群头、气泡、输入区保持。
- **回链和完整结果。** 手机点击 n4“确认用户引导”消息链接，进入正确详情；实际查看 `r5-result-detail.png`，两段原始结果完整保留，空描述提示和编辑入口可用。
- **新生成通知。** 在同一手机会话编辑 n4 待确认→已完成，回 Chat；`r5-generated-phone.png` 显示一条新通知“小王将…设为已完成。@Agent B @Agent A”，自动出现在时间线底部，未附任务结果。补充 DOM 核验为 7 条事件（原 6 + 新 1），事件区标签检查 false、额外结果/展开控件 0、documentWidth=390。截图独立实际查看，未以 DOM 代替视觉检查。

`retained_from: Round 4`：Q36/Q37 的任务头/密度、当前 React 聊天基线、其余三宽度证据、消息回链与删除后提示，以及 R4 中引用的架构、权限、delta、迁移和 M1 结论。**R4 的消息摘要/展开证据仅保留为历史，不继续作为 must-match；当前以 Q39 和本轮为准。** 理由：本轮未改变这些未受影响路径，手机回链亦有本轮复核，不需要重复无关全量检查。

自己的浏览器已关闭；作者 `127.0.0.1:49268` 静态服务保留，未触及其他服务。

### 历史问题闭环

R1-W1–W4、R2-W1/W2 均保持 **closed**；R3/R4 无待关闭问题。Q39 是用户对已通过设计的新增修订，不回写或抹除旧轮结论与 Author Resolutions。

### Issues

无未关闭 CRITICAL/WARNING。

### Recommendations

无。


### Author Resolutions（Round 5 后）

接受 R5 Approved，无实质异议。Q39 的通知展示删除不影响 result 存储、详情、通知对象和投递规则。新用户反馈要求重做任务总览与状态分组，另由 Q40/R6 承接；不把 R5 消息局部通过扩大为新任务页已审查。

## Round 6

### Metadata

- reviewer: `/root/feat584_design_review`（与 R1–R5 同一独立 reviewer）
- target: R5 后冻结的 Q40 任务页信息架构、spec 根总览场景、task-graphs delta、design 根查询/视图/P1/P3/R1、prototype 与当前视觉证据。
- review_mode: `full`
- mode_reason: 不止视觉局部调整；新增根总览需求、扩展根查询摘要并修改 M1/R1 验收要求，需重新确认需求/接口/契约/原型/验收覆盖。未变架构与历史闭环保留既有证据，full 不等于重复所有后端或无关操作。
- started_at: `2026-10-12T22:43:05+08:00`
- completed_at: `2026-10-12T22:48:09+08:00`
- duration: 5 分 4 秒（独立审查与浏览器取证时段）。
- checkout: `main` / `54dd5dc21`，含已完成的未提交 R5；本轮确认产品 `apps/`、`packages/`、`src/` 无 tracked diff。只追加本报告，不改冻结产物、不提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

Q40 的根任务总览、状态列边界、多层深入与显式跨层负责人视图形成一致的操作模型。原型关键路径经独立实际验证，没有未关闭的实质问题。结论仍为 Gate 2 设计通过，不表示真实 Web/iOS、后端权限/分页/通知或生产验收通过。

### Coverage 与证据

#### 现状、需求、接口与架构

- **现状落点。** 重新读取实际 `src/IM/frontend/src/features/tasks/task-graphs-page.tsx`：`TaskGraphListPanel` 使用 `useTaskGraphList`，`TaskGraphsPage` 使用 graphId、scope/node 查询参数与 `TaskGraphCanvas`，现状是左侧根名单、中心画布和详情。读取 `apps/im-server/src/task-graphs.ts:303` 的根 summary 与 `:619` 起的 list，确认现有根摘要、document_json 和游标列表可被扩展；当前代码尚无目标身份/直属计数字段，不把设计当现状。
- **需求收口。** spec 正文新增“比较根任务并进入下一层”，Q40 说明默认全局根总览、列框、去侧栏、覆盖详情和独立子层入口；对应 task-graphs delta 增补同一完整场景，原有逐层/探索嵌套、六状态、父子独立与权限场景保留。Q35 的无外框处理明确被 Q40 覆盖，Q39 的简洁系统消息没有回退。
- **三种范围明确。** 根总览只包含可访问图根，列按自身状态；进入具体任务只显示直属 children，面包屑返回总览/祖先；“按负责人”明确为所有层级，匹配父子可同时出现，并带所属群/父路径。没有将直属记录数量当工作量百分比，也没有由子任务计数自动更新父状态。
- **查询闭合。** 根列表补 conversation、creator、assignee、自身 status 和直属六状态计数，继续从图文档派生，足以支持卡片；深层匹配返回 graph_id/scope_id/node_id 和 parent_path，复用现有定位语义。design 明确总览/负责人继续游标分页，计数标示已加载范围，未加载完不能显示为全部任务或空列；41 节点原型只是全量样例，不是分页实现验证。
- **职责与复用。** IM 继续作为唯一事实源，根摘要/直属计数应归属现有任务读取服务；客户端负责分列和覆盖详情，虚拟总览范围不成为新图或权限域。用既有 root 列表、children 与深链即可兑现 Q40，无需第二份进度、跨根依赖图、新查询服务或 PA/DSH 执行机制。创建根任务继续必选有写入资格的所属会话，未把全局总览作为共享权限域。
- **验收映射。** P1 包含根总览/各层、带框五组、详情不挤压、祖先返回；P3 明确跨层负责人入口；M1/R1 新增根比较、返回和关闭详情恢复位置，W3 仍要求三宽度与 Web/iOS 真页面对照。M1 单一交付范围和 Runbook/外部资源前置未变，未引入未落实的新验收资源。

#### UX 判断

Q40 的分析回应多层任务场景，而非仅修改颜色或复制单层看板：总览提供比较目标的入口，层内看板保持同层任务可比较，跨层负责人入口避免筛选悄悄改变范围。卡片主体用于读/改任务，底部独立入口用于钻入下一层，两种动作在根与子层一致。移除重复根名单后五列获得宽度，覆盖详情让短暂阅读不重排列；有框容器、列头和数量清楚标示每一组，暂缓仍有独立状态标签。原型不以拖拽、自动父状态、跨根结构图等新机制代替需求。

继承现有全局导航、teal token、任务内容与手机 sheet；左侧目录/默认入口/桌面详情方式的改变由 Q40 明确授权，不能要求机械保持旧布局。原型外层保持“示例数据、无后端”标识，搜索/结构连线演示与真实产品边界明确。

#### 独立浏览器走查

使用自己的 Chromium 会话 `feat584-review-r6`，复用作者 `127.0.0.1:49268/prototype.html`。以下图片均独立实际查看，临时证据位于 `output/playwright/feat-584-review/`；DOM 读数仅补充视觉和操作证据。

| 范围 | 本轮操作与结果 |
|---|---|
| 根总览 | `r6-overview.png`：1440×960 默认 7 根，五列计数 2/2/1/1/1，暂缓 n40 在待办但明确标记；n1 的 3/15 与自身进行中分开。总览不出现跨根结构图。 |
| 逐层/祖先/结构 | 从 n1 独立“查看15项子任务”进入，见 `r6-layer.png`；再进 n13，见 `r6-grandchild.png`，仅有 n20/n21/n22，数量3。切结构图仍是同三个节点；切回完成情况，经祖先回 n1、总览均正确。 |
| 列密度与详情 | 1024×760 的 n1 待办列滚至末尾，打开 n19 详情后按 Escape 关闭；`r6-drawer-medium.png` / `r6-medium-restored.png` 证明覆盖详情不重排列。开/关时列宽均186.796875，scrollTop均201，documentWidth=1024，标题/操作无挤压。 |
| 跨层负责人 | 选择 Agent B，`r6-assignee.png` 明确“16项任务·所有层级”，父/子直接匹配均存在，路径可辨；点 n23 后 `r6-deep-link.png` 定位其父 n10“验证邮件链接方案”，不是混在根层。详情选中 n23，父层只有1直属任务。 |
| 手机层级 | `r6-deep-phone.png`、`r6-overview-phone.png`：390×844 五组纵向带框，详情为 sheet；多级路径在自身横向容器中可滚动，返回总览可达，整页无横向溢出。 |
| 新建根任务 | 手机总览新建表单可见所属群选择（单一示例群），填写标题、负责人小王保存；`r6-root-created.png` 显示8根、n42详情、创建者/负责人/所属群，原图未被当成其父任务。 |
| 总览只读状态 | 切公开访客后仍可见8根，但新建 disabled；从示例群“加入群聊”后新建 enabled。只证明本原型入口与既定资格一致，不替代真实 ACL 或多群候选测试。 |
| Q39消息回链 | 新建时分配小王产生简洁事件；点击已有 n4 消息，`r6-chat-backlink-phone.png` 正确回 n1 的15直属层，并打开 n4完整结果。没有重新附加摘要/展开，R5消息呈现保持。 |

已关闭自己的浏览器，保留作者静态服务；未操作其他服务。没有为本次设计审查运行不相关产品测试。

#### 保留的覆盖

`retained_from: Round 1/2/3`：会话权限、真实 actor、创建者/负责人规则、领取/返工、冲突、整子树删除、事务通知/relay、PA/DSH、`/stop`、迁移与相关六份 delta；`retained_from: Round 5`：Q39当前消息语义；`retained_from: Round 4`：React Chat grounding 与未变聊天布局。理由：本轮生产代码、对应职责/状态/通知对象没有修改，Q40不另造后端机制。R4 的旧任务布局证据仅属历史，当前任务布局以本轮为准。

### 历史问题闭环

R1-W1–W4、R2-W1/W2 保持 **closed**。当前层详情仍直接可达，覆盖式详情没有重开 R2-W1；领取赋值逻辑没有相关变化。R5 Approved 仅原消息范围，新任务页由本轮独立覆盖。历史 findings、resolutions 与当时结论全部保留。

### Issues

无未关闭 CRITICAL/WARNING。

### Recommendations

无。按更新后的 P1/P3/M1 真客户端标准实施，不新增视觉偏好或额外门禁。

### Author Resolutions（Round 6）

接受 R6 Approved，无实质异议。Q40 根总览、直属层、跨层负责人入口、带框状态列与覆盖详情已完成设计和原型闭环；Q39 简洁通知保留。此结论仅为 Gate 2 设计通过，真实 Web/iOS 与后端行为按 M1 验收。


## Round 7

### Metadata

- reviewer: `/root/feat584_ux_design_review`（本轮新独立 change-design-reviewer；已读取 Round 1–6 及 Author Resolutions，不沿用旧 Approved 代替独立判断）
- target: `feat-584-task-progress-permissions`，冻结 `37b662370116ff1a4e3a0386b6dc4b94c2fa3598` 的 Q41 spec、design/API、六份 delta、P1–P5/M1、prototype 与视觉证据；结合当前生产装配入口与此前验收报告判断波及范围。
- review_mode: `full`
- mode_reason: Q41 虽只修两个 Web 旅程，但增加共享列表 `statuses` 契约并改变 M1/R1/R4，按 skill 扩为 full；未变职责与旅程逐项说明 retained，而不机械重复后端/原生验收。
- started_at: `2026-10-13T09:48:33+08:00`（首个独立浏览器留存时间；前置 skill、文档及 checkout 读取未单独计时）
- completed_at: `2026-10-13T09:54:18+08:00`
- duration: 5 分 45 秒（可核对浏览器证据时段，不含前置读取与报告追加）
- checkout: `/Users/czj/.codex/worktrees/unit-feat-584/nano-multiagent`，`codex/feat-584-task-progress-permissions`；开工仅既有 untracked `output/`。仅追加本报告，不修改设计、原型、产品代码或历史结论，不提交。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

Q41 的方案方向解决了真实反馈的共同原因：五列先各自完整筛选再分页，短完成列不再被长待办挤出；公开群发现回到聊天的创建入口和内容自适应弹窗，头像、文字层级及手机 sheet 与既有聊天一致。独立看图确认画面已明显改善，不能再用此前“页码可达”“弹窗能打开”的证据代替当前体验判断。

尚不能放行本轮：发现→进入群/返回的原型旅程不成立；列加载只呈现同步成功追加，缺少明确要求的加载/失败恢复等必要状态；公共群发现新增 Scenario 未同步到相应 canonical delta。均可在当前有界范围内修正，不需要扩大到全产品重设计或增加后端机制。本轮是设计审查，不表示真实 Web/iOS 或生产验收通过。

### Coverage 与证据

#### 用户目标、当前装配与架构

- 独立读取 spec Q41 原话及新 Scenario，目标是不同状态的工作能同时比较、各自连续浏览，以及公共群发现与既有聊天体验连贯。没有将反馈降为边距、颜色或控件存在性问题。
- 核实实际 `apps/im-server/src/task-graphs.ts:706–741`：现有 `list` 已在 ACL 限制的图中展开节点，搜索/负责人先于 `slice`，total 来自完整匹配集，cursor 绑定 user/query/assignee；缺少状态条件正是本次增量落点。`src/IM/frontend/src/features/tasks/task-progress.tsx` 的 `TaskOverview` 当前持单一 cursor 列表，再把同一页交给 `TaskBoard` 分组，故只改列 CSS 或把 Next 改成自动触发仍不能解决问题。
- design:136/203–206 已把 `statuses` 放在 limit 前，待办使用 `todo,paused`，其他列单状态；total 与 cursor 都绑定状态集合、搜索、负责人、ACL/主体，规范状态集合避免同一集合不同顺序造成不同查询。每页重新应用 ACL；旧消费者不传可选参数沿用列表语义。方案不增加任务存储、节点投影服务或第二个执行循环。
- Web 网络/累计状态应由总览查询层负责，五个 `useInfiniteQuery` 各自持 cursor/items；完整图内 `TaskBoard` 继续纯展示。design 已明确首批20、3秒可见轮询重读已加载页、graph_id/node_id去重、筛选重置、不可读清缓存、本列失败保持其他列、首批真实total、成功total=0才显示空态。这些契约闭合；本轮没有用同步原型证明真实轮询/取数已实现。必要视觉状态缺口见 R7-W2。
- 核实当前 `chat-workspace-page.tsx:1212` 的裸 public-groups、`conversation-sidebar.tsx:114–116` 的独立 Discover 按钮，与 Q41 根因一致。既有 `NewConversationMenu` 已有联系人/新群两项及关闭/焦点行为；`new-group-modal.tsx`、`global.css:3225–3267` 已有内容高度限制、滚动 body 和手机 sheet，`GroupAvatar` 是现有群辨认方式。复用它们比再造一套固定 inset 弹层更少维护成本；`PublicGroupsModal` 负责展示/选择，父页面使用既有路由/ACL即可，不应承接另一个群治理服务。

#### 实际画面与独立连续走查

使用独立 Chromium session `feat584-review-r7` 打开 parent 持有的 `http://127.0.0.1:58437/prototype.html`。实际查看作者 `prototype-q41-{columns,discovery,phone}.png`、当前 React 聊天基线 `baseline-chat-desktop.png`，并逐张查看以下自己取得的画面。临时截图位于既有 `output/playwright/feat-584-review/`，未作为提交产物；DOM读数仅补充实际渲染与点击证据。控制台仅 favicon.ico 404，与受审路径无关。

| 范围 | 独立操作与体验判断 |
|---|---|
| 桌面列数量悬殊 | 1440×960，独立点演示区“列加载样例”，58根、五列53/2/1/1/1；首批待办20，完成立即可见。`r7-columns.png` 中列外框/标题/数量清楚，卡片标题、负责人、直属完成数互有层级，暂缓独立标记；无需整页翻页。 |
| 列内追加 | 驱动真实列滚动事件，从20→40→53；其他列仍2/1/1/1且scrollTop=0。`r7-columns-tail.png` 可见最后一张“待办51”为暂缓，短完成列位置不变。只证明本地交互成功态，未证明 API/cursor 或轮询。 |
| 中间宽度与窄屏 | `r7-medium-columns.png` 为1024×760，五列仍可辨认。`r7-phone-columns.png` 为390×844，五组纵向排列，待办滚动区464px，随后进行中组在有界距离可达；documentWidth=390，无整页横向溢出。符合长组不无限推远后组的取舍。 |
| 搜索重置 | 已追加到53后搜索“滚动样例”，待办变20/51且其他列为空；清空搜索时恢复53张而不是首批20，scrollTop=0。`loadedColumns` 按完整旧key永久保留，与“筛选变化同时重置”的原型约束未对齐，见R7-W2。 |
| 桌面发现 | Chat→＋→发现公开群，`r7-discovery.png` 为紧凑内容高度，3行头像/标题/成员信息，较现有裸弹层有清晰视觉完成度。但打开后＋菜单仍在遮罩下展开；背景点击不关闭，Escape虽关闭却停留在菜单项焦点，不回＋触发按钮。 |
| 手机真实入口 | 390×844，从群头返回会话列表→＋→发现公开群；`r7-phone-discovery.png` 证明自然入口能打开底部sheet。选择“产品体验讨论”后 `r7-phone-open-group.png` 仍是会话列表，并没有进入该群。原因是sidebar.open未清除，三个示例群行又都只执行同一page='chat'。这是连续旅程缺口，不是原生或真实后端失败。 |

原型外层明确示例/无后端，演示造数仍在独立区。原有聊天正文、系统消息与任务编辑没有借本轮添加产品控制。发现入口仅两项且遗漏现有联系人项，虽设计写明第三项、产品代码仍有联系人，复审应使用完整现有菜单上下文，归入R7-W1。已关闭自己的浏览器，未停止 parent 的静态服务或其他运行服务。

#### 需求、delta 与 milestone

- task-graphs delta:68–91 锚定 `docs/specs/im/task-graphs.md`，保留层级/探索/独立父状态等既有 Scenario，并新增五列自然加载；当前canonical“空、加载、错误与已加载图”仍是消费者基线。新增statuses属于可选查询能力，没有要求Agent/iOS跟随改为五列取数。
- spec:113–118 新增“从已有会话入口发现公开群”，对应的 conversations-messages delta 已有同名群类型 Requirement，但遗漏该Scenario，见R7-W3。不能因design/P4写得完整就视为canonical归并已覆盖。
- P3/P4的must-match已包含自然加载/真实总数与菜单/紧凑头像列表/sheet；R1/R4投影真实长短列与群发现旅程，W1/W3承接接口、三宽度和客户端证据，单一M1合理。R1不仅要求按钮存在，也要求筛选重置和浏览位置；R4不仅能打开，还要求进入群与返回自然。局部原型缺口不应推迟给实施者猜测。
- Runbook仍使用隔离Web+TS IM+Node/公开DSH和真实SwiftUI客户端；账号/节点/端口/配置/workspace来源已有，不需要新的外部租户或权限。Q41没有新增无法落实的验收资源，设计修复只需本地模拟状态/路径，不提前要求真实后端实现。

#### 保留与失效的历史覆盖

- `retained_from: Round 1/2/3`：真实actor、创建者固定/负责人、读取与写入分离、领取/返工、删除子树、revision冲突、事务通知/relay、PA/DSH、`/stop`及一次性迁移；理由：Q41不修改对应身份/写入/投递/执行对象，查询仍由同一IM服务做当前ACL，没有引入新事实源。
- `retained_from: Round 4/5`：现有React聊天视觉基线、Q39轻量事件与结果回链；理由：Q41只换发现入口/弹层，未改变timeline或通知消息语义。发现弹层本轮独立重审，不借旧聊天通过自动放行。
- `retained_from: Round 6`：根/直属/跨层负责人的范围分离、祖先/总览导航、覆盖详情、父状态/直属计数；理由：没有相关实质差异。旧“全状态分页再分列”及其已加载范围证据失效，当前以Q41独立状态查询为准。
- acceptance Round1/2的真实权限、真人/Agent编辑、通知/忙闲/离线/stop、迁移与未受影响原生路径按其原证据边界保留。Round2的Web Previous/Next只能证明旧实现，不继续作为Q41自然加载通过证据；裸公开群弹层的既有可打开证据也不保留为当前体验通过。**原生51条累计列表的Load more/尾部操作仍inconclusive**；Q41明确不重设计iOS，Web原型、iOS build或API测试均不能关闭这项真实操作缺口。

### 历史问题闭环

R1-W1–W4、R2-W1/W2维持此前核实的**closed**；其Author Resolutions、历史证据和当时结论均保留。R3–R6没有遗留未关闭项。本轮问题来自Q41的新增契约/原型覆盖，不重写旧轮，也不重新打开无关后端缺陷。

### Issues

#### R7-W1 — 公共群发现原型未兑现选择与返回的连续旅程

- 位置：`prototype.html:66–68,77`；对照`design.md:207`、spec“从已有会话入口发现公开群”、P4/R4。
- 实证：手机从会话列表真实入口打开发现后选择“产品体验讨论”，弹窗消失但停在列表（`r7-phone-open-group.png`）；所有群行没有选中群身份，均回同一示例聊天。桌面背景点击无效，＋菜单保持展开，Escape/关闭没有把焦点恢复到创建按钮；菜单还省略既有联系人项。
- 用户代价：用户已经选了目标群却无法继续查看/加入，退出后上下文和操作位置也与设计不符。作者手机截图是在已打开弹窗后resize，不能替代真实入口→选择的路径证据。
- 闭环要求：在本地原型保留完整现有＋菜单上下文；选择至少一个未加入示例群能明确进入该群访客查看/加入，手机关闭列表层；关闭/背景/Escape正确恢复入口与上下文。无需连接真实后端或重建无关聊天功能。

#### R7-W2 — 独立加载的必要状态没有可评审呈现，筛选重置与原型不一致

- 位置：`prototype.html:54,57–60`；`design.md:204–206`；spec/delta“Web五列独立自然加载”。
- 实证：原型只有同步切片追加与“已加载x/共y·滚动继续”，没有独立首批加载、追加中、本列追加失败/重试及刷新失败保留已加载内容的呈现；加载全量后页脚直接消失，没有已到底反馈。把加载过的无搜索query切走再切回会恢复53张，`loadedColumns`未随筛选变化清空，仅scrollTop归零。作者visual-review:117明确把轮询/失败重试全部留待实施，当前无法判断新状态的阅读/恢复成本。
- 用户代价：真实接口稍慢或某列失败时，实施者仍需自行决定怎样区分“没有任务”“尚在读”和“只加载了一部分”，怎样恢复而不破坏其余列。正是本次独立列表体验的关键，而非后端正确性可代证的细节。
- 闭环要求：在独立演示区提供有代表性的本列加载/追加失败/重试/刷新保留状态，画面中保留其他列与原位置；展示明确到底状态，并使搜索/负责人重置行为与契约一致。只需本地模拟，无需真实API/3秒轮询定时器或穷举每种失败组合；真实取数和轮询验证仍在M1。

#### R7-W3 — 公共群发现新增Scenario遗漏canonical delta

- 位置：`spec.md:113–118`与`specs/im/conversations-messages.md:95–117`。
- 实证：首文档在“群类型具有明确默认值、加入方式与切换资格”新增从已有会话入口发现公开群，包含原列表布局、内容高度、头像行、手机sheet、关闭/进入访客流程；同一Requirement的conversations-messages delta仍只含创建加入/改范围/外部影子/读写分离，没有投影新增Scenario。
- 后果：按现有delta归并会保留公开群权限，却丢掉这次用户纠正的入口和旅程体验契约；后续消费者只读current spec时仍可退回独立按钮/裸弹层。
- 闭环要求：将该Scenario投影到`docs/specs/im/conversations-messages.md`对应delta，保留该Requirement已有Scenario；不把Web控件细节塞入Agent工具或任务权限契约。

### Recommendations

无。只闭环上述有证据的问题，按影响一次复查，不增加视觉偏好或无关门禁。

收尾 `git diff --check` 通过。共享 worktree 同时出现 IM collaboration、conversation-sidebar、task-graphs 三个测试文件的修改，均非本 reviewer 所写，已保留未处理；本报告审查目标仍为冻结版本37b662370。

### Round 7 Author Resolutions

- R7-W1 accepted：原型补齐三项＋菜单，发现时关闭菜单并保存触发器焦点；背景/关闭/Escape恢复入口；未加入群选择记录真实示例群名、关闭手机列表并进入访客历史，加入保持明确动作。
- R7-W2 accepted：演示区加入待办列首批加载、追加中、追加失败/重试、刷新失败保留状态；正常滚动有追加反馈，完整列显示到底。筛选key变化清空累计与模拟状态，其他列/同筛选下滚动位置保持。只模拟状态，真实API/轮询仍留M1验证。
- R7-W3 accepted：新增群发现Scenario同步至conversations-messages delta，保留原Requirement全部Scenario。

产品源代码仍为此前冻结实现；新增三处回归测试已取得API不识别statuses、短完成首屏不可见、独立Discover按钮仍出现的预期失败，未改运行代码。


## Round 8

### Metadata

- reviewer: `/root/feat584_ux_design_review`（与Round7同一独立reviewer）
- target: 冻结 `dac05051e1a89d70b7e69d970f8623c15eba8962` 的Round7 Author Resolutions、prototype、conversations-messages delta和相应视觉记录。
- review_mode: `closure`
- mode_reason: 三项修订均限于R7问题的原型路径/状态与缺失Scenario，没有新增需求、查询接口或milestone决定；复核历史问题及必要波及，其他覆盖`retained_from: Round7`。
- started_at: `2026-10-13T10:02:35+08:00`（独立浏览器首个留存时间；前置读取未单独计时）
- completed_at: `2026-10-13T10:07:45+08:00`
- duration: 5分10秒（可核对浏览器证据时段）
- checkout: `/Users/czj/.codex/worktrees/unit-feat-584/nano-multiagent`，`codex/feat-584-task-progress-permissions`。开工确认HEAD与上述冻结一致，三处既有dirty测试及untracked output/保留；仅追加本报告，不改其他产物、不提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R7-W1/W2/W3全部独立闭环。两项体验修正现在能从实际入口连续操作，异步读取的必要状态也有可判断呈现；没有需要实施者自行补决策的阻断项。此结论仅为Gate2设计通过，真实API的状态筛选/cursor/total、Web网络轮询/失败以及iOS累计加载尾部仍按M1完成对应验证，不能由本地原型替代。

### Coverage 与证据

`retained_from: Round7`：需求/Q41根因、IM事实源与查询归属、可选statuses先于limit、todo+paused组合、total/cursor主体和筛选隔离、Web独立查询与完整图纯展示边界、P1–P5/M1、既有权限/通知/PA/DSH/迁移、原生范围及验收资源。理由：本轮只修原型对这些既定契约的表达及补齐同一群Requirement的delta，未修改共享接口、授权或执行数据流。

使用自己的Chromium session `feat584-review-r8` 打开parent服务58437；1440×960核对列状态，390×844从手机自然入口核对群旅程。实际逐张查看临时截图 `output/playwright/feat-584-review/r8-{initial-load,append-error,refresh-error,loading,all-loaded,phone-discovery,phone-visitor}.png`。这些是本地原型证据，无真实后端。控制台仅favicon.ico 404；自动化曾使用失效ref，刷新定位后完成目标操作，不据此报告产品问题。

### 历史问题闭环

| 原Issue | Author Resolution | 独立复核证据与用户结果 | 状态 |
|---|---|---|---|
| R7-W1 | accepted：完整三项菜单、发现时关闭菜单，背景/关闭/Escape恢复焦点，选择群进入对应访客页，加入明确触发 | 桌面实际打开＋，看见新建聊天/新建群/发现公开群；发现弹窗打开时菜单已关闭，搜索获焦。真实点击背景后dialog=false、焦点为“新建会话”、原群标题保留；Escape同样关闭且恢复＋。手机从群头“会话列表”→＋→发现→产品体验讨论，实际进入该群头与简洁公开历史，sidebar.open=false、显示未加入/加入群聊、输入disabled（r8-phone-visitor.png）。点击加入后群名保持、未加入消失、输入enabled；再次打开/点击关闭回到原会话列表且焦点为＋。与设计的选择/返回/不自动加入一致。联系人功能仍为注明背景能力，不要求本轮重建。 | **closed** |
| R7-W2 | accepted：首批/追加/失败重试/刷新保留/到底，筛选变化清空累计与模拟状态 | 独立演示首批加载：待办卡片0、数量“—”、正在加载任务，其他列2/1/1/1保持，未显示暂无任务；追加失败：原20张保留，列尾失败与重试可见，其他列位置0；点重试变40张、待办scrollTop1830保持。刷新失败：40张保留，列尾说明与重试可达，其他列仍稳定；点刷新重试恢复40张，然后正常滚动显示“正在加载更多”（r8-loading.png），延迟后追加。独立再次从20→40→53，页脚明确“已显示全部53项”（r8-all-loaded.png）。已有40张后搜索样例变20/51、清空变20/53且scrollTop0；负责人Agent A加载至40后换Agent B再回A，首批20/52、scrollTop0，旧失败/累计均未带回。 | **closed** |
| R7-W3 | accepted：群发现Scenario同步delta，保留其他Scenario | 逐项对照spec:113–118与conversations-messages delta:104–109，新增Scenario内容一致、位于同一群类型Requirement；创建和加入、更改可见范围、外部影子、公司读取与成员写入分离均仍保留。canonical target继续为docs/specs/im/conversations-messages.md，没有把UI细节投影到Agent权限契约。 | **closed** |

加载/失败反馈放在本列既有内容之后，文案区分新增读取失败与刷新失败保留；用户可在继续比较其他状态时恢复当前列，不需要全局重新开始。新的到底文案没有改卡片/列头信息层级。手机发现沿用内容高度的底部sheet，从真实入口进入目标群后也能明确辨认群名和访客状态；这次没有仅凭静态截图放行连续旅程。

R1-W1–W4、R2-W1/W2维持此前closed。R7明确失效的旧Web整页分页/裸群弹层证据不恢复为当前通过；真实权限、消息通知、编辑与迁移等未变路径继续按Round7说明保留。三处dirty测试是实施前预期红测，本轮未执行或把它们当成设计失败，也未修改产品源码。**原生51条累计列表尾部Load more实际操作仍inconclusive**，本轮没有原生复验，也不关闭该验收缺口。

### Issues

无未关闭CRITICAL/WARNING。

### Recommendations

无。按已冻结契约实施并进行有风险针对性的真实复验，不增加纯偏好或额外审查循环。已关闭自己的浏览器，parent静态服务及既有状态保留。

## Round 9

### Metadata

- reviewer: `/root/ios_q42_design`（新独立 change-design-reviewer；接收前轮问题及证据交接，独立核对本轮实际来源与画面）
- target: `23063f39f75396911fd4190030426acda0b88f80` 的 Q42、`ios-experience.md`、`ios-prototype.html`、design 补充链接及 IM task-graphs ADDED requirement；PR #338 尚未合并的同一用户修订。
- review_mode: `full`
- mode_reason: 用户将单一编辑方向扩大为整个原生任务流程，并新增草稿离开确认、逐字段三方冲突选择及 M1 原生退出条件，属于需求与验收范围变化；因此重新覆盖原生需求、现状、设计、delta 和 milestone。未改后端/Web/Agent 范围保留 Round 7/8 的证据，不重复无关产品验收。
- started_at: `2026-10-13T12:07:30+08:00`（首次显式时间记录；前置 skill、checkout 和文档读取未单独计时）
- completed_at: `2026-10-13T12:11:22+08:00`
- duration: 3 分 52 秒（独立来源/原型复核时段，不含前置读取与报告追加）
- checkout: `/Users/czj/.codex/worktrees/unit-feat-584/nano-multiagent`，`codex/feat-584-task-progress-permissions`；开工及复核结束 status clean。只追加本报告，不改设计/原型/产品，不提交。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

内容优先的详情、持续字段标签、紧凑状态/负责人行和独立冲突比较页方向成立，实际编辑旅程可辨认且比当前 Form 的无标签多行记录清楚。三方合并、明确保存和原 API 复用的文字设计闭合。

但受审原型仍主要覆盖一个任务的编辑；用户已确认的总览、逐层、创建和入口统一范围没有足够可评审呈现，且保存后的示例状态与总览归组相互矛盾。该缺口影响实施者对整条旅程的理解，不能把它留给真实验收再补设计。用户方向已确认，修复不需要重新询问方向；只需在已授权范围补足代表性路径和对应边界。

### Coverage 与证据

#### 现状 grounding、用户约束与职责

- 核对 `NanoIMApp.swift:124` 的原生 Tasks NavigationStack、`ChatInfoView.swift:57` 的 GroupTasksView 入口，以及 `TasksView.swift` 的总览、TaskGraphView、TaskNodeView、GroupTasksView 实际装配。当前详情从 List 的创建者/负责人/修改者开始，编辑复用同一个 TaskEditorView；创建根节点另有所属会话、首次拆分另有父层结构选择，不能仅把“编辑任务”改标题当成完整创建设计。
- `TaskEditorView.swift` 当前确为 Form、描述最少三行/结果最少四行，latestNode 区域直接串联无字段标签；Cancel 直接 dismiss，只有 busy 禁止滑动关闭。独立查看既有原生 `evidence/acceptance-r1-ios-conflict.png`，可见固定留白和无持续标签的正文/结果。Q42 的问题陈述与真实源码/原生画面一致。此次没有把该历史截图当成新 App 已验收。
- 新 `TaskEditField / TaskConflict` 应承担与 SwiftUI 无关的字段比较，TaskEditorView 负责草稿、请求和页面状态；共享 TaskPresentation 小视图承担现有状态/身份展示复用。该分工复用 TaskDraft、TaskNode 和现有 IMClient，不需要新状态框架、后端接口、任务存储或第二执行循环，维护成本与本次范围相称。
- 服务端 `apps/im-server/src/task-graphs.ts:493–517,586–590` 已提供 request_key 回执及 graph revision 原子校验。Q42 使用同一 `apply` 写入，既有 `can_edit/can_claim/can_delete` 仍为展示信息而非授权替代；未绕过服务端成员资格和已解散只读规则。

#### 三方冲突与数据闭合

- `ios-experience.md:25–29` 明确以 baseline/draft/fresh 比较标题、描述、结果、状态、负责人，负责人使用 type:id；远端独改采用 fresh，本地独改保留，两侧相同不冲突，同字段不同值要求显式选择。这比“加载 latest 后用完整旧 draft 重试”更准确地保护协作更新。
- 读取最新只准备比较，零冲突也必须明确确认；再次 409 使用最近比较 baseline 和当前草稿重新比较。changeNote 保留、done→doing 按 fresh 状态验证原因、删除/失权不重建、子任务创建刷新父图后明确重试均有收口。body/revision 变化换 key、完全相同的不确定请求重用 key，未破坏原幂等契约。
- 沿用完整字段 patch 在 graph revision 检查下可成立；无须增加服务端字段级 merge。所列值类型测试覆盖真实比较分支，不是为样式变化补机械 UI 单测。

#### 实际画面与连续操作

独立用 CUA 在后台浏览器打开 reviewer 临时静态服务 `http://127.0.0.1:58449/ios-prototype.html`；先看实际 390px 手机容器，再将浏览器设为 352×844（外层各16px，产品容器320px）。实际看图并操作，DOM/源码只用于补充定位。

- 编辑页标题明显高于属性行，说明/结果有持续标签，轻分隔和留白形成清楚阅读顺序；状态面板六项完整，有图标、选中勾与关闭按钮。选择“待确认”返回草稿，尚未保存。
- 负责人面板显示未分配、两名真人和机器人标识的 Agent；搜索“不存在”显示空态，搜索“设计”选择设计助手后返回草稿。点返回出现继续编辑/放弃确认，继续编辑保留状态和负责人。
- 修改说明与结果，启用外层模拟冲突再保存：独立比较页完整显示“保留我的内容/采用最新内容”，默认无选择且确认按钮禁用；选择最新说明后明确确认保存，详情显示最新说明、本地结果和待确认状态，随后可返回总览。此处是原型交互成功，不是服务器真实 409 证据。
- 320px 容器下追加长标题、十段中文说明并清空结果，文字换行、输入随内容长高，空结果收为单行，尾部内容可达；未看到横向裁切。大字体与真实键盘/VoiceOver 尚未独立验证，保留为受影响原生验收条件，不宣称浏览器已替代这些检查。
- 详情→子任务实际打开两组静态条目；子项无详情/下层操作。返回总览只有三个组，保存为待确认的任务仍在“进行中·1”，没有完整五组、独立子层入口、负责人筛选或创建/聊天上下文。见 R9-W1。

临时复查截图 `/tmp/feat584-q42-design-review/overview-320.png`、`long-edit-empty-result-320.png` 未提交（本轮授权只追加报告）。关闭了自己的浏览器、还原 viewport 并停止58449静态服务；没有关闭或改动用户/parent 的 App、模拟器和服务。

#### delta、milestone 与验收资源

- 新 ADDED Requirement 锚定 `docs/specs/im/task-graphs.md`，内容是原生用户可观察结果，现有权限、六状态、层级、结果、通知 Scenario 未被删除。共同 IM 任务文档承载任务特有体验合适，不需要在 ios-client 再复制一份；后者既有原生、中文输入、大字体和可复制约束继续适用。
- 仍是单一 M1，Q42 补充明确投影 R1–R4/W3：原生总览到详情、子层/聊天返回、根/子创建、真人/Agent、保存/放弃、实际服务端并发409、窄屏/大字体、分页末页，以及聚焦/全套原生 tests/build、独立代码/一致性/产品核对。无需并行新增 milestone。
- 本轮只读核实 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl list devices available`：专属 `Nano feat584` UUID 与设计一致且 Booted，其他可用 iPhone 模拟器存在；脚本和隔离身份/fixture 来源有定义，不依赖生产或外部租户。parent 后续报告 App 已登录、隔离 IM62306 健康及 fixture 已创建，本轮未独立操作该运行态，故只作为下一轮可用资源交接，不记产品通过。
- 历史原生累计51条尾部仍需实际操作；此次原型、值类型测试计划和 Simulator 可用性均不关闭该缺口。真实键盘、字体、保存反馈和并发恢复仍由新 App 的实际旅程判定。

#### retained coverage

`retained_from: Round 7/8`：Q41 Web 独立状态查询/自然加载/失败恢复/公开群发现、后端 ACL/事务/revision/通知及 Agent/PA/DSH/迁移责任。理由：冻结提交只修改五份 Q42 设计产物，未改这些接口、权限、执行和 Web 体验；本轮核实原生仍复用同一事实源。旧原生编辑外观和旧冲突呈现的通过不能作为 Q42 新体验通过。Round 8 对 R7-W1/W2/W3 的 closed 结论保持，原始证据边界不扩大。

### 历史问题闭环

R1-W1–W4、R2-W1/W2 与 R7-W1/W2/W3 依前轮核实保持 **closed**。本轮不重开无关后端/Web 项，也不以旧 Approved 自动批准新增原生范围。

### Issues

#### R9-W1 — 扩展为整条原生旅程后，原型仍缺少关键上下文且保存结果与总览矛盾

- 位置：`ios-experience.md:7,13–21,35`；`ios-prototype.html:1946–1956`；Q42 范围与 M1/R1–R4。
- 独立实证：状态选为待确认并保存，详情显示待确认，但返回总览仍被硬编码放在“进行中·1”。总览只三个组，子层只两组且所有子项不可进入；没有根/子创建（所属会话、首次拆分结构）、全局负责人筛选或群任务入口的可判断呈现，也没有区分这些缺失是沿用背景还是本次待实施增量。受审文件不是已经覆盖整条流程的原型。
- 用户/实施代价：用户无法据该原型判断创建上下文和逐层/返回是否保持，实施者可能只统一编辑页而遗漏已授权范围，或把无子层入口和保存后错误归组当成可接受示例。总览五组及空组的密度、头像/身份和详情/子层入口关系尚无实际画面证据。
- 闭环要求：保留已通过的编辑与选择/冲突方向，补最小代表性的总览五组（含空组）、详情/子层分离入口、可进入一项子任务并返回、根/子创建的特殊上下文、负责人筛选及群任务入口上下文；保存后总览/子层从同一示例状态刷新。无需重建所有聊天功能或连接真实后端；沿用背景可静态呈现并明确标注，受影响路径须能连续判断。将这些代表页与 must-match、真实入口、R/W证据对应，留下代表性渲染证据；缺失状态不得仅以“将于模拟器验收”后移。

### Recommendations

无。修复上述有界证据缺口后复核，不扩大为全 App 重设计或额外审批。


### Round 9 Author Resolutions

- R9-W1：accepted。补齐五组、状态保存重分组、可进入子层/详情及返回、根/子创建、跨层负责人筛选和群任务入口；保留原编辑/面板/冲突方向。`ios-experience.md` 追加路径、真实入口、R/W映射及四张作者实际看过的代表截图。过程中发现并修正子项详情返回错误进入其子层的问题。提交后再进行独立 closure；不把原型当真实产品验收。

## Round 10

### Metadata

- reviewer: `/root/ios_q42_design`（与 Round 9 同一独立 reviewer）
- target: 冻结 `ee82e0e20281821cdb3c9e3815ed1d183c8e9050` 的 R9 Author Resolutions、补充原型与四张证据、`ios-experience.md` 路径/入口/R/W 映射。
- review_mode: `closure`
- mode_reason: 变更仅落实 R9-W1 要求的原型上下文和旅程，未新增产品需求、API 或 milestone；按原问题及必要波及复核，其他覆盖 `retained_from: Round 9`。
- started_at: `2026-10-13T12:22:28+08:00`（本轮首次显式时钟；此前已完成文档读取和主路径走查，不纳入此计时）
- completed_at: `2026-10-13T12:24:05+08:00`
- duration: 1 分 37 秒（有时间记录的尾段核查与清理，不代表全轮耗时）
- checkout: 原 worktree/branch，开工与结束 status clean；仅追加本报告，不修改或提交其他文件。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

R9-W1 的原型范围与状态归组缺口已关闭；补充路径现在能指导整个任务流程，保留内容优先的共同风格。复核共享选择面板的必要波及时，实际发现取消筛选后污染任务改派的局部问题（R10-W1）。无需再次改变方向或扩大重设计，只需修正该上下文清理并复核同一序列。

### Coverage 与历史问题闭环

`retained_from: Round 9`：原生实际装配、用户约束、三方冲突值类型/API/幂等/权限职责、delta、M1/R1–R4/W3、验收资源和后端/Web 的 retained 边界。理由：本轮只增加原型示例状态和上下文，文字契约及产品代码未变。新的原型保存仍不代表服务端409或原生Simulator验收。

本轮 IAB 不可用且浏览器扩展无法连接，改用 CUA 的 Chrome 原生 AX/截图在独立新标签操作 parent 的58449服务；未操作隔离IM62306或模拟器。实际看过四张作者截图及自己的总览、创建、负责人页面渲染，未只依据源码或作者通过声明。

| 历史问题 | Author Resolution 与独立证据 | 结论 |
|---|---|---|
| R9-W1：五组、保存归组与入口不足 | 首屏显示五组和紧凑空组；标题、真人身份和子层入口分开。实际打开根任务→编辑→状态待确认→保存→详情→总览，进行中1→0、待确认1→2，卡片进入正确组。独立点子层→“补齐邀请链接失效提示”详情→返回，回到“完成首次登录流程”的直属层，未进入子节点自身层。 | closed |
| R9-W1：根/子创建、负责人筛选及聊天上下文不足 | 子层＋显示父任务/所属会话和首次拆分结构示例；输入“R10 子任务”保存，详情返回原父层，待办新增1且未分配。总览＋显示会话选择和根结构，选择示例群后创建“R10 根任务”，返回总览出现待办1、已加载3。负责人选林悦，同时看到根“整理新版本发布说明”和深层“补齐邀请链接失效提示”，后者带父路径。总览返回明确标注的静态聊天背景→群任务→子项详情→返回，回到同一群任务列表。 | closed |
| R9-W1：呈现范围与证据映射缺失 | `ios-experience.md` 新表将总览/子层创建/跨层筛选/群任务映射真实入口和R/W，聊天明确静态背景，单群选择与首次拆分控件的演示边界明确；四张截图体现五组、空组、父任务上下文和身份/路径层级。作者注明创建控件截图早于最终间距/选中底色修正，本轮实际渲染已核实最终样式。 | closed |

上表范围已经闭环。新发现只涉及取消筛选后改派的复用状态，不重新打开 R9 整体范围问题。Round 1/2/7 的历史 closed 保持。

### Issues

#### R10-W1 — 取消负责人筛选后，编辑任务负责人仍走筛选分支

- 位置：`ios-prototype.html:1942,1975,1978–1982`（`closeSheet`、`filtering` 与 `choose-owner`）。
- 实际复现：新标签总览→“按负责人·所有层级”→关闭选择面板→打开“完成首次登录流程”→编辑任务→点负责人。面板标题下仍是“筛选可见任务的负责人”，缺未分配项；选择林悦后直接跳回总览并显示“负责人：林悦”，没有回到改派草稿。
- 原因与代价：筛选入口置 `filtering=true`，关闭时没有复位；后续编辑复用面板仍进入筛选处理。用户只是取消过一个浏览筛选，之后的改派动作却改变浏览范围并离开编辑流程，违背“选择仅改草稿，保存明确提交”的已确认契约。这是本轮原型新路径间的实际干扰，不是推测性边角问题，也未宣称真实App已有此bug。
- 闭环要求：使筛选与编辑面板目的随每次打开/关闭确定，不把取消后的筛选状态带入编辑；核实上述序列回到编辑草稿、未分配项恢复且改派尚未保存，同时正常筛选仍能完成。无需新抽象或扩大测试矩阵。
- 临时截图：`/tmp/feat584-q42-design-review/r10-cancel-filter-redirect.png`，未提交；独立AX记录同时确认进入编辑前后的标题及错误跳转。

### Recommendations

无。已关闭自己创建的复审标签，未修改浏览器缩放设置；parent静态服务和运行验收环境保留。


### Round 10 Author Resolutions

- R10-W1：accepted。closeSheet 对关闭、Escape 和遮罩关闭统一清除 filtering，避免下次编辑负责人继承全局筛选语义。保留 R9-W1 closed。本轮只修该状态生命周期，原生实现将使用独立 sheet 状态。

## Round 11

### Metadata

- reviewer: `/root/ios_q42_design`（与 Round 9/10 同一独立 reviewer）
- target: 冻结 `6e3085890418f9f32f529af8f80dfe726fdb9d39` 的 R10 Author Resolutions 及 `closeSheet` 单行状态清理修复。
- review_mode: `closure`
- mode_reason: 仅关闭 R10-W1 的共享面板状态污染；没有需求、接口、视觉方案或 milestone 变化，不重复已通过的整体旅程。
- started_at: `2026-10-13T12:25:34+08:00`
- completed_at: `2026-10-13T12:27:01+08:00`
- duration: 1 分 27 秒（来源及实际交互复核，不含报告追加）
- checkout: 原 worktree/branch，开工 clean；仅追加本报告，不改其他文件、不提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R10-W1 已独立闭环。取消筛选不会改变后续编辑负责人面板的用途，正常跨层筛选仍可完成。该结论只批准当前 Q42 设计及原型，不表示原生实现或 Simulator 验收已经通过。

### Coverage 与历史问题闭环

`retained_from: Round 9/10`：原生完整范围、实际装配与架构、三方冲突/API/权限/幂等、delta、M1和验收资源；五组/归组、根与子创建、层级返回、跨层负责人、群任务及已核实视觉方向。冻结 diff 只在 `closeSheet` 增加 `filtering=false`，没有使上述证据失效。

- **R10-W1 — closed**。Author Resolution 接受并统一清理关闭状态。独立 CUA/Chrome 新标签走原复现：总览打开负责人筛选→X关闭→打开登录任务→编辑→负责人。面板这次显示“产品协作·会话成员”、未分配、真人/Agent及分配说明；选林悦回到编辑页，负责人草稿变林悦，保存按钮仍在，没有跳总览。随后返回→放弃修改，详情负责人仍为陈子健，证明选择没有隐式保存。临时实看截图 `/tmp/feat584-q42-design-review/r11-editor-assignee-restored.png`。
- **必要波及核查**：再次从总览进入负责人筛选，面板显示筛选语义且无未分配，选林悦后仍得到其根与深层两项结果。源码可见X、Escape、遮罩共同调用 `closeSheet`，这次在统一出口清理状态；不为同一出口机械重复三套完整旅程。
- R9-W1 以及此前所有已关闭问题保持 closed，无新发现。原生分页末页、真实409、键盘、大字体和新App视觉仍按既定 M1 实际验收，未借原型复查扩大证据边界。

已关闭本轮独立标签，parent58449静态服务、IM62306和模拟器未操作。

### Issues

无未关闭 CRITICAL/WARNING。

### Recommendations

无。按已审设计实施与原生验收，不增加额外审查循环。

### Round 11 Author Resolutions

R10-W1 closure accepted；R9-W1 retained closed。Gate 2 Approved，0 CRITICAL / 0 WARNING，按冻结设计进入原生实施。原型与 Simulator 产品验收分别记录。

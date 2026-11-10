# perf-753 · 独立设计审查

## Round 1

- Reviewer target `/root/work_reads_design`，独立设计 reviewer。
- review_mode `full`。首次 Gate 2，覆盖首文档、设计、delta-spec、milestone 和实际 Web／iOS／IM 接线。
- started_at `2026-11-10T00:50:45+08:00`，completed_at `2026-11-10T00:51:53+08:00`，duration 68 秒。
- 基线 `3179cd45f`。冻结输入 `motivation.md` SHA-256 前缀 `779e98708e81`、`design.md` `765543232272`、`specs/im/agent-work.md` `2c9f38637615`，milestone 骨架仅 `.gitkeep`。

**Issues Found · 0 CRITICAL / 6 WARNING**

### Coverage

- 真实服务由 `apps/im-server/src/server.ts:195` 挂载 `registerWorkRoutes`，`work.ts:394–445` 做身份、个人归属、空间和删除检查，`work-records.ts:43–52` 已能按 root＋session 定向读元数据。复用 `Work` 的节点连接与同步状态、由 `WorkRecords` 负责持久查询、由客户端决定加载范围的分工符合现有边界。设计不改变 Gateway 写入或模型上下文。允许按旧接口继续读是本次兼容决定，另一交付解决大记录上传。
- Web 设置和公开资料的 Work 共用 `AgentWorkPanel`，公开资料另有历史入口。Work 列表和原生轨迹选择器都依赖关联目录。iOS 从 Agents 和 Skills 进入同一个 `AgentWorkView`，也从目录及 item 内部直接进入子执行。用现有列表和导航控件表达局部分页足以继续设计，无需单独制作原型。已查看源入口和状态依赖，未观察候选界面。
- [Delta](specs/im/agent-work.md) 指向正确的 IM Work canonical 文件，ADDED 不覆盖既有场景。需与下列刷新、历史连续性和兼容决策一起固定适用边界。单一端到端 M1 合理，现有验收描述尚不足以判定规模目标。
- 性能设计核对了真实查询与已建议的索引方向。旧目录全量返回可从 `WorkRecords.view()` 直接证实。首文档的 17.8 MB 是作者样本，本轮未重跑。另用本机 SQLite 的同构最小表确认当前 `MAX(revision)` 可用 root 索引逆向 seek 后结束，未把 revision 查询单独列为缺陷。无产品实现验收。

### Issues

#### R1-W1 · 固定头部与历史区间的连续性

[设计](design.md) 只说替换头部、去重和保留原游标。按现有独占 `before_turn` 语义，旧首屏为 100…81，后续页为 80…61。刷出 120…101 后，如果首屏整体被替换而旧后页及游标保持，100…81 就失去正常入口。如果保留已看过的整段记录，一次新增超过一屏时仍可能有未读取区间。现有 Web `WorkTurnList` 只给 focus anchor 产生断档提示，普通页之间默认相邻。PA 恢复又可能更换主 Session，旧游标仅能在原 Session 下使用。请定义分页及缓存的 Session 归属、新头与旧区间相接或补洞的规则，以及历史主轮次如何保留在关联执行下。验证在两次刷新之间新增超过一页、已存在回复焦点、跨 Session 更换三个情况。证据见 `work-records.ts:75–86,437–460`，`agent-work-panel.tsx:31–59,133–169,204–210` 和 current spec 的 View Work 场景。

#### R1-W2 · 双端刷新范围与活动详情更新未收口

[设计](design.md) 只限制 Web 自动刷新。iOS 实际每三秒刷新，逐页重读 `pageCount`；选中关联执行时另外请求一次 root。若 iOS 改用 `view=summary`，既有轮次详情依赖内嵌首批 items，当前逻辑既不会在展开时触发首个延迟请求，也会失去用于折叠行预览的 items。Web 的更新、恢复、可见性、权限处理和 query 自动重取也都需要服从新分区。详情不能只按 item 序号追加，工具完成、文本增量和授权决定可在原 `seq` 上更新 `revision`，包括已展开轮次中更后面的 item。请明确两端何时保留历史、重取哪份活动轮次／详情，iOS 如何展开延迟详情与提示待授权，以及哪些刷新入口共同遵守该限制。决定性证据应同时显示旧页请求数不增长、旧内容仍可操作、原 item 真实变更仍可见。证据见 `AgentWorkView.swift:49–107,120–170`，`agent-work-panel.tsx:176–193,211–212,267–295,321–322`，`app/providers.tsx:10–20`，`work-records.ts:349–392`。

#### R1-W3 · 返回轮次数有限仍可同步读取大量 item

[设计](design.md) 收口了目录和 usage 的索引方向，但主／关联摘要目前在每轮执行精确 `COUNT`，并为寻找后台返回读取和解析 JSON。一个持续很久、没有后台返回或只在末尾出现后台返回的轮次足以使一次 20 条首屏同步遍历大量记录。主视图还重复调用 `items(root, main, "")`，将最多 100 条控制记录正文放进每次摘要，包括翻页。请定义分页模式下首屏允许的摘要字段与读成本，明确哪些元数据有可 seek 的投影、哪些详情在展开时获取，并保留现有可达性及未知值语义。对重轮次、无 usage、控制记录含大结果的样本测响应字节与读取工作，单测子目录规模不能覆盖这条热路。证据见 `work-records.ts:405–425,437–471,524–565`。当前影响集中在中心的同步 SQLite 读，上传拆分不处理这一路径。

#### R1-W4 · 旧关联有两种入口，单一工具回退规则不够

[设计](design.md) 只为缺少 ID 的旧工具记录定义父 Session＋call／child 的定向回退。Web 与 iOS 还从独立 `background_return` 和消息附带的 `background_returns` 构造入口。其旧记录可只有 agent ID，当前匹配范围也与工具不同。Web 取首个匹配、iOS 枚举多个，且现有谓词将明确 session ID 与较弱回退条件并列。同一个子 agent 的多个运行或父级同时存在时，仅保留各端的列表匹配容易因分页顺序打开错误执行。请按可靠来源分清工具、消息源和后台结果，规定明确 ID 的优先级、旧匹配消歧或多候选呈现方式，以及未同步时如何显示。定位仍在 root 授权下，不为判断入口拉完整目录。证据见 `agent-work-panel.tsx:298–327`，`AgentWorkView.swift:180–185,203–231,248–250`，current spec 的「并行、重复唤起与嵌套」。验收覆盖跨父级同 agent ID、明确 session ID 指向未加载目录项及旧后台结果。

#### R1-W5 · 回退只证明存储可读，混合版本入口仍缺约定

[设计](design.md) 用兼容 schema 解释旧二进制可回退。旧中心会忽略 `catalog=separate`，然后返回旧目录格式，新分页和按 ID 元数据路由并不存在。新版 iOS 已安装后可能继续访问回退中的旧中心。请收口中心和客户端发布顺序、模式确认方式，以及可回退期间新版客户端如何使用旧响应或维持可用入口。在隔离环境验证旧客户端→新中心和新客户端→可回退中心两向。新增索引走正常 schema 安装可接受，建议以旧库副本确认首次索引安装的时间和占用、启动成功及回退可读性。证据见 `work.ts:408–433` 和 `db.ts:5–24`。

#### R1-W6 · M1 退出标准没有覆盖用户给定的容量与入口

[设计](design.md) 已列 1 千／1 万／10 万子执行的 20 条首屏对照，以及浏览器旧页请求数。仍缺少面向实际客户端和中心的 M1 退出表，未说明如何从这些样本判断 50 Global／Gateway、约 1000 用户和一年历史下的改善。请将客户端关键旅程和实现证据分别列入单个 M1。保持现有单 root 尺度对照，再说明怎样用代表性的多 root 活动、旧轮次与相关并发读验证响应字节、实际扫描／请求增长和首屏时间；不需要模拟 1000 个浏览器。加入 W1–W5 的窄验收，并把 [delta](specs/im/agent-work.md) 的主执行分页适用范围写清，使历史长但关联稀少的 Work 也受同一规则。结合现有「工作概览按需读取完整过程」与「非管理者持续查看工作进度」场景保留详情、实时、错误恢复和权限边界。

### Author Resolutions

- R1-W1 accepted。按实际 Session 分区，保留页区段和 next_turn_id 作为连续证据，显式补缺口。
- R1-W2 accepted。Web 和 iOS 同时约束，旧页与活动详情分别处理，原 item revision 可刷新，iOS 明确首批展开。
- R1-W3 accepted。新头部避开 control 正文、COUNT 与后台结果 JSON 扫描，状态与使用量索引读取，控制和其他详情另取。
- R1-W4 accepted。区分显式 ID、旧 tool 匹配和背景返回的旧 agent 候选，多次运行留待明确选择。
- R1-W5 accepted。响应标记协商旧中心，保留旧客户端入口，双向组合验证与旧库索引时间。
- R1-W6 accepted。M1 双轨补 50 Agent/1,000 账号、固定增长维度、重轮次与版本、体验测试。

## Round 2

- Reviewer target `/root/work_reads_design`，延续独立设计 reviewer。
- review_mode `delta`。修订收紧同一 Work 查询与缓存边界，明确回退和 M1 退出标准。需求、系统职责和单 M1 切片沿用 Round 1。复查全部 R1 findings，以及受影响的焦点和详情调用链。
- started_at `2026-11-10T01:01:05+08:00`，completed_at `2026-11-10T01:01:55+08:00`，duration 50 秒。
- 复核 checkout `57b2200da`。相关 IM／客户端基线相对 `3179cd45f` 无变更。冻结设计 SHA-256 前缀 `5360c28e7064`，delta `93150e17b047`，首文档和 milestone 骨架沿用 R1。

**Issues Found · 0 CRITICAL / 3 WARNING**

### Coverage

- retained_from Round 1。需求、中心权限接线、独立目录和选中详情的职责、既有两端入口、无需独立原型的判断仍适用。
- 修订确定按实际 Session 分区，按服务返回的区段边界保持相邻关系。独立 anchor 和目录让历史主 Session 继续可达。模式标记闭合旧中心兼容，M1 已明确两轨与目标负载。工作仍在设计阶段。

### 历史问题闭环

| R1 issue | Author Resolution 与本轮证据 | 状态 |
| --- | --- | --- |
| R1-W1 | [设计](design.md) 第 11 行固定 Session 专属游标、已读区段和按需补缺口。一次增量超过一页、切换主 Session 和历史 anchor 都有分区和继续读取路径。 | closed |
| R1-W2 | 双端有统一头部、iOS 延迟首批和原 item revision 的概念。可选回读范围和待同步焦点仍缺具体规则，见 R2-W1。 | still-open |
| R1-W3 | 头部已移除逐轮 COUNT／JSON 和控制正文，另取详情。需把同一轻摘要扩展到实际焦点及分页入口，见 R2-W2。 | still-open |
| R1-W4 | 显式 session ID 优先、后台结果可保留多个候选。旧工具的强弱匹配和有界候选可达性仍需明确，见 R2-W3。 | still-open |
| R1-W5 | [设计](design.md) 第 7 行以响应标记协商，旧中心保留内嵌目录，新中心保留旧客户端模式。M1 加混合版本验证。 | closed |
| R1-W6 | M1 有双轨退出、50 个 Agent／1,000 账号、目录规模和重轮次验证，delta 的主历史不依赖关联目录规模。 | closed |

### Issues

#### R2-W1 · 固定详情刷新边界与待同步的回复焦点

[设计](design.md) 第 13 行仍允许「按当前已展开范围重读」。单个活跃轮次内连续加载多个 item 页后，这个范围本身可增长，仍允许重复重取历史详情。原序号更新也需要定义无漏的读取切点。请固定有界的增量或等效策略，区分活动详情和展开过的旧历史，并说明有积压时怎样续接；覆盖更新落到已加载后页的同一 item。同时显式保留当前 reply focus 为空时的自动重试。现在 Web 的 Work 更新会使 focus query 重新读取，切到只更新头部后若遗漏这一条，发信事实稍迟到达时仍会停在「尚未同步」。只需在所选消息仍待定位时按现有更新信号重新请求一次相关 focus。证据见 `agent-work-panel.tsx:135–143,176–193,267–295` 和 `docs/specs/im/agent-work.md:274–277`。

#### R2-W2 · 轻摘要必须覆盖实际打开、翻页和关联执行入口

[设计](design.md) 第 11、13 行只承诺新模式头部轻读。真实 View Work 首次打开同时访问 `/focus`，其 `WorkRecords.focus()` 单独调用旧 `turnView(..., true)`。新版按 Session 翻页也会访问现有 `/sessions/:id/turns`，该路径会做逐轮 item 扫描并附控制正文。明确这两个调用如何在协商后的模式中共用同一轻摘要投影，旧模式仍保留现有契约。这样重轮次的回复直达和点击旧执行才不会从旁路回到同一同步扫描。证据见 `agent-work-panel.tsx:133–139,165`、`work.ts:408–432`、`work-records.ts:437–471,492–497`。

#### R2-W3 · 旧工具的确切关联应先于较弱的 agent ID

[设计](design.md) 第 17 行的「父 execution + tool call ID 或 child agent ID」仍允许把两类证据并列。旧卡已有确切父级 call 匹配、同一 child agent 还有其他唤起时，这会把本可直达的入口变成多个候选，或误选另一运行。请规定明确 session ID、父级下确切 call、弱 agent ID 的优先顺序。弱匹配存在多候选且超过页限时，应给用户继续选取的入口或明确提示还未覆盖所有候选，不按首批结果推断身份。证据见 `agent-work-panel.tsx:316–320`、`AgentWorkView.swift:180–185` 和 `docs/specs/im/agent-work.md:144–147`。

### Author Resolutions

- R1-W2 residual accepted。活动详情明确只按 revision 增量读，待同步 focus 精确重试。
- R1-W3 residual accepted。轻摘要明确覆盖 root、选中 child、older 与 focus。
- R1-W4 residual accepted。精确父级 call 先于弱候选，歧义可继续分页。

## Round 3

- Reviewer target `/root/work_reads_design`，延续独立设计 reviewer。
- review_mode `closure`。修订仅关闭 Round 2 的三处局部歧义，工作目标、模式协商、外部依赖、delta 和单 M1 未变。
- started_at `2026-11-10T01:03:17+08:00`，completed_at `2026-11-10T01:03:26+08:00`，duration 9 秒。
- 复核 checkout `57b2200da`。IM／客户端相关基线相对 `3179cd45f` 无变更。冻结设计 SHA-256 前缀 `4494f5aabfa2`，delta `93150e17b047`。retained_from Round 2，三个修订不影响已通过的入口、权限、回退和容量安排。

**Approved · 0 CRITICAL / 0 WARNING**

### 历史问题闭环

| 问题 | Author Resolution 与本轮证据 | 状态 |
| --- | --- | --- |
| R2-W1（R1-W2） | [设计](design.md) 第 13 行取消回读已展开范围，以活动轮次首次详情的 revision 为切点，每次自动更新只读一页，按稳定 item ID 更新原序号上的内容，积压沿游标续读。该办法与 `work-records.ts:379–392` 实际保留 item seq 并更新 revision 的写入兼容。当前消息的空 focus 独立按真实身份重试，保留待同步恢复的 canonical 行为。 | closed |
| R2-W2（R1-W3） | [设计](design.md) 第 13 行明确将轻摘要用于已协商的主 head/older、选中 Session turns 和旧消息 focus，覆盖 `work.ts:408–432` 和 `WorkRecords.focus()` 的所有相关入口。正文与控制详情继续按需读取，旧模式不变。 | closed |
| R2-W3（R1-W4） | [设计](design.md) 第 17 行明确真实 session ID 优先，其次在已授权父执行查 exact call，查不到才用弱 agent ID。模糊候选按界限续页、由用户选择，避免旧目录排序决定真实执行。 | closed |

本轮结论限于 Gate 2 设计。候选实现、真实双端操作和容量仍按 M1 验证。

# feat-764 · 独立设计审查

## Round 1

- reviewer target: `/root/work_design_review`，独立于设计作者。受审基线 `84c9eacf89da7f0331a9aadb1eeee0819363b9ab`。
- review_mode: `full`
- mode_reason: Full unit 首轮，覆盖 Web 交互、中心读侧、Gateway/DSH 维护指标、性能和验收前置。
- started_at: 2026-11-12T16:24:00+08:00
- completed_at: 2026-11-12T16:30:00+08:00
- duration: 6 分钟
- verdict: **Issues Found**，0 CRITICAL / 6 WARNING。

### Coverage

- **用户约束和体验。** 对照 [需求](spec.md)、[设计](design.md) 和两份本机交互原型。在 Chromium 操作派工关系、二级节点和返回，在 390px 宽度打开私聊头像卡、关闭并从群聊消息头像打开。关系页将主 Agent 自身用量、子节点用量、层级和未报告状态就近呈现。子节点进入同一个工作阅读区，返回动作明确回到图。头像卡在聊天原位显示主状态、子执行计数和 Work 操作，配置另有图标入口。快照与示例足以表达这些交互决定。同步、权限、真实时间线分页及浏览器负载仍须在实施后验证。已关闭本轮浏览器及本地服务并清理临时快照。原型含私有 Work 记录，本轮不将截图或快照写入仓库。
- **真实组装与权限。** [聊天消息组件](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx#L1254) 已提供实际 Agent ID 和发信 ID。[Agent 详情页](../../../src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx#L1744) 与 [Agent 资料页](../../../src/IM/frontend/src/features/settings/agents/agent-profile-page.tsx#L159) 共用 Work 面板。由 [IM server](../../../apps/im-server/src/server.ts#L195) 注册的 [Work 路由](../../../apps/im-server/src/work.ts#L401) 校验 Global/PA、用户空间、个人绑定、删除及选择执行的归属，适合复用为两个聚合的权限边界。配置入口需以 [配置路由](../../../apps/im-server/src/control-routes.ts#L285) 的人类用户和 owner 资格为准。来源聊天和附件仍使用各自的读取权。公司成员可读 Work 不代表可读来源或改配置，私有绑定必须拒绝其他人。派工与头像聚合属于中心已同步数据，Web 消费授权后的产品投影。Dreaming 原生事实与运行资源仍由 DSH integration 持有，PA 经 RuntimePort 转交产品事实。这符合 [运行时与包职责](../../../SPEC.md)。未引入模型可见上下文变化或一次性生产迁移。
- **工具、原生轨迹和兼容。** [Work 投影](../../../apps/im-server/src/work-records.ts#L373) 已经按真实 call ID 将工具开始/结束、实际发信、委派回执归并到同一工具项，可复用事实去重与来源链接。无确认回执时，工具完成不推导投递或子执行完成。现有 [轨迹观察者](../../../apps/im-server/src/trajectory.ts#L64) 从已授权执行沿真实父链检查并绑定设备，继续承担原生读取。Web 新聚合、项目预览及 timeline 不需要改变原生轨迹内部、旧详情格式或 iOS 布局。
- **性能与保真。** [perf-749](../archive/perf-749-direct-work-focus/design.md) 的 `message_sent` 部分索引与单轮 focus 独立于历史页。[perf-753](../archive/perf-753-bounded-work-reads/design.md) 的轻摘要、独立目录、按真实 session 分区和 `after_revision` 更新是现有实现的可复用边界。新图和头像只访问中心投影，原则上保留 [perf-751](../archive/perf-751-incremental-global-descendants/design.md) 的 Gateway 子执行增量发现。现有容量基准可提供历史对照，新方案的自动正文与聚合仍需测量。具体缺口见下方。
- **delta 和 milestone。** [Agent Work delta](specs/im/agent-work.md) 与 [Web Chat UX delta](specs/im/web-chat-ux.md) 锚定正确 canonical 目标。对 Dreaming、长历史、旧回复的 MODIFIED 保留未改变的 scenario，明确 Web 时间线与保留现有客户端读取；派工、统一工具详情和头像交互均从消费者视角表达。单 milestone 能覆盖相互依赖的 schema、API 与 Web 变化。设计选择的真实 Web 旅程、性能、前端体验和最终 diff 审查与风险相称，实施前置仍有 R1-W6。

### Issues

#### R1-W1 · 自动加载的 20 项仍会读入大正文

设计第 2 项及接口段把现有 items 页用于进入视区后的自动首批过程，同时承诺大结果显式按需。基线 [`WorkRecords.items`](../../../apps/im-server/src/work-records.ts#L450) 以条数限制 `SELECT *`，同步解析每条完整 `payload`，`after_revision` 同样返回完整内容。已镜像的大参数或结果落在第一项就能造成同步 DB、JSON、网络及浏览器开销。两个并发只限制请求数。[perf-754](../perf-754-bounded-work-transfer/design.md) 仍在独立设计，也无法替代旧版已落库正文的有界读取。请落实自动路径的字节与字段边界和按需正文入口，明确覆盖已有普通行及活跃增量。新客户端保持原有完整正文可达和权限，旧读取形态仍可用。将大正文放在自动首批和原 seq 的实时更新中验收，观察字节、中心事件循环及页面可交互性。

#### R1-W2 · 头像状态缺少无需新 Work 事件的同步与离线刷新来源

设计第 4 项只列出基于 `agent.work.updated` 的可见浮窗刷新。[Work.append](../../../apps/im-server/src/work.ts#L78) 在应用新事实时广播，该请求的 [同步声明](../../../apps/im-server/src/work-sync.ts#L174) 在 handler 成功后交给 [`reportProgress`](../../../apps/im-server/src/work.ts#L43)，后者只写内存，并可由无新事实的进度请求推进。`agent.status_changed` 的 [节点状态广播](../../../apps/im-server/src/gateway.ts#L165) 当前只发 owner。公司成员可打开浮窗，但可能一直显示「同步中」，或节点实际离线后仍显示旧的在线及实时计数。请给出对所有当前有 Work 权限的用户都成立的刷新触发，或复用现有 Work 可见期间轮询、连接恢复及回前台的有界机制。同步状态不能仅用事实 revision 去重。补充无新事件完成同步、非 owner 离线/重连与关闭浮窗停止读的验收。

#### R1-W3 · 主轮与维护的独立分页缺少有序连续区间

设计接口段对主轮和维护分别取页后按时间合并。[主轮查询](../../../apps/im-server/src/work-records.ts#L487) 以持久 seq 翻页并返回 `next_turn_id`，旧回复 focus 仍按原轮次身份和邻居标记缺口。两流第一页末尾处在不同时间时，直接合并会展示另一流更旧的记录，直到翻页才发现中间漏了一段。例如维护活动密集时，维护次页仍可能比界面已显示的主轮新。请确定公共顺序和两流分页边界，或让中心返回合并后的稳定游标，并明确更新只改头部及旧回复锚点如何继续使用独立邻接证明。覆盖两种密度反转、同时间戳、旧回复和补页时滚动锚点。delta 中「逐页浏览历史关联执行」也应明确何时自动续页或由用户点击，当前表述与首文档未明确同一触发。

#### R1-W4 · 普通派工与后台维护不能按当前 session scope 区分

设计第 3、4 项要求普通活跃子 Agent 排除 Dreaming，但 [`KnowledgeUpdates`](../../../packages/personal-assistant/src/knowledge.ts#L51) 的历史维护链接与普通链接共用 `session_linked`，[中心注册](../../../apps/im-server/src/work-records.ts#L214) 在没有 workflow_run_id 时统一存为 `subagent`。历史 Dreaming 的正向证据是启动轮次的 `origin: 'dreaming'`，不是 scope 或标题。链接与轮次也可能分批抵达。请明确普通派工、Workflow/fork 和维护的可信分类数据、历史已知 Dreaming 的识别及仅有链接时的状态。否则维护可能混入普通活跃数或图节点，缺失事实也可能被当成普通子执行零值。以真实普通子执行、维护同时运行及同步只到链接的场景验证。

#### R1-W5 · 历史 Dreaming 指标没有可执行的授权请求链

设计第 6 项拟在点击历史维护时向 DSH 有界读指标并缓存，但当前 [`knowledge.facts`](../../../packages/dsh-integration/src/index.ts#L578) 只列已知 facts/reviews，[Dreaming reviews](../../../packages/dsh-integration/src/knowledge/dreaming.ts#L412) 没有选定会话的指标方法，[原生观察者](../../../apps/im-server/src/trajectory.ts#L102) 也只转发既有白名单方法。请确定实现能复用的授权请求路径，明确点开哪个界面会触发、中心如何校验 root/session/run 与当前绑定、PA 如何路由到对应 RuntimePort，以及超限、离线和结果回填的行为。另一种可收口的范围是新维护记录投影指标，历史缺指标时明确未报告。无论选择哪种路径，统计事实须能区分完整记录中的零与未知，且结束统计不扩大每次知识通知或启动的工作量。实施证据需要验证真实维护失败、指标缺失、原回执不改写，并核对 perf-751 的子目录读取不因这条链重回全树扫描。

#### R1-W6 · 实施前置尚未落实到可执行的真实旅程

设计第 42–54 行列出真实 Web、IM、Gateway 与对照场景，但没有 reviewer runbook 或对必验资源的对应说明。[体验审查实施验收前置](../../../.agents/skills/frontend-experience-review/references/prototype-and-runbook.md#实施验收前置) 要求明确现有隔离启动模板、身份与数据来源。这里有真实只读公司成员、无权用户和 owner 三个结果，另需旧回复映射、真实二级委派、可打开的 Dreaming 以及只推进同步声明的恢复。请链接固定模板并列出该模板之外的必要角色/数据、如何得到和按何入口验证。容量样本补一组窗口内密集活动或较多活跃子执行，区分索引候选扫描、图聚合与响应条数；同一已确认头部增量和历史旧页请求数仍单独比较。无需重跑全产品或提前启动生产。

### Recommendations

无。


### Author Resolutions

| ID | Resolution | 对应修改 |
| --- | --- | --- |
| R1-W1 | accepted | 自动路径改为 4 KiB/item 有界预览，旧大项走元数据占位，精确正文只在主动查看时取；增量用同预览规则。隔离基线重测包含 2 MiB 首项，证实只限制条数不够。 |
| R1-W2 | accepted | 可见浮窗补 Work 现有周期、恢复、回前台触发；无 revision 变化的进度与连接同样处理，关闭取消。 |
| R1-W3 | accepted | 中心按共同 seq cursor 二路合并严格前缀，旧回复锚点独立并保留缺口；Web 历史继续由边界操作触发。 |
| R1-W4 | accepted | 明确新 kind、旧 Dreaming origin、已注册普通 descendant 和 Workflow，未确认 link 不混入。 |
| R1-W5 | accepted | 仅新结束路径持久化自己的事实。旧 Work 缺指标显示未报告，仍有现成原生轨迹入口；取消新增历史 relay 和后台回扫。 |
| R1-W6 | accepted | 增加 daily runbook、身份/事实来源、密集窗口和活跃压力；锁定复测夹具与指标。 |

R1 后用户新增消息操作入口调整和性能关注；相应 spec/delta、界面决策和验收范围一并提交复审。

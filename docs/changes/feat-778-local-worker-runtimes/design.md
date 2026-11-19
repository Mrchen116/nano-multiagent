# feat-778 本机 Global 一级派工

## Changelog

## 现状与可复用机制

NodeConfiguration 持有机器 YAML。apps/node 通过 dsh-integration/client 启动 DSH。ConfigurationScopes 在真实 Agent scope 挂载 GlobalMode，后者区分内部 send_message 与 IM 发送。原生 DSH 的 startContinuable、sendMessage、interrupt 已支持普通子会话的建立、追加和打断。它的 continuable provider 只返回创建原生会话所需的数据，不能用来持有 Codex thread 或 Claude session。Workflow 和 Dreaming 还独立使用原生 provider。保留这些专用入口。

GlobalAgent.projectRootPage 把根会话的持久事件与 Work checkpoint 在同一批提交。DescendantReader 与 projectChild 另行同步原生子会话正文。Web 派工图从 Work 会话关系和活动时间分页，支持历史 DSH 轨迹。feat-676 引入工作子会话提炼，feat-759 改进 Dreaming；对应的 MemorySources 和 DocumentMemory 是本次调整入口。

## 派工和职责

1. 本机 Gateway YAML 的 gateway.worker_runtime 接受 dsh、codex、claude，缺省 dsh，配置在节点读取配置时生效。个人助理和普通 Global root 使用同一机器选择。保留 PA 专用的原始授权和对外披露审核，外部 worker 只收父级提供的工作材料，不能代替 PA 对外发送。新建委派消费当前配置，后续按已存的 worker id、runtime、原生会话和所属 root 定位。克隆/合并其他 Agent 配置时无需同步机器选择。CLI 未安装、登录失效或启动失败的具体错误交回原 Global。
2. 在 dsh-integration 注册 Nano 自己的一级派工工具。Global 可派完整事项、给指定 worker 补充或停止；工具从受信任的当前 root 取 workspace 和机器配置。保留 IM send_message 的 public target 分支。Global 的普通派工走一个明确入口；运行时内部 helper、Workflow、维护和历史 DSH 会话仍使用相应的原生接口。能力选择保持现有宿主限制。DSH 路径调用公开的 startContinuable 等接口。
3. 外部驱动同样放在 dsh-integration 内，直接以无 shell 的 stdio 启动 CLI，由各框架执行模型和工具循环。Codex 使用 app-server 的 thread/start 或 resume、turn/start 或 steer、turn/interrupt；Claude 使用带 stream-json 输入输出的 print 模式、session id 或 resume、user message 和 interrupt。每个适配只消费已接受、需决定、最终结果、失败和停止。两者均省略模型和 provider 设置，使用本机 CLI 身份和 cwd。区分本机 CLI 的环境与 Nano 为 Router 注入的模型凭据。
4. Codex 使用 workspace-write、on-request 和 auto_review；Claude 使用 permission-mode auto。出现待裁决的请求时只把请求给出的操作、目标、原因报回父级，权限未决时不放行动作。明确拒绝维持拒绝。需要人决定时 Router 按原 IM 授权路径沟通，取得的新信息由原 worker 消费。对仍有效的 server/control request，驱动以原请求 ID 立即回送拒绝或取消，把待澄清事项交父级，结束该协议等待。后来的授权只形成同一会话的新输入，由框架重新审核；停止后的迟答不能放行旧请求。已终局拒绝的动作不重试。
5. 外部 worker 有简短角色提示和只向当前父级汇报的 send_message；通过启动时绑定的本机 MCP 适配到同一个内部消息处理方法，无 IM 凭据或收件人选择。中间问题可在原 turn 报给父级；最终回答由宿主按原生 turn 完结事件回传一次。父级用现有原生消息注入/唤醒通道继续工作。外部 MCP 报告与 CLI 回合终态共用宿主 report(workerId, eventId, text)；从持久绑定查真实 root，生成标明 worker ID、标题及消息性质的内部来源消息，以原生 Agent 的 steer / 空闲输入唤醒 root。复用宿主 submit 的持久消息 ID 去重办法，用 worker id 加原生回合或调用 ID 作稳定键，投递前检查已受理的相同消息。该入口不调用需要原生子 Agent 的 sendMessage，不构造来自用户或 Inbox 的授权。工具被受理与实际完成/公开交付有不同语义。
6. 每个真实委派记录稳定 id、父 root、框架、CLI session 标识、标题与最近状态，复用 DSH 的持久存储。原生 DSH 预留 childId。新请求按 root 与原调用标识去重；继续和停止校验真实归属。进程在宿主停止、Agent 停用或被删除时回收。恢复时保留 CLI 原生 id；宿主丢失进行中进程则标记中断，明确续做从原会话恢复，不能静默另起会话。CLI 明确回应中止或进程已退出才确认停止；失败回传真实状态。旧会话的生命周期不需要一次性转换。

## Work 与模型上下文

- 每次状态改变与待投递的关系事件同存于该 worker 的持久记录。Work 根分页带回该 root 的待投递事件，PA 按事件 ID 幂等写入 checkpoint 和 outbox 后确认。DSH 固定版本的公共 Session writer 无法为自定义原生事件标记 ignorable，直接把关系写入原生日志会阻止重启恢复。新增关系使用独立的 Work scope，进入现有派工图的活动筛选、时间窗及分页。原生 DSH 新委派从全量子轨迹同步和轨迹子范围导航中排除，内部 helper 同属该子树。新关系可查看标题、框架和状态，省去打开子轨迹入口。旧 DSH 关系、Global 和维护视图保留自己的行为。
- Router 实际看到的输入为用户原话、任务约束和一级 worker 的回复。worker 首轮只加角色说明与具体委派；续做使用同一个 CLI thread/session。以“把第一个文件改成只读检查”为例，追加给原 worker 的是这句更正与必要背景，CLI 自己恢复先前的文件上下文。
- 普通工作 worker 从 Nano 记忆 prompt、能力/skill 注入和维护工具中退出，保留框架自己的仓库指令和普通文件权限。Dreaming 只使用主会话允许的来源，主会话真实收到的汇报仍是主会话材料。检查旧待处理批次和历史 summary 引用，避免通过恢复或 source_history 重新读取工作 worker 轨迹；已写好的长期记忆无需重写。维护自身所需能力保持可用。

## 契约增量

- SPEC.md 及 gateway/service-lifecycle 说明 Global 根和 Node 受管运行时仍由 DSH 提供，一级委派可使用节点配置的本机 CLI。AGENTS 的包边界和依赖契约同步体现这项限定。
- gateway/global-agent、gateway/agent-capabilities 描述首文档中的委派、原事项续做、停止、来源和记忆契约。im/agent-work 中按派工入口区分关系与可读轨迹。与本机部署相关的配置名、默认值和重启生效方式进入 Gateway 运行文档。

## 验证、风险与回退

单个 M1 覆盖同一项跨层行为。用真实 DSH root 对三种配置验证派工，使用真实 CLI 和独立临时目录验证本机登录、默认模型、补充、回传与停止；用可控 stdio 对端稳定覆盖权限请求、并发工作、续接、失败和明确拒绝。比较真实模型可见 prompt、工具列表与 Dreaming 输入。使用同一用户入口发两个事项和一次更正，从 Work 查真实一级关系并验证根轨迹和历史子轨迹入口。未取得第三方模型成功回包的场景单列，协议测试不能代替该项。

运行隔离服务前执行 python3 scripts/dev_host.py check，使用 ./scripts/e2e-up.sh --profile daily --wt "$PWD" 和 ./scripts/e2e-down.sh --wt "$PWD" 启停；确认生成的 .e2e-daily.json 对应本 worktree。实际 CLI 版本用 codex --version 和 claude --version 核对，验证要发最小只读请求，登录状态查询不能证明账号能收到模型答复。配置回 dsh 后新委派使用 DSH，已有会话继续绑定创建时的框架。无一次性部署迁移。

| ID | 依赖 | 并行组 | 文件范围 | 退出标准 |
|---|---|---|---|---|
| M1-local-workers | 无 | 单组 | apps/node、dsh-integration、product-contracts、personal-assistant、IM Work 与相关 specs | [reviewer] 从原 IM 交办、更正、停止和交付，Web 可辨认两个事项并回看 Global。[worker] 机器配置、原生会话、权限和生命周期有窄测试，Work 和记忆边界有实测证据，三种框架分别标记实测结果。 |

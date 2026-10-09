# refactor-581：Agent 能力覆盖与源码可扩展性核查

> 2026-10-09，源码核查稿。先回答“DSH 已经覆盖什么、差异是什么、公开接口能补到哪里”。[终态架构](target-architecture.md)已同步全量审计与Q22—Q24修订，已随正式设计通过独立Round 3复审；本页保留原生覆盖及扩展成本的源码依据。
>
> 本轮再次 `git fetch origin`：Nano `origin/main` 仍为 `4915c44cb7f7b829414a19087877ad9b73d69ea1`，DSH `origin/master` 仍为 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`（`0.2.1-alpha.1`）。以下是固定版本的源码／契约核查，未运行 Nano↔DSH 接入 PoC，不代表已验证产品等价。

## 1. 先给结论

**能力地图按真实行为核查原生覆盖与扩展边界。** “支持插件”“支持Workflow”“有schedule”仅是入口；以下核查进一步覆盖作用域、后台运行、恢复、权限、配置和交付，最终方案以design及其详述为准。

本轮发现：

- 通用工具、工具编程调用、MCP、Skill 发现／加载、脚本化 Workflow、持续子 Agent、在线后台 jobs、压缩和会话日志，DSH 有可以复用的实现。
- workspace／全局自建能力的**底层注册和隔离原语存在**，但 Nano 的目录发现、优先级和产品配置语义不直接等价。旧 Python Tool／Hook 对象也不能原样装进 DSH。
- Nano 的记忆维护、Skill 使用统计／生命周期与后台自进化没有找到等价第一方实现；DSH 文件工具、MCP 记忆示例和执行原语不能直接算作这套功能已经存在。
- Workflow 的后台运行已经存在；保存／命名、暂停、逻辑 child restart、完成前缀复用与共享预算则有明确差异。
- Cron已确认采用原生schedule回到创建它的主对话，不建独立会话；Heartbeat缺失的忙时/静默/任务选择策略迁移。不能把两者整体判为必须保留旧引擎。
- 权限不是“原生没有 Auto”：DSH 有默认关闭的实验性 Auto，但其真人来源识别、Inbox 摄取和子 Agent 审批与 Nano 存在实质差异。

**按Q23确定5个Feature插件单元，其他共享接入/策略按职责组合。** 先前的“3＋1”候选划分撤回为未收口设想；本稿先完成能力和扩展面核查。用户补充：相近体验的小幅差异可以接受，但须确认，避免为差异重新造轮子。缺失机制按已确认迁移原则补齐；产品体验选择已收口，当前决定见motivation与design，不以原生缺失为理由删功能。第 7 节给出源码能够确定的可行性，第 8—9 节区分真正的接口缺口、产品取舍和后续实施验收。

## 2. 怎样判定“满足”

盘点范围来自 Nano PA 工厂、默认工具、feature registry，以及 kernel／Gateway current specs；不是仅扫描工具名字，也不包含停用的自研 CLI 专属体验。本轮只对本机默认配置做脱敏定向核实，未读取Mini运行态，因此“源码默认可用”“配置中存在”“某个线上Agent已启用”仍分开。[N01]、[N02]

本表使用以下结论：

| 标记 | 含义 | 核查后的处理 |
|---|---|---|
| 原生 | DSH 有对应执行机制，允许采用其工具名／参数 | 复用并验证关键旅程，不重写同类引擎 |
| 装配 | 原生机制存在，但须选择包、配置、provider 或 scope | 写 Nano profile／preset，不能把包存在等同于默认已开启 |
| 接入 | 原生执行可用，缺产品绑定、来源、事件或 UI 映射 | 确认产品接入责任，暂不定插件归并 |
| 扩展 | 原生缺失或部分覆盖，需要补迁已有用户能力 | 缺失部分迁移；相近机制比较后只补决定保留的差异 |
| 产品 | 事实和规则应由 IM／节点服务持有 | DSH 只提供调用入口，避免双写业务状态 |
| 待决 | 原生体验可以替代，但会改变当前已存在行为 | 写清差异，由用户选择；不默认为已允许删减 |

“原生”仍以静态源码为证据上限。它不保证与 Nano 每个错误文本、工具参数和历史格式完全相同。涉及来源、持久恢复和权限的差异不能仅靠 prompt 近似。

## 3. 能力地图

### 3.1 工具、扩展与配置作用域

| ID | Nano 当前能力 | DSH 覆盖及差异 | 覆盖结论与差异处理 |
|---|---|---|---|
| T01 | read／write／edit／bash，输出限制、错误和取消 | 有文件、搜索、shell、终端、超时与结果处理包；具体 schema、截断和展示不同 | **原生 + 装配**；不制作 Nano 同名工具全集 [N03]、[D01] |
| T02 | web_search／web_fetch，可选搜索 provider | 有 `tool-web` 和 provider；查询是 queries 数组等原生接口，配置/provider 不可用会真实失败 | **原生 + 装配**；第一方 search providers 为 DeepSeek／Exa／Perplexity；旧 DDG／Brave／SearXNG 不在同一集合，保留可用公开 provider 接口适配，详见 §7.8 [N01]、[D02] |
| T03 | workspace 下创建 Python tools，被该 workspace 发现；同名覆盖共享／内置 | `tools.register`、scoped shadow、Agent setup／preset 可实现局部工具；未发现与 Nano `.nanoassistant/tools/*.py` 等价的自动加载器 | **扩展或接受原生创作方式**；详见第 4 节 [N03]、[N04]、[D01]、[D03] |
| T04 | 全局 `~/.nanoassistant/tools` 共享给本节点各 Agent，workspace 可覆盖 | 原生 Host／preset 工具可共享；`plugin_manager` 作用于整个 profile，不以 Nano workspace 目录为界 | **已确认标准格式＋两层装配**；共享注册与workspace覆盖按§4.3实现 [N01]、[D03]、[D04] |
| T05 | 全局／workspace 自定义 Python hooks，拦截与观察 | Cordis 与 tools／agent events 有公开扩展点；旧 setup(hooks)、事件名、priority、timeout/fail-open 不兼容 | **原生事件 + 扩展加载**；迁移实际 Hook，避免实现通用 Python Hook 兼容虚拟机 [N03]、[N04]、[D01] |
| T06 | 工具白名单是执行限制，显式空代表无工具 | `tools.restrict` 可筛继承的全局工具，但 scoped registrations 不受该 mask 隐藏；另有不可被后续监听器放行的 `tools.guard` | **接入**；过滤本层注册与继承工具；scoped/MCP/PTC调用复用原生有效视图，不另加名单guard，不能只调用 restrict 就宣称已覆盖 [N03]、[D01] |
| T07 | 不同 Agent 的 workspace／模型／工具／Skills／配置隔离，下一轮整体生效 | per-agent setup、模型选择和 preset scope 已有；preset 变更后旧 Agent 保留原 revision，子 Agent 继承 preset 不等于复制 parent 临时 scope | **装配 + 接入**；统一装配 root／child 身份与权限，明确安全切换边界 [N05]、[D05]、[D06] |
| T08 | Agent 可以自建／安装新的工具能力 | 原生 Creator 流程可写 bundle、安装插件／MCP；安装影响整个 profile，可能需要重启加载替换后的包 | **优先复用**创作和包管理；面向当前数字人的局部启用由产品 scope 接入 [D03]、[D04] |
| T09 | 第三方工具生态复用目标 | MCP stdio／HTTP、工具发现／更新、取消／重连、命名空间与部分媒体已有 | **原生 + 装配**；不重新实现 MCP client；Python 脚本可经 bash 或独立 MCP 暴露 [D07] |

### 3.2 Skills、记忆与自进化

| ID | Nano 当前能力 | DSH 覆盖及差异 | 覆盖结论与差异处理 |
|---|---|---|---|
| K01 | workspace／共享多个 Skill roots，有序同名覆盖 | filesystem provider 支持项目、用户、自定义 roots；可关闭默认 roots；registry 分层按 scope 合并 | **原生 + 装配**；Nano 使用明确绝对 roots，防止 `.git` 推导误扫别的 workspace [N06]、[D08] |
| K02 | 按名加载、显式 `/skill:name` 调用、资源按需读取 | 原生 `skill` 工具和用户 `/name`，加载正文／资源 base；命令名与显式调用注入方式不同 | **原生 + 接入**；可采用原生命名，兼容命令只是小输入适配 [N06]、[D08] |
| K03 | default discovery 与 explicit allowlist，含显式空；preview 与运行集合一致 | 原生 invocation policy 区分 model/user 可见性，但不是 Nano per-Agent allowlist；普通 registry 合并不会自动过滤所有来源 | **接入/扩展**；需统一过滤 discovery、loader、显式命令与 preview，限制见 §7.2 [N05]、[N06]、[D08] |
| K04 | Agent 可创建／编辑／patch Skill、写资源；agent／PA 两种写入 scope | 原生文件工具能写 SKILL.md，watcher 能发现变化；没有等价 `skill_manage` 的受控 scope、来源事件和配置调和 | 文件创作复用原生；**管理和自动启用策略已确认迁移保留** [N06]、[D08] |
| K05 | Skill 使用去重统计、stale／archived、自动来源与阈值 review | 原生 Skill registry/loader 未提供这套 lifecycle／计数／F3-F4 策略 | **已确认迁移扩展**；保留使用统计与生命周期，不把“读过工具结果”当已有使用管理 [N06]、[N07]、[D08] |
| K06 | 会话冻结技能目录；压缩后重新注入已使用 Skill；自动新增技能避免重建旧前缀 | DSH catalog 变化追加完整替换，正文是普通 tool history；不保证 Nano 的目录冻结和压缩存活策略 | **知识维护接入**；保留技能更新可见与压缩后仍可使用的行为，目录冻结/append-only等内部实现由接入设计处理，不重复向用户询问是否保留知识能力 [N06]、[D08] |
| K07 | MEMORY.md／USER.md，受控 add/replace/remove、大小限制、来源、锁／原子更新和后续注入 | 没有找到等价第一方 memory store/curator；文件工具、指令文件、第三方 memory MCP 是不同机制 | **已确认迁移扩展**；保留受控管理与注入，不以普通文件／MCP替代，也不双份写入 [N08]、[D09]、[D10] |
| K08 | 达到阈值后后台 review，自动维护 Memory／生成 Skill；只确认真实成功写入 | 有 fork/spawn/jobs/events 作为执行原语，没有等价触发和维护策略；Ralph 是显式目标循环 | **已确认迁移扩展**，保留自动触发和维护策略，复用 DSH child 执行，不重写调度内核 [N07]、[N09]、[D11] |
| K09 | Skill 创建后按 mode 调和可见配置，前台结束后也处理事件 | DSH 文件 watcher 只解决目录变化，不解决 Nano IM 配置操作、allowlist 和创建归属 | **知识维护产生事实 + 产品服务调和**；经接入回调，幂等处理 [N05]、[D08] |
| K10 | workspace AGENTS.md、嵌套指令和稳定产品 prompt | 原生 agent-instructions 支持全局/项目/嵌套文件、变更和 budget；persona/systemPrompt 可分层 | **原生 + 装配**；USER/MEMORY 的业务角色不能简单冒充用户授权 [N10]、[D09] |

### 3.3 子 Agent、后台、Workflow 与主动运行

| ID | Nano 当前能力 | DSH 覆盖及差异 | 覆盖结论与差异处理 |
|---|---|---|---|
| O01 | 普通子 Agent、角色/工具子集、前台执行 | 有 spawn/fork 和 in-process／SDK／ACP 等 provider，支持 role/toolFilter 等配置 | **原生 + 装配**；采用合适 preset/provider，不做新子 Agent 引擎 [N03]、[D06] |
| O02 | 后台子 Agent，继续向同一个 child 发新任务、停止／恢复、回父会话 | continuable 模式有 descriptor、cold resume、消息与控制；one-shot 不能替代持续委派 | **原生 + 接入**；选择 continuable 并验证 parent 生命周期 [N11]、[D06] |
| O03 | 后台任务完成后主 Agent 继续，记录归因 | jobs/subagent 有在线完成通知和唤醒；parent 必须仍可定位为 live，jobs-local 是内存 Map | **原生在线能力 + 接入**；跨 runtime 只按仍存在的持久结果证据补对账，不承诺重建丢失结果或持久父 mailbox [N11]、[D06]、[D12] |
| O04 | Python Workflow，并行／pipeline／结构化输出／阶段日志 | 原生 JS Workflow 有 agent/parallel/pipeline/phase/log、结构化结果；pipeline 按 item 连续流过各阶段 | **JavaScript已确认**；不额外维护受限Python Workflow执行器，四项控制仍保留 [N12]、[D13] |
| O05 | Workflow async launch，父轮结束后继续，最终结果返回 | tool-workflow 的 `run_in_background` 使用 jobs.start；核心 README 的 foreground 限制不等于工具层无后台 | **原生 + 接入**；完成与 UI 映射需要产品接入 [D13]、[D12] |
| O06 | Workflow 按名称／路径保存发现、project/personal/builtin、一层嵌套 | 原生接受 script/meta/args；没有等价 saved/nested 管理 | **已确认按原行为保留**，补命名catalog与共享父限额/停止/预算的一层嵌套 [N12]、[D13] |
| O07 | Workflow pause/resume、某个 logical child restart、最长已完成前缀复用 | 原生 handle 为 result/cancel/dispose，没有脚本状态／中间值 checkpoint 或 Nano 前缀复用 | **已确认保留，需专项扩展**；不是改事件格式能完成 [N12]、[D13] |
| O08 | Workflow 总 token target、统计、规模 guideline、子调用 effort/type/worktree 等控制 | 原生有并发／child 数／item 数限制，但不是同一共享 token budget，child 参数也不同 | **共享 output-token预算已确认保留**；其他参数按实际用途映射，不把 limit 名称相似当等价 [N12]、[D13] |
| O09 | Workflow child在父前台结束后向原Web/飞书消息弹审批卡 | 默认child为never；公开创建生命周期可设置初始policy | **缺失能力补迁**：迁移可信绑定、delegation提示和原消息审批，复用原生child/ApprovalService；不另造provider [N13]、[D06] |
| O10 | Cron创建/管理、执行、运行历史与交付 | 原生schedule绑定当前主会话，持久定义/timer/calendar/冷恢复已有；receipt只到inbox | **已选原生主对话投递＋补迁产品执行历史/交付**；退出旧每次新建隔离session的派发，见S1—S3 [N14]、[D14] |
| O11 | Heartbeat 主上下文、忙时跳过、静默、活跃时段；错过周期不刷屏，一次性过期不补跑 | schedule 可定时发输入，但不自动实现这一组规则；overdue active 一次性安排仍可能投递 | **Heartbeat产品策略迁移；Cron过期一次性已确认改为DSH补发**，退出旧跳过规则；不新增Nano DSH heartbeat引擎 [N14]、[D14] |

### 3.4 执行支持与产品边界

| ID | Nano 当前能力 | DSH 覆盖及差异 | 覆盖结论与差异处理 |
|---|---|---|---|
| R01 | 多模型／推理强度／上下文窗口／代理／OAuth | pi-ai 与直接 provider 有模型路由、手动网关配置及部分 OAuth；具体已用链路未测 | **原生 + 装配/接入**，不从头写 provider [N05]、[D15] |
| R02 | 同模型重试，失败原因分类 | llm-retry 在 request-error 扩展点处理请求失败／backoff，与 provider 配置结合 | **原生**，由 integration 映射产品错误 [N15]、[D16] |
| R03 | 有序备用模型链、session 粘性、已有公开输出后不切、改配置重置 | 已查 retry/model-selection/provider 配置未见等价策略；同模型 retry 不等于跨模型 failover | **非原生等价**；公开 request-error 可接策略，但同 step 重试不重装 prompt，不能只更新 selection.current，详见 §7.6 [N05]、[D16]、[D05] |
| R04 | 上下文压缩、持久 session、fork、图片上下文 | DSH 已有 compaction、session persistence、fork 和附件/provider 能力 | **原生 + 接入**；新历史消息锚点、媒体授权和重启契约分别验证；旧聊天转换已排除 [N10]、[D17] |
| R05 | per-tool 自动审查、真人审批、来源判断、无人值守回退 | 有 user-approval、permission presets、实验 Auto；原生 Auto 的来源选择与 global Inbox 不等价 | **权限策略差异**；见第 6、7 节，不能先承诺原生等价 [N03]、[N16]、[D18] |
| R06 | 工具卡、reasoning／token／缓存用量、Work 轨迹 | DSH 有执行事件／元数据；自带 Web renderer 不自动进入 Nano Web/iOS | **接入 + 产品呈现**；不要给每种工具写独立业务插件 [N03]、[D01] |
| R07 | global Inbox、conversation 查询、显式外发、群更正复核、task_graph | DSH 提供工具入口原语，不拥有 Nano 公司身份、聊天与任务记录 | **产品 + 工具入口接入**；这些不是待寻找的通用 Agent 内核工具 [N16]、[N17] |

## 4. 用户自建 workspace／全局工具：到底已经有多少

### 4.1 Nano current 的准确基线

PA 把全局 tools/hooks roots 传给内核；workspace root 为 `<workspace>/.nanoassistant/tools` 和 `hooks`。工具 loader 读取 Python 文件的 `TOOL`、`TOOLS` 或 `get_tool()`，workspace 同名覆盖共享基底。不同 workspace 隔离。[N01]、[N04]

这里有一个容易误记的限制：全局工具在内核装配时加载，workspace 工具由 `_SessionCapabilityResolver.scope_for()` 在首次使用时建立并缓存快照。**源码不能证明“Agent 刚写完 Python 文件，当前运行就自动热加载”。** 终态要保留的是“能够创作、限定共享范围、使它在后续执行可用”，是否要求当前会话立即生效应另行明确。

### 4.2 DSH 的三种机制，不能混为一个

| 机制 | 已有用途 | 对 Nano 的限制 |
|---|---|---|
| 普通 Cordis plugin/bundle + plugin_manager | Agent 用文件工具创作，持久安装，重启后可继续使用 | 安装与 profile 配置影响所有使用该 profile 的会话；不是按 Nano workspace 扫描 |
| Agent preset／setup／scoped tool registration | 限定工具、prompt 和事件可见范围；支持同名 shadow | 需要宿主决定数字人与 preset/scope 的绑定；没有原目录发现／优先级产品规则 |
| dynamicCordisRunner | 程序调用 define/run/stop 的临时动态扩展 | session-scoped、进程内定义，重启清空；当前 shipped model tools 不能创建／更新定义，不能用于声称“持久自建工具已全覆盖” |

来源：[D03]、[D04]、[D19]。`cordis_inspect_*` 是只读开发查询，不是安装／执行工具。

### 4.3 已选A：标准插件格式，保留全局/workspace两层

用户已确认采用DSH标准plugin/bundle接入，并要求保留原有两个层级。**采用标准插件格式与保留两层不是互斥选项**：格式交给DSH，Nano管理“这份扩展属于全局还是哪个workspace”，调用选择/覆盖使用原生scoped registry。

| 产品层级 | 持久定义与装配归属 | DSH注册位置 | 可见/执行范围 |
|---|---|---|---|
| 全局共享 | 节点owner的共享插件声明，指向标准bundle/module及配置 | 该owner运行时的共享工具层 | 本节点该owner的Agent均可发现，再按各自allowlist决定实际可用性 |
| workspace局部 | workspace的标准插件声明；产品绑定记录其规范化workspace root | 创建/恢复该workspace会话时，在对应Agent scope装配局部插件 | 只有绑定该workspace的会话可用；同workspace多会话加载同一份声明，其他workspace不可调用 |

同名规则由原生工具registry完成：workspace scope中的`lookup`覆盖共享层`lookup`，schema与真实执行均只命中局部版；另一个workspace继续命中共享版。移除局部注册后按原allowlist重新显现共享版；同一层重复名称按DSH规则明确拒绝，不引入不确定加载顺序。[scoped registration实现][A30]、[既有隔离/覆盖/释放测试][A31]

**Nano要做的具体接线**：

1. Agent用原生文件/开发能力生成标准插件。启用请求明确选择全局或当前workspace；Nano使用已验证的owner/workspace绑定决定挂载层，普通“安装包”不自动意味着给所有Agent启用。
2. 包/模块安装与工具启用分开。全局插件只在共享层挂载；workspace插件只在所绑定Agent的scope挂载，不能因为包安装进同一个profile就顺带在全局调用`apply`。同一份代码可供多个会话装配，不复制工具文件。
3. 创建、恢复及配置生效时读取持久声明。workspace依据会话的可信绑定，不能跟随一次shell `cd`或模型传入任意路径变化。子Agent按其实际绑定workspace和继承的能力子集装配，不假设DSH会复制父Agent临时注册。
4. 工具更新在已有配置安全边界装配，scope释放时注销。JS包替换遵守原生重载/重启限制，不承诺写文件后任意热替换；重启后按持久声明恢复两个层级。
5. 注册层级不授予权限：名单、审批和产品业务guard仍执行。`tools.restrict`不屏蔽本层新注册，因此局部插件需过滤注册，并核实原生调用限制；未选项从有效集合移除，原生执行器反馈UNKNOWN_TOOL，不另加名单guard。来源展示标明共享/工作区及实际命中版本，便于排障。

示例：共享`lookup`返回“共享版”；workspace A声明同名局部版，A的两个会话都返回“A版”，workspace B返回“共享版”。A再创建`private_check`，B既看不到也无法执行。停用A的override后A回到允许使用的共享版；runtime重启后的结果一致。

以上使用DSH现有注册、scope、配置与dispose原语；不保留旧Python Tool对象协议，也不新增通用工具执行器。普通Python程序可以继续由受管shell/MCP承载，现有依赖旧SDK的适配代码按资产转换。源码可证明层级/隔离/覆盖原语，产品装配和重启链路仍需实施验收。日常工具命令、截断等变化不包含在此次A选择中。

## 5. Workflow、Cron 与 Knowledge 的取舍不能相互替代

### 5.1 Workflow：优先复用执行，单列高级兼容

DSH 已有模型能调用的 JS Workflow，能并行、流水线、验证结构化 child 结果，也能后台运行。因此基础“把多个 Agent 编排起来”不缺。Nano 的受限 Python 语法无需作为必须保留的产品价值。[D13]

真正要单列的是控制与恢复：Nano resume 也不是恢复任意 Python 栈，而是新 run 复用同 parent session 下最长匹配的完成前缀；DSH 当前没有同等机制。要补它，必须管理调用身份、结果持久化和复用条件，已经是 Workflow 扩展，而不是一个薄 wrapper。[N12]

另须区分状态与结果：`jobs-local` 以内存 Map 保存 job，Workflow 的持久 `run-end` 只记录 runId/stopReason，不包含最终脚本返回值。若要求普通 jobs／后台 Workflow 的结果跨重启可交付，必须在结果产生时保存结果及交付身份。公开 `WorkflowRun.result` 可以取得值，但原生 `workflow/end` 和 jobs observer 都不提供这一非消费结果；具体边界已查清，见 §7.3。结果未进入父 session 或产品持久记录就退出时，应报告中断／结果未知，不能只靠“补对账”承诺恢复结果。

**2026-10-09 用户已确认采用DSH的JavaScript，并保留四项控制、保存/命名复用和一层嵌套。** 这些进入必须实现范围，不能以“原生没有”取消。原有Workflow审批路由补迁，风险政策已确认默认Nano且可配置切换DSH；原问题10转为具体运行边界工程核查，统一见 [产品决定](pending-decisions.md)。

四项的公开接口复核与具体接入方案已落在 [Workflow控制设计](workflow-control-design.md)：推荐自有Workflow provider复用DSH PTC/subagents；stock观察事件不能代替派发控制。该文维护控制、身份、持久前缀和预算规则，本图不重复展开。

### 5.2 Cron：原生有定时器，但默认不另建插件 owner

用户已确认11a：直接使用原生`schedule_create`绑定创建它的主会话，到点在同一会话followup并沿用上下文，不建立每次隔离或每任务专用会话。旧Nano独立执行语义退出目标范围。DSH持有安排存储、timer、calendar和冷恢复。[N14]、[D14]

产品保留真实触发来源、立即运行、执行历史及渠道交付；结果已在主认知产生，无需隔离上下文回灌。Heartbeat任务选择/忙时/静默仍补迁，11b已确认原生恢复后补发过期一次性提醒；同一安排不双写。完整处置见§8.3。

### 5.3 Knowledge：现有机制存在，不等于现有策略存在

**用户已明确：记忆与Skill自动整理必须迁移保留。** DSH的本地Skill provider/loader承担发现和加载；Nano知识维护扩展承担选择规则、管理结果、使用／来源统计、受控记忆写入与自动维护策略。DSH缺少对应策略，不能将改为手动整理作为类似原生替代。

MCP memory 示例说明 DSH 可以连接外部记忆服务；上游明确不负责下载服务、建库、迁移或自动维护。它不是 Nano 的 MEMORY/USER 文件语义和 Skill curator 的现成替代。[D10]

Nano 的自动 review 触发计数本身含进程内状态，本轮不把它夸大为持久任务系统；迁移默认不额外承诺跨重启精确恢复所有 review 计数。review 使用 DSH child/jobs，读取、更新、去重和成功事实由知识插件负责；配置调和交产品服务。不同职责各留一个 owner。[N09]

## 6. 两个最容易漏掉的执行权限缺口

### 6.1 原生 Auto 有，但不会自动理解 Nano Inbox

DSH Auto 当前把 `source.kind === 'user'` 且 `rpcId` 为 string 的持久消息视作真人指令；其他来源按规则归为约束、checkpoint、事实或 direct-parent instruction。它排除普通 tool results，并使用固定重建逻辑。[D18]

Nano global 真人消息经 Inbox read 工具进入主上下文，wake 自己是系统来源。直接接 stock Auto，会漏掉这种真实授权；把每个 wake／tool result 改成 `user` 又会错误扩大权限。[N16]

保留 Nano Auto 时必须提供受控接入：只从产品验证过的原消息提取真人／Agent／系统／引用来源，把批准范围和完整动作交给唯一审核链。本轮继续追到源码：来源分类与快照函数未导出，也没有来源贡献回调，不能配置完成这组要求。若无法复用，需由 Nano policy 插件部分提供审查策略，复用 DSH 工具 gate／LLM／approval，替代 stock Auto，而不是两套分类器各跑一次。

还有两处边界：DSH Auto 的原始拒绝原因进入结构化用户展示，默认不作为主模型正文；Nano global 需要原因来选择下一步，需补结果投影。原生 PTC 程序的直接 Node effects 也不经过 inner-tool Auto，因此不能把工具 allowlist／Auto 当成对任意插件和脚本的强安全沙箱。

这意味着权限接入可能有明显工程量，不能用“薄桥”掩盖。必须评估实现和上游升级成本，再决定保留多少 Nano Auto 语义。

### 6.2 子 Agent 的 preset 继承与人工审批分开看

DSH in-process child 会继承父 preset composition，并装配自己的 toolFilter；parent 临时 scope 内安装的 Nano 工具、guard 和身份不自动等于被复制。root／普通 child／Workflow child 必须分别验证有效能力。[D06]

其本地 child approval 被明确设为 `never`。因此 Nano 普通 global child “拒绝后回主”的目标接近原生；Nano Workflow child “弹卡到原 launch message”并不满足。后者作为现有能力补迁，公开agent/created与setApprovalPolicy已提供首次执行前覆盖入口，但须同时处理可信绑定、delegation 提示和冷恢复。它是策略接入，不是只加 UI 卡片，也不必因此重写 child provider，详见 §7.5。

## 7. 公开接口核查：代码已经能确定什么

这里回答的是“现成包是否满足、补齐需要触及哪一层”，不是先选插件再找理由。**“插件可做”不等于“值得做”，更不等于“写一个监听器就够”。**

### 7.1 自建工具、共享和同名覆盖：原语已足够，旧加载方式不兼容

DSH `tools.register()` 将工具放入调用 context 的 scope，近层同名覆盖远层；返回 disposer，scope 卸载撤销注册。`tools.guard()` 在所有适用层逐层检查，只能收紧，不能强行放行别的 guard 已拒绝的动作。上游 `scoped.spec.ts` 已有局部可见、同名覆盖、限制交集的源码测试，本轮只阅读、未重新运行。[S01]

因此 A/B 私有、共享、覆盖、注销无需先做实验来判断有没有机制。缺的是 Nano 目录发现和 Python 对象协议：标准 DSH 插件可直接创作；若要保留 `.nanoassistant/tools` 的习惯，就需要目录/启用适配，不能原样加载 `TOOL`／`get_tool()`。

`tools.restrict()` 只过滤继承的工具，不阻止当前 scope 新注册工具；`run_code` 又是保留 transport 名称，不能直接放进 restrict。若产品要求“未选中的能力绝不执行”，在注册和继承过滤时落实到有效工具集合；原生get/schema/execute共用该视图，未选工具调用返回UNKNOWN_TOOL，不另加名单guard；PTC 内部经 registry 调用会经过 guard，任意插件/脚本的直接宿主副作用不等同于工具调用。这个区别直接来自执行路径，不能以两次调用成功推导安全隔离。[S01]

**结论**：局部/共享自建工具优先原生替代；原目录体验属于可选适配，硬名单属于产品接入。没有源码依据要求为此重写工具引擎。

### 7.2 Skill 可见性：provider 能过滤自己的来源，不能屏蔽所有其他来源

`FileSystemSkillProvider` 是公开导出类，可指定绝对 `customSkillDirs` 并关闭默认 roots；`skills.registerProvider()` 是公开生命周期接口，可包装其 `list/get`，在每个数字人的 scope 中只暴露所选 names。catalog、`skill` 工具和显式命令都从 `skills.list/get` 取得胜出条目，可共享这一筛选结果。[S02]

但 registry 的 `collectFresh()` 合并 global 和 scope chain，只覆盖同名条目；没有“过滤最终集合”的公开 restrict/deny 接口。某个 provider 返回空集合不会屏蔽 global provider 或其他 bundle 注册的 Skill。于是必须区分：

- **受控 Nano 装配**：只注册受筛选的 provider，把 packaged/runtime Skill 也纳入同一受控来源；可以不改 DSH 实现完整名单。
- **任意社区插件可自行全局注册 Skill，同时要求统一名单**：单包 provider wrapper 不够。本设计按终态架构§5.5要求其通过公开适配纳入受控提供方后才启用；不修改上游registry，也不声称原生支持任意插件下的统一过滤。

此外，DSH Skill 名称只接受小写 kebab-case。旧名称若含其他字符，需要名称映射或重命名；命令形式 `/skill:name` 与 `/name` 的差异也属于用法变化，确认后可直接接受，不建设旧语法兼容层。[S02]

**结论**：普通发现/加载原生满足；完整名单在受控装配下可适配。统计、归档、Memory 更新、自进化 review 是独立策略，不能由 provider 自动获得。

### 7.3 后台 Workflow：执行已具备，结果持久交付不能只挂 observer

源码链为 `tool-workflow → workflow.start → WorkflowRun.result → jobs.start().done → jobs-local.settle`。`WorkflowRun.result` 返回完整 value；`workflow/end` 的公开类型明确排除 value；工具写入的 `tool-workflow/run-end` 只有 runId/stopReason。[S03]

jobs 的 `settled` 事件只带 JobView/cause/awaited；`readAt()` 非消费读取的是输出 ring，不含单独的最终 result；`read()` 才返回 result，且第一次读取后将其标记已交付。另挂监听器调用 `read()` 会与模型消费者竞争，不能称为无侵入持久化。[S04]

源码可确定两条不同代价的路线：

- 仅要求前台结束后仍在线完成并通知：复用 stock Workflow/jobs 即可，父 Agent 生命周期必须仍存活。
- 要求 Workflow 最终值跨进程退出仍可靠交付：自有工具 consumer 可以调用公开 `workflow.start()`，拿到 `run.result` 后先持久保存再交付，仍复用原生编排引擎。若坚持 stock tool-workflow 和 jobs consumer 均不变，则现有公开事件不足；Q22下选择自有consumer/公开provider接线，不修改上游以补事件。

**结论**：无需因后台需求再造Agent执行器；已有持久交付保证通过结果consumer补迁，不依赖用户再次确认。Workflow控制额外维护范围另见专项设计，一次实验也不能替代接口分析。

### 7.4 原生 Auto：来源和专用审核模型不是配置项

`isHumanInstruction()` 只识别 `user + rpcId`，`snapshotAutoReview()` 与分类/构建请求函数都是模块私有；`apply()` 直接安装工具 gate。审核请求沿用当前 session request 的 provider/model，没有独立 reviewer-model 配置。[S05]

Nano global 的可信真人原话来自 Inbox tool result，而不是普通 Web user input；Nano 还允许专用审核模型、有效拒绝计数和无人值守回退。原生 Auto 不能只靠配置就获得这些行为。把系统 wake 伪装为 user 会改变授权事实，不是兼容方案。

**结论**：原生gate/approval/LLM骨架直接复用。Nano专用审核模型、来源及产品分流缺失，必须迁移：以公开gate/approval/LLM接口维护一个Nano consumer，不修改stock Auto源码。不能算零成本配置，也不复制执行loop。问题6已确认默认沿用Nano规则，并支持配置切换DSH默认规则。

**已确认的规则选择边界**：在同一个Nano Auto consumer中选择Nano现有判定规则或DSH默认三档风险规则，默认Nano；每次工具权限判定只运行所选一套，不叠加两次审核。两套选择共用专用审核模型、可信来源、人工确认及拒绝/无人值守分流，切换不绕过这些产品保证。配置按产品既有生效边界应用到后续判定，已发出的审批继续原请求，不因切换重新解释。DSH默认规则的接入仍需上述有界扩展，不能说stock已经提供此配置开关。验收覆盖默认Nano、改配置后使用DSH规则及原审批路由/模型保持有效；不另建通用策略框架。

### 7.5 子 Agent 人工审批：默认拒绝是显式契约，不是缺少 UI

原生 child composition 带“权限在启动时固定，超出后回报父 Agent”的指令，`captureDelegatedPolicyOverrides()` 写入 `approvalPolicy: never`；`ApprovalService` 在触发任何 answerer 前先处理 never。因此只装 Web/飞书 answerer 不会让子 Agent 弹卡。[S06]

公开 `setApprovalPolicy()`／`approval.setPolicy()` 能切换 policy；Agent 创建会等待 `agent/created` 监听器完成后才释放 queued work。因此宿主可在验证 Workflow child 身份后、首次执行前设 ask，保留原 spawn/fork/continuation provider。还须经公开 `system-prompt/assemble` 修改固定 delegation 提示；同层重注册同名 context 会报重复，不能靠重复注册覆盖。初始化用 `setApprovalPolicy`，避免 live `setPolicy` 的“changed by the user”文案错误归因。新建、cold resume、原 launch message 审批路由必须应用同一规则。

**结论**：普通global child延续原有回主规则；Workflow child直接弹卡按缺失能力补迁，使用上述公开生命周期接入。不再要求用户选择是否删除，源码也不要求修改loop或重写provider。

### 7.6 模型 fallback：可接错误策略，但不是修改一个 selected model 即可

原生 `agent/request-error` 返回 retry 后，在**同一个 step**内重新 `prepareRequest()`；它不重新运行 `system-prompt/assemble`。`installModelSelection()` 在 assemble 时把 current 捕获到 assembled，后续请求使用 assembled。因此仅修改 `selection.current` 再返回 retry，并不能完成该次跨模型重试。[S07]

公开 `agent/request` 可以改变下一次请求路由，`llm/stream` 也有包装接口；这说明无需 fork loop 才能发往备用模型。模型相关prompt、上下文上限、模型变更提示、失败重试优先级均在补迁范围，必须处理它们的一致性，不能直接把 stock retry + selection 拼起来宣布等价。准备阶段/stream 抛异常与正常 error finish 也不是同一路 request-error 分支。

**已选方案（Q22）**：原生retry优先，Nano fallback插件在失败turn结束且Agent idle后，通过公开maintenance/model-selection/followup衔接新的原生turn。产品logicalRun不变，输入按已提交/未提交分流，新turn重新装配prompt/effort，新请求窗口与原生overflow恢复生效；不要求同DSH step，不修改loop。完整准入、来源与恢复见[终态架构§10.2](target-architecture.md#102-配置生效不是保存按钮成功)。

### 7.7 配置更新：新 session 的装配与旧 session 下一轮更新不同

`agents.create/resume` 的 setup 窗口支持发布前装配；preset revision 绑定、scoped registration/dispose 支持各数字人隔离。可是 `agentPresets.select()` 明确拒绝已经开始过 turn 的 session；`recompose()` 文档也要求 blank Agent，由调用者检查。[S08]

**结论**：不能把“配置下一轮整体生效”映射为随时 select preset。固定 preset 中由自有配置层管理可变工具、Skill、模型和 prompt 的 scoped effects 是可行扩展方向；整体 preset 替换则需重新建立受支持的会话/运行对象；本unit不修改上游契约。两者成本和用户体验不同，正式设计前应选明，不把旧会话强行当空会话操作。

### 7.8 Web search：工具原生存在，旧 provider 并未一并覆盖

Nano search 提供 DuckDuckGo、Brave、SearXNG；本基线 DSH 第一方包是 DeepSeek、Exa、Perplexity。`web.registerSearchProvider()` 与 `WebSearchProvider.search(request, signal)` 是公开接口。[S09]

**结论**：采用 DSH provider 只需配置并确认服务/账号变化；必须保留某个旧 provider 时可写 provider adapter，不复制 web_search 工具、渲染和执行链。是否更换服务的费用/可用性属于用户选择，本稿不声称新服务免费或已有凭据。

### 7.9 接收、摄取和恢复：原生持久原语存在，官方 wire 不等于产品契约

`agent.send/followup/steer/inject`、`session/event` 和 `sessions.flush(session)` 都是公开接口；flush 返回是否真的有持久化监听器参与，必须检查成功且为 true 后才能发 durable ACK。持久 Inbox splice 和 tool/result 给出了输入/正文事实，原生 SDK 只有 initialize/session/prompt/shutdown 不能直接代表全部能力。[S10]

`claim()` 从持久队列删除输入，随后才在请求阶段追加 user/message；resume 对中断 turn 补合成闭合事件，不恢复任意执行栈。官方 controller 的 requestId 去重只查 pending 和 user/message，无法单独表达“已接收、已 claim 但未写 user/message、已中断”的完整产品状态。完整 splice 日志仍能重建输入身份；接入层须基于该证据区别处理中断与未曾接收，不能以“查不到 pending”就盲目重投。[S10]

**结论**：会话持久化、取消和输入控制无需重写内核；稳定 input 身份、来源、消费证明、断桥查询属于必要接入逻辑。实现后再验证崩溃/断连边界，本阶段先根据这些接口作方案，不要求先迁移或先跑 PoC 才允许设计。

### 7.10 Workflow 运行约束也是差异，不能只比较并行 API

Nano Python Workflow 拒绝脚本直接 import、文件/进程/网络副作用，工作由 child 工具完成。DSH workflow-ptc 在 Node 子进程和所选文件 sandbox 下运行；文档明确 VM 不是安全边界，文件 policy 不限制网络。两者的执行约束并不等价。[S11]

**结论**：常规使用都是脚本编排、child工具执行；撤销问题10的A/B问法。先按DSH原生运行方式接入，具体核查sandbox及审批链；遇到影响已要求权限行为的实际缺口再说明。不预建更严格脚本执行器，也不声称底层隔离保证完全等价。

## 8. 全量覆盖与处置审计

本节统一记录迁移去向；第3节保留逐项能力事实，第7节保留难点接口证据。判断原则为：**原生缺失的现有用户能力迁移保留；已有相近机制才比较替代；部分覆盖拆成复用与补迁两部分。** 不再把“只有改手动才省事”列为原生替代。

### 8.1 覆盖如何得到，哪些还不能称已完成

本轮再次fetch，两仓基线仍为Nano `4915c44c` / DSH `5badb150`。写作checkout为Nano `main@76fe1d7e`，保留全部既有dirty/untracked；源码按固定提交取证，相关kernel/PA主体与本checkout一致，PA差异仅配置指纹三行。最新iOS及Web契约用`git show`/固定提交链接读取。没有接入运行或线上验收。

从四个入口双向核对，避免围绕已有问卷补材料：

1. **Nano实际装配**：基础工具注册read/write/edit/bash/agent/task_stop/web_fetch；PA额外注册cron/send_message/web_search/inbox/conversations/task_graph；路径与feature装配memory/skill_manage/skill_view/workflow。PA还明确加载chat_history hook及工具/Skill/hook roots，不能只迁DEFAULT_TOOL_IDS。[N01]、[N02]、[N04]、[A01]
2. **Nano当前契约**：kernel执行、模型、上下文、后台、工具/hooks、Skills、prompt；Gateway路由、global、调度、配置、渠道、Workflow；IM身份、聊天、Work、任务图、媒体、客户端与节点。既有迁移规划第4/6节负责数据/协议/验证，不以工具清单代替产品清单。
3. **DSH反向能力目录**：对照packages分组，除loop/tools/session外，明确检查schedule、goal、jobs、compaction、preset、hooks、MCP、attachment、deliverables、plan、interaction、webhook等。存在某包只说明有候选；是否进入Nano由用户任务和下面的边界决定。[A02]
4. **剩余未知独立列出**：实际启用的provider/MCP/自建工具/hooks集合与数据量，部分存量上下文转换、每个渠道最终呈现以及版本升级回归仍需具体证据。源码核查完成不等于这些资产和运行结论已完成。

表内“源码明确”表示当前静态证据足以选择机制；“有界未决”表示原生差异已查清、需要产品决定；“资产待核”表示机制有方案、实际使用集合尚不完整。没有将“文档已提到”算作实现或生产验证通过。

### 8.2 产品与知识领域的覆盖去向

| 用户任务 / 范围 | 原生证据与直接采用的变化 | 可删除的Nano职责 | 必须保留的最小接入 / 自研理由 | 推荐、状态与未知 |
|---|---|---|---|---|
| K：Skill发现、加载、创作与选择 | 文件provider、catalog、skill工具已覆盖发现加载；命令名、名称格式、目录更新时机不同。见K01—K06及§7.2 | 旧发现器、普通正文loader与重复目录watcher | 受控roots/名单/preview、受控管理与成功使用记录；普通文件写入不能证明创建来源或自动启用 | 原生发现/加载＋知识管理；小用法差异集中确认，自动维护已确认。不另造Skill引擎 |
| M：记忆与Skill自动维护 | 原生没有对应curator、阈值策略、使用去重、归档与生成启用机制；child/jobs是执行原语。见K04—K09 | 旧内核side-chain执行器及其loop；不删除自动策略 | 迁移记忆受控更新/注入、统计/阈值/来源、自动review与配置调和；只成功写入发系统通知，维护文本不投递成聊天 [A03] | **必须迁移，已确认**；内部F阶段可重组，功能不改手动；不额外宣称所有触发计数跨重启持久 |
| I：一个数字人处理多聊天 | Agent/inbox是执行输入队列；session-query查询的是执行档案，不包含Nano公司成员、聊天资格、业务摄取分片 | 旧Agent执行协调内部实现；用DSH输入/child原语 | 产品Inbox、真实来源、完整摄取、显式目标、群更正与持久交接；少一层会丢业务含义，非通用队列重复建设。见R07/§7.9与终态§8 | 产品保留＋原生执行，源码明确；独立多聊天旅程验收 |
| T：讨论后保存、协作编辑任务图 | DSH todo/plan/goal各自是session工作状态，未覆盖共享图revision、成员资格、mutation回执及“不自动开工” [N17]、[A04] | 不新增自研执行DAG；现有共享图继续是业务记录 | IM保存共享图，薄工具调用产品API；不把单session todo升级为共享图 | 必须迁移，源码明确；无需询问用todo替换共享产品 |
| C：Web/iOS/飞书消息与审批 | DSH事件、attachment、present支持执行媒体/文件声明；present只声明本机路径，不上传到飞书或提供IM媒体资格 [A05] | 旧内核媒体进入模型的实现、旧事件内部类型；按DSH事件统一投影 | 三端传输、身份/附件资格、上传、回复目标、镜像/回执、审批路由；模型看见图片不等于用户收到图片 | 保留产品接线；媒体转码/格式限制按实际provider核查，原生Web UI不直接替代三端 |
| V：过程、用量与工作记录 | 原生session/tool/usage事件是事实来源，DSH Web renderer不自动适用于Nano客户端。见R06 | 旧事件产生器、重复的模型用量采集 | 一套产品投影适配工具/思考/用量/Work；保留来源、顺序与用户可理解的结果。特殊产品工具保留结构化展示 | 推荐通用原生工具展示＋既有业务卡片；工具文案/参数的小变化合并确认，不逐工具重做插件 |
| H：可读聊天副本、内置说明书与Lark Skills | DSH持久session和本地Skills可读写，但没有Nano可读输入投影与受控内置资源升级策略 [A01]、[A06] | 旧hook事件名耦合、旧Skill loader | 将可读副本作为产品投影接事件；保留内置资源刷新、用户文件隔离、Lark现有身份约定；不是继续维护旧HookRegistry | 必须迁移，源码明确；存量用户hooks脚本需资产核查，不承诺零转换 |
| N：多数字人/节点配置及生命周期 | preset/scope、模型选择、tools与Skill服务可组合；preset并非任意旧session热切换。见T07/§7.7 | 旧Kernel工厂、会话能力resolver；复用scope注册与原生插件装配 | owner/node/agent绑定、配置operation/实际revision、有效工具集合、重建边界；DSH共享进程不是产品授权模型 | 原生装配＋产品配置，源码明确；不建立每会话进程池 |
| D：旧历史、数据、发布回滚与退役 | DSH session有自己的格式，不原生解释Nano历史和业务DB | 切换验收后退役旧loop/SDK及Coding CLI；保留PA运维命令 | 配置/非聊天资产、新会话绑定、单消费者切换、新写入回滚处理；旧聊天兼容排除；见迁移规划§4/7/8 | 开发态不做旧聊天续接/fork适配；非聊天资产接入及切换演练仍需完成 |
| U：社区插件及上游升级 | 原生profile/plugin-manager具备安装、依赖与版本兼容检查；作用域是profile而非单数字人。实验包不承诺稳定 [A02]、[A07] | 不写第二套包管理器或自研通用后端抽象 | 锁定runtime/profile/依赖版本；Nano接入只依赖公开服务；升级验证输入/取消/审批/后台/配置/历史，禁止上游patch，核查锁定依赖与公开导入 | 推荐原生安装与兼容校验；升级前回归由Nano负责，运行时与插件变更不自动批准生产更新 |

### 8.3 主动执行、子Agent与权限的处置

| 用户任务 / 范围 | 原生证据与直接采用的变化 | 可删除的Nano职责 | 必须保留的最小接入 / 自研理由 | 推荐、状态与未知 |
|---|---|---|---|---|
| S1：指定时间、周期和时区 | schedule公开导出create/resolveOccurrence日历算法，支持at/after/every/daily/weekly/cron；every至少60秒且以创建时间为锚 [A10] | 自研cron解析、时区/日历/DST和最近周期计算 | 任务身份、per-agent开关；每数字人独立原生schedule服务/存储，开关卸载重挂fiber，详见终态架构§10.1；旧interval锚点与短周期存量核查/映射 | **直接复用算法**，不因派发不同重写时间引擎；存量表达式待核 |
| S2：定时工作在什么上下文执行 | stock `schedule_create`绑定当前主会话，到期恢复同一session并followup [A11] | 旧每次新建隔离session的runner及对应timer/安排存储 | 原对话绑定、系统触发来源、运行历史与交付；global/single_thread按原身份路由 | **11a已确认原生主对话投递**，不建独立任务会话；过期策略见11b |
| S3：错过周期、立即运行与历史 | 原生周期取最近一次，过期一次性仍发；同session周期任务合批；delivery history仅证明入Inbox，不是执行成功 [A12] | 原生reminder范围可删时间推进/定时入队；不能把运行历史全删 | 现有run-now、accepted/running/terminal、结果错误历史、失败恢复、投递/主认知回流缺失，均补迁；一次性过期已确认采用原生补发，退出旧跳过逻辑 | **部分复用**；不把schedule收据当已完成，选择原生也需业务运行记录 |
| S4：Heartbeat主动检查 | schedule有周期followup，但没有HEARTBEAT.md子节律、activeHours、busy-skip和HEARTBEAT_OK静默 [N14]、[A12] | 复用日历计算与Agent输入，退出旧Kernel调用 | 缺失的选择/忙时/静默/归属/结果规则迁移；若仍需due裁决就保留唯一产品触发器，不让stock timer先排进忙Agent | **缺失策略必须迁移**；不再用“周期唤醒相似”取消主动产品机制 |
| B1：普通子Agent派发与继续 | continuable原生持久身份、初始收件、再次发送与冷恢复；显式前台一直等待，后台立即返回，没有Nano前台等待超预算自动转后台 [A13] | 子会话执行器、冷恢复执行循环、父子接收锁 | 业务身份/角色/tool filter/结果映射；默认将需继续交互的工作设continuable后台，可用原生wait短等，保留长任务不阻塞主Agent的能力 | **原生continuable＋等待接入**；不为了旧工具参数重写子Agent引擎，具体前后台用法纳入普通工具差异 |
| B2：父子通信及父Agent醒来 | sendMessage支持相邻父子；child可冷恢复，parent必须live；steer/followup真实唤醒driver，非仅排信 [A13]、[A14] | 底层busy/idle收件、父会话wake与续跑循环 | task/status/result/usage/duration消费归因及产品结果交付；跨进程只能从持久结果恢复，不能放大为任意父mailbox持久保证 | **原生通信与唤醒＋产品归因**，范围明确 |
| B3：后台Bash及长工具输出 | jobs/tool-jobs已有wait/read/kill、output cursor、忙时inject/闲时followup与重复通知抑制；通知让模型再读job_output [A15] | 通用进程内job registry、轮询cursor、完成唤醒；Bash超时转后台底层 | 产物路径、消费事件归属及真实渠道交付；jobs-local内存状态不是跨重启工作账本 | **直接原生jobs**；补结果投影，不建立第二套同义job引擎 |
| B4：停止运行并继续聊天 | 原生abort/interrupt及子树清理可用；工具执行明确等body完成后才收口，不放弃Promise [A16] | 正常合作式取消、原生process/job清理 | Nano现有parked run释放保证需核查具体provider/RPC取消；不响应signal的扩展不可写成已兼容。Nano旧Task.cancel也不是任意代码强杀 | **原生取消优先，接入履行清理**；窄缺口单列，不预建每session进程池 |
| P1：人工批准/拒绝/取消 | 原生request/answer/一次性grant/审计对/取消迟答都有，request需open turn [A17] | 底层permission Future/broker、重复审批配对状态机 | Web/iOS/飞书answerer、可信owner、原消息/Work路由；离开模型turn的产品授权保持产品policy，不能伪造DSH工具turn | **复用原生审批**，产品路由保留；Workflow child初始policy接公开生命周期，不再询问是否删弹卡 |
| P2：自动审批 | 原生Auto有LLM风险分类和deny优先；但固定当前run模型、私有snapshot/classifier，global工具来源及专用模型无法配置等价 [A18]、§6—7；风险政策差异来自原生三档规则与Nano可配置规则 [A28]、[A29] | 复用gate/approval/LLM执行；若将来上游开放来源和路由，可进一步删除自有consumer | 专用审核模型、可信Inbox授权、短确认、拒绝阈值、无人值守及no-verdict分流缺失，迁移进**一个**Nano Auto consumer，不与stock Auto同时判定 | 默认Nano判定规则，配置可切换DSH默认规则；共用一个consumer和产品保证，切换不消除上述接入成本 |

### 8.4 会话、基础工具、模型与扩展的处置

| 用户任务 / 范围 | 原生证据与直接采用的变化 | 可删除的Nano职责 | 必须保留的最小接入 / 自研理由 | 推荐、状态与未知 |
|---|---|---|---|---|
| E1：会话落盘与重启继续 | create/resume、JSONL persistence/checkpoint、flush、日志重放及工具闭合已有；格式与Nano不同 [D17]、§7.9 | 旧transcript引擎、普通事件重放及悬空tool-call闭合 | 业务绑定、真实持久ACK、完整claim/splice交接；旧聊天不读取/转换适配，新会话独立建立 | **底层原生**；不能把业务消息去重转交给session日志自动完成 |
| E2：插话、排队与停止后续接 | steer/next-step、followup/next-turn、inject与keepInbox已有；不自带Nano expected_run_id和业务pending回执 [S10]、[A14] | 普通执行FIFO、step派发和wake循环 | 在产品输入ID与运行代次上校验插话目标，映射消费与未消费交接；claim后崩溃须看完整日志，不能靠pending缺席盲目重发 | **队列与输入原生**；保留接收/消费/交付分界，源码明确 |
| E3：自动压缩与超窗恢复 | compaction-basic按窗口/输出预留/headroom压缩，支持模型策略及摘要模型；阈值/摘要格式不同 [A19] | 旧压缩选择、摘要执行、上下文重建及overflow retry算法 | 登记真实context window、摘要模型与通知；Skill正文压缩后可用由知识策略补齐 | **推荐原生算法**；接受内部摘要/阈值差异，不保留旧算法副本 |
| E4：手动压缩重点与重试 | compactNow提供维护边界和持久barrier；sourceCommandId仅展示关联，不承诺幂等，也无focus参数；summarize有受支持定制入口 [A20] | 旧手动压缩执行器 | operation receipt与原结果查询、定制摘要传入focus；不将focus伪装成普通真人消息 | **附加能力补迁**，无需重写压缩引擎；具体接入写入正式接口 |
| E5：从新DSH消息分支 | 公开sessionController.fork复用底层inclusive event prefix/lineage且保留preset，事件seq不是Nano消息ID [A21] | 新会话的旧fork引擎 | message→seq和当时配置代次；产品新分支按历史配置装配，旧Nano历史不做兼容 | **新fork原生＋产品锚点**；问题7/8已按开发态撤销旧历史兼容 |
| E6：身份、指令、时间与prompt | section/context/variable/assemble、persona、AGENTS/嵌套指令原生；不保持四槽模板字节相同 [A22] | 固定四槽模板引擎、指令文件发现器 | PA/global身份与路由、来源/时间、Custom Instructions、MEMORY/USER业务注入；限定原指令roots，不用complete覆盖公共约束 | **原生装配＋保留产品内容**；模板顺序属于工程处理，不再逐字兼容旧prompt |
| F1：文件读写、编辑、搜索 | tool-fs、glob/grep、observation/CAS覆盖；长输出采用明确截断而非Nano超预算直接报错 [A23]、[N03] | 基础文件工具、观察缓存与通用结果处理 | workspace边界、名单与通用IM呈现；模型必须看见截断事实和后续读取方式 | **已确认直接原生**；Q21统一接受原生命名/参数和截断续读，迁移Skill引用 |
| F2：网页搜索/抓取/定向提取 | search/fetch provider seam与通用工具已有；DSH第一方无Nano DDG/Brave/SearXNG，tool fetch也无原prompt提取参数 [A24] | 通用fetch/格式处理/工具分发；不保留旧工具壳参数全集 | 现有search provider接公开seam；prompt提取做小consumer，保留不偷偷换源的规则；不为换核强换付费服务 | **骨架原生，后端/提取补迁**；具体已用服务与网络仍需核实 |
| F3：MCP、社区、自建工具/hooks | MCP stdio/HTTP、重连、namespace/tool sync与Cordis注册原生；Nano当前PA未发现真实MCP client，不能声称替换已有MCP引擎 [A25] | 接受原生扩展格式后退役旧Python工具loader；复用原生包管理 | 存量Python工具转TS plugin或作为Python程序由受管shell/MCP承载；旧Python hooks事件/timeout/fail-open逐项迁移，Claude/Codex hooks bridge不自动兼容它们 | **原生扩展标准已确认，两层均保留**；已找到的共享工具列入资产，不删除其用户功能 |
| L1：已有模型/协议/代理/reasoning | pi-ai支持catalog、baseURL、协议、contextWindow、reasoning及OAuth；无通用arbitrary extra_request_body配置 [A26] | 可退役旧Anthropic/OpenAI通用client、SSE与普通请求装配 | 先用现代理；将已用thinking映射到原生参数，无法表达的wire参数通过adapter/上游接口补迁；不是静默忽略 | **pi-ai为主路线**；实际代理参数等价待定向联调，原生OAuth是另一路径，不在本次强行改登录 |
| L2：错误重试与自动备用链 | llm-retry同模型retry已有，备用链/粘性/公开输出后不换缺失；同step retry不重新装配prompt [D16]、§7.6 | 普通backoff/retry与provider执行器 | Nano policy在同产品运行内衔接原生turn，重新装配路由/prompt/effort并采用目标窗口与原生overflow；详见§7.6 | **retry原生，fallback必须迁移**；本机未启用不等于可删除能力 |
| L3：用量、缓存与回复统计 | token-meter累积usage；inputTokens是uncached，cacheRead/cacheWrite另列 [A27] | 通用计量与上下文压力估计 | total input按不重叠buckets归一，再按业务reply归因；摘要/审核辅助调用维持原产品口径，不直接抄session总数 | **计量原生＋产品投影**；验证已用provider真实输出，不把缺失记成0 |

### 8.5 本机资产的有界核实

本轮仅定向读取本机默认配置的非敏感字段以及`~/.nanoassistant/tools`、`hooks`的目录/源码结构，没有扫描所有workspace或访问Mini运行态：

- 默认配置为Anthropic协议，经`127.0.0.1`代理，登记10个模型；配置了context window、reasoning和独立审批模型。`extra_request_body`已用顶层功能为thinking，实际wire对应仍待联调。不输出凭据、headers、URL query或具体参数值。
- 本机这份配置没有model_fallbacks，不据此推定其他节点不用，也不削掉产品备用链支持。模型名中的OAuth字样不是Nano内置认证provider；Nano当前factory只有openai_compat/anthropic。
- 共享tools目录有两个顶层Python文件：一个包含X/小红书/抖音读取与抖音下载工具，且依赖`agent.sdk.PermissionDecision`；另一个是用户自建reviewer工具。共享hooks目录存在，无顶层Python文件。这里只证明文件存在与依赖，不声称各Agent当前均已启用，也不推断workspace/其他节点为空。
- Nano核心/PA源码未发现MCP client实现。DSH MCP属于可直接利用的新扩展能力；现有外部CLI/Skills不能按名字误记为已配置MCP server。

正式资产转换清单仍须按owner/节点/数字人的已声明roots收集：工具和hook条目、Skill名称映射、模型实际路由、搜索后端、现有cron周期/锚点、数据及媒体数量。保留原文件，逐项转换并以用户任务验收；这属于确定范围的盘点，不要求再向用户确认是否搬迁已用能力。

### 8.6 原生新增能力不自动扩大迁移范围

反向盘点还找到下列能力。它们可以减少未来重复建设，但本次不能拿来冒充现有机制，也不为了“全量”全部打开：

- **goal/round-driver**：支持一个session内单一持久目标，重启后自动继续权限被解除，需要重新resume；不是多聊天、多目标责任记录，也不代替Heartbeat。可以用于单项长任务的未来增量，不替换本次必须迁移的主动机制。[A04]
- **webhook**：可信规则可创建新root session，但delivery ID不是去重执行保证，成功followup后不负责完成交付。可用来接新事件来源，不替代已有飞书/IM消息消费及发送账本。[A08]
- **ask_user_question/plan**：原生问题工具会等待回答，plan提供会话协作状态；适合单项交互，不能替代global“问完后继续其他聊天”的异步业务流程。该缺失流程继续保留；如启用原生问题工具，由产品提供UI answerer和取消/来源路由。[A09]
- **browser/computer-use、LSP、PTY、文档转换**：是社区复用增量，按实际工具需求与依赖启用；未核查的设备驱动/部署条件不写成现有PA已拥有。无需将它们变成本次必须完成的新产品。

## 9. 从核查进入完整迁移规划

本轮已经将关键“待验证接口”推进为明确的源码结论；整体安排见 [迁移规划](migration-plan.md)。当前应依次完成：

1. 用相同粒度覆盖产品接线与历史数据，尤其是全局/单聊群复核、后台结果、新DSH会话fork/蒸馏、客户端与多节点；旧聊天兼容已排除。
2. 把真正影响体验的选项写成“旧方式 → 原生方式 → 差异 → 保留成本原因”，请用户确认。以原生为优先，不因微小差异增设兼容层。
3. 依据确认结果再确定终态职责、插件划分、接口和数据方案，并编排迁移依赖、阶段退出证据、切换与回滚。
4. 实施后验证真实旅程、恢复和渠道交付。源码能力判断不需要先完成迁移；接入后的产品验收也不能由源码阅读代替。

此前“先跑五组实验，才能冻结插件方案”的排序撤回。运行实验仅用于无法由源码确定、且会改变设计的具体问题，或作为实施验收；当前不启动测试 Agent、不建立迁移运行环境。

## 10. 证据说明与索引

直接核查了 Nano current specs、PA 注册/配置、workspace resolver，以及 DSH 公开服务、实际工具入口和包装配。Workflow/子 Agent/jobs/Cron/Knowledge 的对照另经独立只读分析，纠正了“核心 README foreground only = 无后台 Workflow”和“child flat scope = 完全不继承 preset”这两种不准确推断。

前稿独立复核指出后台结果缺少持久来源。本轮另由两项独立只读任务复核公开接口和完整迁移范围，已吸收 child 审批可用公开初始化覆盖、同 step fallback 装配限制、最终结果非消费读取缺口，以及旧档案 fork/蒸馏、single_thread 群复核和切换资产遗漏。复核不再确认插件数量，也不是正式 Gate 2 审查。

“未找到等价机制”限于本固定版本第一方源码与文档，不代表全社区没有第三方实现。没有安装未知社区插件、修改生产配置或以模型调用验证替代体验。

| 编号 | 固定版本证据 |
|---|---|
| N01 | [PA工具注册、默认工具与搜索roots][N01] |
| N02 | [feature registry][N02] |
| N03 | [工具与Hooks current][N03] |
| N04 | [全局装配与workspace首次使用快照][N04] |
| N05 | [Agent能力、配置与Skill调和][N05] |
| N06 | [Skill完整current契约][N06] |
| N07 | [Skill使用、来源与批次阈值][N07] |
| N08 | [Memory文件更新机制][N08] |
| N09 | [自动review触发与真实更新][N09] |
| N10 | [上下文、持久化与图片][N10] |
| N11 | [后台任务current][N11] |
| N12 | [Workflow执行、控制、保存与恢复][N12] |
| N13 | [Workflow渠道与权限路由][N13] |
| N14 | [Cron与Heartbeat current][N14] |
| N15 | [模型运行current][N15] |
| N16 | [global Inbox与来源授权][N16] |
| N17 | [任务图current][N17] |
| D01 | [Tools注册、restrict、guard、PTC][D01] |
| D02 | [Web工具与provider边界][D02] |
| D03 | [持久插件管理与profile范围][D03] |
| D04 | [Agent preset注册、revision和scope][D04] |
| D05 | [Agent公共创建、恢复与setup][D05] |
| D06 | [子Agent模式、消息与恢复][D06] |
| D07 | [MCP client机制与scope][D07] |
| D08 | [Skill文件发现与变化][D08] |
| D09 | [指令文件与上下文机制][D09] |
| D10 | [第三方Memory示例的明确边界][D10] |
| D11 | [显式fresh-agent Ralph循环][D11] |
| D12 | [进程内jobs实现][D12] |
| D13 | [Workflow模型工具含后台路径][D13] |
| D14 | [Schedule原session与持久投递][D14] |
| D15 | [pi-ai模型路由与OAuth][D15] |
| D16 | [同模型retry而非Nano fallback策略][D16] |
| D17 | [压缩机制][D17] |
| D18 | [实验Auto的来源识别和历史筛选][D18] |
| D19 | [动态扩展的session/进程内限制][D19] |

源码细节补充：

- [自建工具对象的Python导出协议](https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/platform/tools/loader.py#L116)。
- [SkillRegistry分层合并](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/skill/README.md#L1)。
- [原生Skill目录替换与加载结果](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/tool-skill/README.md#L1)。
- [指令文件候选拒绝路径分隔符](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/context/agent-instructions/src/config.ts#L119)。
- [原生Auto说明与PTC限制](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/experimental/auto-review/README.md#L1)。
- [child preset继承与never审批](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/subagent/subagent/src/child-agent.ts#L179)。
- [continuable child完成时检查live parent](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/subagent/subagent/src/continuation-activation.ts#L871)。
- [jobs完成通知](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/jobs/tool-jobs/src/index.ts#L271)。
- [Workflow handle的result/cancel/dispose](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/workflow/src/runtime-types.ts#L40)。
- [Workflow JS编排与值传递](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/workflow-ptc/src/runtime.ts#L179)。
- [Schedule到期执行路径](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/schedule/schedule/src/runtime.ts#L85)。
- [Nano resume完成前缀策略](https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/platform/workflows/manager.py#L229)。
- [Nano Skill批次review](https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/platform/background/skill_batch_review.py#L57)。
- [持久Session flush屏障](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/session/session-persistence/src/index.ts#L118)。

[N01]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/personal_assistant/product.py
[N02]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/core/agent/prompt_sections/feature_registry.py
[N03]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/kernel/tools-hooks.md
[N04]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/sdk/kernel.py
[N05]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/gateway/agent-capabilities.md
[N06]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/kernel/skills.md
[N07]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/core/skills/usage.py
[N08]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/core/memory/store.py
[N09]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/platform/hooks/builtins/self_improvement.py
[N10]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/kernel/context-persistence.md
[N11]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/kernel/background-tasks.md
[N12]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/kernel/workflows.md
[N13]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/gateway/workflows.md
[N14]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/gateway/heartbeat-cron.md
[N15]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/kernel/model-runtime.md
[N16]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/gateway/global-agent.md
[N17]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/gateway/task-graphs.md
[D01]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/tools/README.md
[D02]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/web/tool-web/README.md
[D03]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/boot/plugin-manager/README.md
[D04]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/preset/agent-preset-registry/README.md
[D05]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent/src/index.ts
[D06]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/subagent/subagent/README.md
[D07]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/mcp/mcp-client/README.md
[D08]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/skill-filesystem/README.md
[D09]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/context/agent-instructions/README.md
[D10]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/docs/user/guide/mcp-memory.md
[D11]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/tool-ralph/README.md
[D12]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/jobs/jobs-local/src/index.ts
[D13]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/tool-workflow/src/index.ts
[D14]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/schedule/schedule/README.md
[D15]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/llm/llm-pi-ai/README.md
[D16]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/llm/llm-retry/README.md
[D17]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/compaction/compaction/README.md
[D18]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/experimental/auto-review/src/index.ts
[D19]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/extensions/cordis-host-runner/README.md

[S01]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/tools/src/index.ts#L1093
[S02]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/skill/src/index.ts#L390
[S03]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/workflow/src/index.ts#L82
[S04]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/jobs/jobs/src/types.ts#L156
[S05]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/experimental/auto-review/src/index.ts#L178
[S06]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/subagent/subagent/src/child-agent.ts#L179
[S07]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/agent.ts#L399
[S08]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/preset/agent-preset-registry/src/index.ts#L329
[S09]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/web/web/src/index.ts#L97
[S10]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/session/src/index.ts#L1180
[S11]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/workflow-ptc/README.md#L59

进一步实现定位：

- [工具局部/共享覆盖的现有测试](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/tools/tests/scoped.spec.ts#L61)、[FileSystemSkillProvider](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/skill-filesystem/src/index.ts#L150)、[Skill 最终集合合并](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/skill/src/index.ts#L549)。
- [Workflow 完整结果 handle](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/workflow/src/runtime-types.ts#L40)、[jobs 一次性结果读取](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/jobs/jobs-local/src/index.ts#L440)、[后台 Workflow 完成链](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/workflow/tool-workflow/src/index.ts#L274)。
- [Auto 审核模型构造](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/experimental/auto-review/src/index.ts#L617)、[唯一 Auto integration 注册](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/interaction/permission-presets/src/index.ts#L307)。
- [公开审批 policy 更新](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/interaction/user-approval/src/index.ts#L100)、[首次工作前等待 agent/created](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent/src/index.ts#L173)、[公开 prompt assembly](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/system-prompt/src/index.ts#L20)。
- [模型选择捕获时机](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent/src/model-selection.ts#L81)、[同 step retry 分支](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/agent.ts#L494)。
- [Inbox claim](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/inbox.ts#L109)、[官方 requestId 查询](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/api/session-controller/src/commands.ts#L602)、[中断日志恢复](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/index.ts#L838)。

[A01]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/personal_assistant/product.py#L494
[A02]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/README.md
[A03]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/gateway/routing-delivery.md#L500
[A04]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/goal/goal/src/index.ts#L255
[A05]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/deliverables/tool-present/src/index.ts#L90
[A06]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/docs/specs/gateway/agent-capabilities.md#L289
[A07]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/boot/plugin-manager/README.md
[A08]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/webhook/webhook/README.md
[A09]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/interaction/tool-ask-user/src/index.ts#L99

[A10]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/schedule/schedule/src/index.ts#L29
[A11]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/schedule/schedule/src/index.ts#L213
[A12]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/schedule/schedule/src/runtime.ts#L85
[A13]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/subagent/subagent/src/continuation.ts#L97
[A14]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/agent-loop/src/agent.ts#L154
[A15]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/jobs/tool-jobs/src/index.ts#L256
[A16]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/tools/src/index.ts#L1559
[A17]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/interaction/user-approval/src/index.ts#L107
[A18]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/experimental/auto-review/src/index.ts#L618

[A19]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/compaction/compaction-basic/src/index.ts#L148
[A20]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/compaction/compaction-basic/src/index.ts#L377
[A21]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/session/src/index.ts#L1236
[A22]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/system-prompt/src/index.ts#L450
[A23]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/fs/tool-fs/src/index.ts#L53
[A24]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/web/web/src/index.ts#L97
[A25]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/mcp/mcp-client/src/index.ts#L47
[A26]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/llm/llm-pi-ai/src/config.ts#L89
[A27]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/llm/token-meter/src/usage-projection.ts#L21

[A28]: https://github.com/Mrchen116/nano-multiagent/blob/4915c44cb7f7b829414a19087877ad9b73d69ea1/src/agent/platform/hooks/builtins/auto_mode_policy_assets/cc-2.1.267-nano-v1/defaults.json
[A29]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/experimental/auto-review/src/index.ts#L39

[A30]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/tools/src/index.ts#L1057
[A31]: https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/tools/tests/scoped.spec.ts#L61

# feat-798 浏览器与桌面控制设计

## Changelog

## 当前接线与职责

基线见 [spec](spec.md)。Node 管理 Gateway 并把 macOS 应用包加入 PATH，安装脚本已有 Cua 0.38.0 校验；PA 分发的 Cua 手册目前指导 Agent 走 Bash。ConfigurationScopes.attachPreset 在插件发现后注册产品工具，ToolSelection 负责目录和可调用集合。NanoApproval 通过 tools/pre-execute 在原生 dispatch 前判定，支持分类、人工反馈、取消与来源核实。LocalWorkers 持有 root Agent、Worker activation、私有报告桥和关闭通知。

Node 负责本机配对和工具安装；DSH integration 负责任务归属、产品工具 dispatch、后端 stdio 客户端和退出回收；PA 分发使用说明，并在已认证入站处提供当前人类发送者的原文。CLI、安装和发布包沿用现行机制。无需新建 HTTP 控制端口、修改 DSH 或迁移用户数据。

## 任务与连接

节点本机 CLI 增加 browser pair/status/disconnect，并在 Web IM（`POST /im/v1/nodes/:node_id/browser` 经 `node.browser.request` 瞬时转发，`Cache-Control: no-store`、不落库、不记日志，覆盖电脑详情抽屉与助手勾选 `computer_use` 时的就地状态提示）以及 Crewden Desktop「这台电脑」（经 `apps/desktop` 本地回环与 `local-admin browser` 按 `owner_id` 门禁桥接）共用同一套可视化配对组件。引导流不读取系统剪贴板、不让模型接触凭据：触发引导时按选定 Profile 检查官方扩展（0.5.0+），未安装则打开官方商店页并在检测到扩展落盘后自动打开扩展 Token 管理页（0.6.0+ 为 `manage.html`，兼容 0.5.x `status.html`），已安装则直接打开 Token 页；用户手动填入 Token（兼容整行 `PLAYWRIGHT_MCP_EXTENSION_TOKEN=…` 与裸值），原子写入当前用户 `0600` 私有节点配置目录，免重启即时生效。状态区分配置存在、连接已验证、失效和平台不可用；探测结果不得包含 token。Gateway 启动只交付私有路径，token 仅交给当前任务的扩展子进程。隔离轨显式选择，按任务创建临时 profile。固定浏览器后端依赖进入 release 的依赖清单，隔离轨使用本机 Chrome 或 Chromium。

宿主维护 root 当前交办或 CLI activation 的 seat。每个 seat 懒启动独立 Playwright MCP 客户端，只暴露该客户端拥有的标签页。扩展轨要求支持独立 tab group 与后台连接的官方扩展版本；缺少能力时返回升级引导。连接日常 Chrome 前从当前进程与安装元数据核实浏览器已运行、Chrome 至少 158.0.8127.2、选定 Profile 的官方扩展至少 0.5.0；缺任一项直接给升级或启动引导。这样才可同时后台打开连接页与任务页。连接日常 Chrome 前验证浏览器运行状态，避免冷启动把窗口带到前台。后台动作验收观察前台应用及后台页面的实际输入和更新；锁定版本必要的焦点模拟只作用于本 seat 自己的页面。关闭只释放本客户端与其创建的标签；隔离轨还释放浏览器进程与临时 profile。取消中的写操作不重放；等待当前发送者退出后再释放 seat。运行中断后的重复启动只清理由节点创建且可核实所属实例的资源。

桌面走现有 CuaDriver.app 的标准 MCP 代理，保留系统已授予应用的 TCC 身份；status 用无提示权限检查，报告需要开启的权限。首次选择窗口由宿主核对当前任务授权与实际应用标识、PID 和窗口 ID；成功后绑定 seat。窗口切换、进程重启或权限撤回清除绑定。只在绑定窗口中观察、滚动、输入；司机拒绝后台投递时返回可恢复原因。用户切换到另一应用后停止有冲突的输入，绝不自动提升到前台。工作区的旧 Shell 调用仍受现有策略管理，产品操作手册优先引导已启用的共享工具。

## 单次 dispatch 与最小工具面

新增可选的 computer_use 工具，默认关闭，产品目录与 ToolSelection 对齐。关闭时普通 Global、PA 和无工具委派无新增 schema。启用时仅公开简短的操作入口；describe 按轨列出支持的动作和形状，status 返回能做什么和下一步。模型可见示例为「日常 Chrome 尚未配对。请主人在设置 → 电脑（/settings/nodes?pair_browser=1）连接日常 Chrome 后重试；需要干净环境时选择 isolated。」不会在系统提示或 Skill 元数据里重复工具目录。状态与快照只在请求时返回，有界的截图沿用原生图片输出。状态丢失后重新观察，恢复的历史 ref 无效。

DSH 直接进入已注册工具。授权委派才在现有私有本地桥中挂载固定名称的操作工具；绑定可信 root、activation 和 signal，调用方不能自报身份、覆盖 server 命令或传后端环境。桥通过 DSH 公开 tools.resolve/execute 进入同一工具与宿主审批，携带宿主生成的调用 ID，与普通主会话 seat 区分。派工、取消和 toolset 释放分别由 LocalWorkers 与 DSH 的既有生命周期管理。对照并行 feat-797 的 hostedWorkerMcp 注册表，仅提供精确的工具名与 launch 配置，保留所有原生 CLI 提权行为。当前 develop 如缺该注册表，独立抽取同等最小注册接口，合并基线时收敛为一份；不复制 797 其余状态机。

一次调用依次完成参数形状和目标范围核实、NanoApproval 判定、执行前重新比对目标、投递一次、回传。审批读取 seat 掌握的 URL、标题、目标 ref/窗口与控件说明，区分宿主观察与不可信页面正文。拒绝、取消或过期时不投递。允许名称清单由宿主持有；不透传原生 MCP 任意工具、脚本、启动参数或会话身份。浏览器明确区分 tabs.list/select 与打开/关闭；快照、截图、已分配页的控制台与网络摘要只读，排除凭据、请求正文及任意文件输出参数。点击、输入、指定新 URL 和上传受审，上传限任务准入文件。桌面状态只返回授权窗口的观察；移动/滚动仅支持后台窗口参数；审核过的纯导航快捷键按 seat、PID、窗口、规范化按键、短时有效期复用。跨窗、组合写入及改变焦点失效。这里的“0ms”按调用审核模型零次验收；工具执行本身有耗时。

## 剪贴板与原始用户输入

浏览器会话有自己的内存剪贴板；宿主只支持在 seat 内复制可见内容和粘贴已知文本，浏览器 MCP 不开放系统剪贴板接口。系统读取独立为一次性桌面动作。PA single-thread 在组装 quotes、成员、卡片和历史之前，给每条已认证的人类消息填 directHumanText，仅取当前发送者自己的 input.message.content；宿主要求直接发送者 actorId 与本节点已绑定的 ownerId 一致。普通 Global Inbox 在 PA 侧从真实 read(session,call) 的选中原始 RelayInput 判定：完整的同一消息、sender_type=user、sender_user_id 与节点 ownerId 一致，且为此 Agent 的直聊或明确 @其 agentId 的群消息。通过已提交读取的 session/call/message 关联把资格交给宿主，不要求普通 Global 提供 PA 专有字段。PA 另需 personal_delivery=participant。协作者、被观察到的消息、代理代发、未知身份和只有渠道关联账号相同的消息均不能授权节点资源。同一句「把我刚复制的内容整理一下」分别由主人和协作者发送时，仅主人原话得到一次资格；直接输入从这一字段取，缺失的旧输入不能授予新资格；Global Inbox 从本进程真实读取的、面向当前 Agent 的完整主人交办取。复用现有来源身份，不信任页面、历史回放、委派转述或调用方自填的原话。明确肯定的请求如「把我刚复制的内容整理一下」产生一次读取资格，引用、否定、转述和无法确认的表达不产生资格。未命中时说明原因和可直接使用的明确请求。仅在根会话明确启用 computer_use 时，delegate_worker.start 才增加可选的 computer_request_ref；它指向根会话本轮已获取的真实交办。宿主校验原始消息身份、所属会话、当前轮次、目标及操作范围后，将引用绑定到此次 activationId；父 Agent 选择消息不能创造权限。普通委派不挂载工具；新的 activation 必须重新绑定。剪贴板资格由 root 和被绑定的单一 Worker 共用，按真实原始消息 ID 作唯一键。宿主在首次异步读取前占用；并发、失败重试、恢复、结束后均不能再次取新值。关闭能力、撤回指令或结束当前 activation 使未用资格失效。只交付该次读取结果，审计记录动作和来源标识，省略剪贴板内容。系统剪贴板始终只按调用时的值读取。

## 验证与交付

| Milestone | 依赖与并行 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1 共享宿主操作 | 单一集成 milestone | Node CLI/lifecycle、release、技能、integration、能力目录、局部 Worker MCP 注册及相应测试 | [reviewer] 从产品入口分别走默认 Chrome、隔离 Profile、桌面窗口、单次剪贴板和三种 Worker；核对拒绝无副作用与恢复行为。[worker] 通过真实 stdio MCP 和 DSH dispatch 记录 scope、读写审核次数、实际目标、回收状态以及关闭/启用的出站请求差异。 |

用同版本 Playwright 与独立测试账号/配置验证双 seat；登录态验证只能使用为测试配置的扩展和测试站点。使用唯一命名的可丢弃窗口和合成剪贴板内容测试并发消费。M1 覆盖普通 Global 的真实 Inbox 中主人与协作者的同文对照、未填原文字段的旧输入、普通单条直聊、仅引用含指令、两条交办并发派工、旧浏览器连接前停止，以及能力关闭时委派工具 schema 无增量。先运行窄契约测试，再检查发布产物、冷启动及停止。agent-context-review 阅读同一任务能力关闭/启用/工具结果后的实际出站请求和下一步动作；模型可见摘要不包含 token，截图原件存仓外。代码审查核对当前工具审批与能力契约、delta 和未验证项。新增条款见 [能力](specs/gateway/agent-capabilities.md) 与 [审批](specs/gateway/tool-approval.md)。

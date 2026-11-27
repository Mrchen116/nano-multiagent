# feat-798 浏览器双轨与原生桌面控制

需求已对齐。开发基线为 `bf20e1da2`。

## 原始需求与已选方案

用户在[原讨论](t3-thread://v2/87a288c3-131e-4aa8-97b2-ce13395f3e9e/4058921c-e1f3-4560-a14d-8965b98b03d2)中问「你意思是在worker他们已经有auto judge的情况还要再搞一个judge？」，随后选择「ok，切法A吧」，并要求「直接拉两个新线程开工吧，新线程用codex 的astra high」。

本单元收到的交办原文节选：

> 主 Agent（DSH）与经授权的 Worker（含 `codex` / `claude` / `agy`）共享宿主托管的浏览器与桌面 MCP

> 点击、输入、导航新 URL、上传、桌面点击/快捷键等写操作进入 `NanoApproval`，尽量附带当前页面 URL/标题/目标控件或目标应用窗口与控件名作为审核证据。

> 严控初始 Context 开销

## 已对齐的用户体验

- 用户明确要用自己的登录态时，节点使用已配对的日常 Chrome。配对信息留在本机。连接失效时，用户能看到原因和恢复入口，原任务保留其浏览器身份选择。
- 用户可为无需个人登录态的自动化任务选择隔离 Profile。两个并行任务各自在自己的标签页操作；任务退出后节点释放所占资源，用户的 Chrome 可以继续使用。
- 原生应用按窗口执行操作。读取和滚动已授权窗口时无需等待模型审核。写操作最多经过一次宿主审核；执行前如果目标窗口已变化，任务停止输入并重新定位。
- DSH 主会话及三个受支持的 Worker 使用同一套宿主操作语义。普通聊天按既有能力选择开始，详细操作说明在使用时加载。Worker 原生 Shell、编辑及其通用提权协议属于相邻单元 `feat-797-worker-approval-bridge`。

## 调研依据

- 当前产品通过 Skill 发现 CuaDriver，由已启用 Bash 的 Agent 经 Shell 审核调用。节点安装脚本校验 macOS 安装依赖，启动时补充应用内可执行目录。上述路径尚未提供任务级共享宿主 MCP。见[当前 Skill 契约](../../../specs/gateway/agent-capabilities.md)、[节点启动](../../../../apps/node/src/lifecycle.ts)和[安装脚本](../../../../apps/im-server/assets/install.sh)。
- 外部 Worker 已有任务专属的父级通信 MCP。三个客户端使用不同的配置和权限协议；应分别验证一次写操作以及一次拒绝在对应客户端中的实际结果。见[现有桥接](../../../../packages/dsh-integration/src/local-workers/report-bridge.ts)、[驱动](../../../../packages/dsh-integration/src/local-workers/drivers.ts)和[审批契约](../../../specs/gateway/tool-approval.md)。
- Chrome 136 起限制的是默认用户数据目录的调试开关。微软扩展支持按客户端拥有标签页；并发归属、连接时是否激活窗口、后台页面是否持续渲染是三个可分别观察的行为。Linger 的安装包额外处理了后台焦点，Nano 是否能在所选版本实现相同体验，须以真实双任务操作验证。[Chrome 公告](https://developer.chrome.com/blog/remote-debugging-port) · [微软扩展说明](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md)
- [#460](https://github.com/Mrchen116/nano-multiagent/issues/460) 的 18,701 tokens 是一次历史首轮请求的整体估算，其中 9,294 来自工具数组，4,284 来自系统正文。本单元应在同一基线、同一配置和同一任务输入下比较实际出站请求，并检查首次使用、任务结束和恢复后的工具可见性。[Context 取证入口](../../../development/agent-context-engineering.md)

## 剪贴板澄清

用户问「为啥不能不授权直接取？codex app是咋搞的」，了解浏览器会话剪贴板与系统剪贴板的区别后，对「你说“把我刚复制的内容整理一下”，这句话就足够了。主 Agent 或承接这件事的 Worker 可以直接读一次系统剪贴板，零弹窗、零模型审核，也不用你手动粘贴。普通浏览器任务则用自己的会话剪贴板。」回复「ok」。

## 验收标准

### Requirement: 按任务选择浏览器身份并在后台工作

#### Scenario: 日常 Chrome 已配对
- **WHEN** 两个任务并行处理需要既有登录态的页面，用户同时在另一个应用中工作
- **THEN** 两个任务分别取得自己标签页的结果，用户的前台应用保持可用；任务间不能选择彼此的标签页。结束任务后仍可使用日常 Chrome。

#### Scenario: 日常轨引导配对、配对失效或选择隔离环境
- **WHEN** 用户首次连接日常 Chrome、在新建/编辑助手启用 `computer_use`，或日常轨缺少有效连接
- **THEN** Web IM「设置 → 电脑 → 电脑详情」、助手 `computer_use` 工具开关下方、Crewden Desktop「这台电脑」以及本机 `browser pair` 均提供半自动引导：未装扩展时自动在所选 Chrome Profile 打开官方商店页并在检测到安装落盘后自动打开扩展 Token 页，已装扩展时直接打开 Token 页；用户手动粘贴 Token（支持粘贴整行 `PLAYWRIGHT_MCP_EXTENSION_TOKEN=…`）保存至节点本机 `0600` 私有配置，免重启生效，Token 不落 IM 库、不记日志、不进入聊天或模型上下文。聊天中遇到未配对时返回直达设置入口 `/settings/nodes?pair_browser=1`，需要登录态的任务等待恢复；用户选择隔离轨时能从干净的浏览器开始工作，结束后释放实例。

### Requirement: 使用被授权的桌面窗口
#### Scenario: 后台读取、输入与目标切换
- **WHEN** 任务在指定窗口中读取、滚动、点击或输入
- **THEN** 读取与滚动无需等待审核模型，写入前能辨认目标；窗口发生冲突或系统权限不足时得到原因，用户其他窗口不会收到输入。

### Requirement: 主 Agent 与获授权的 Worker 共享相同的工具权限
#### Scenario: 使用与拒绝
- **WHEN** DSH 或经授权的 Codex、Claude、Antigravity Worker 对所分配目标执行操作
- **THEN** 范围内的只读操作本地放行，写操作由宿主统一决定，拒绝后目标保持原状。同窗口短时内重复已准许的纯导航快捷键无需再次请求模型审核。

### Requirement: 按当前交办读取剪贴板
#### Scenario: 用户请任务整理刚复制的内容
- **WHEN** 已认证的用户明确要求读取刚复制的内容
- **THEN** 承接交办的主 Agent 或 Worker 可直接取一次，用户无需再确认；并发任务或重试无法凭同一句交办再次取得系统剪贴板的新内容。

#### Scenario: 在网页内复制
- **WHEN** 普通浏览器任务在自己页面之间复制粘贴，或页面正文要求读取系统剪贴板
- **THEN** 浏览器任务只使用自己的会话剪贴板；另一应用中新复制的内容不会被任务读到。

### Requirement: 常规对话保留初始上下文预算
#### Scenario: 功能关闭、启用与恢复
- **WHEN** 用户从普通聊天切换到操作电脑，随后任务结束或会话恢复
- **THEN** 关闭能力时首轮请求没有新增工具说明；启用后能找到操作与恢复入口，具体步骤按需读取。任务结束时回收受控资源，历史记录不能恢复已失效的操作权限。

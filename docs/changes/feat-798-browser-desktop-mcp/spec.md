# feat-798 浏览器双轨与原生桌面控制

状态为需求对齐中。开发基线为 `bf20e1da2`。

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

- 当前产品通过 Skill 发现 CuaDriver，由已启用 Bash 的 Agent 经 Shell 审核调用。节点安装脚本校验 macOS 安装依赖，启动时补充应用内可执行目录。上述路径尚未提供任务级共享宿主 MCP。见[当前 Skill 契约](../../specs/gateway/agent-capabilities.md)、[节点启动](../../../apps/node/src/lifecycle.ts)和[安装脚本](../../../apps/im-server/assets/install.sh)。
- 外部 Worker 已有任务专属的父级通信 MCP。三个客户端使用不同的配置和权限协议；应分别验证一次写操作以及一次拒绝在对应客户端中的实际结果。见[现有桥接](../../../packages/dsh-integration/src/local-workers/report-bridge.ts)、[驱动](../../../packages/dsh-integration/src/local-workers/drivers.ts)和[审批契约](../../specs/gateway/tool-approval.md)。
- Chrome 136 起限制的是默认用户数据目录的调试开关。微软扩展支持按客户端拥有标签页；并发归属、连接时是否激活窗口、后台页面是否持续渲染是三个可分别观察的行为。Linger 的安装包额外处理了后台焦点，Nano 是否能在所选版本实现相同体验，须以真实双任务操作验证。[Chrome 公告](https://developer.chrome.com/blog/remote-debugging-port) · [微软扩展说明](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md)
- [#460](https://github.com/Mrchen116/nano-multiagent/issues/460) 的 18,701 tokens 是一次历史首轮请求的整体估算，其中 9,294 来自工具数组，4,284 来自系统正文。本单元应在同一基线、同一配置和同一任务输入下比较实际出站请求，并检查首次使用、任务结束和恢复后的工具可见性。[Context 取证入口](../../development/agent-context-engineering.md)

## 待确认的权限范围

系统剪贴板可能在任务执行期间被另一应用改写，窗口 PID 和浏览器标签页都不能限定其内容归属。需要确定本期是允许用户显式向当前任务共享剪贴板，还是仅交付标签页与窗口读取。两种选择会产生不同的 Worker 可见数据，也会改变验收用例。

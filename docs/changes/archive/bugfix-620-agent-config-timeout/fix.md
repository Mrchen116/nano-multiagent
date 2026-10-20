# bugfix-620: Agent 配置等待确认时连接被切断并显示网关 HTML

## Relations

- Related: feat-616、feat-394 Agent 配置回执与待应用恢复。
- Lifecycle: Bugfix lite，唯一 milestone `M1-fix`。

## 原始报告

用户：“随便选一下还会报错。”
附件：`codex-clipboard-17090077-5fde-4274-99cd-8f51932f6938.png`。生产 `/settings/agents/personal-agent` 保存区展开整页 Cloudflare 502 HTML，挤占配置界面。

后续用户询问“这个能力当时为啥引进？”。用户随后明确要求：“PA在机器之间迁移这个功能也先去掉，还没设计成熟”。本次一并撤回 PA 专用换机入口与接口，不迁移现有 PA 或工作区，不扩展成数据搬家能力。

## 现象 / 复现

- 生产中心在 `2026-10-20T01:10:47.966Z` 持久化 `personal-agent` 的配置 apply operation，节点侧配置文件在约 17ms 后持久化，节点回执最终为 applied，但中心仍为 pending。
- Cloudflare Tunnel 在 `2026-10-20T01:11:02Z` 对同一 `/im/v1/agents/personal-agent/config` 请求记录源站 EOF。IM 原进程继续存活，调查时 loopback/public 均为 200；不是字段非法或整个进程崩溃。
- 隔离真实 HTTP 复现：现有 createServer 下，配置 GET 的节点响应延迟 16 秒，客户端在 15024ms 收到 `UND_ERR_SOCKET`，未收到 HTTP/JSON 结果。该复现只替换隔离节点响应，不访问生产账号或数据。
- 用户期望：配置操作能够得到应用成功、待确认或明确失败的 HTTP 结果；等待确认不能被误报为网络断连。真正的非 JSON 网关错误应显示简短且随语言切换的提示，不能展示 HTML，不能自动重发有副作用的修改。

## 根因

- IM HTTP 服务器把 `connectionTimeout` 设置为 15000ms。该 socket inactivity timeout 也作用于完整请求已收到、业务正在等待的阶段。既有配置 receipt 流程可能经过多次各 10 秒的节点 RPC，或等待此前配置操作；业务返回前连接已被服务器销毁，Tunnel 因源站 EOF 生成 502。原意是限制公网请求，但与既有配置恢复契约不相容。`requestTimeout` 与 bodyLimit 才负责限制接收请求；keepAliveTimeout 管理空闲复用连接，两者需要保留。
- 前端 Agent 配置 requestJson 在 JSON 解析失败时直接使用 rawBody 作为 Error.detail；通用 authFetchJson 同样把整段响应正文拼入错误。页面直接展示这些字符串，因此 Cloudflare HTML 被当作用户提示展开。原意是保留业务错误详情，缺少 JSON 业务响应与代理错误页面的边界。
- 已有测试保护即时配置 ACK、持久 receipt 和局部错误状态，但没有覆盖真实 HTTP 连接等待超过 15 秒，或代理返回 HTML 的输入。生产节点变慢的具体起因未确认；本次修复不声称解释全部节点延迟。

## 修复

- 移除业务处理期间的 15 秒 socket inactivity 截断；保留 requestTimeout、bodyLimit、keepAliveTimeout，配置回执和原有 RPC 超时/恢复逻辑继续负责业务结果。
- Agent 配置与通用认证 JSON 请求共用一个 JSON 业务错误读取函数；代理 HTML/非业务错误仅展示本地化短提示及状态码，保留业务 code、agent_id 和结构化 pending 信息，不增加 mutation 自动重试。
- 按用户后续决定撤回 PA 换机：移除页面控件、客户端 helper、专用 POST restore 路由及唯一调用的 restorePersonal；保留普通配置/设备管理和已有数据库绑定，不执行任何数据迁移。移除旧换机交互测试，改为断言已撤下的接口不会改绑定或触发节点请求。
- 同步 current IM 配置与 PA 契约。

## 验证

- Red：真实配置 HTTP 在 15 秒被关闭；HTML 和结构化 pending 的 3 条前端新增用例失败。
- Green：16 秒节点响应经真实 HTTP 返回 200；后台窄测试 34 条通过；前端配置、认证及 PA 设置窄测试 58 条通过，覆盖保存报错后编辑内容保留、无自动重发、旧换机接口 404 且绑定不变。
- 全量：后端 104 文件 / 449 测试；前端 100 文件 / 936 测试；非 E2E Python 62 测试通过。根 build/typecheck、Web build、ruff check/format、docs-check 通过。旧 Chat 错误测试改为真实 JSON 业务响应，原 operation label 与业务消息断言保留；新 HTML 输入由共享最低层测试保护。
- 独立 code review：full 核对 `a4c4b1b3..7a4f53763`，patch 核对 `7a4f53763..e2cc070d7`，无存活 findings，详见 `code-review.md`。
- 真实浏览器：隔离 IM 数据库、账号、工作区及端口 54842，正常登录并打开 PA 配置；即使有两台在线电脑也没有迁移入口。反向代理对一次保存返回 HTML 502，页面只展示中文短提示，显示名编辑保留，计数确认只有一次 PATCH；手动重试成功，刷新后新名称与 v2 保留。
- 浏览器 evidence 位于本地 `data/acceptance/bugfix-620/config-error.png` 与 `config-saved.png`，不提交截图/fixture。该验收的节点回执为可控 fixture，仅证明 UI/HTTP 交互；真实 TCP 超时由长期后端测试覆盖，不宣称验证了真实模型或生产保存。自建服务与浏览器页已清理。
- 主仓 dirty/untracked 内容保留；复用本任务已附着、干净的 worktree 从最新 main 建专属 bugfix 分支，未在 dirty main 创建产品提交。

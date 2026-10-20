# bugfix-620: Agent 配置等待确认时连接被切断并显示网关 HTML

## Relations

- Related: feat-616、feat-394 Agent 配置回执与待应用恢复。
- Lifecycle: Bugfix lite，唯一 milestone `M1-fix`。

## 原始报告

用户：“随便选一下还会报错。”
附件：`codex-clipboard-17090077-5fde-4274-99cd-8f51932f6938.png`。生产 `/settings/agents/personal-agent` 保存区展开整页 Cloudflare 502 HTML，挤占配置界面。

后续用户询问“这个能力当时为啥引进？”。已说明更换电脑用于恢复同一 PA 身份，但入口取舍不属于本次报错修复；不删除或扩展换机能力。

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

待 M1-fix 回填。

## 验证

待 M1-fix 回填。

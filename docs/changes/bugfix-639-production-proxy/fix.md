# bugfix-639: 持久代理配置必须作用于正式业务客户端与公网验收

## Relations

- Related: PR #387（Node 24.22.1 双机升级）、feat-542（Gateway 稳定运行环境）、refactor-581（Node/DSH 迁移）。
- 单一 `M1-fix`，Bugfix lite；按用户要求复用 `codex/node24-security` worktree 与现有 PR，不另建实施分支。

## 原始报告

用户在主对话要求：“那就两台统一升级到 24.22.1 LTS，Brotli、自启配置和仓库 CI 也一起处理，完成后验证公网 IM 和两个节点的真实回复。”

随后侧聊向主对话转交要求：“让主 thread 改下吧，彻底解决这个问题。”转交的明确澄清为“正式服务默认走代理”；需覆盖真实 HTTP/fetch、WebSocket、DSH/工具、登录自启和与业务相同出口的验收，并保留直连失败证据。侧聊是 ephemeral thread，历史接口不可读取；这里保留转交来源，不冒充完整逐字对话。

已确定范围：正式 HTTP/fetch、WebSocket、DSH/工具及公网验收使用各机现有普通代理，本机/内网直连。用户明确指出社区用户通常不开 TUN，因此取消候选 TUN 策略，不更改两机 Clash 配置。Cloudflare Tunnel 属于中心部署组件，其 QUIC 路径不能用 HTTP_PROXY 假装已代理；不把这一特殊组件变成社区客户端的前提。

## 现象 / 复现

- 升级后两节点能经公网完成一次真实回复，但 Air 仍有 `fetch failed` 与直接访问官网的连接超时；变量存在与一次回复不能证明全部正式客户端使用了代理。
- `gateway.environment` 在 Node 模块导入后才写入 `process.env`。如果 HTTP 全局 agent 或 fetch dispatcher 已初始化，随后设置 `NODE_USE_ENV_PROXY=1` 不会刷新已创建的客户端。
- macOS 登录服务不能继承交互终端中的代理；Mini Gateway 未显式持久配置现有代理，Air 虽有配置，也不能以此证明既有 HTTP 客户端已重新路由。
- 运行中的 Mini `prod-tunnel.py` 与开发主仓未跟踪副本 SHA256 相同：`73bad73df9683598a40ad2579f52a58628f59a61b8923f7d91557bfd6d4d278d`。公网探针明确 `trust_env=False`，runbook 示例明确 `curl --noproxy '*'`，检查的是直连路径。
- 侧聊只读对照显示：IPv4 直连曾在已收到 200 后正文仍为 0 字节并超时；IPv6 或既有代理可完整成功。不能把这些失败统一归因为 Cloudflare 平台或 Tunnel 故障。
- 代码回归复现应先初始化原生 HTTP/fetch 客户端，再应用配置，用本地代理接收原本不可直连的 HTTP 与 WebSocket 请求，并检查 NO_PROXY 的本机请求直接到达原服务。

## 根因

1. **配置应用只改环境，没有更新已创建的网络客户端。** `apps/node/src/lifecycle.ts` 的 `applyGatewayEnvironment` 自 `58c1ff99ee`（Node/DSH 迁移）起只赋值 `process.env`。Node 官方提供运行时 `http.setGlobalProxyFromEnv()`，可同步刷新 HTTP、HTTPS 和原生 fetch；当前代码未使用它。
2. **WebSocket 与 QUIC 存在独立绕过。** ws 设置自己的 createConnection；未显式传 agent 时不会使用刷新后的 HTTPS 全局 agent。Feishu SDK 和 WebRelay 都需通过公开参数传入该 agent。QUIC 是 UDP，HTTP_PROXY 无法接管。
3. **生产配置与交互 shell 混用。** 正式自启依赖 config，而部分验收与手工调用依赖临时 shell 变量；二者不能互相证明。工具子进程也必须继承经过配置确定的代理和 NO_PROXY。
4. **公网检查与业务出口不一致，且失败层被混合报告。** 当前 supervisor 的 loopback readiness、Tunnel 路径/QUIC 指标与外部 HTTPS 探针混在一份 snapshot 中，外部 HTTPS 又被强制直连；正式业务代理成功时仍可因独立直连失败被误判为 Tunnel 不健康。

原设计意图来自 `docs/changes/archive/feat-542-gateway-autostart/design.md:99`：稳定环境由本地配置拥有，配置覆盖继承环境；不能把 shell 快照或配置秘密复制到 plist。该不变量继续保留。修复应在进程读取配置后、业务请求发出前，通过公开 Node API 应用网络路由；不复制秘密到服务定义，不绕过 TLS 验证，不 fork/patch DSH，不增加第二套运行时或网络降级路径。

成功标准：正常和受管启动使用同一配置；HTTP/fetch、WebSocket、DSH/工具的公网请求有实际代理路径证据；本机/内网 NO_PROXY 通过；代理失败明确失败且不静默直连；正式公网页面/API/实时连接连续检查通过，两节点经公网完成真实模型回复与持久 completed 回执。

## 修复

- 配置应用后调用公开 http.setGlobalProxyFromEnv，刷新已初始化 HTTP/HTTPS 与原生 fetch；WebRelay 与 Feishu WebSocket 显式传全局 agent。稳定环境仍由 config 拥有，不复制到 plist。
- 最低 Node 收口为已修补的 24.22.1（保留 26.12.1 线），移除缺少上述 API 的 22 线；@types/node 更新至 24.19.2。
- 两 Gateway 与 Mini IM launcher 持久配置大小写普通 HTTP 代理环境与 NO_PROXY，无 TUN 依赖。DSH 的 ALL_PROXY 必须为 HTTP URL；实测 SOCKS URL 会警告并为该 scheme 直连，因此不配置 SOCKS URL。
- 已核对的 supervisor 纳入版本管理；保留 QUIC/IPv6 和 readiness 恢复，保留既有 QUIC/IPv6 路径条件与四连接检查。公网 HTTPS 默认读服务 config 并消费完整正文。
- --public-only 供 Air 检查相同业务出口；--direct-diagnostic 仅绕过应用 HTTP 代理，不进入正式业务验收。既有失败证据保留，各失败层分开记录。
- 同步 Gateway canonical spec、生产拓扑与部署 Skill/runbook。

## 验证

- 修复前已复现真实失败：仅写环境时 HTTPS/fetch 目标 ENOTFOUND；刷新原生代理后，未传 agent 的 WSS 阶段仍 ENOTFOUND。
- Node 窄回归通过：真实本地 CONNECT + TLS 校验，初始化后的 HTTPS/fetch、实际 WebRelay、继承环境的 Node 工具均成功；loopback 不入代理，代理不可用明确 ECONNREFUSED。
- Python CLI 的真实 CONNECT/TLS 回归 3 项通过：持久配置覆盖 shell、完整正文、缺失配置拒绝、代理失败不静默直连且不误报 Tunnel。
- 本地构建/typecheck/iOS runtime 检查通过；Node 121 文件/576 测试，Python 非 E2E 65 项通过；ruff 与 docs-check 通过。
- 生产源码 e54d7d2d84495747a3eba1809a0195e53b77db0c；对应远端 CI run 39892638228 的后端、前端、iOS detection/build/tests 全部 success。
- 两机正式 Gateway/DSH 使用 Node24.22.1，自启 CLI 确认 enabled；state 与 LaunchAgent PID 一致、ready/connected=true；Brotli补丁 -17。公网持久 HTTP 代理环境生效，TUN=false，Clash 原配置文件哈希未变。
- 官网真实会话：Mini 输入 f09008d61fa64b0db1442d66fe0b61dd → 回复 227e30eaf37440efb44e6385bcb9ce2a；Air 输入 65220d8a21444680ba2e799f639caca6 → 回复 0f8326ff42664dba964001a5d9e922d9。两者均实际执行 curl，HTTP200/15bytes，消息与relay/receipt全completed。
- Air 11:21:29–11:21:58、Mini 11:27:27–11:27:57 的配置代理页面/API连续样本均200，正文分别538/15bytes；浏览器真实实时回复成功。采样只证明该窗口，不能外推无限稳定。
- Mini 原日本Z03节点经同机TLS探针超时，其他既有节点通过；现有选择组切到新加坡Z01后上述连续门禁通过。未启用TUN或修改Clash规则；该选择由其既有 store-selected 持久化。
- 保留失败边界：最初IM切换期间Air因relay未ready退出，由LaunchAgent恢复并完成原输入；Mini恢复早期有relay-notready日志。早期SOCKS ALL_PROXY配置已改HTTP。旧出口的代理TLS失败与独立QUIC关闭计数增长均保留，不归因为模型或统一归因Cloudflare。
- 独立code review按实际返回结果收口；未收到结论前不伪造完成。生产截图、运行态与失败记录在本机 output/proxy-20261023/，不入Git。

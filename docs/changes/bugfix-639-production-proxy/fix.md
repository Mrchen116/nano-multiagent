# bugfix-639: 持久代理配置必须作用于正式业务客户端与公网验收

## Relations

- Related: PR #387（Node 24.22.1 双机升级）、feat-542（Gateway 稳定运行环境）、refactor-581（Node/DSH 迁移）。
- 单一 `M1-fix`，Bugfix lite；按用户要求复用 `codex/node24-security` worktree 与现有 PR，不另建实施分支。

## 原始报告

用户在主对话要求：“那就两台统一升级到 24.22.1 LTS，Brotli、自启配置和仓库 CI 也一起处理，完成后验证公网 IM 和两个节点的真实回复。”

随后侧聊向主对话转交要求：“让主 thread 改下吧，彻底解决这个问题。”转交的明确澄清为“正式服务默认走代理”；需覆盖真实 HTTP/fetch、WebSocket、DSH/工具、登录自启和与业务相同出口的验收，并保留直连失败证据。侧聊是 ephemeral thread，历史接口不可读取；这里保留转交来源，不冒充完整逐字对话。

已确定范围：两机现有代理作为默认公网出口；loopback 与应直连内网保留 NO_PROXY；公网正式验收使用同一持久配置。用户随后直接澄清所有公网流量都走代理，包括海外 Cloudflare，本地请求可以直连。因此两机使用既有 Clash TUN 接管不读取代理变量的流量，公网规则统一代理，本机/局域网/Tailscale 直连；Mini Tunnel 保持 QUIC/IPv6，实际连接改走 TUN，并执行恢复验证与 600 秒稳定门禁。

## 现象 / 复现

- 升级后两节点能经公网完成一次真实回复，但 Air 仍有 `fetch failed` 与直接访问官网的连接超时；变量存在与一次回复不能证明全部正式客户端使用了代理。
- `gateway.environment` 在 Node 模块导入后才写入 `process.env`。如果 HTTP 全局 agent 或 fetch dispatcher 已初始化，随后设置 `NODE_USE_ENV_PROXY=1` 不会刷新已创建的客户端。
- macOS 登录服务不能继承交互终端中的代理；Mini Gateway 未显式持久配置现有代理，Air 虽有配置，也不能以此证明既有 HTTP 客户端已重新路由。
- 运行中的 Mini `prod-tunnel.py` 与开发主仓未跟踪副本 SHA256 相同：`73bad73df9683598a40ad2579f52a58628f59a61b8923f7d91557bfd6d4d278d`。公网探针明确 `trust_env=False`，runbook 示例明确 `curl --noproxy '*'`，检查的是直连路径。
- 侧聊只读对照显示：IPv4 直连曾在已收到 200 后正文仍为 0 字节并超时；IPv6 或既有代理可完整成功。不能把这些失败统一归因为 Cloudflare 平台或 Tunnel 故障。
- 代码回归复现应先初始化原生 HTTP/fetch 客户端，再应用配置，用本地代理接收原本不可直连的 HTTP 与 WebSocket 请求，并检查 NO_PROXY 的本机请求直接到达原服务。

## 根因

1. **配置应用只改环境，没有更新已创建的网络客户端。** `apps/node/src/lifecycle.ts` 的 `applyGatewayEnvironment` 自 `58c1ff99ee`（Node/DSH 迁移）起只赋值 `process.env`。Node 官方提供运行时 `http.setGlobalProxyFromEnv()`，可同步刷新 HTTP、HTTPS 和原生 fetch；当前代码未使用它。
2. **WebSocket 与 QUIC 存在独立绕过。** ws 设置自己的 createConnection；未显式传 agent 时不会使用刷新后的 HTTPS 全局 agent。Feishu SDK 和 WebRelay 都需通过公开参数传入该 agent。QUIC 是 UDP，HTTP_PROXY 无法接管；原两机 Clash TUN 均未开启，旧 supervisor 还要求 en0 路径。
3. **生产配置与交互 shell 混用。** 正式自启依赖 config，而部分验收与手工调用依赖临时 shell 变量；二者不能互相证明。工具子进程也必须继承经过配置确定的代理和 NO_PROXY。
4. **公网检查与业务出口不一致，且失败层被混合报告。** 当前 supervisor 的 loopback readiness、Tunnel 路径/QUIC 指标与外部 HTTPS 探针混在一份 snapshot 中，外部 HTTPS 又被强制直连；正式业务代理成功时仍可因独立直连失败被误判为 Tunnel 不健康。

原设计意图来自 `docs/changes/archive/feat-542-gateway-autostart/design.md:99`：稳定环境由本地配置拥有，配置覆盖继承环境；不能把 shell 快照或配置秘密复制到 plist。该不变量继续保留。修复应在进程读取配置后、业务请求发出前，通过公开 Node API 应用网络路由；不复制秘密到服务定义，不绕过 TLS 验证，不 fork/patch DSH，不增加第二套运行时或网络降级路径。

成功标准：正常和受管启动使用同一配置；HTTP/fetch、WebSocket、DSH/工具的公网请求有实际代理路径证据；本机/内网 NO_PROXY 通过；代理失败明确失败且不静默直连；正式公网页面/API/实时连接连续检查通过，两节点经公网完成真实模型回复与持久 completed 回执。

## 修复

- 配置应用后调用公开 http.setGlobalProxyFromEnv，刷新已初始化 HTTP/HTTPS 与原生 fetch；WebRelay 与 Feishu WebSocket 显式传全局 agent。稳定环境仍由 config 拥有，不复制到 plist。
- 最低 Node 收口为已修补的 24.22.1（保留 26.12.1 线），移除缺少上述 API 的 22 线；@types/node 更新至 24.19.2。
- scripts/prod_proxy_policy.js 作为既有 Clash 全局扩展：TUN + 私网直连 + 公网 MATCH 到现有选择节点。保留订阅和节点，持久开启 TUN/登录自启；两 Gateway 与 Mini IM launcher 持久配置大小写代理环境及 NO_PROXY。
- 已核对的 supervisor 纳入版本管理；保留 QUIC/IPv6 和 readiness 恢复，前置路径改为实际 TUN，snapshot 额外要求四条 cloudflared UDP 7844 具有非 DIRECT 代理链与双向字节。公网 HTTPS 默认读服务 config 并消费完整正文。
- --public-only 供 Air 检查相同业务出口；--direct-diagnostic 仅绕过应用 HTTP 代理，TUN 开启时仍受系统路由接管，不能称为物理直连。既有失败证据保留，各失败层分开记录。
- 同步 Gateway canonical spec、生产拓扑与部署 Skill/runbook。

## 验证

- 修复前已复现真实失败：仅写环境时 HTTPS/fetch 目标 ENOTFOUND；刷新原生代理后，未传 agent 的 WSS 阶段仍 ENOTFOUND。
- Node 窄回归通过：真实本地 CONNECT + TLS 校验，初始化后的 HTTPS/fetch、实际 WebRelay、继承环境的 Node 工具均成功；loopback 不入代理，代理不可用明确 ECONNREFUSED。
- Python CLI 的真实 CONNECT/TLS 回归 3 项通过：持久配置覆盖 shell、完整正文、缺失配置拒绝、代理失败不静默直连且不误报 Tunnel。
- 其余门禁与生产实测完成后在此回填精确版本和结果。

# bugfix-639: 持久代理配置必须作用于正式业务客户端与公网验收

## Relations

- Related: PR #387（Node 24.22.1 双机升级）、feat-542（Gateway 稳定运行环境）、refactor-581（Node/DSH 迁移）。
- 单一 `M1-fix`，Bugfix lite；按用户要求复用 `codex/node24-security` worktree 与现有 PR，不另建实施分支。

## 原始报告

用户在主对话要求：“那就两台统一升级到 24.22.1 LTS，Brotli、自启配置和仓库 CI 也一起处理，完成后验证公网 IM 和两个节点的真实回复。”

随后侧聊向主对话转交要求：“让主 thread 改下吧，彻底解决这个问题。”转交的明确澄清为“正式服务默认走代理”；需覆盖真实 HTTP/fetch、WebSocket、DSH/工具、登录自启和与业务相同出口的验收，并保留直连失败证据。侧聊是 ephemeral thread，历史接口不可读取；这里保留转交来源，不冒充完整逐字对话。

已确定范围：两机现有代理作为正式业务的默认公网出口；loopback 与应直连内网保留 NO_PROXY；公网正式验收使用同一持久配置，直连只作为显式诊断。Tunnel 的 QUIC/UDP 路径独立核实，不把 HTTP_PROXY 变量当作 Tunnel 已代理的证据；其传输变更按实际授权范围与能力另做对应门禁。

## 现象 / 复现

- 升级后两节点能经公网完成一次真实回复，但 Air 仍有 `fetch failed` 与直接访问官网的连接超时；变量存在与一次回复不能证明全部正式客户端使用了代理。
- `gateway.environment` 在 Node 模块导入后才写入 `process.env`。如果 HTTP 全局 agent 或 fetch dispatcher 已初始化，随后设置 `NODE_USE_ENV_PROXY=1` 不会刷新已创建的客户端。
- macOS 登录服务不能继承交互终端中的代理；Mini Gateway 未显式持久配置现有代理，Air 虽有配置，也不能以此证明既有 HTTP 客户端已重新路由。
- 运行中的 Mini `prod-tunnel.py` 与开发主仓未跟踪副本 SHA256 相同：`73bad73df9683598a40ad2579f52a58628f59a61b8923f7d91557bfd6d4d278d`。公网探针明确 `trust_env=False`，runbook 示例明确 `curl --noproxy '*'`，检查的是直连路径。
- 侧聊只读对照显示：IPv4 直连曾在已收到 200 后正文仍为 0 字节并超时；IPv6 或既有代理可完整成功。不能把这些失败统一归因为 Cloudflare 平台或 Tunnel 故障。
- 代码回归复现应先初始化原生 HTTP/fetch 客户端，再应用配置，用本地代理接收原本不可直连的 HTTP 与 WebSocket 请求，并检查 NO_PROXY 的本机请求直接到达原服务。

## 根因

1. **配置应用只改环境，没有更新已创建的网络客户端。** `apps/node/src/lifecycle.ts` 的 `applyGatewayEnvironment` 自 `58c1ff99ee`（Node/DSH 迁移）起只赋值 `process.env`。Node 官方提供运行时 `http.setGlobalProxyFromEnv()`，可同步刷新 HTTP、HTTPS 和原生 fetch；当前代码未使用它。
2. **生产配置与交互 shell 混用。** 正式自启依赖 config，而部分验收与手工调用依赖临时 shell 变量；二者不能互相证明。工具子进程也必须继承经过配置确定的代理和 NO_PROXY。
3. **公网检查与业务出口不一致，且失败层被混合报告。** 当前 supervisor 的 loopback readiness、Tunnel 路径/QUIC 指标与外部 HTTPS 探针混在一份 snapshot 中，外部 HTTPS 又被强制直连；正式业务代理成功时仍可因独立直连失败被误判为 Tunnel 不健康。

原设计意图来自 `docs/changes/archive/feat-542-gateway-autostart/design.md:99`：稳定环境由本地配置拥有，配置覆盖继承环境；不能把 shell 快照或配置秘密复制到 plist。该不变量继续保留。修复应在进程读取配置后、业务请求发出前，通过公开 Node API 应用网络路由；不复制秘密到服务定义，不绕过 TLS 验证，不 fork/patch DSH，不增加第二套运行时或网络降级路径。

成功标准：正常和受管启动使用同一配置；HTTP/fetch、WebSocket、DSH/工具的公网请求有实际代理路径证据；本机/内网 NO_PROXY 通过；代理失败明确失败且不静默直连；正式公网页面/API/实时连接连续检查通过，两节点经公网完成真实模型回复与持久 completed 回执。

## 修复

## 验证

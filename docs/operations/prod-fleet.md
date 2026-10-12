# 生产舰队（IM@mini + 双 Gateway）

> 版本切换说明：本页现有 Python launcher/运行记录是 DSH 切换前的生产拓扑快照。refactor-581 的合并不代表已部署；首次切换必须先完成 [DSH 资产迁移](dsh-migration.md)，再按部署 skill 更新为 Node launcher。保留 Mini 唯一 IM、双节点 owner 和公网域名等拓扑约束。

本文描述个人生产拓扑：Mac mini 跑唯一 IM，MacBook Air 与 Mac mini 各跑一个常驻 Gateway，均连同一 IM。Agent 执行部署/重启时的逐步命令与局部动作表见 [`.claude/skills/prod-fleet-deploy/SKILL.md`](../../.claude/skills/prod-fleet-deploy/SKILL.md)。单机开发的一次性主链路见 [`local-stack.md`](local-stack.md)；worktree 隔离见 [`../development/worktree-runtime.md`](../development/worktree-runtime.md)。

## 拓扑

```text
                           任意设备的浏览器
                                  │ HTTPS / WSS
                                  ▼
                     Cloudflare · im.nanoim.win
                     HTTPS 入口；HTTP → HTTPS 308
                         ▲                 │
                   HTTPS / WSS        加密 Tunnel
                         │                 │
┌────────────────────────┴──────────┐      │
│ MacBook Air · jmacbook-air        │      │
│ Tailscale: 100.92.244.68          │      │
│                                   │      │
│ Gateway · node_id=macbook-air     │      │
│   │ HTTP → 127.0.0.1:4000         │      │
│   ▼                               │      │
│ LLM_PROXY :4000                   │      │
│                                   │      │
│ No IM on this host                │      │
└───────────────────────────────────┘      │
                                           ▼
┌────────────────────────────────────────────────────────────┐
│ Mac mini · Tailscale: 100.88.34.122 · ssh: mini            │
│                                                            │
│ cloudflared · nano-im-public                               │
│   │ HTTP → 127.0.0.1:8011                                  │
│   ▼                                                        │
│ IM :8011 (only IM; loopback only)                          │
│   ▲ HTTP / WS → 127.0.0.1:8011                             │
│   │                                                        │
│ Gateway · node_id=mac-mini ── HTTP ──▶ LLM_Bridge :4000    │
│   │                                  127.0.0.1:4000        │
│   └── Search → 127.0.0.1:8888 ──▶ SearXNG :8888            │
│                                      ▲                     │
└──────────────────────────────────────┼─────────────────────┘
                                       │ Tailscale / :8888
                          macbook-air Gateway 的搜索请求
```

约束：

- MacBook Air **禁止**再起 IM `:8011`；正式 Web IM 入口为 `https://im.nanoim.win/`；源站只监听 Mini loopback，不以 Tailscale `:8011` 作为用户入口。
- 两边 `node_id` 必须不同；后连同名会踢掉先连。
- 两边 Gateway 使用同一个 IM owner；`node.user_id` 必须是该用户的 **IM UUID**（`GET /im/v1/me`），不能是用户名或占位符。错了会出现飞书能回、内部 IM 看不到影子会话。
- mini 上 LLM 走 `LLM_Bridge`；MacBook Air Gateway 走 MacBook Air 的 `LLM_PROXY`。两边 SearXNG 都指向 mini `:8888`。
- 两边 Gateway 的 `gateway.autostart` 保持默认开启，稳定的 SearXNG 地址写入各机 `gateway.environment.SEARXNG_URL`；不要依赖一次重启命令前的 inline 环境。

## 节点身份

| 机器 | `node_id` | `im_service.url` | LLM 代理 |
|---|---|---|---|
| Mac mini | `mac-mini` | `http://127.0.0.1:8011` | `~/Repos/LLM_Bridge` → `:4000` |
| MacBook Air | `macbook-air` | `https://im.nanoim.win` | `~/Repos/LLM_PROXY` → `:4000` |

各机使用各自的 `~/.nanoassistant/config.yaml`，保留独立设备密钥与已绑定的节点运行凭据。普通发布不重新 bind，也不恢复旧账号密码认证方式。`node.user_id` 对齐与飞书影子会话验收步骤见 skill 验证清单。

## 源站与隧道

官网与 Mini 上的 IM 是同一套服务。更新 Mini 主仓代码、重建前端并重启受管 IM 后，官网使用新版本；无需创建第二套公网实例。

| 项目 | 当前生产配置 |
|---|---|
| 公网入口 / `IM_PUBLIC_URL` | `https://im.nanoim.win` |
| IM LaunchAgent | `io.github.mrchen116.nano-multiagent.public-im` |
| IM launcher | Mini `~/.nanoassistant/bin/run-public-im.sh` → 主仓 `.venv/bin/python -m IM.cli.public_server` |
| 源站 / worker | `127.0.0.1:8011` / 1 |
| 生产数据库 | Mini `~/Repos/nano-multiagent/data/im_service.sqlite3` |
| 附件 | 数据库旁 `message-images/` 与 `data/uploads/`，保留原目录及元数据 |
| Tunnel LaunchAgent | `io.github.mrchen116.nano-multiagent.public-tunnel` |
| Tunnel | `nano-im-public`，配置 `~/.cloudflared/nano-im-public.yml` |
| ingress | `im.nanoim.win` → `http://127.0.0.1:8011`，最后兜底 404 |
| HTTPS 强制规则 | Cloudflare Single Redirect `IM — Force HTTPS`：仅该主机 HTTP → HTTPS，308，保留路径/query/请求方法 |
| 日志 | Mini `~/.nanoassistant/public-im.log`、`~/.nanoassistant/public-tunnel.log` |

两个 plist 均位于 Mini `~/Library/LaunchAgents/`，启用 RunAtLoad/KeepAlive。常规发布复用 launcher、plist、Tunnel 凭据和 DNS；不得用旧 `nohup uvicorn --host 0.0.0.0` 替换。TLS 在边缘终止，源站 loopback HTTP 是预期拓扑。

公网规则不随 Git 代码发布而重建，但每次完整发布必须验证仍有效。308 不是 HSTS；当前未配置 HSTS，不得在验收中把二者混为一谈。账号准入、签名密钥、设备身份及数据库恢复是独立操作，普通 Feature 发布不重复首次迁移。

## 日常入口

| 任务 | 去做 |
|---|---|
| 全量更新代码并重启舰队 | 触发 `prod-fleet-deploy` 完整闭环 |
| 只重启 IM / 某一侧 Gateway / LLM 代理 | 同一 skill 的「局部动作」表 |
| 改 Gateway 配置 | 目标机先 `stop`，改 config，再启动；运行中直接编辑可能被 token 回写覆盖，细节见 [`gateway.md`](gateway.md) |
| 排障 | [`troubleshooting.md`](troubleshooting.md)；结合两边 `gateway.log` 与 IM `~/.nanoassistant/public-im.log` |

mini 的 IM 签名密钥是生产持久状态：`~/.nanoassistant/im-jwt-secret`（权限 `0600`）。常规更新在停止 IM 前读取并复用它，不能临时生成。需要主动换钥时才覆盖这个文件；换钥会使 Web IM 既有登录态失效，它与 Gateway 的节点运行凭据是不同身份边界，不应因此自动重新 bind 或重建节点身份。首次从旧目录升级时，先执行 [`PA workspace layout migration`](pa-workspace-layout-migration.md)，再按 [`prod-fleet-deploy` skill](../../.claude/skills/prod-fleet-deploy/SKILL.md) 完成启停与验收。

## 可用性判断

同时满足才视为舰队正常：

1. `https://im.nanoim.win/` TLS 验证通过并返回 200，本次前端资源及相关真实页面正确；HTTP 首页与登录 POST 均 308 跳转至同主机 HTTPS，保留路径/query。
2. 经官网认证的 `GET /im/v1/nodes` 中两个生产节点均为 `online` 且心跳新鲜；真实浏览器实时连接正常。
3. IM/Tunnel LaunchAgent 正常、源站只监听 Mini `127.0.0.1:8011`；MacBook Air 无 IM `:8011`。
4. 两边 `node.user_id` 等于 `GET /im/v1/me` 的用户 id；gateway 日志无持续的 `configured node owner differs`。
5. 两边 LaunchAgent 均已加载；plist、live process 与 `.gateway-state.json` 都指向本次部署的 checkout 和同一 PID/process birth。MacBook Air 旧 production worktree 只能在这些证据成立后清理。

## 飞书

保持现有节点的通道归属，不在常规部署中自动迁移或删除。2026-10-02 正式切换时 Mini 和 MacBook Air 都存在既有飞书通道；后续以 IM desired state 和实际节点注册为准，不能再按旧“仅 Mini”假设修改生产配置。

## IM 用户访问入口配置

IM 启动必须显式设置 `IM_PUBLIC_URL` 为用户实际打开 Web IM 的 HTTP(S) 绝对 URL；允许部署路径前缀，不允许凭据、query 或 fragment。它与 Gateway 的内部 `im_service.url` 独立。IM 在已认证的 `node.register` ACK 下发 `im_user_url`，Gateway 注册完成前不会启动依赖 IM 的 PA 工作；重连期间保留最近一次认证的入口，下一轮会话 runtime 使用新入口。

Gateway YAML 的 `node.execution_access_address` 可选，填写执行设备供用户访问的主机名或 IP（不含协议、端口、路径或凭据）；缺失时省略提示中的该行。此值仅提供访问事实，不开放监听端口、不授予文件权限，也不保证用户能访问任意服务。

升级前保留原配置并为 IM 增加 `IM_PUBLIC_URL`，先升级 IM 再升级 Gateway。旧 IM 未下发入口时，新 Gateway 报配置/版本不匹配，不采用内部连接地址猜测。回退代码时可保留新增环境变量；此配置说明不授权执行生产部署。

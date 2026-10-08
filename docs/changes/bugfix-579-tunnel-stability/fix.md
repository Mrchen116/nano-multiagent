# bugfix-579: 生产 Tunnel 固定代理路径与健康恢复

## 原始报告

- 用户：“我要实际解决这个管道稳定性问题”。
- 用户：“做稳定后，还要更新部署skill，提pr，要确保以后都是稳定的路径来部署”。

## 现象 / 复现

2026-10-08，源站 `127.0.0.1:8011` 正常，公网却返回 530/1033。原 Tunnel 的 IPv4 TCP 7844 连接持续超时，进程存活不能证明公网可用。改为 IPv6 HTTP2 后恢复。

为确定生产出口，检查 Mini live socket、路由与 Clash API：原 Tunnel 经 en0 直连；系统 HTTP/SOCKS 代理没有接管它。限定 Cloudflare 两个 Tunnel IPv4 网段的 TUN 转发后，同一固定日本 Z03 节点上，HTTP2 多次 TLS EOF，QUIC 则注册四条连接，Clash 显示 UDP 7844 双向流量。代理重启后配置保留且连接恢复。但受管 Tunnel 一次 QUIC 启动陷入持续握手超时，重新启动进程后恢复，暴露出进程存活时缺少健康恢复的问题。

## 根因

原生产管理依赖 launchd KeepAlive，只覆盖进程退出；没有验证实际出口，也没有处理存活但 `/ready` 503 的 Tunnel。仅配置系统代理不会改变 cloudflared 的原始 TCP/UDP 拨号路径。现有部署验收缺少固定节点、TUN 路由与真实代理流量的交叉核对，无法阻止未代理或未完成握手的路径进入生产。

本次不推断 IPv4 超时的运营商/路由根因；修复实际可控制的出口和恢复边界。保留现有 Tunnel 身份、DNS、HTTPS、Mini 唯一 loopback IM、原数据库与双 Gateway 身份。唯一 milestone 为 `M1-fix`；现有产品 API 无 spec delta。

## 修复

- 持久化 Mini 的限定 TUN 路由与固定 Z03 规则，代理重启后保留；既有 Tunnel 改为 QUIC/IPv4，保留原身份、源站与数据。
- 原 Tunnel LaunchAgent 运行 `scripts/prod_tunnel.py` 的 supervisor runtime copy；检查出口，阻止丢失代理路径后的直连，自动替换存活但持续不健康的子进程。增加 Clash 登录自启依赖。
- 部署 Skill、runbook、生产舰队及两级文档入口指向同一运行门禁；以生产子 PID 对齐的四条双向 QUIC 流和公网 HTTPS 为验收依据，完整部署须持续采样 600 秒。

### 测试策略

搜索 `tests/` 中 public/health/watchdog/deployment 相关覆盖后，没有既有测试守护 cloudflared 的出口与进程身份。新增 `tests/unit/test_prod_tunnel.py`：从 CLI 的退出状态和受管子进程替换结果保护错误出口、其他 connector 掩盖生产失败、错误节点及存活但不健康恢复。真实恢复由生产演练交叉验证，mock 不替代现场证据。现有 IM、Gateway 与 Agent 测试没有被替代或删除。

本次为生产操作配置与运维门禁，不改变产品 API；no spec delta。

## 验证

- 5 项聚焦测试通过；全仓 Ruff check/format、`git diff --check` 与 staged documentation integrity 通过。
- 代理 GUI/内核重启后，限定 TUN 路由和固定规则仍生效，候选 connector 自动重连；候选随后停止，正式验收只看原受管服务子 PID。
- 23:53 暂停正式 cloudflared 子 PID 23872，supervisor 自动替换为 24012；59.53 秒后四条固定代理流及 HTTPS 200 恢复，无人工重启。
- 23:55 暂时关闭专用 TUN：6.14 秒内子进程停止，恢复 TUN 后总计 19.11 秒重连为 PID 24144，并通过真实路径门禁。
- 持续 600 秒公网/路径采样、独立 code review 和远端 CI 是最终交付门禁；结果在执行后记录。

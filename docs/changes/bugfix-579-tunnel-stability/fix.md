# bugfix-579: 生产 Tunnel QUIC/IPv6 路径与健康恢复

## 原始报告

- 用户：“我要实际解决这个管道稳定性问题”。
- 用户：“做稳定后，还要更新部署skill，提pr，要确保以后都是稳定的路径来部署”。

## 现象 / 复现

2026-10-08，源站 `127.0.0.1:8011` 正常，公网却返回 530/1033。原 Tunnel 的 IPv4 TCP 7844 连接持续超时，进程存活不能证明公网可用。改为 IPv6 HTTP2 后恢复。

同一 Mini、cloudflared 2026.3.0、Tunnel 身份和源站进行实际 connector 对比：系统代理没有接管原始拨号；IPv4 固定 Z03 代理上的 HTTP2 握手反复 EOF，QUIC 虽能注册，但连续验收出现四连接超时与公网 502，不能作为稳定部署路径。核对真实路由又发现 Clash 在仅设置 IPv4 route-address 时仍创建 IPv6 默认路由；此前带 TUN 的 IPv6 比较不能算直连证据。

关闭测试 TUN 的 IPv6 接管后，确认 IPv6 目的地址实际走 en0、Clash 无候选 PID 的 IPv6 代理流。IPv6 QUIC 成功建立四条 LAX 连接，作为新的连续验收候选。

## 根因

原生产路径为 IPv4/TCP 7844 直连，出现持续超时；本次实际对比排除了源站故障，并观察到代理 UDP 路径也有断连。尚无证据把网络失败进一步归因于某运营商或国内位置。

可控制的管理缺陷是 launchd KeepAlive 只覆盖进程退出，无法恢复存活但 `/ready` 503 的 Tunnel；部署验收没有对齐生产 PID、实际路由与连接健康，临时 connector 可掩盖失败。

保留现有 Tunnel 身份、DNS、HTTPS、Mini 唯一 loopback IM、原数据库与双 Gateway 身份。唯一 milestone 为 `M1-fix`；现有产品 API 无 spec delta。

## 修复

- 原 Tunnel 改为已实测的 QUIC/IPv6 en0 路径；不再依赖测试代理/TUN，将其配置恢复到改动前。
- 原 Tunnel LaunchAgent 运行 `scripts/prod_tunnel.py` 的 supervisor runtime copy；路由漂移时等待，自动替换退出或存活但持续不健康的子进程。
- 部署 Skill、runbook、生产舰队及两级文档入口指向同一门禁；核对生产 PID 的 metrics listener、四个 IPv6 UDP socket、四条 HA 与双向计数，以及公网 HTTPS。完整部署持续采样 600 秒，PID 替换或断连计数增加也使窗口失败。

### 测试策略

搜索 `tests/` 中 public/health/watchdog/deployment 相关覆盖后，没有既有测试守护 cloudflared 的出口与进程身份。新增 `tests/unit/test_prod_tunnel.py`：从 CLI 退出状态和受管子进程替换结果保护错误协议/家族、TUN 路由漂移、其他 connector 掩盖生产失败、缺失双向流量和存活但不健康恢复。连续窗口通过断连计数捕获采样间重连。真实恢复由生产演练交叉验证，mock 不替代现场证据。现有 IM、Gateway 与 Agent 测试没有被替代或删除。

本次为生产操作配置与运维门禁，不改变产品 API；no spec delta。

## 验证

- QUIC/IPv6 版本聚焦测试 10 项通过；全量及独立审查在冻结版本后执行。
- 代理 QUIC 的 600 秒 gate 在公网 502 时失败，未按稳定路径交付。
- 原代理 supervisor 的现场演练验证了暂停进程后自动替换、TUN 丢失时停子进程；最终 IPv6 路径仍须单独演练。
- IPv6 QUIC 连续观察、最终受管服务 600 秒采样、独立 code review 与远端 CI 为交付门禁；结果在执行后记录。

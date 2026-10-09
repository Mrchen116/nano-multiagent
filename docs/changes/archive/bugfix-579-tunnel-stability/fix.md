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
- 部署 Skill、runbook、生产舰队及两级文档入口指向同一门禁；核对生产 PID 的 metrics listener、四个 IPv6 UDP socket、四条 HA 与双向计数，以及公网 HTTPS。普通公网服务部署短时间采样 30 秒，Tunnel 路径、协议、cloudflared 版本、恢复机制变更或其故障恢复采样 600 秒；Gateway/LLM 局部更新按影响范围验收，纯文档不做运行验收。采样窗口内 PID 替换或断连计数增加也使窗口失败。

### 测试策略

搜索 `tests/` 中 public/health/watchdog/deployment 相关覆盖后，没有既有测试守护 cloudflared 的出口与进程身份。新增 `tests/unit/test_prod_tunnel.py`：从 CLI 退出状态和受管子进程替换结果保护错误协议/家族、TUN 路由漂移、其他 connector 掩盖生产失败、缺失双向流量和存活但不健康恢复。连续窗口通过断连计数捕获采样间重连。真实恢复由生产演练交叉验证，mock 不替代现场证据。现有 IM、Gateway 与 Agent 测试没有被替代或删除。

本次为生产操作配置与运维门禁，不改变产品 API；no spec delta。

## 验证

- `a187723a4` 全量非 E2E Python：`pytest -m "not e2e" -n 4 --dist worksteal -q`，4,129 passed（92.84 秒）。指标格式修复 `510ffb2e4` 的 11 项聚焦测试通过；该后续变更由最低层 CLI 回归与 closure 复审保护，保留全量证据。
- 代理 QUIC 的 600 秒 gate 在公网 502 时失败，未按稳定路径交付。
- 最终 QUIC/IPv6 现场演练：00:24 暂停正式子 PID 25974，自动替换为 26218，56.55 秒后完整 gate / HTTPS 200 恢复；00:25 结束子 PID 26218，7.98 秒自动恢复为 26262。源站未重启。
- 候选 en0 IPv6 QUIC 在 00:12–00:22 连续观察 600 秒通过：四条 HA、无重注册/错误、公网全 200；随后清理候选，最终受管 PID 26262 于 00:26:04–00:36:03 通过 `--seconds 600`（退出码 0）：54 次采样全 HTTPS 200、HA=4、en0、closed_connections=0、PID 未变化。原始 JSONL 留在 Mini `~/.nanoassistant/tunnel-579-final-acceptance.jsonl`。
- 源/runtime SHA256 均为 `73bad73df9683598a40ad2579f52a58628f59a61b8923f7d91557bfd6d4d278d`；原 LaunchAgent 已加载该 supervisor，Mini 只留一个 cloudflared，Clash TUN 已关闭并恢复本次字段，既有代理选择保留。公网 HTTP GET/POST 均 308 保留路径/query，源站首页 200，两节点 owner 一致且持续 online。
- 本地 Ruff check/format、docs-check 与 diff-check 通过；完整前端 86 文件 / 808 测试通过。交付所需 `npm audit --audit-level=critical` 实际被旧 Tinypool 的两项 critical 阻塞，因此仅对 Vitest 的 Tinypool 固定 2.1.2 并更新该锁文件叶子，随后再次 808 passed，audit 0 critical。Vitest 主版本与 CI Node20 不变；依赖变更不部署到 Mini，本次生产 runtime 不受影响。
- 远端 CI 是最后交付门禁，创建 PR 后核对实际结果。

## 独立 code review

- executed_base：`d87ffa3d19160d45d309f281b0ace4ff92f55a38`。
- Round 1 full `e0996ffa1`：Clash Direct/Global 可绕过规则，CONFIRMED；代理路径被实际连续验收拒绝，最终实现移除该依赖，因此 finding superseded。
- Round 2 full `a187723a4`：Prometheus 科学计数法被整数 regex 误拒绝，CONFIRMED；`510ffb2e4` 修复并增加 CLI 回归。
- Round 3 closure `a187723a4..510ffb2e4`：metric finding closed，存活 findings `[]`。
- Round 4 patch `510ffb2e4..befe62119`：Tinypool override / lock / Node 要求与 Vitest 接口核对通过，findings `[]`；runtime full 与 closure 保留。
- validated_at：`befe6211994ab47d9bdff97680034a8dcb0196ab`；后续仅澄清首次更新前先检查已安装 runtime、目标代码到位后再查 source 的文档命令顺序，记录最终现场结果并归档；runtime 未变，无 spec delta。

## 部署验收范围校正

用户指出每次部署都等待 600 秒不合理。将原先过宽的完整部署门禁改为按实际影响分级，权威规则见 [Tunnel 验收分级](../../../operations/prod-fleet.md#tunnel-验收分级)。普通公网服务部署用 30 秒健康采样及受影响功能验收；600 秒保留给 Tunnel 变更与其故障恢复，故障注入仅在恢复机制变更时执行。纯文档不重启生产、不重复运行验收。本次仅修正文档，runtime、既有现场验证及代码审查结论不变。

# bugfix-585: 节点连接恢复、在线状态与断连诊断 — 技术方案

> 对齐: incident.md

## Changelog

## 现状分析

### 涉及范围

IM `server.ts` 执行 5 秒/90 秒活动检查；`gateway.ts` 持有连接、持久状态及 owner 广播。Channels `index.ts` 管理注册、ACK、退避与撤权终态；Node `main.ts` 接入诊断。Web 页面沿用现有状态事件与发送错误体验；Agent detail 的草稿同步只修正状态事件覆盖未保存编辑的问题。

### 既有约束

遵守根 AGENTS 的包边界；不 import DSH 到 Channels/IM，不新增 Agent Loop。只在独立测试身份、端口和数据目录验收。禁止记录未经约束的远端载荷。

### 可复用能力

保留 Relay 的 generation fence、指数退避、每次取凭据与注册、业务帧不重放语义。复用 IM 当前连接身份判断、owner 广播和数据库。复用 Node stderr；持久托管启动已将 stdout/stderr 写入 config 同目录 `gateway.log`，隔离 CLI 同样写 `gateway.log`。不新增日志服务或持久存储。

### 相关历史

refactor-581 建立当前 TypeScript 路径；feat-583 原生轨迹明确将 #331 留给独立修复。其连接退出时关闭观察通道行为须保留。#320 旧 Python 路径只作为需求来源。

## 架构总览与关键决策

**可恢复断线与撤权采用不同关闭语义。** IM 超时使用 1012 / `heartbeat_timeout`，撤权保留 1008 / `authority_revoked`；服务关闭使用 1001 / `server_shutdown`；连接替换保留终止旧实例的 1008 / `connection replaced`。

**由 IM 统一清理当前连接及离线状态。** 抽出短小的连接清理操作，对当前 Connection 实例做身份检查：删除连接、关闭轨迹、写 offline/last_error、广播一次。超时/撤权主动关闭前调用；普通 close 回调也调用。旧连接 close 不影响新的已注册连接。超时不变更凭据、账户或绑定。

**状态更新覆盖节点与关联 Agent 的现有消费者。** IM 在当前节点上线/离线转换时向 owner 同时广播 node.status_changed 和各非 stale Agent 的 agent.status_changed。注册恢复清空 last_error，并在事件中带 null。Agent detail 现有缓存消费者不变；draft 同步比较上一份服务端 config，若仅 node_status 变化则只 patch draft.node_status，保留未保存输入及错误提示；真正配置变化沿用现有替换语义。覆盖 Nodes、Chat、Agent detail 标识及“未保存编辑跨离线/在线不丢失”。无布局、文案、新交互，不新增原型。

**Channels 输出有类型的生命周期诊断，Node 接入既有持久日志。** 诊断含 ISO 时间、node_id、连接 generation、event、phase、attempt、delay_ms、close_code、close_reason、error_type、稳定原因分类、outage_ms（按事件适用）。事件覆盖 connecting/registering/ready/disconnected/retry_scheduled/stopped；不记录每条心跳或业务帧。断线阶段区分 connect/register/heartbeat/receive/send/stop；已获 close code/reason 不丢弃。

安全采用已知原因白名单与固定错误摘要：未识别的远端 reason 记 `[redacted]`，不原样输出 Error.message、URL、header 或 frame。异常类型仅输出本地已知错误类别；诊断 callback 失败不能阻断清理/重连。保留原有 onError 兼容消费者，不用未脱敏异常替换。

## 接口与数据流

IM 超时检查 → recoverable disconnect → 当前连接 offline 持久化/owner 事件 → socket close 1012 → Relay 诊断断线/退避 → 重新连接并注册 → IM online 事件 → Relay ready/恢复时长 → Node 原有 recover hooks。

Channels 新增 `RelayDiagnostic` 和可选 `onDiagnostic` callback；Node 将固定字段 JSON 行输出 stderr。不改变帧 envelope、请求 API 或离线发送语义。不创建新跨包依赖。

## 契约层增量

- `specs/gateway/relay-protocol.md`：可恢复连接、撤权边界、持久诊断。
- `specs/im/agents-nodes.md`：补足普通关闭与重连/旧连接关闭的状态一致性。

## 风险与回退

风险是清理与新连接注册的竞态，以及日志意外泄露外部字符串；分别用当前实例 fencing 和字段白名单限制。保留 owner 隔离、撤权终止和不重放测试。无 schema 迁移；可回退本 unit 代码，但回退会恢复已知故障。

## Runbook for Reviewer

常驻服务为隔离 IM、Node/DSH；使用前端静态构建由 IM 提供页面，不另开 Vite。

在实施 worktree 根执行：

```bash
pnpm install --frozen-lockfile
pnpm build
(cd src/IM/frontend && npm ci && npm run build)
export PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH"
mkdir -p .runtime-585
IM_FRONTEND_DIST_DIR="$PWD/src/IM/frontend/dist" ./scripts/e2e-up.sh --wt "$PWD/.runtime-585"
source .runtime-585/.e2e-ports.env
curl -fsS "$IM_URL/health"
# 浏览器打开 $IM_URL，使用下述专用身份登录。
# 停止本次所有进程：
./scripts/e2e-down.sh --wt "$PWD/.runtime-585"
```

fixture 来自 `config/e2e/gateway.yaml`：脚本重写端口、node identity、workspace、DB；测试账户 `nano` / `nano1234`，只用于新隔离服务。脚本的 TypeScript 接线已核实（e2e-up.sh:223–292）。日志位于 `.runtime-585/gateway.log`，进程与端口在同目录 pid/state/ports 文件。每次验收前记录 git HEAD、构建时间、PID/cwd 与健康结果，停止后检查端口无监听。

**Review 驱动方式**：端到端真栈。HTTP/WS 用客户端同一接口验证收发及授权；真实浏览器覆盖 Nodes、Chat、Agent detail 的在线→离线→在线及发送提示，Agent detail 编辑未保存时保留输入。无布局变更，不生成 prototype。真实 Node 使用 fixture 的 `deepseek:deepseek-v4-flash`，不以假 Agent 回声替代回复。caller 集中准备服务并交接解析后的 URL/PID/命令，reviewer 无需决定启动方案。

**验收前置与已核实资源**：2026-10-12 本机 proxy `http://127.0.0.1:4000/health` 返回 200；对 `/v1/messages` 发上述模型的最小请求返回 message / model deepseek-v4-flash，模型路径可用（不替代产品回复验收）。Cua in-app browser 已成功创建 about:blank 验证可用；Chrome 扩展查询失败，使用可用的 IAB。只暂停/恢复隔离 Node PID 模拟心跳超时，等待真实 90 秒阈值和 5 秒 guard；不休眠宿主机或操作生产。完整日志保持 gitignored，报告留脱敏证据。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-recovery | 连接恢复与诊断闭环 | 无 | 单组 | IM server/gateway、Channels Relay、Node 日志接线、Agent detail 草稿同步、对应测试和 specs | [reviewer] R1–R4 全通过，真消息回复、Nodes/Chat/Agent detail 状态变化和未保存草稿保留有证据；[worker] 真实 IM 扫描+Relay 回归覆盖 offline 落库/owner 广播/重连注册/恢复后新消息投递/真实撤权/旧连接 fencing；Relay 测试覆盖 ACK 超时、连接失败、远端关闭、退避及日志脱敏，无业务重放；本地 CI、独立门禁通过 |

## 测试归属

保留 `packages/channels/tests/web-relay.test.ts` 原有行为测试并扩展诊断断言；IM 跨边界故障链放 `apps/im-server/tests/node-connection.test.ts`（当前无真实 server guard + Relay 覆盖），使用真实 socket、临时数据库、公开 Node API 和 owner 用户流。可将连接 lastSeen 向前调整以注入超时，必须等待真实 guard 执行，不直接调用清理函数代替超时路径。新增文件不超过 400 行。真实全栈/浏览器作为本次验收证据，不复制成平行永久测试。

前端扩展既有 Agent detail/状态消费测试，验证离线/在线更新不覆盖未保存编辑，不新增重复测试套件。

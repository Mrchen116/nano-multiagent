# refactor-461 — 验收报告

> 对齐：`motivation.md` 的用户侧验收标准
>
> Round: 1（full）  
> Date: 2026-07-13

## Verdict

- **Verdict:** `fail`
- **Highest Required Action:** `fix-implementation`
- **Issues:** blocking 0 / major 1 / minor 0
- **Needs Re-review:** `true`

真实产品的 10 个 Scenario 均已从用户入口走通；当前发布阻塞来自用户文档与 canonical 契约仍承诺已经删除的 `health_url` / 健康与 readiness 语义。第一轮不使用 `revise-design`。

## User Journeys Exercised

### Journey 1 — Web IM 消息与主动 cron 仍由真 Gateway 完成

- 先按 `design.md` Runbook 执行 `./scripts/e2e-down.sh` → `./scripts/e2e-up.sh`，在持久 tmux 中接管 ephemeral IM + Gateway。
- 健康检查观察到 IM `/openapi.json` 可达、Gateway PID 存活、日志出现 auto-bind、无 `.api.pid`，且无 `personal_assistant.kernel_app` 进程；本地 LLM proxy `/health` 返回 `{"ok":true}`。
- 以关键路径套件的真实 IM HTTP/WebSocket 用户入口，运行：
  - `test_tool_call_then_reply_carries_sentinel`
  - `test_cron_job_auto_pushes_message`
- 结果：`2 passed in 87.63s`。第一条消息经真 LLM 工具调用返回随机哨兵；cron 到点后在 IM 对话产生用户可见主动推送。

### Journey 2 — 运维者管理一个后台 Gateway

- 用 worktree 隔离 config 真实执行默认 start：exit 0，输出：

  ```text
  Gateway started (pid=18584)
  IM service:      http://127.0.0.1:65043  [connected]
  Log:             .../.review-r1-operator/gateway.log
  ```

- 新状态文件 keys 只有 `config_path,log_path,pid`；启动输出无 `health` / `ready`；运行期无 `.api.pid` 或独立 Kernel app。
- 同 config 再次 start：exit 1，显示 `gateway is already running (pid=18584)`，并指引 `stop` / `restart`；原 PID 继续存活。
- restart：旧 PID 18584 退出，新 PID 23274 存活；输出仍是 `Gateway started (pid=...)` + IM status + Log。
- 向隔离 state 注入历史 `health_url`（指向持续在线 IM）后执行 stop：输出 `STOPPED pid=23274 ...`；Gateway PID/state 被清理，IM 仍返回 200，说明 stop 没把 IM 健康误作 Gateway 停止判据。
- 以隔离 config 设置 `shutdown_grace_seconds=1` / `poll_interval_seconds=0.1`，启动 PID 26904 后对其进程组发送 `SIGSTOP` 模拟不响应。真实 stop 输出 `forced=true`；PID、state、`gateway.pid` 均消失。

### Journey 3 — 旧配置单向迁移且可回滚

- Legacy-only config：仅在 `kernel:` 设置 timing `9 / 4 / 0.4`，同时放入不可达 `base_url`、假 token/request、极短 HTTP timeout、不可执行 command 与 dead health path。真实后台 Gateway 仍正常启动。
- 现有登录/同步流程触发保存后：
  - `config.yaml.pre-refactor-461.bak` 与启动前原文逐字节一致；
  - canonical config 不再含 `kernel:`；
  - `gateway:` 精确为 `startup_timeout_seconds=9`、`shutdown_grace_seconds=4`、`poll_interval_seconds=0.4`。
- Mixed config：新 `gateway:` 提供 startup=12、poll=0.3；旧 `kernel:` 提供 startup=9、shutdown=4、health-poll=0.4。保存后 backup 与原文逐字节一致，canonical `gateway:` 为 `12 / 4 / 0.3`，证明逐字段新值优先、缺省字段从旧值迁移。
- Backup failure：在预期 backup 路径预置目录，触发同一真实保存流程；Gateway 可继续运行，但原 config 与保存前原文逐字节一致，未被覆盖。

### Journey 4 — IM 完全离线时真实 Feishu P2P 仍自治

- 经 orchestrator 明确确认后，只执行一次外部写操作：以已授权 Feishu user 身份向唯一名为 `nano` 的 bot P2P 发送纯文本哨兵 `OFFLINE_ACK_R461_REVIEW_R1_1783937529`。
- 隔离 Gateway PID 63406 的 `im_service.url` 指向 `127.0.0.1:51687`；发送前、等待中均确认该端口无 listener。默认 start 用户可见输出为 IM `[unavailable (running offline, will retry)]`，Gateway PID 仍存活。
- 用户消息 ID：`om_x100b6a7fd17894a4b496de67fbecc15`。
- 同一 P2P 随后收到 sender type=`app` 的回复，内容包含同一哨兵；回复消息 ID：`om_x100b6a7feee6bca0b247951bb9f5c27`。
- 这条旅程只用了真实 Feishu user/app、真实 Gateway、真实 LLM；没有 fake event、stub channel 或内部 runtime 调用。

### Journey 5 — 一键真栈只管理 IM 与 Gateway 并完成清理

- `scripts/e2e-up.sh` 成功启动 ephemeral IM + Gateway 并完成 auto-bind；运行期 `.api.pid` 不存在、无旧 Kernel app 进程。
- `scripts/e2e-down.sh` 后，本轮所有 Gateway PID 均退出，`.im.pid` / `.gateway.pid` / `.api.pid` / worktree config migration backup 均无残留；两个 reviewer tmux session 已删除。

## Reference Artifacts Reviewed

N/A — 本 unit 不包含原型、设计稿、reference screenshot 或 must-match 视觉契约。

## Issues

### 1. 用户启动文档与 canonical 生命周期契约仍承诺已删除的 health/readiness 语义

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 本 unit 明确把默认 start 收口为 PID/liveness 启动确认，并要求 active 运维叙事与该行为一致；真实 CLI 已变化，但用户入口与 canonical 仍教运维者等待不存在的 `health_url` / ready 信号。主路径可运行，但操作者会按错误输出格式和错误 readiness 承诺编排启动，第一轮验收按 major 判 fail。
- **Expected:** README、operator runbook 与 Gateway lifecycle canonical 都只描述 `Gateway started (pid=...)`、Log、独立 IM status，并明确这不是 runtime/channel readiness；canonical 同时承载 `gateway:` timing、旧三项逐字段迁移、per-file backup 与保存后移除 `kernel:` 的行为。
- **Actual:**
  - `README.md:79` 仍给出 `STARTED pid=<pid> health_url=... log=...`；`README.md:113` 仍把 `STARTED ...` 引向 ready 判断。
  - `docs/operator-runbook.md:86` 仍给出同一旧输出；`:110` 仍描述后续 readiness。
  - `docs/specs/gateway/service-lifecycle.md:24` 仍规定主命令打印 `pid / 健康提示 / 日志路径`，且整份 canonical 没有本 unit 的 Gateway lifecycle timing / legacy migration / migration backup 契约。
- **Reproduction:** 对照上述三份文档后，真实执行默认 start；实际可见输出是 `Gateway started (pid=...)`、`IM service: ... [connected|unavailable]`、`Log: ...`，没有 `health_url`，也不承诺 runtime ready。
- **User Impact:** 新用户会认为实际输出异常或等待一个永远不会出现的 health/readiness 信号；依赖 README/runbook 的运维脚本也会错误解析启动结果。canonical 漂移还会让后续实现重新引入本 unit 刚删除的语义。

## Acceptance Criteria Coverage

### Requirement: 用户消息与主动任务仍由进程内 Kernel 正常执行 — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Web IM 或外部通道消息正常回复 | `motivation.md` Scenario；`docs/specs/gateway/routing-delivery.md` | Journey 1 真实 IM HTTP/WS 工具调用消息；Journey 4 真实 Feishu P2P | `test_tool_call_then_reply_carries_sentinel` pass；Feishu user message `om_x100b6a7fd17894a4b496de67fbecc15` → app reply `om_x100b6a7feee6bca0b247951bb9f5c27` | pass | 两条路径均由用户入口观察回复。 |
| Heartbeat 与 Cron 活路径不受清理影响 | `motivation.md` Scenario；`docs/specs/gateway/heartbeat-cron.md` | Journey 1 到点 cron 主动推送 | `test_cron_job_auto_pushes_message` pass；两条 live path 合计 `2 passed in 87.63s` | pass | Scenario 允许 heartbeat 或 cron；选择已有 v1 必保活 cron 真旅程。 |

### Requirement: 运维者仍把 Gateway 当一个后台服务管理 — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 默认启动确认 | `motivation.md` Scenario；`design.md` D3 / Runbook | Journey 2 真实 operator CLI 默认 start | exit 0；`Gateway started (pid=18584)` + IM status + Log；state keys=`config_path,log_path,pid`；无 health/ready/.api.pid | pass | 产品行为通过；相关用户文档漂移另列 major issue。 |
| stop 与 restart 保持现有结果 | `motivation.md` Scenario；`design.md` D3/D4 | Journey 2 restart、历史 state stop、强杀兜底、单实例 | PID 18584→23274；旧 `health_url` state 可 stop；受控卡死 PID 26904 stop 显示 `forced=true` 并清状态 | pass | 覆盖优雅路径、历史 state 与超时强杀。 |
| IM 离线时 Gateway 本地自治不变 | `motivation.md` Scenario；`docs/specs/gateway/service-lifecycle.md` | Journey 4 IM 端口无 listener + 真 Feishu user/app P2P | offline port 51687；Gateway PID 63406；user/app message IDs 见 Journey 4 | pass | IM 全程不可达，外部通道仍收到 Agent 回复。 |

### Requirement: Gateway 生命周期 timing 有明确且可迁移的配置所有权 — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 旧自定义 timing 继续生效 | `motivation.md` Scenario；`design.md` D2 | Journey 3 从 legacy-only config 真实启动并触发 canonical save | legacy `9 / 4 / 0.4` → `gateway 9 / 4 / 0.4`；Gateway start/stop 成功 | pass | 三项未静默回默认。 |
| 新配置优先于旧值 | `motivation.md` Scenario；`design.md` D2 | Journey 3 mixed config 逐字段验证 | 新 startup=12/poll=0.3 + 旧 shutdown=4 → canonical `12 / 4 / 0.3` | pass | 未提供的新字段才从 legacy 迁移。 |
| 保存后只保留 Gateway 所有权 | `motivation.md` Scenario；`design.md` D2 / Runbook | Journey 3 两种真实启动/保存 + backup failure | 两份 migration backup 均与原文 byte-identical；canonical 无 `kernel:`；backup 失败时原 config byte-identical | pass | 覆盖不可覆盖 backup、canonical save 与失败不覆盖。 |
| 旧连接与 HTTP 字段不再形成运行时输入 | `motivation.md` Scenario；`design.md` D1/D2 | Journey 3 legacy config 放入不可达 URL/假凭据/不可执行 command/dead health path 后真实启动 | Gateway exit 0 并形成正常 PID/state；保存后旧字段随 `kernel:` 消失 | pass | 用户面证明这些字段没有阻断或改走独立 Kernel。 |

### Requirement: 维护者的一键真栈只管理 IM 与 Gateway — 组内结论：pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| e2e 起停无 Kernel API 产物 | `motivation.md` Scenario；`design.md` Runbook | Journey 5 真实 `e2e-up.sh` → live journey → `e2e-down.sh` | IM/Gateway ready；`.api.pid` 始终不存在；无 `personal_assistant.kernel_app`；down 后自启服务与 PID/state 全清 | pass | 仅 IM 与 Gateway 两类服务。 |

## Clarifications

- 2026-07-13：为验证 IM 离线自治，按 `lark-im` 安全门禁请求确认。Orchestrator 明确授权：以当前已授权 Feishu user 身份，仅向已核实为 `nano` 的唯一 bot P2P 发送 1 条纯文本哨兵；不得扩展 recipient/chat 或发送额外内容。本轮严格按该边界执行一次。

## Side Findings

无。

## Upper-level Documentation Sync

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**。已明确 Kernel 为 Gateway 进程内库、无内建 HTTP API。
- [x] `docs/specs/gateway/`（长青行为契约层）：**需要更新**。`service-lifecycle.md` 仍写“健康提示”，且缺失本 unit 的启动确认与 lifecycle timing 迁移契约；见 issue #1。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。`AGENTS.md` 已只描述 IM + Gateway，并明确 Kernel 进程内；仓库无额外本 unit CLAUDE 增量要求。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：**无需更新**。本 unit 未改变文档体系。
- [x] `README.md` / `docs/operator-runbook.md`：**需要更新**。二者仍展示旧 `STARTED ... health_url` / readiness；见 issue #1。

## Recommended Next Step

派一个小范围 `fix-implementation`：只同步 `README.md`、`docs/operator-runbook.md` 与 `docs/specs/gateway/service-lifecycle.md` 到本 unit 已验证的真实输出和迁移契约；修复后针对 issue #1 做 targeted re-review，并复跑默认 start 输出对照即可。产品代码旅程本轮已全部通过。

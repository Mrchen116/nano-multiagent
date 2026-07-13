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

---

# Round 3 — 2026-07-13

## Verdict

- **Verdict:** fail
- **Highest Recommended Action:** fix-implementation
- **Needs Re-review:** true
- **Review Mode:** full（M3 高风险修复后全量产品复验）
- **Implementation Head:** `8cb3a12c5eab56914af8b1409d2bffb35e2288d6`
- **Issue Count:** critical 0 / major 1 / minor 0

Round 1 的 README / operator runbook 启动输出漂移已修复，真实默认 start 与文档均只承诺 PID + child liveness，不再输出 `health_url` 或宣称 runtime/channel ready。但 M3 新增的 e2e ownership 建立窗口在真实冷启动下过早超时，并且失败后不回滚本次刚创建的 IM/Gateway，因此本轮仍不可放行。

## Issue #1 — e2e 冷启动在 Gateway 建立 PID 前超时，失败后留下无 identity 的活栈

- **Severity:** major
- **Regression Relation:** direct（M3 R3 新增 ownership identity / fail-atomic teardown）
- **Recommended Action:** fix-implementation
- **Action Rationale:** 一键真栈是本 unit 的明确用户入口。首次冷启动会误报失败、遗留监听进程，而 down 因缺少 identity 又会 fail closed；运维者只能越过安全门禁手工核对 PID/argv 后清理。
- **Expected:** `e2e-up.sh` 在 Gateway 允许的启动预算内等待 internal PID 与本轮 spawned PID 收敛；任何 identity/readiness 失败都只根据本 shell 刚获得的 PID 停止并确认退出，不留半栈。
- **Actual:**
  - 首次完全干净的冷启动在固定 `60 × 0.1s` identity 窗口后返回 `Gateway did not establish teardown identity` / rc=1。
  - 失败后真实 IM PID 58399 与 Gateway PID 59165 仍存活，`.gateway.pid == gateway.pid == 59165`，Gateway argv 精确指向本 worktree config，但 `.gateway-identity.json` 不存在。
  - 因 down 必须先验 identity，该现场无法由正常 `e2e-down.sh` 关闭；本轮只在精确核对内外 PID、argv 和 config 后手工 TERM/KILL 并清理。
  - 再次从干净状态暖启动用时 10.722s，成功生成 identity（Gateway PID 67483），说明这是冷启动时序/可恢复性缺陷，不是真实 PID ownership 冲突。
- **Minimal Reproduction:** 清空 worktree lifecycle 产物后，在持久 shell/tmux 中直接执行 `./scripts/e2e-up.sh`；观察上述超时后的两个活 PID、一致内外 PID 和缺失 identity。

## Product Journey Evidence

### Journey 1 — 用户消息与 Cron 真栈

- 在新 HEAD 的工作树 IM + Gateway + 真 LLM proxy 上，Web IM tool-call reply 与 cron auto-push 两条 critical path 同进程复跑：`2 passed in 46.23s`。
- 终端用户回复仍由进程内 Kernel 处理；Cron 按既有会话/投递语义完成。

### Journey 2 — 真实 operator start / stop / restart

- 预置 malformed `gateway.pid` 后默认 start 仍正确清除 residue 并启动 PID 82124；输出为文档所述三行，state 仅含 `config_path/log_path/pid`。
- 重复 start rc=1 且不替换已有 PID；restart 从 82124 切换到 83823，旧 PID 退出、新 PID 存活。
- 对新 Gateway 进程组发 `SIGSTOP` 后 stop 返回 `forced=true`，并且只在确认 PID 消失后清理 state/PID。

### Journey 3 — 配置迁移与失败原子性

- 95 个受影响 targeted tests 全部通过，覆盖 FIFO hard-timeout、existing/new hardlink、source drift、atomic replace failure、launch identity、state/PID-only forced stop 和 e2e fail-atomic。
- 真实 legacy-only config 从 `kernel 9 / 4 / 0.4` 迁移到 `gateway 9 / 4 / 0.4`；backup 与原文 byte-identical、`nlink=1`、mode 0600，canonical config 不再含 `kernel:`。
- 真实第三方 hardlink backup（backup/third-party 同 inode，nlink=2）与 FIFO backup 都拒绝覆盖 source；Gateway 本地运行不被配置保存失败拖垮。
- mixed config 逐字段新值优先的 Round 2 真实证据（`12 / 4 / 0.3`）仍有效；M3 targeted 回归未改变该映射。

### Journey 4 — e2e ownership 正负路径

- 暖启动成功后篡改 internal `gateway.pid`，真实 down rc=1，Gateway/IM 均保持存活，identity/config/env/PID 证据全保留；恢复 PID 后 down rc=0，Gateway/IM 均退出，identity/state/config/env/PID 全清。
- 未确认退出的 fail-atomic 路径由 shell integration 覆盖；真实正常 down 证明只管理 IM + Gateway，始终无 `.api.pid` / `personal_assistant.kernel_app`。
- 冷启动负路径触发 issue #1，因此该 Scenario 整体为 fail。

### Journey 5 — M170 鲜活 runtime

- `stop → rebuild → start` 从空 runtime 注册/登录用户、Bearer 查询并 auto-bind；start 输出真实三行，`node_online=true` / `node_status=online`。
- stop 后 `im_http_ok=false`、`gateway_pid=null`、`gateway_running=false`、`node_online=false`、`node_status=null`，无运行态残留。

## Scenario Coverage Matrix

| Scenario | Round 3 证据 | 结果 | 备注 |
|---|---|---|---|
| Web IM 或外部通道消息正常回复 | 真 Web IM tool-call reply | pass | 按 Scenario 的“或”由 Web IM 覆盖。 |
| Heartbeat 与 Cron 活路径不受影响 | 真 cron auto-push | pass | 与 tool-call 同栈复跑。 |
| 默认启动确认 | malformed residue + 真后台 start | pass | 文档与三行输出一致，无 health/readiness。 |
| stop 与 restart 保持现有结果 | duplicate/restart/SIGSTOP forced stop | pass | 确认退出后才清证据。 |
| IM 离线时 Gateway 本地自治不变 | 未发送外部 P2P | not-run | 未获得本轮单次发送授权；严格未执行，不影响已存在的 blocker。 |
| 旧自定义 timing 继续生效 | 真 legacy migration `9 / 4 / 0.4` | pass | 启停与 canonical save 均完成。 |
| 新配置优先于旧值 | Round 2 真 mixed + M3 targeted regression | pass | 逐字段 `12 / 4 / 0.3`。 |
| 保存后只保留 Gateway 所有权 | 真 migration + hardlink/FIFO 失败原子性 | pass | source/backup 约束满足可执行路径。 |
| 旧连接与 HTTP 字段不再形成运行时输入 | legacy 假 URL/token/request/command/health 后真实启动 | pass | 仍只构建进程内 Kernel。 |
| e2e 起停无 Kernel API 产物 | 真冷/暖启动、identity mismatch、normal down | **fail** | 冷启动 identity timeout 留活半栈；见 issue #1。 |

## Upper-level Documentation Sync

- [x] `README.md` / `docs/operator-runbook.md`：Round 1 issue 已修复，与真实三行 start 及“非 readiness”语义一致。
- [x] `SPEC.md`：无需更新，仍正确规定 Kernel 为 Gateway 进程内库。
- [ ] `docs/specs/gateway/service-lifecycle.md`：按 orchestrator §7.0 在验收通过后归并；本轮因实现 blocker 未进入该步，不单独列为 blocker。

## Recommended Next Step

修复 `e2e-up.sh` 的 identity deadline 与 pre-identity 失败回滚：等待预算对齐 Gateway lifecycle startup timeout，且任何 up 失败都必须使用本轮刚 spawn 的 PID 停止并确认 Gateway/IM 退出。修复后做 targeted re-review：至少覆盖延迟超过 6 秒的 cold child、identity 建立前失败的自动回滚，以及随后真实 up/down 全清。

---

# Round 4 — 2026-07-13

## Verdict

- **Verdict:** pass
- **Highest Required Action:** pass
- **Needs Re-review:** false
- **Review Mode:** full（M4 高风险修复后全量产品复验）
- **Implementation Head:** `34a9de3840422ebbc34a5a0a22ab8e7e4b776b1e`
- **Issue Count:** blocking 0 / major 0 / minor 0

Round 3 的冷启动 identity timeout / 失败留活半栈已关闭。本轮从完全干净状态启动真实 e2e 栈成功，并在真实短 timeout 下观察到本轮 IM/Gateway 均自动退出。missing/mismatch evidence 均 fail closed，恢复证据后 normal down 完成全栈停止。默认 operator 生命周期、旧 `health_url` state 安全升级、配置 sidecar/backup/mode/failure rollback、Web IM 消息与 Cron、M170 均通过。

## Round 3 Issue Closure

### Issue #1 — closed

- 完全干净冷启动：`e2e-up.sh` rc=0，总用时 6.131s；IM/Gateway 存活且节点 online，`gateway.identity.json` 含 PID/process-start/resolved-config/entry/argv，无 `.api.pid` / `personal_assistant.kernel_app`。
- 真实短 timeout：将 `gateway.startup_timeout_seconds=0.1` 后 up rc=1，报 identity 尚未建立；本轮 Gateway PID 12916 与 IM PID 11912 均自动 TERM 并确认退出，分配端口 51543 无 listener。external/internal PID、identity、state、ports env 均不存在，日志保留用于排查。
- 结论：等待预算已能承载真实 cold child，pre-identity 失败也不再留活半栈。

## User Journeys Exercised

### Journey 1 — 冷启动真栈、用户消息与 Cron

- 按 reviewer Runbook 在持久 tmux 中从无 lifecycle 产物状态执行 `./scripts/e2e-up.sh`，冷启动 rc=0，IM/Gateway 健康检查通过。
- 在该真 IM + Gateway + LLM proxy 上复跑 Web IM tool-call reply 与 cron auto-push：`2 passed in 62.24s`。回复仍由进程内 Kernel 完成，Cron 仍按原会话/投递语义产生用户可见推送。

### Journey 2 — public operator 生命周期与旧 state 向前读

- 隔离 config 默认 start 返回文档所述三行，PID 93057 存活，state 不含 health/readiness，process identity 完整持久化。
- restart 从 PID 93057 切换到 94377：旧 PID 退出、新 PID 存活。
- 为模拟真实旧实例，移除新 identity 并向 state 注入多余 `health_url`。public stop 通过 resolved config + exact argv 无信号安全升级 identity，返回 `STOPPED pid=94377`；PID/state/identity 全清，同一 IM 仍返回 HTTP 200，未把 IM health 当停止判据。

### Journey 3 — config sidecar transaction、迁移与失败回滚

- M4 高风险组合的 119 个 affected tests 全通过；另定向复跑 6 个 public transaction case，覆盖两个独立进程在稳定 sidecar lock 上串行、existing/new backup path swap、mode drift、post-replace directory fsync 回滚与 distinct rollback-failure outcome，全部通过。
- 真实 legacy-only config 以 mode 0600 启动并触发 save；稳定 `config.yaml.lock` 存在，migration backup 与原文 byte-identical，config/backup 均保持 0600，canonical config 无 `kernel:` 且 timing 精确为 `9 / 4 / 0.4`。
- mixed config 的 `12 / 4 / 0.3` 逐字段优先与 dead connection/command/HTTP 字段忽略已有 Round 2/3 真实证据；M4 改动只加固 save transaction，本轮的真实 legacy 与 affected regression 继续证明该映射未退化。

### Journey 4 — e2e evidence fail-closed、恢复与 normal down

- 篡改 internal PID 后 down rc=1，明确拒绝 signal/teardown；Gateway/IM 均存活，config/env/PID/identity 证据全保留。
- 恢复 internal PID，再移走 external `.gateway.pid` 模拟 incomplete evidence；down rc=1，再次零 teardown，两个进程与全套证据仍保留。
- 恢复 external owner 后 normal down rc=0，Gateway/IM 均退出，external/internal PID、identity、state、IM PID、config/ports env 全清，始终无 Kernel API 产物。

### Journey 5 — M170 鲜活 runtime

- 从空 runtime `rebuild → start`，真实注册/登录、Bearer 查询和 auto-bind 完成；Gateway PID 18587，`node_online=true` / `node_status=online`。
- stop 后 `im_http_ok=false`、`gateway_pid=null`、`gateway_running=false`、`node_online=false`、`node_status=null`，无运行态残留。

## Scenario Coverage Matrix

| Scenario | Round 4 证据 | 本轮执行 | 累计结论 | 备注 |
|---|---|---|---|---|
| Web IM 或外部通道消息正常回复 | 真 Web IM tool-call reply | pass | pass | 按 Scenario 的“或”由 Web IM 覆盖。 |
| Heartbeat 与 Cron 活路径不受影响 | 真 cron auto-push | pass | pass | 与消息同栈复跑。 |
| 默认启动确认 | 真 public background start + identity | pass | pass | 只承诺 PID/liveness，无 health/readiness。 |
| stop 与 restart 保持现有结果 | restart + legacy health_url state stop | pass | pass | 旧 state 无信号安全升级后停止。 |
| IM 离线时 Gateway 本地自治不变 | 本轮未发送飞书 P2P | not-run (authorization) | pass | Round 1 真实 offline Feishu user/app P2P 已 pass；M2-M4 未改 channel/runtime 路径；本轮无单次授权，禁止发送。 |
| 旧自定义 timing 继续生效 | 真 legacy migration `9 / 4 / 0.4` | pass | pass | timing 与 mode/backup 同时核验。 |
| 新配置优先于旧值 | 前轮真 mixed + M4 affected regression | reused | pass | 逐字段 `12 / 4 / 0.3`。 |
| 保存后只保留 Gateway 所有权 | 真 migration + sidecar/mode/rollback 定向验证 | pass | pass | backup 与 source 失败语义均完整。 |
| 旧连接与 HTTP 字段不再形成运行时输入 | 前轮真 legacy dead-fields + 本轮 legacy 启动 | reused | pass | 仍只构建进程内 Kernel。 |
| e2e 起停无 Kernel API 产物 | 真 cold up、timeout rollback、missing/mismatch、normal down | pass | pass | Round 3 blocker 已关闭。 |

## Reference Artifacts Reviewed

N/A — 本 unit 无原型、设计稿、reference screenshot 或视觉 must-match 契约。

## Issues

无 blocking / major / minor 产品可接受性 issue。

## Side Findings

- e2e 的 ephemeral `.gateway-config.yaml` 已被 down 删除后，M4 新增的零字节 `.gateway-config.yaml.lock` 仍留在 worktree，重复 down 也不删除。它不影响再次启动、进程安全或 Scenario 的服务停止语义，属于 non-blocking cleanup polish；本 reviewer 收尾时已清理自己产生的 lock。

## Upper-level Documentation Sync

- [x] `README.md` / `docs/operator-runbook.md`：与真实三行 start 及“非 readiness”语义一致。
- [x] `SPEC.md`：无需更新，仍正确规定 Kernel 为 Gateway 进程内库。
- [x] `AGENTS.md` / `CLAUDE.md`：无新增产品运维漂移。
- [x] `docs/SPEC_GUIDE.md`：本 unit 未修改文档体系，无需更新。
- [ ] `docs/specs/gateway/service-lifecycle.md`：由 orchestrator 按 §7.0 在验收通过后归并；当前未归并不是 blocker。

## Recommended Next Step

产品验收通过，可进入 orchestrator §7.0 长青契约归并和后续 PR/CI 门禁。`.gateway-config.yaml.lock` 的 ephemeral cleanup 可作为非阻断 polish 后续处理。

---

# Round 5 — 2026-07-13

## Verdict

- **Verdict:** pass
- **Highest Required Action:** pass
- **Needs Re-review:** false
- **Review Mode:** final full
- **Implementation Head:** `20f301a61414b126689df70f07a36cde471a9a57`
- **Issue Count:** blocking 0 / major 0 / minor 0

M5 对 startup publication、PID + birth identity 与 e2e evidence cleanup 的最终收口通过产品验收。真实含空格/双引号 config 的 start/restart/stop、跨时区 legacy `health_url` state 升级、state publication 失败回滚、cold/timeout e2e、Gateway survivor 与 dangling/missing/malformed/drift 证据边界、normal down、Web IM/Cron 和 M170 均得到可观察的正确结果。

## Prior Finding Closure

- Round 3 cold identity timeout：继续保持 closed。本轮完全干净 cold up rc=0，用时 4.789s。
- Round 4 ephemeral sidecar residue：**closed**。本轮 normal down 后 `.gateway-config.yaml.lock` 已自动清理；短 timeout rollback 后 sidecar 也不存在。

## User Journeys Exercised

### Journey 1 — 特殊路径 operator 与跨时区 legacy state

- 隔离 config 目录名为 `.review-r5 operator "quoted"`，config 文件名为 `config "node".yaml`。在 `TZ=Pacific/Honolulu` 下默认 start 成功，PID 93868 存活，identity 完整保留带空格/引号的 resolved config 和 argv。
- restart 从 PID 93868 切换到 97464，旧 PID 退出、新 PID 存活。
- 移除新 identity 并在 state 中注入旧 `health_url`，改用 `TZ=UTC` 执行 public stop。返回 `STOPPED pid=97464`，PID/state/identity 全清，IM 仍 HTTP 200。说明 locale/TZ 与 command quoting 不再影响旧 state 的安全升级与停止。

### Journey 2 — startup publication 失败的用户结果

- 在隔离 config 目录预置不可覆盖的 `.gateway-state.json/` 目录，然后走真实默认 start。
- 用户可见结果为 `Gateway failed to start` / rc=1，并指引查看 Gateway log；命令没有误报启动成功。
- 本轮观察到的 child PID 99449 已退出，`gateway.pid` / `gateway.identity.json` 不存在，预置 state 目录保留。publication 失败未留下无法管理的 Gateway。

### Journey 3 — e2e cold/rollback/evidence/normal-down 全状态机

- 完全干净 cold up rc=0，用时 4.789s；Gateway PID 90183、IM PID 89581 均存活，节点 online，identity 存在，无 `.api.pid` / `personal_assistant.kernel_app`。
- 真实负路径：移走 external PID、将 external PID 改为 malformed 内容、将 external PID 改为 dangling symlink、放入 malformed optional state，四次 down 均 rc=1，Gateway/IM 均保持存活，证据未被拆除。
- Gateway 在 rollback 中 survive 时保留 IM 与全套 evidence，以及 same-content/new-inode drift 零删除，由真 shell entry + child/signal harness 定向复跑：11 passed。
- 恢复真实 evidence 后 normal down rc=0，Gateway/IM 都退出，external/internal PID、identity/state、IM PID、config、sidecar、ports env 全部不存在。
- 短 timeout：`startup_timeout_seconds=0.1` 的真实 up rc=1，Gateway PID 14496 与 IM PID 14199 均收到 TERM 并确认退出，端口 60584 无 listener，PID/identity/state/sidecar/env 无残留，日志保留。

### Journey 4 — 用户消息、Cron 与配置迁移不变性

- 在本轮 cold 真 IM + Gateway + LLM proxy 上复跑 Web IM tool-call reply 和 cron auto-push：`2 passed in 47.14s`。消息仍由进程内 Kernel 回复，Cron 仍按原会话/投递语义产生用户可见推送。
- M5 没有修改 config loader/save transaction。Round 4 真实 legacy `9 / 4 / 0.4`、backup/mode/sidecar/rollback，Round 2 mixed `12 / 4 / 0.3` 与 dead-field 忽略证据继续有效。

### Journey 5 — M170 鲜活 runtime

- `rebuild → start` 完成真实注册/登录、Bearer 查询和 auto-bind；Gateway PID 18075，`node_online=true` / `node_status=online`。
- stop 后 `im_http_ok=false`、`gateway_pid=null`、`gateway_running=false`、`node_online=false`、`node_status=null`，无运行态残留。

## Automated Supporting Evidence

- M5 affected launch/publication/identity/legacy/e2e up/down 组合：70 passed。
- survivor/dangling/missing/malformed/drift 高风险 shell 定向组：11 passed。
- 自动化证据仅用于补足无法对真实 OS 进程强制制造的 survivor/drift 时序；主路径、常见负路径与用户结果均已由真实入口观察。

## Scenario Coverage Matrix

| Scenario | Round 5 证据 | 本轮执行 | 累计结论 | 备注 |
|---|---|---|---|---|
| Web IM 或外部通道消息正常回复 | 真 Web IM tool-call reply | pass | pass | 按 Scenario 的“或”由 Web IM 覆盖。 |
| Heartbeat 与 Cron 活路径不受影响 | 真 cron auto-push | pass | pass | 与消息同栈复跑。 |
| 默认启动确认 | quoted/spaced config start + publication failure | pass | pass | 成功只承诺 PID/liveness；publication 失败明确 rc=1。 |
| stop 与 restart 保持现有结果 | quoted restart + cross-TZ legacy stop | pass | pass | 新/legacy identity 都进入明确终态。 |
| IM 离线时 Gateway 本地自治不变 | 本轮未发送飞书 P2P | not-run (authorization) | pass | Round 1 真实 offline Feishu user/app P2P 已 pass；M5 未修改 channel/runtime；本轮无单次授权，禁止发送。 |
| 旧自定义 timing 继续生效 | Round 4 真 legacy + M5 lifecycle regression | reused | pass | `9 / 4 / 0.4`。 |
| 新配置优先于旧值 | Round 2 真 mixed | reused | pass | 逐字段 `12 / 4 / 0.3`；M5 未改 loader。 |
| 保存后只保留 Gateway 所有权 | Round 4 真 migration/backup/mode/rollback | reused | pass | M5 未改 config transaction。 |
| 旧连接与 HTTP 字段不再形成运行时输入 | 前轮真 legacy dead-fields | reused | pass | 仍只构建进程内 Kernel。 |
| e2e 起停无 Kernel API 产物 | cold/timeout/survivor/evidence/normal down | pass | pass | PID/identity/config/sidecar/env 全清，无 Kernel API。 |

## Reference Artifacts Reviewed

N/A — 本 unit 无原型、设计稿、reference screenshot 或视觉 must-match 契约。

## Issues

无 blocking / major / minor 产品可接受性 issue。

## Side Findings

- 当 optional `.gateway-state.json` 是 malformed JSON 时，`e2e-down.sh` 会先打印 Python `JSONDecodeError` traceback，再打印明确的 `gateway identity mismatch ... refusing to signal or tear down stack`。rc=1、Gateway/IM 保留和 evidence 不删除都正确；该 traceback 仅属非阻断诊断文案 polish。

## Upper-level Documentation Sync

- [x] `README.md` / `docs/operator-runbook.md`：与真实 start/stop/restart 及“非 readiness”语义一致。
- [x] `SPEC.md`：无需更新，仍正确规定 Kernel 为 Gateway 进程内库。
- [x] `AGENTS.md` / `CLAUDE.md`：无新增产品运维漂移。
- [x] `docs/SPEC_GUIDE.md`：本 unit 未修改文档体系，无需更新。
- [ ] `docs/specs/gateway/service-lifecycle.md`：由 orchestrator 按 §7.0 在最终验收通过后归并；当前未归并不是 blocker。

## Recommended Next Step

最终产品验收通过，可进入 orchestrator §7.0 长青契约归并和 PR/CI 门禁。malformed optional state 的 traceback 可作为非阻断 CLI polish 后续处理。

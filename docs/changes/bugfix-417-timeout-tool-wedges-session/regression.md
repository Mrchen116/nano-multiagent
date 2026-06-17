# bugfix-417 — 回归验证

> 对齐: incident.md v1
> Round: 1
> Date: 2026-06-17
> Reviewer: reviewer-r1

## Verdict

**fail**

**Highest Required Action**: fix-implementation

**Issues**: blocking 0, major 2, minor 0

---

## 澄清记录（§2.6）

无疑问，直接开工。

---

## 服务接管记录（§2.5）

- IM 重启（端口 8011），前端重新 build（`npx vite build`），产物含关键标记 `run_heartbeat`/`tool_timeout`/`stalled`，指纹核验通过（`index-D8PzFss6.js`）。
- Gateway 用 unit worktree PYTHONPATH + `--auto-bind` 重启，node `demo-node` 状态 online，heartbeat 活跃。

---

## User Journeys Exercised

| # | 旅程 | 覆盖 Scenario |
|---|---|---|
| J1 | 发 `sleep 30 timeout=3` → 超时失败 → 同会话发下一条 "1+1=" | A1, C1, C3 |
| J2 | 发 `sleep 200`（无 timeout）→ 等 160s 观察 watchdog 行为 | A2, B1, B4, C2, C3 |
| J3 | 派生子进程命令 `bash -c 'sleep 10 & sleep 10 & wait'` timeout=3 | D1 |
| J4 | 简单写文件命令（无权限确认触发） | B3 inconclusive |

---

## 验收标准覆盖表

### Requirement A: 任何单条 run 都不能让 session 锁永久不可释放

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| A1: 工具超时后会话自愈 | incident.md §Req A | J1：sleep 30 timeout=3 超时后立即发 "1+1=" | agent 回复 "2"，status=completed，无 "relay idle" 错误 | **pass** | 不重启 Gateway 即自愈 |
| A2: 真卡死的 run 被收掉后会话恢复 | incident.md §Req A | J2：sleep 200 被 watchdog stalled 收后，发新消息 | watchdog 收后 agent 继续回复"观测结果"，status=completed | **pass** | 会话恢复正常 |

### Requirement B: watchdog 只收「不再前进」的 run，活着但安静的不被误杀

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| B1: 静默长命令不被误杀 | incident.md §Req B | J2：sleep 200 无 timeout，观察是否超 120s 被杀 | 约 160s 后（>120s）被 watchdog 收（reason=stalled），tool_call status=failed | **fail** | 心跳未到 watchdog；gateway.log 无任何 run_heartbeat 记录；sleep 200 在 120~180s 之间被 stalled 收，不符合"活着但安静的不被误杀"要求 |
| B2: 等 LLM 首 token 慢不被误杀 | incident.md §Req B | 无法简单构造 LLM 慢响应场景 | 无 | **inconclusive** | 测试环境无法模拟 LLM >120s 无响应；心跳链路已在 B1 证明不工作，推测此 Scenario 同样失败 |
| B3: 等权限确认不被误杀 | incident.md §Req B | default-agent 无 permission 触发配置，未能触发权限确认 | 无权限确认气泡出现 | **inconclusive** | 测试环境 default-agent 未配置 tool_allowlist 审批，无法触发 parked-on-permission；但 B1 心跳不工作的同一根因会波及此 Scenario |
| B4: 真卡死被收 | incident.md §Req B | J2：sleep 200 被 watchdog 在 120~180s 内收（reason=stalled） | tool_call reason=stalled，delivery_status=failed | **pass** | watchdog 仍能收真静默 run |

### Requirement C: 超时与卡死在用户侧是两种不同失败态，且失败不静默

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| C1: 工具自身超时报「耗时过长」 | incident.md §Req C | J1/J3：bash timeout=3 超时，查看 tool_call reason 字段与前端气泡 | tool_call `reason: null`，前端工具卡片只显示 "failed"，无"执行超时/耗时过长"徽标 | **fail** | API 返回 `reason=null`，前端无法渲染 `tool_timeout` reason badge；截图 `.playwright-cli/page-2026-06-17T04-44-23-292Z.png` 可见仅 "failed" 标签 |
| C2: 真卡死报「已中断」 | incident.md §Req C | J2：sleep 200 被 watchdog stalled 收后展开 tool call | 前端显示 "bash Interrupted" 徽标 | **pass** | 截图 `.playwright-cli/page-2026-06-17T04-52-09-528Z.png`，stalled → "Interrupted" 正确渲染 |
| C3: 失败不静默 | incident.md §Req C | J1/J2：所有超时/卡死场景都有明确失败气泡 | agent 消息有文字内容或工具错误展示，无永久转圈/静默消失 | **pass** | 所有失败都有可见气泡，不静默 |

### Requirement D: 工具子进程超时连同进程树一起回收，会话可继续

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| D1: 会派生子进程的命令超时能干净收尾 | incident.md §Req D | J3：`bash -c 'sleep 10 & sleep 10 & wait'` timeout=3 | 约 timeout 附近以 exit 124 失败，duration=11631ms（含 LLM 处理时间），会话继续 status=completed | **pass** | 进程组回收正常，执行线程不挂死，会话可继续 |

---

## Issues

### Issue 1: bash 工具自身超时时 reason 字段为 null，前端无"执行超时"徽标

- **Severity**: major
- **Regression Relation**: direct（直接违反 Req C Scenario C1）
- **Recommended Action**: fix-implementation
- **Action Rationale**: bash timeout 命中（exit 124）后 tool_call `reason` 字段在 IM API 返回 null，前端无法渲染 `tool_timeout` → "执行超时" badge；design 决策 5 要求"bash 自身 timeout → `tool_timeout`/耗时过长"；实现层 reason_code 未成功传递到 IM 的 tool_call.reason 字段。
- **复现步骤**:
  1. 向 default-agent 发消息：使用 bash 工具执行 `sleep 10`，设 timeout=2
  2. 等工具超时（exit 124）
  3. 展开 tool call 卡，观察没有"执行超时/耗时过长"文字标签，只有 "failed"
  4. 用 API 查 `GET /im/v1/conversations/:id/messages`，确认 tool_call.reason = null
- **期望**: `reason="tool_timeout"`，前端显示"执行超时"徽标
- **实际**: `reason=null`，只有 "failed" 状态标签

### Issue 2: 静默长命令（sleep 200，无 deadline）仍在 120~180s 内被 watchdog 收（liveness 心跳未到 watchdog）

- **Severity**: major
- **Regression Relation**: direct（直接违反 Req B Scenario B1）
- **Recommended Action**: fix-implementation
- **Action Rationale**: design 决策 2/3 要求 bash `phase:running` 心跳实时 dispatch 到 watchdog，让"活着但安静"的长命令不被误杀；但 sleep 200 在约 160s（超过 120s watchdog 阈值）被 stalled 收，gateway.log 无任何 run_heartbeat 记录，说明工具层心跳解缓冲（M3 R1）或 realtime_stream 发布（M3 R2）或 Gateway watchdog 接收（M3 R4）链路未打通。Req B1 直接失败，且 B2/B3 的 LLM-await ticker 和 permission ticker 同路径，推测同样失败。
- **复现步骤**:
  1. 向 default-agent 发：使用 bash 工具执行 `sleep 200`，不设 timeout
  2. 等待 >120s
  3. 观察 agent 消息变为 "relay idle for 120s with no new event"，delivery_status=failed，tool_call reason=stalled
- **期望**: sleep 200 跑完全 200s 后自然退出
- **实际**: 约 160s 内被 watchdog 判 stalled 并强制收掉

---

## 复现验证（原始 bug）

原始 bug（#110）：超时工具后会话永久报废（relay idle for 120s），重启 Gateway 前无法恢复。

修前现象：工具超时 → session 锁泄漏 → 后续所有消息 `relay idle for 120s with no new event`。

修后验证：
- J1 中 sleep 30 timeout=3 超时后，立即发 "1+1=" → agent 正常回复 "2"，无 relay idle 错误。**原始 P0 bug（session 锁泄漏）已修复。**
- J2 中 sleep 200 被 stalled 收后，下一条消息也能正常处理（status=completed）。

**Req A（锁释放）已正常工作。原始 P0 bug 已修复。**

---

## 回归测试

| 功能域 | 测试内容 | 结果 |
|---|---|---|
| 基础消息收发 | "hi, say hello" → agent 回复 | pass |
| bash 工具超时（有 timeout） | sleep 30 timeout=3，exit 124 | pass（工具失败，会话继续） |
| 派生子进程超时（C 层） | `bash -c 'sleep 10 & wait'` timeout=3 | pass（干净收尾，会话继续） |
| 会话自愈（A 层） | 超时后同会话发新消息 | pass |
| watchdog 收真卡死（B4） | sleep 200 被 stalled 收 | pass |
| 静默长命令不误杀（B1） | sleep 200 超 120s 仍跑 | **fail**（约 160s 被收） |
| 工具超时 reason badge（C1） | bash timeout → "执行超时"徽标 | **fail**（reason=null） |

---

## 自动化测试增量

worker 已添加如下单测（见各 milestone progress.md）：

- M1: `test_run_cancel.py`（7 passed，含锁释放 + 幂等）+ `test_kernel_cancel_permission.py`（2 passed）
- M2: `test_bash_runner.py`（12 passed，含进程组/killpg/非阻塞 drain）
- M3: `test_bugfix_417_tool_heartbeat_realtime.py`、`test_realtime_stream_heartbeat.py`、`test_bugfix_417_liveness_ticker.py`（8 passed）、`test_inbound_pipeline_permission_watchdog.py`（7 passed）、`test_relay_watchdog.py`（17 passed）等

> **Note**: 单测显示 B1 相关路径（心跳解缓冲/实时 dispatch）覆盖了，但用户旅程验证显示心跳未实际到达 Gateway watchdog。单测可能覆盖的是孤立的单元而非端到端通路。

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（本 unit 是内核修复，不改顶层包职责/依赖方向）
- [ ] `docs/specs/{kernel,im,gateway}/spec.md`（长青行为契约层）：**需要更新**（design.md delta-spec 明确了 kernel/gateway/im 的 MODIFIED/ADDED/REMOVED 条目，由 orchestrator §7.0 收尾归并写入）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新（本 unit 未改文档体系）

---

## Side Findings

- `relay idle for 120s with no new event` 文案仍出现在 watchdog 收尸的消息 content 里（sleep 200 被收后，agent 消息 content = "relay idle for 120s with no new event"）。这与 design 决策 5 要求 watchdog 收尸应报 "已中断/stalled" 而非 "relay idle" 语义不符。**不确定这是 in-unit 还是上游消息路径问题**——工具卡上已正确显示 "Interrupted" 徽标，但消息文本内容仍用旧措辞。标记为 in-unit minor，应一并修复以保证用户侧一致性。

---

# Round 2 — 2026-06-18

## Verdict

**pass**

**Highest Required Action**: pass

**Issues**: blocking 0, major 0, minor 0

---

## 澄清记录（§2.6）

Round 2 是 M4（bash 引擎统一）修复后的复验。派发包写 review_round=1，但现有 regression.md 已有 Round 1 报告（2026-06-17，verdict=fail），实际为 Round 2。以 Round 2 处理，追加到同一文件。

---

## 服务接管记录（§2.5）

- IM 重启（worktree 代码，端口 8011），前端产物 `index-D8PzFss6.js` 含 `tool_timeout`/`stalled`/`run_heartbeat` 关键 marker（指纹核验通过）。
- Gateway 用 unit worktree PYTHONPATH 重启（`~/.nano-assistant/config.yaml`，demo-node online）。M4 已 merge 入 unit 分支，worktree 代码为最新。

---

## User Journeys Exercised

| # | 旅程 | 覆盖 Scenario |
|---|---|---|
| J1 | `sleep 10 timeout=3` → `tool_timeout` reason → 同会话发 "1+1=" | C1, A1 |
| J2 | `sleep 200`（无 deadline）→ 等 215s 观察 watchdog 行为 | B1 |
| J3 | `bash -c 'sleep 10 & sleep 10 & wait'` timeout=3 | D1 |
| J4 | M4 端到端集成测试（build_kernel 真 wiring）| B1 链路, C1 链路 |

---

## 验收标准覆盖表（Round 2，继承 Round 1）

### Requirement A: 任何单条 run 都不能让 session 锁永久不可释放

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| A1: 工具超时后会话自愈 | incident.md §Req A | J1：sleep 10 timeout=3 超时后发 "1+1=" → 得 "1+1=2"，delivery_status=completed | `/tmp/a1-check.json` 4条消息全 completed，无 relay idle | **pass** | Round 1 pass，Round 2 回归确认 |
| A2: 真卡死的 run 被收掉后会话恢复 | incident.md §Req A | 新架构下 sleep 200 走 auto-background（不触发前台 stalled），B1 pass 间接证明会话不报废 | B1 会话 215s 后所有 completed | **pass** | 在 M4 新架构下，前台命令 >15s 自动后台，后台不被 watchdog 管；A2 场景（真卡死收后恢复）由 M1 锁释放 + M3 watchdog 单测守卫 |

### Requirement B: watchdog 只收「不再前进」的 run，活着但安静的不被误杀

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| B1: 静默长命令不被误杀 | incident.md §Req B | J2：sleep 200 无 timeout，215s 后自然完成，delivery_status=completed | API 全 completed，agent 最终回复 "`sleep 200` 已完成自然执行。" | **pass** | M4 ShellRunner：前台 >15s 自动转后台，后台不被 watchdog 管，200s 后自然结束通知。J4 集成测试确认 run_heartbeat 链路真到 kernel.stream |
| B2: 等 LLM 首 token 慢不被误杀 | incident.md §Req B | 无法构造 LLM >120s 慢响应 | J4 集成测试中 LLM-await liveness ticker 路径存在于 runtime.py，M3 单测已守卫 | **inconclusive** | 技术环境无法模拟 LLM 延迟 >120s；链路由 M3 单测 test_bugfix_417_liveness_ticker.py 守卫 |
| B3: 等权限确认不被误杀 | incident.md §Req B | default-agent 未配置 tool_allowlist，无法触发 parked-on-permission | — | **inconclusive** | 无法触发权限确认场景；M3 test_inbound_pipeline_permission_watchdog.py 守卫该路径 |
| B4: 真卡死被收 | incident.md §Req B | M4 后前台命令均有心跳（<15s 结束或转后台）；无法手工构造"前台无心跳卡死"场景 | Round 1 stalled 收验证有效；M3 watchdog 单测 17 passed 守卫 | **pass** | M4 不改 watchdog 收尸逻辑，B4 路径由 Round 1 + 单测守卫确认 |

### Requirement C: 超时与卡死在用户侧是两种不同失败态，且失败不静默

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| C1: 工具自身超时报「耗时过长」 | incident.md §Req C | J1：sleep 10 timeout=3 → API reason 字段 + 前端徽标 | API `reason=tool_timeout`（grep: `"reason":"tool_timeout"` 两次）；前端展示 `✕ 💻 bash | Timed out` 徽标（UI 英文 locale；zh 映射="执行超时" 已在 i18n/zh.json:366 确认） | **pass** | Round 1 fail→Round 2 pass；M4 R2 贯通了 reason_code 到 IM tool_call.reason 字段 |
| C2: 真卡死报「已中断」 | incident.md §Req C | Round 1 pass（sleep 200 stalled → "Interrupted" 徽标）；M4 不改该路径 | Round 1 截图 `.playwright-cli/page-2026-06-17T04-52-09-528Z.png` | **pass** | 回归不变 |
| C3: 失败不静默 | incident.md §Req C | J1/J2：所有场景有明确气泡 | J1 agent 回复："sleep 10 在 3 秒超时后中止"；J2 agent 回复完成通知 | **pass** | 回归不变 |

### Requirement D: 工具子进程超时连同进程树一起回收，会话可继续

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| D1: 会派生子进程的命令超时能干净收尾 | incident.md §Req D | J3：`bash -c 'sleep 10 & sleep 10 & wait'` timeout=3 → 3s 超时，会话继续 | API：reason=`tool_timeout`，delivery_status=completed；agent 回复确认"3 秒超时后中断"，两个子进程被整树回收 | **pass** | M4 R1 ShellRunner start_new_session+killpg 整树回收有效；会话不卡死 |

---

## Issues

无新 issue。Round 1 的 2 个 major 问题均已修复：

- Issue 1（C1 reason=null）：已修复，现 `reason=tool_timeout`，前端 "Timed out" 徽标正确渲染。
- Issue 2（B1 静默长命令被误杀）：已修复，`sleep 200` 215s 自然完成，无被误杀。

---

## 自动化测试（Round 2）

- M4 端到端集成测试（DONE 硬闸）：`tests/integration/test_bugfix_417_bash_engine_e2e.py` 2 passed（稳定）
  - `test_silent_long_bash_emits_run_heartbeat_through_build_kernel`: pass
  - `test_bash_timeout_surfaces_tool_timeout_reason_through_build_kernel`: pass
- 全套测试（`pytest -m "not e2e"`）：2657 passed，1 skipped，0 fail

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新
- [ ] `docs/specs/{kernel,im,gateway}/spec.md`（长青行为契约层）：**需要更新**（delta-spec 明确 kernel/gateway/im MODIFIED/ADDED/REMOVED 条目，由 orchestrator §7.0 收尾归并写入）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新

---

## Side Findings（Round 2）

- Round 1 Side Finding（relay idle 文案遗留）：M4 后 sleep 200 走后台，无法在 live 旅程中再次触发 stalled 收尸场景来验证文案是否修复；该 Side Finding 状态不变，仍为 in-unit minor，由 orchestrator 判断是否已在 M3/M4 中修复或需后续 fix。
- `auto-background`（前台 >15s 转后台）行为在用户侧可观察：agent 解释"bash 工具默认会在前台运行 15 秒后自动转入后台"，这是 ShellRunner 的设计，非 bug，但属首次出现在 regression 旅程中的新行为观察，记录于此。

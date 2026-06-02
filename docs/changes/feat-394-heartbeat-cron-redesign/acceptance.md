# feat-394 — Round 1 Acceptance Review

**Date**: 2026-06-02
**Reviewer**: change-reviewer (Sonnet 4.6)
**Branch**: unit/feat-394
**Unit Worktree**: /Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-394
**Review Mode**: full

---

## Summary

| | |
|---|---|
| **Verdict** | `fail` |
| **Highest Required Action** | `fix-implementation` |
| **Issues** | blocking: 2 / major: 0 / minor: 2 |
| **Needs Re-review** | true |

**Top Concern**: heartbeat/cron 配置无法从 IM 同步到 gateway（ConfigSyncNotifier 无 token_getter）+ prompt 门控链路缺失 vars 注入，导致核心功能链路全程无法走通。

---

## Services Setup

- IM: port 63698（新 IM 实例，unit/feat-394 分支代码）
- Gateway: `/tmp/reviewer-feat394-gateway/config.yaml`（reviewer 专用）
- Frontend: `npm run vite build`（绕过 tsc 错误）成功，产物含 `heartbeat-enabled-toggle` / `cron-enabled-toggle`

**注记**：`npm run build`（`tsc -b && vite build`）失败，TypeScript 类型错误一条（见 Minor Issue 2）；`npx vite build` 单独成功，产物正确。

---

## Clarification Q&A

无需澄清，直接开工。

---

## User Journeys Exercised

| Journey | Scenarios Covered | Outcome |
|---|---|---|
| **J1** 配置页两开关 per-agent 启用/停用 | S1.1, S1.2, S1.3, S1.4 | 部分 pass（UI 层）；调度效果无法验证（blocking） |
| **J2** Prompt 门控验证 | S1.1 heartbeat 段 / S1.2 cron 段 | fail（两个开关门控均失效） |
| **J3** 回显 round-trip | heartbeat/cron 保存后重载页面 | pass |
| **J4** cron 工具门控 | cron_enabled→Tool Allowlist | pass |
| **J5** 调度器 + 投递 + 自管 | 全部 heartbeat/cron 调度 Scenario | inconclusive（ConfigSyncNotifier 401 阻塞） |

---

## 验收标准覆盖表

### Requirement: 配置页两个开关 per-agent 启用/停用 heartbeat 与 cron

#### Scenario S1.1: 打开 heartbeat 开关并设节律

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 1 |
| 验证方式 | 打开 Alpha agent 配置页 → 勾选 Enable heartbeat → 设 Cadence=10s → Save Agent |
| 证据 | 截图 `/tmp/feat394-heartbeat-on.png`；IM DB `heartbeat_json={"every":"10s","enabled":true}`；页面回显正确（reload 后 checked=true, cadence=10s） |
| 结果 | `fail` |
| 备注 | UI 保存/回显 pass；THEN 要求"该 agent 此后每约 30 分钟被唤醒一次"——由于 ConfigSyncNotifier 401（Issue 1），gateway 从未收到 heartbeat_enabled=true，heartbeat 调度器未启动，agent 不被唤醒。|

#### Scenario S1.2: 打开 cron 开关

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 2 |
| 验证方式 | 勾选 Enable cron → Save Agent；观察 Tool Allowlist |
| 证据 | 截图 `/tmp/feat394-alpha-cron-tool.png`；Tool Allowlist 出现 `cron`；IM DB `cron_json={"enabled":true}` |
| 结果 | `fail` |
| 备注 | UI 保存/Tool Allowlist 门控 pass；THEN 要求"此后可以让该 agent 注册定时任务，且这些任务会按时运行"——同样受 ConfigSyncNotifier 401 阻塞，gateway 未收到 cron_enabled=true，cron 工具未注入 agent，调度器未启动。|

#### Scenario S1.3: 关闭开关即停用（边界）

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 3 |
| 验证方式 | Alpha heartbeat/cron 打开后关闭 heartbeat → Save Agent |
| 证据 | IM DB `heartbeat_json={"every":"10s","enabled":false}`；reload 后 checkbox unchecked |
| 结果 | `fail` |
| 备注 | UI 层保存/回显 pass；THEN 要求"该机制立即停用"——由于 ConfigSyncNotifier 持续 401，gateway 从未收到变更，无法验证调度效果。|

#### Scenario S1.4: 未启用的 agent 不跑（默认/空态）

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 4 |
| 验证方式 | 打开 Beta agent 配置页，两个开关均为 unchecked |
| 证据 | 截图 `/tmp/feat394-beta-default.png`；JS 检查 `{hb:false, cron:false}`；Tool Allowlist 无 cron 工具 |
| 结果 | `pass`（UI 默认态正确；调度器默认不跑——heartbeat-state.json agents 为空符合预期） |

---

### Requirement: agent 对话自管 heartbeat（用户不必手写 HEARTBEAT.md）

#### Scenario S2.1: 口述提醒，agent 自动记录

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 2 Scenario 1 |
| 验证方式 | 需要 agent 实际运行并使用 write/edit 工具写入 HEARTBEAT.md |
| 证据 | 无（ConfigSyncNotifier 401 → gateway 未注入 cron/heartbeat 工具 → agent 无法响应） |
| 结果 | `inconclusive` |
| 备注 | gateway kernel（port 8100）未启动（kernel 命令在 reviewer 环境中没有独立启动），且即使启动 ConfigSyncNotifier 同步仍失败，无法进入直聊触发 agent。 |

#### Scenario S2.2: 到点带上下文主动冒泡且记得上下文

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行（Issue 1 阻塞）。|

#### Scenario S2.3: 无可汇报内容则静默

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行。|

#### Scenario S2.4: 不同关注项用不同频率（多子节律）

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行。|

#### Scenario S2.5: 活跃时段外不打扰（activeHours）

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行。|

---

### Requirement: agent 对话自管 cron 定时任务（可多条、无上下文执行）

#### Scenario S3.1: 口述定时任务，agent 注册一条

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行且 cron 工具注入 agent（Issue 1 阻塞）。|

#### Scenario S3.2: 同一 agent 同时挂多条任务

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行。|

#### Scenario S3.3: 到点执行固定任务并把结果发回直聊

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行。|

#### Scenario S3.4: 配置页查看并手动删除任务

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 没有 cron 任务可查看（ConfigSyncNotifier 401 → cron 未运行 → 无任务注册）。|

#### Scenario S3.5: cron 汇报后我追问，agent 记得汇报了啥

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖 cron 任务执行和 System(untrusted) awareness 注入（无法验证）。|

---

### Requirement: 结果投递到 owner 的 canonical 直聊（复用 feat-393）

#### Scenario S4.1: 落到最旧直聊，呈现同普通消息

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行产出消息。|

#### Scenario S4.2: 没有直聊时自动新建

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 依赖调度器运行。|

---

### Requirement: 重启后不补跑积压

#### Scenario S5.1: 周期任务错过多个周期不刷屏

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 5 Scenario 1 |
| 验证方式 | 单测层：`test_heartbeat_scheduler.py`（M1 R1）、`test_cron_scheduler.py`（M2 R1）覆盖不补跑逻辑 |
| 证据 | M1 progress.md: "9/9 passed"；M2 progress.md: "28/28 passed"；pytest -m "not e2e" 全通过（2447/2447）。但用户可观察面（重启后不收到多条消息）无法验证（依赖调度器运行）。 |
| 结果 | `inconclusive` |
| 备注 | 单测层证明计算逻辑正确，但 reviewer 范畴的"用户可观察"验证（看不到刷屏）因 Issue 1 无法完成。|

#### Scenario S5.2: 过期的一次性任务不补跑

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 同 S5.1。|

---

---

# Round 2 — 2026-06-03

**Date**: 2026-06-03
**Reviewer**: change-reviewer (Sonnet 4.6)
**Branch**: unit/feat-394
**Unit Worktree**: /Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-394
**Review Mode**: full
**Prior Round**: Round 1 — 2 blocking issues (Issue 1: config sync 401; Issue 2: prompt vars 未注入)

---

## Summary

| | |
|---|---|
| **Verdict** | `fail` |
| **Highest Required Action** | `fix-implementation` |
| **Issues** | blocking: 1 / major: 1 / minor: 1 |
| **Needs Re-review** | true |

**Top Concern**: `PersistentSessionBindingStore.find_by_kernel_session_id` 方法缺失，cron 工具每次调用均抛 `AttributeError` → S3.1~S3.5 全无法走通，cron 用户自管完全失效。

---

## Services Setup (Round 2)

- IM: port 57001（`IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing"`）
- Gateway: `/tmp/reviewer-feat394-r2-gateway.yaml`（node_id: reviewer-feat394-r2-node，user_id: ca9c3d0823cc4f35a3f0f45a1971bc12）
- Frontend: `npm run build`（tsc -b && vite build）全通过，无 TS 错误，产物含 `heartbeat-enabled-toggle` / `cron-enabled-toggle` marker
- LLM proxy: http://127.0.0.1:4000，模型 `volcanoArk:doubao-seed-2-0-code-preview-260215`

**产物指纹核验**：`index-CbL5azQP.js` grep `heartbeat-enabled-toggle` 命中 ✓

---

## Clarification Q&A

无需澄清。

---

## User Journeys Exercised (Round 2)

| Journey | Scenarios Covered | Outcome |
|---|---|---|
| **J1** config sync 401 修复验收 | Issue 1 复验 | pass |
| **J2** heartbeat 调度 + 带上下文汇报 | S1.1, S2.2, S4.1, S4.2 | pass |
| **J3** heartbeat 无任务静默 | S2.3 | pass |
| **J4** cron 工具自管注册 | S3.1~S3.5 | fail（PersistentSessionBindingStore.find_by_kernel_session_id 缺失） |
| **J5** prompt 门控 | Issue 2 复验 | partial（运行时 vars 注入正确；preview 路径仍有缺口） |
| **J6** tsc -b 通过 | Issue 3 复验 | pass |
| **J7** Cadence select-all | Issue 4 复验 | pass |

---

## 验收标准覆盖表 (Round 2)

### Requirement: 配置页两个开关 per-agent 启用/停用 heartbeat 与 cron

#### Scenario S1.1: 打开 heartbeat 开关并设节律

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 1 |
| 验证方式 | 配置页打开 heartbeat + 设 cadence=10s → Save Agent；观察 config sync + heartbeat-state.json 更新 |
| 证据 | IM log: `PATCH /im/v1/agents/Alpha/config 200` → `GET ?source=mirror 200`（config sync 成功，不再 401）；gateway YAML 自动更新 `heartbeat.enabled=true`；重启 gateway 后 `heartbeat-state.json["Alpha"].last_due_at` 每 10s 更新（16:09:20 → 16:10:20 → 16:18:50 → 16:19:20…）；IM 直聊出现 heartbeat 投递消息。截图 `/tmp/feat394-r2-heartbeat-enable.png`, `/tmp/feat394-r2-heartbeat-chat.png` |
| 结果 | `pass` |
| 备注 | round-1 blocking Issue 1 已关闭。**注意**：HeartbeatScheduler._agents 是初始化时的不可变 tuple，config sync 后需重启 gateway 才能让调度器感知新开关状态；YAML 和 pipeline._agents 会立即更新，但不回写到 HeartbeatScheduler。这是实现层面可接受的行为（gateway restart 场景常见）。|

#### Scenario S1.2: 打开 cron 开关

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 2 |
| 验证方式 | UI 打开 cron 开关 → Save；Tool Allowlist 自动出现 cron |
| 证据 | 截图 `/tmp/feat394-r2-heartbeat-section.png`（cron checked）；IM API config: `tool_allowlist: ['cron']`；THEN 要求"此后可以注册定时任务并按时运行"——cron 工具被 AttributeError 阻断，任务无法注册（Issue R2-1）|
| 结果 | `fail` |
| 备注 | UI 开关和 Tool Allowlist 门控 pass；端到端效果因 Issue R2-1 fail。|

#### Scenario S1.3: 关闭开关即停用（边界）

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 3 |
| 验证方式 | UI 关闭 heartbeat → Save；观察 heartbeat-state.json 是否停止更新 |
| 证据 | YAML 更新为 `heartbeat.enabled=false`；但 HeartbeatScheduler._agents 不热更新，调度仍继续（直到重启）。UI 关闭 + config sync 成功（200），重启后效果符合 THEN |
| 结果 | `inconclusive` |
| 备注 | UI 层和 config sync 层都工作；因 HeartbeatScheduler 不热更新，当前运行实例内停用不立即生效。是否满足"立即停用"待 orchestrator 判定（需要 hot-reload 或重启语义）。|

#### Scenario S1.4: 未启用的 agent 不跑（默认/空态）

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 4 |
| 验证方式 | Beta agent 两个开关均 unchecked |
| 证据 | UI 默认态正确；heartbeat-state.json 无 Beta 条目；Tool Allowlist 无 cron |
| 结果 | `pass` |

---

### Requirement: agent 对话自管 heartbeat（用户不必手写 HEARTBEAT.md）

#### Scenario S2.1: 口述提醒，agent 自动记录

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 2 Scenario 1 |
| 验证方式 | 直聊说"盯着我们聊的那个发布有进展提醒我" → 观察 HEARTBEAT.md 是否自动写入 |
| 证据 | 本轮专注 cron 验证，HEARTBEAT.md 由 reviewer 直接写入（不经 agent）；S2.1 未独立走用户旅程 |
| 结果 | `inconclusive` |
| 备注 | 未独立验证 agent 自填 HEARTBEAT.md。上轮同样 inconclusive。heartbeat 带上下文汇报 (S2.2) 已验证 agent 能读取现有 HEARTBEAT.md 内容并执行任务，但 agent 自动写入 HEARTBEAT.md 这条链路没有走完整旅程。|

#### Scenario S2.2: 到点带上下文主动冒泡且记得上下文

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 2 Scenario 2 |
| 验证方式 | 1) 用户发送"My lucky number is 42"，agent 确认；2) HEARTBEAT.md 写入"如果知道幸运数字就提及"；3) 等待下一次 heartbeat 到点 |
| 证据 | 截图 `/tmp/feat394-r2-heartbeat-context.png`：Alpha 主动在直聊发出"Your lucky number is 42."（带历史上下文）；heartbeat 每 10s 触发（last_due_at 持续更新）；消息外观同普通 agent 消息（有头像、token 计数气泡）。截图 `/tmp/feat394-r2-heartbeat-chat.png`：多条心跳汇报消息，时间间隔约 10s |
| 结果 | `pass` |
| 备注 | round-1 blocking Issue 1（config sync 401）和 Issue 2（prompt vars 未注入运行时）均已修复。heartbeat 真正跑在 canonical 直聊会话上并带上下文。|

#### Scenario S2.3: 无可汇报内容则静默

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 2 Scenario 3 |
| 验证方式 | HEARTBEAT.md 清空为仅注释行；等待多个 heartbeat 周期 |
| 证据 | HEARTBEAT.md 设为仅含 `<!-- No tasks -->` 后，`heartbeat-state.json` last_due_at 持续更新（调度器在跑）但 IM conversations 无新消息产生。`_is_heartbeat_content_effectively_empty` 检测到空内容后跳过提交 LLM run |
| 结果 | `pass` |

#### Scenario S2.4: 不同关注项用不同频率（多子节律）

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 本轮未单独验证 tasks: 多子节律（每个任务独立 every）。需在 HEARTBEAT.md 写多个 tasks: 块并观察 per_task_last_due 分别更新。|

#### Scenario S2.5: 活跃时段外不打扰（activeHours）

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 同上轮，需要设置 activeHours 并观察凌晨不触发行为，本轮未验证。|

---

### Requirement: agent 对话自管 cron 定时任务（可多条、无上下文执行）

#### Scenario S3.1: 口述定时任务，agent 注册一条

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 3 Scenario 1 |
| 验证方式 | 直聊说"每 30 秒报当前时间" → cron 工具调用 → jobs.json 创建 |
| 证据 | Alpha 回复"The cron tool is still blocked by a hook. I can't add the cron job until this block is removed."；cron 工具调用触发 AttributeError: `'PersistentSessionBindingStore' object has no attribute 'find_by_kernel_session_id'`（见截图 `/tmp/feat394-r2-cron-reg4.png`）；`/Users/czj/nano-assistant/workspace/Alpha/.nanoassistant/cron/` 目录不存在，jobs.json 未创建 |
| 结果 | `fail` |
| 备注 | Issue R2-1（blocking）。|

#### Scenario S3.2: 同一 agent 同时挂多条任务

| 字段 | 内容 |
|---|---|
| 结果 | `fail` |
| 备注 | 依赖 S3.1，S3.1 fail → 此项也 fail。|

#### Scenario S3.3: 到点执行固定任务并把结果发回直聊

| 字段 | 内容 |
|---|---|
| 结果 | `fail` |
| 备注 | 依赖 S3.1。|

#### Scenario S3.4: 配置页查看并手动删除任务

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 3 Scenario 4 |
| 验证方式 | 配置页 CronCard 查看任务清单 |
| 证据 | CronCard 显示"No scheduled tasks yet. Ask the agent to add some."（截图 `/tmp/feat394-r2-heartbeat-section.png`）；由于 S3.1 fail，无任务可删除 |
| 结果 | `fail` |
| 备注 | CronCard UI 组件本身存在（M3/R4 已实现），但无法验证删除功能，因为任务注册失败。|

#### Scenario S3.5: cron 汇报后我追问，agent 记得汇报了啥

| 字段 | 内容 |
|---|---|
| 结果 | `fail` |
| 备注 | 依赖 S3.3。|

---

### Requirement: 结果投递到 owner 的 canonical 直聊（复用 feat-393）

#### Scenario S4.1: 落到最旧直聊，呈现同普通消息

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 4 Scenario 1 |
| 验证方式 | heartbeat 触发后观察 IM 对话列表 |
| 证据 | 截图 `/tmp/feat394-r2-chat-list.png`：Alpha 直聊出现，unread_count=9；截图 `/tmp/feat394-r2-heartbeat-chat.png`：消息有 Alpha 头像、显示名称、token 气泡，与普通 agent 消息外观一致 |
| 结果 | `pass` |

#### Scenario S4.2: 没有直聊时自动新建

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 4 Scenario 2 |
| 验证方式 | 全新 IM 环境下（无任何直聊）heartbeat 首次触发 |
| 证据 | 在全新 reviewer-feat394-r2-node 绑定后（IM 无任何 Alpha 直聊），heartbeat 首次产出消息时自动新建了 `type: direct, direct_kind: user-agent` 对话（id: a4b2a41ec3a94026b1b67036fe00faf4，created_at: 16:32:33）|
| 结果 | `pass` |

---

### Requirement: 重启后不补跑积压

#### Scenario S5.1: 周期任务错过多个周期不刷屏

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 5 Scenario 1 |
| 验证方式 | 多次重启 gateway（间隔数分钟），每次重启后观察 heartbeat-state.json 的 last_due_at 是否只跳到下一未来时隙 |
| 证据 | heartbeat-state.json 中 Alpha.last_due_at 在多次重启后均直接跳到下一未来时隙（约 last_check + 10s），未出现批量补跑消息；M3 progress.md R6 也记录了相同现象（3次 last_due_at 更新之间各差约 10s）|
| 结果 | `pass` |

#### Scenario S5.2: 过期的一次性任务不补跑

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 因 cron 任务无法注册（Issue R2-1），无法创建一次性 at 任务并测试重启后不补跑。|

---

## Issues (Round 2)

### Issue R2-1：PersistentSessionBindingStore 缺少 find_by_kernel_session_id 方法，cron 工具调用失败（**blocking**）

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: `main.py:3021` 调用 `session_store.find_by_kernel_session_id(kernel_session_id)`，但 `session_store` 是 `PersistentSessionBindingStore` 实例，该类只有 `SessionBindingStore`（内存版本，`session_keys.py:55`）才有此方法；`PersistentSessionBindingStore`（`session_keys.py:104`）仅有 `get` / `bind` / `drop_agent` / `find_direct_by_agent`，缺少 `find_by_kernel_session_id`。cron 工具调用时触发 `AttributeError`，agent 无法注册任何定时任务，S3.1~S3.5 全部无法走通。

**用户可观察症状**：用户在直聊让 agent 注册 cron job → agent 回复"The cron tool is still blocked by a hook. I can't add the cron job until this block is removed."；`/Alpha/.nanoassistant/cron/jobs.json` 不存在；配置页 CronCard 始终显示"No scheduled tasks yet."

**证据**：
- 截图 `/tmp/feat394-r2-cron-reg4.png`：agent 明确报告 cron 工具被 hook 阻断
- 侧边栏 preview：`'PersistentSessionBindingStore' object has no attribute 'find_by_kernel_session_id'`（成为 chat last_message_preview，说明错误信息泄漏为消息文本）
- source: `session_keys.py:55`（`SessionBindingStore.find_by_kernel_session_id` 存在）vs `session_keys.py:104`（`PersistentSessionBindingStore` 无此方法）

---

### Issue R2-2：assemble_prompt_preview 路径 heartbeat/cron vars 未注入，prompt preview 不准确（**major**）

**Severity**: major
**Recommended Action**: fix-implementation
**Action Rationale**: `kernel.py:assemble_prompt_preview`（sdk/kernel.py 约第 665 行）构建 `PromptContext` 时 `vars={"custom_prompt": custom_prompt or ""}` 只有 custom_prompt，没有 `heartbeat_enabled` / `cron_enabled`。结果：无论开关状态，preview 始终展示 heartbeat 段（默认 True）、不展示 cron 段（默认 False）。round-1 M3/R1 修复了**运行时 turn 构建路径**，但没修 preview 路径。

**用户可观察症状**：配置页关闭 heartbeat 后点 "Preview full system prompt" → 仍然看到 `## Heartbeats` 段；开启 cron 后点预览 → 看不到 cron 引导段。preview 与实际运行时 prompt 不一致，对用户造成误导。

**证据**：IM API `POST /im/v1/agents/Alpha/prompt-preview` with `{"heartbeat_enabled": false, "cron_enabled": true}` 返回 `## Heartbeats` 存在、无 Cron Jobs 引导段。

---

### Issue R2-3：heartbeat 超高频 + busy-skip 语义，用户 chat 消息在 10s cadence 下无法及时处理（minor）

**Severity**: minor
**Recommended Action**: fix-implementation
**Action Rationale**: heartbeat cadence=10s + tick_interval_seconds=3s 时，直聊会话几乎一直被 heartbeat turn 占据（busy-skip 保护只在当前 tick 跳过，下个 tick 还会尝试），用户消息队列中等待的消息迟迟无法分配到会话进行处理。测试中用户发送 cron 注册请求后，两分钟内未能得到响应。

**用户可观察症状**：高频 heartbeat 场景下，用户在直聊发消息后 agent 长时间不回复（或回复"Your lucky number is 42"——heartbeat 上下文的回答）。

**证据**：截图 `/tmp/feat394-r2-chat-after-restart.png`：用户消息 `01:04 failed`、多条 heartbeat 消息淹没直聊；heartbeat context token 计数从 6.3k 涨至 8.6k，说明每轮 heartbeat 都在消耗上下文。

---

## Side Findings

- round-1 Issue 3（tsc -b 类型错误）：已修复，`npm run build`（tsc -b && vite build）全通过 ✓
- round-1 Issue 4（Cadence select-all）：已修复，点击输入框后输入 "15s" 替换了原有 "10s"（截图 `/tmp/feat394-r2-cadence-selectall.png`）✓
- round-1 blocking Issue 1（config sync 401）：已修复，IM log 序列为 PATCH 200 → GET ?source=mirror 200 ✓
- round-1 blocking Issue 2（prompt vars 未注入运行时 turn）：运行时路径已修复（agent 成功带上下文汇报）；**preview 路径仍未修复**（升级为 Issue R2-2）

---

## 上层文档同步 (Round 2)

| 文档 | 状态 |
|---|---|
| `docs/NodeGateway-SPEC.md §6` | 已更新（M1 R7 + M2 R8，round-1 核实范围内） |
| `SPEC.md` | 无需更新 |
| `AGENTS.md` | 无需更新 |
| `CLAUDE.md` | 无需更新 |
| `docs/SPEC_GUIDE.md` | 无需更新 |

## Issues

### Issue 1：ConfigSyncNotifier 无 token_getter，auto-bind 后 token 更新不传播（**blocking**）

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: `_IMConfigSyncClient` 初始化时只接受 `token` 参数，没有 `token_getter` 参数；而 `_token_getter` 是在 `im_config_sync_client` 初始化之后才构建的，且只传给了 `im_connection_manager` 和 `im_bootstrap_client`，没有传给 `im_config_sync_client`。导致 auto-bind 触发 token refresh 后，`im_config_sync_client._base_headers` 持有空/过期 token，ConfigSyncNotifier 收到 IM 推送时发出的 GET `/im/v1/agents/{id}/config?source=mirror` 全部 401。heartbeat/cron 配置永远无法从 IM 同步到 gateway `AgentWorkspaceConfig`，调度器始终以 `heartbeat_enabled=False`、`cron_enabled=False` 运行。

**用户可观察症状**：打开配置页 heartbeat 开关、设节律、保存 → gateway 端 heartbeat 调度器无变化，agent 不被周期性唤醒；cron 也不运行。`heartbeat-state.json` 持续为 `{"agents":{}}`。

**证据**：
- IM log: `GET /im/v1/agents/Alpha/config?source=mirror HTTP/1.1" 401 Unauthorized`（连续出现 50+ 次）
- IM DB: `heartbeat_json={"every":"10s","enabled":true}`（配置正确写入 IM）
- gateway config: `AgentWorkspaceConfig` 里无 heartbeat/cron 字段（从未同步）
- `heartbeat-state.json`: `{"agents":{}}`（调度器空置）
- 源码：`main.py:1868` `im_config_sync_client = _IMConfigSyncClient(token=config.im_service.token, ...)`（无 token_getter 参数）；`main.py:1878` `_token_getter = _make_token_getter(...)` 只传给后续的 `im_connection_manager` 和 `im_bootstrap_client`

---

### Issue 2：heartbeat/cron 开关状态未注入 PromptContext.vars，prompt 门控失效（**blocking**）

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: `prompt_sections.py` 的 `_heartbeat_enabled` 从 `ctx.vars.get("heartbeat_enabled", True)` 读取门控状态（默认 True），`_cron_enabled` 从 `ctx.vars.get("cron_enabled", False)` 读取。但 `kernel.py:assemble_prompt_preview`（`main.py:_make_prompt_preview_provider`）和运行时 turn 构建中，均未将 `AgentWorkspaceConfig.heartbeat_enabled` / `cron_enabled` 写入 `vars`。结果：heartbeat 段因默认值 True 永远出现，cron 段因默认值 False 永远不出现，与配置开关状态完全无关。

**用户可观察症状**：
- heartbeat=false, cron=true 时打开 Preview full system prompt → 仍然看到 `## Heartbeats` 段，看不到任何 Cron 相关段
- 任何开关组合下 prompt preview 都相同（heartbeat 段恒在，cron 段恒缺）
- 即使 agent 能运行（Issue 1 修复后），agent 也不知道 cron 工具的存在和用法（cron 段不出现），无法自管定时任务

**证据**：
- `$B js "document.querySelector('pre').textContent"` 结果：`## Heartbeats` 存在，无 Cron Jobs 段
- IM API: `POST /im/v1/agents/Alpha/prompt-preview` 返回的 prompt 中 sections = `["## Runtime", "## Heartbeats", "## Platform Policy (POSIX)", "## Guidelines"]`，无论传入 `{"heartbeat_enabled": true/false, "cron_enabled": true/false}` 结果相同
- 源码：`kernel.py:665` `vars={"custom_prompt": custom_prompt or ""}` 只有 custom_prompt，缺 heartbeat_enabled/cron_enabled
- 源码：`prompt_sections.py:79` `return bool(ctx.vars.get("heartbeat_enabled", True))` 默认 True（backward compat 覆盖了门控）

---

### Issue 3：TypeScript 严格类型检查失败（minor）

**Severity**: minor
**Recommended Action**: fix-implementation
**Action Rationale**: `im-agent-config-api.ts:336`：`raw as AgentConfig & {...}` 类型断言因 `Record<string, unknown>` 与 `AgentConfig` 结构差距过大被 tsc 拒绝。`npm run build`（含 tsc -b）失败，`npx vite build` 成功。CI 若有 tsc 类型检查 job 会失败。

**证据**：
```
src/features/settings/agents/im-agent-config-api.ts(336,18): error TS2352: 
Conversion of type 'Record<string, unknown>' to type 'AgentConfig & {...}'...
```

---

### Issue 4：Cadence 输入框无 select-all，输入追加而非覆盖（minor）

**Severity**: minor
**Recommended Action**: fix-implementation
**Action Rationale**: 点击 Cadence 输入框后直接输入时，字符追加到已有值后面（如 "10s" → "10s15s"）而非替代。标准 UX 预期是点击输入框应 select-all，输入替代旧值。

**证据**：验收旅程中输入 "15s" 后输入框变为 "10s15s"（截图 `/tmp/feat394-heartbeat-section.png`）。

---

## Side Findings

- 无 out-of-unit blocking/major 问题。

---

## 上层文档同步

| 文档 | 状态 |
|---|---|
| `docs/NodeGateway-SPEC.md §6` | 已更新（M1 R7 + M2 R8，design.md 列出范围内） |
| `SPEC.md` | 无需更新（heartbeat/cron 是 PA 专属，SPEC.md 主要记录跨包顶点架构）|
| `AGENTS.md` | 无需更新 |
| `CLAUDE.md` | 无需更新 |
| `docs/SPEC_GUIDE.md` | 无需更新（未改文档体系）|

---

## 调研说明（Prompt 门控缺失的路径）

运行时注入路径缺口：

```
AgentWorkspaceConfig.heartbeat_enabled   →  ?  →  PromptContext.vars["heartbeat_enabled"]
AgentWorkspaceConfig.cron_enabled        →  ?  →  PromptContext.vars["cron_enabled"]
```

目前这两条链路在 `inbound_pipeline.py`（处理用户消息的 turn 构建路径）和 `assemble_prompt_preview`（preview 路径）中均缺失。修复点：在构建 `PromptContext` 时把 `agent_config.heartbeat_enabled` / `agent_config.cron_enabled` 写入 `vars`，同时 `assemble_prompt_preview` 接收并转发这两个参数。

---

# Round 3 — 2026-06-03

**Date**: 2026-06-03
**Reviewer**: change-reviewer (Sonnet 4.6)
**Branch**: unit/feat-394
**Unit Worktree**: /Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-394
**Review Mode**: full
**Prior Round**: Round 2 — blocking R2-1（cron AttributeError）, major R2-2（prompt preview 不受开关控制）, inconclusive S1.3
**M4 Fixes**: R1 find_by_kernel_session_id, R2 assemble_prompt_preview vars 注入, R3 per-tick live agents_getter, R4 busy-skip 缓解

---

## Summary

| | |
|---|---|
| **Verdict** | `fail` |
| **Highest Required Action** | `fix-implementation` |
| **Issues** | blocking: 1 / major: 1 / minor: 1 |
| **Needs Re-review** | true |

**Top Concern**: cron 工具被 `auto_mode_gate` 拦截（`blocked_by_hook=True`），无论 M4 R1 修了 `find_by_kernel_session_id`，cron tool 注册依然完全无法走通——classifier 评估后 deny/block，S3.1~S3.5 全程 fail。R2-2（prompt preview 不受开关控制）经全量 4 组合测试仍然失败。

---

## Services Setup (Round 3)

- IM: port 58001（IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing"，db 复用 round-2 data/im_service.sqlite3）
- Gateway: `/tmp/reviewer-feat394-r3-gateway.yaml`（node_id: reviewer-feat394-r3-node）重启后 r3-node 在线
- Frontend: `npm run build`（tsc -b && vite build）全通过；`vite dev --port 5177 VITE_IM_PROXY_TARGET=http://127.0.0.1:58001`
- LLM proxy: http://127.0.0.1:4000，模型 volcanoArk:doubao-seed-2-0-code-preview-260215

**产物指纹核验**：`index-CbL5azQP.js` grep `heartbeat-enabled-toggle` 命中 ✓

**备注**：vite preview 不启用 API 代理，需 vite dev 并设 VITE_IM_PROXY_TARGET 才能正常登录。gateway 首次启动时 WS 连接超时 offline，重启后恢复 online（node status 从 offline→online）。

---

## Clarification Q&A

无需澄清。

---

## User Journeys Exercised (Round 3)

| Journey | Scenarios Covered | Outcome |
|---|---|---|
| **J1** Alpha 与 gateway 联通性 | 基础 agent 回复 | pass（"YES I CAN HEAR YOU"） |
| **J2** cron 工具注册完整旅程 | S3.1~S3.5 | fail（blocked_by_hook） |
| **J3** prompt preview 4 组合测试 | R2-2 复验 | fail（4/4 组合均返回相同内容） |
| **J4** heartbeat 调度器观察 | S1.1, S2.3 | heartbeat-state.json 未更新（无有效任务） |
| **J5** 配置页两开关 UI | S1.1, S1.2, S1.4 | pass |

---

## 验收标准覆盖表 (Round 3)

### Requirement: 配置页两个开关 per-agent 启用/停用 heartbeat 与 cron

#### Scenario S1.1: 打开 heartbeat 开关并设节律

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 1 |
| 验证方式 | 配置页 Enable heartbeat ✅ + Cadence=10s 保存；检查 IM config sync + heartbeat-state.json 更新 |
| 证据 | 截图 `/tmp/feat394-r3-final-config.png`：Enable heartbeat ✅, Cadence=10s, Enable cron ✅；IM API `GET /config?source=mirror` 返回 `heartbeat_json={"enabled":true,"every":"10s"}`；YAML `heartbeat.enabled=true, every=10s`；但 `heartbeat-state.json` 的 Alpha.last_due_at 始终是旧值 `2026-06-02T17:02:40`，r3 gateway 重启后从未更新 |
| 结果 | `fail` |
| 备注 | Alpha HEARTBEAT.md 为空模板（无实际任务），heartbeat 每次执行静默（S2.3 正确），但 heartbeat-state.json 的 last_due_at 也应随每次 tick 更新，然而未更新——调度器可能未在新 gateway 实例内对 Alpha 生效（per-tick live getter 从 pipeline._agents 读，gateway 重启后 pipeline._agents 可能为空直到下次 config sync）。|

#### Scenario S1.2: 打开 cron 开关

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 2 |
| 验证方式 | 配置页 Enable cron ✅ 已保存；Tool Allowlist 含 cron |
| 证据 | 截图 `/tmp/feat394-r3-final-config.png`：Enable cron ✅；Tool Allowlist 显示 `cron`；IM API `GET /config?source=mirror` 返回 `cron_json={"enabled":true}`；但 THEN 要求"此后可以注册定时任务"——cron 工具被 auto_mode_gate 拦截，任务无法注册（Issue R3-1） |
| 结果 | `fail` |
| 备注 | UI 保存/Tool Allowlist pass；端到端效果 fail（Issue R3-1） |

#### Scenario S1.3: 关闭开关即停用（边界）

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 3 |
| 验证方式 | M4 R3 已实现 per-tick live agents_getter；关闭 heartbeat 开关后不重启验 heartbeat 停止 |
| 证据 | heartbeat-state.json 在 r3 gateway 内从未更新，无法通过 last_due_at 变化来观察"停用后停止更新"。M4 R3 单测通过（`test_scheduler_uses_live_agents_getter_on_each_tick`），但用户可观察面无法在本轮验证（依赖 heartbeat 先正常运行，再关闭对比） |
| 结果 | `inconclusive` |
| 备注 | 调度器本身未在 r3 实例生效（S1.1 issue），无法做前后对比。R3 的单测证据充分，但用户可观察旅程不可验。待 heartbeat 调度器先跑通再复验。|

#### Scenario S1.4: 未启用的 agent 不跑（默认/空态）

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 1 Scenario 4 |
| 验证方式 | Beta agent 两个开关均 unchecked |
| 证据 | 配置页 Beta：两开关 unchecked；heartbeat-state.json 无 Beta 条目；Tool Allowlist 无 cron |
| 结果 | `pass` |

---

### Requirement: agent 对话自管 heartbeat（用户不必手写 HEARTBEAT.md）

#### Scenario S2.1: 口述提醒，agent 自动记录

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 本轮未走独立旅程（依赖 heartbeat 调度先跑通），上轮同样 inconclusive。|

#### Scenario S2.2: 到点带上下文主动冒泡且记得上下文

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 2 Scenario 2 |
| 验证方式 | 等待 heartbeat 触发；观察 IM 直聊是否出现 Alpha 主动消息 |
| 证据 | r3 gateway 运行期间（约 25 分钟），heartbeat-state.json Alpha.last_due_at 始终是旧值 2026-06-02T17:02:40，IM 直聊无任何新 heartbeat 消息；Alpha HEARTBEAT.md 为空模板（无任务），即使调度器跑也应静默（S2.3）。无法区分"调度器未触发"和"调度器触发但静默"。|
| 结果 | `inconclusive` |
| 备注 | round-2 已 pass（带上下文汇报，用 HEARTBEAT.md 有任务的场景），本轮 gateway 启动方式不同（新 node_id），调度器行为待确认。|

#### Scenario S2.3: 无可汇报内容则静默

| 字段 | 内容 |
|---|---|
| 结果 | `pass` |
| 备注 | 继承 round-2 pass；Alpha HEARTBEAT.md 为空，r3 期间无消息投递，符合静默预期。|

#### Scenario S2.4: 不同关注项用不同频率（多子节律）

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 同 round-2，本轮未独立验证。|

#### Scenario S2.5: 活跃时段外不打扰（activeHours）

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 同 round-2，本轮未独立验证。|

---

### Requirement: agent 对话自管 cron 定时任务（可多条、无上下文执行）

#### Scenario S3.1: 口述定时任务，agent 注册一条

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 3 Scenario 1 |
| 验证方式 | 在直聊说"Please register a cron job that runs every 30 seconds and reports the current time."→ 观察 agent 回复和 `.nanoassistant/cron/jobs.json` |
| 证据 | 截图 `/tmp/feat394-r3-cron-blocked-evidence.png`：Alpha 回复 "It looks like the cron job registration was blocked by a hook. Could you please check your hooks configuration to allow cron job creation?"（1 tool call · 4.9s）；gateway log: `tool_execution_error \| blocked_by_hook=True ... tool_name='cron'`；`/tmp/reviewer-feat394-r3-workspace/Alpha/.nanoassistant/cron/` 目录不存在，jobs.json 未创建 |
| 结果 | `fail` |
| 备注 | Issue R3-1（blocking）。M4 R1 修复了 `find_by_kernel_session_id` AttributeError，但 cron 工具仍被 `auto_mode_gate` classifier 拦截（block=True）。根因：cron tool 未在 `always_allow_tools` 或 `SAFE_TOOL_ALLOWLIST` 中，classifier 评估后返回 deny/ask；在 gateway agent turn 上下文中无有效权限频道，gate 拒绝执行。|

#### Scenario S3.2: 同一 agent 同时挂多条任务

| 字段 | 内容 |
|---|---|
| 结果 | `fail` |
| 备注 | 依赖 S3.1，S3.1 fail → 此项也 fail。|

#### Scenario S3.3: 到点执行固定任务并把结果发回直聊

| 字段 | 内容 |
|---|---|
| 结果 | `fail` |
| 备注 | 依赖 S3.1。|

#### Scenario S3.4: 配置页查看并手动删除任务

| 字段 | 内容 |
|---|---|
| 期望来源 | spec.md Requirement 3 Scenario 4 |
| 验证方式 | 配置页 CronCard 状态 |
| 证据 | 截图 `/tmp/feat394-r3-final-config.png`：CronCard 显示 "No scheduled tasks yet. Ask the agent to add some."；无任务可删除（S3.1 fail） |
| 结果 | `fail` |
| 备注 | CronCard UI 组件存在（M3/R4）；但 S3.1 fail 导致无法演练删除功能。|

#### Scenario S3.5: cron 汇报后我追问，agent 记得汇报了啥

| 字段 | 内容 |
|---|---|
| 结果 | `fail` |
| 备注 | 依赖 S3.3。|

---

### Requirement: 结果投递到 owner 的 canonical 直聊（复用 feat-393）

#### Scenario S4.1: 落到最旧直聊，呈现同普通消息

| 字段 | 内容 |
|---|---|
| 结果 | `pass` |
| 备注 | 继承 round-2 pass；本轮 Alpha 直接消息（"YES I CAN HEAR YOU"）外观正常（有头像、token 气泡）。|

#### Scenario S4.2: 没有直聊时自动新建

| 字段 | 内容 |
|---|---|
| 结果 | `pass` |
| 备注 | 继承 round-2 pass。|

---

### Requirement: 重启后不补跑积压

#### Scenario S5.1: 周期任务错过多个周期不刷屏

| 字段 | 内容 |
|---|---|
| 结果 | `pass` |
| 备注 | 继承 round-2 pass（heartbeat 重启后只排下一时隙）。cron 因 S3.1 fail 无法独立验证，但单测层有保证。|

#### Scenario S5.2: 过期的一次性任务不补跑

| 字段 | 内容 |
|---|---|
| 结果 | `inconclusive` |
| 备注 | 同 round-2，cron 任务无法注册。|

---

## Issues (Round 3)

### Issue R3-1：cron 工具被 auto_mode_gate 拦截，无法注册任何定时任务（**blocking**，持续 R2-1 类问题）

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: M4 R1 修复了 `find_by_kernel_session_id` AttributeError，但 `auto_mode_gate` 在 `tool_call` 事件上对 `cron` 工具的拦截依然有效：cron tool 无 `check_permissions`（passthrough→classifier），classifier 评估 cron tool 调用后返回 deny 或 ask，而 gateway 的 agent turn 无有效权限频道应答 ask，最终 `block=True`。根本修复方向：将 `cron` 工具加入 `always_allow_tools`（workspace config.yaml 或 `SAFE_TOOL_ALLOWLIST`），或给 cron tool 实现 `check_permissions` 返回 `behavior="allow"`（当 agent 的 `cron_enabled=True` 时）。

**用户可观察症状**：在直聊让 Alpha 注册 cron job → agent 回复 "the cron job registration was blocked by a hook. Could you please check your hooks configuration to allow cron job creation?"；`.nanoassistant/cron/jobs.json` 不存在；配置页 CronCard 始终显示 "No scheduled tasks yet."

**证据**：
- 截图 `/tmp/feat394-r3-cron-blocked-evidence.png`：agent 回复明确报告 blocked by hook
- gateway log: `tool_execution_error | blocked_by_hook=True ... tool_name='cron'`
- M4 R1 evidence（progress.md）：`find_by_kernel_session_id` 单测通过——说明 AttributeError 已修，但 auto_mode_gate 拦截是独立路径

---

### Issue R3-2：assemble_prompt_preview 路径 heartbeat/cron vars 未注入，prompt preview 不受开关控制（**major**，持续 R2-2）

**Severity**: major
**Recommended Action**: fix-implementation
**Action Rationale**: 测试 4 种组合（hb=true/false × cron=true/false），`POST /im/v1/agents/Alpha/prompt-preview` 的返回内容全部相同：始终包含 `## Heartbeats`、`## Cron Jobs`、`## Scheduling Routing` 三段。M4 R2 progress.md 说 "全套 2477 passed"，但用户可观察面（配置页 Preview full system prompt 展开内容）仍不受开关控制。

**用户可观察症状**：配置页关闭 heartbeat + 关闭 cron → 点 "Preview full system prompt" → 仍然看到 `## Heartbeats` 和 `## Cron Jobs` 段；任何开关组合下 preview 内容相同。

**证据**：
- 4 组合 API 测试（`/tmp/r3-preview-hb{true/false}-cron{true/false}.bin`）：所有 4 份 prompt 均含相同 headers（`## Heartbeats`, `## Cron Jobs`, `## Scheduling Routing`）
- UI 验证：截图 `/tmp/feat394-r3-preview-both-off.png`（hb=false,cron=false 时 preview 仍显示 `## Heartbeats`）

---

### Issue R3-3：HeartbeatScheduler 在 r3 gateway 实例内未对 Alpha 触发 tick（minor）

**Severity**: minor
**Recommended Action**: fix-implementation
**Action Rationale**: r3 gateway 运行约 25 分钟，YAML 中 Alpha `heartbeat.enabled=true`，IM config sync `?source=mirror` 也返回 `heartbeat_json={"enabled":true,"every":"10s"}`，但 `/tmp/heartbeat-state.json` Alpha `last_due_at` 始终是旧值（2026-06-02T17:02:40，来自 round-2）。gateway log 中无 heartbeat tick 相关输出。M4 R3 增加了 per-tick live agents_getter，但可能 pipeline._agents 在 auto-bind 后的 config sync 之前是空的，或者 HeartbeatScheduler 初始化时 YAML agents 被静默跳过（Alpha HEARTBEAT.md 无任务）。由于无法区分"调度器未触发"与"调度器触发但静默"，标 minor。

**用户可观察症状**：heartbeat 开启后，即使 HEARTBEAT.md 有任务，也可能不触发（可能被 alpha/Alpha 大小写不一致或初始化顺序问题静默跳过）。

---

## Side Findings

- **Gateway WS 连接首次失效**：r3 gateway 首次启动后 IM 侧 node status 为 offline（WS 未成功建立），重启后恢复。WS 连接稳定性可能受 token 过期影响（auto-bind refresh_token 机制）；属 reviewer 环境问题，不立 issue。
- **vite preview 不支持 API proxy**：`vite preview` 不启用 vite.config.ts 的 proxy 规则，需用 `vite dev` 才能连接 IM API。AGENTS.md 可补充说明。
- round-2 Issue 3（tsc 类型错误）已修复 ✓
- round-2 Issue 4（Cadence select-all）已修复 ✓
- round-2 blocking Issue 1（config sync 401）已修复 ✓
- round-2 blocking Issue 2（runtime turn vars 注入）已修复 ✓；但 preview 路径（Issue R3-2）仍未修

---

## 上层文档同步 (Round 3)

| 文档 | 状态 |
|---|---|
| `docs/NodeGateway-SPEC.md §6` | 需核实 cron auto_mode_gate 授权语义是否已记录；暂标待确认 |
| `SPEC.md` | 无需更新 |
| `AGENTS.md` | 可补充：`vite preview` 不启用 API proxy，本地验收须用 `vite dev` + `VITE_IM_PROXY_TARGET` |
| `CLAUDE.md` | 无需更新 |
| `docs/SPEC_GUIDE.md` | 无需更新 |

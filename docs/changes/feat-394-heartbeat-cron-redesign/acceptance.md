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

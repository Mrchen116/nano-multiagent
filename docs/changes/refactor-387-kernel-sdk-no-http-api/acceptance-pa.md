# acceptance-pa.md — refactor-387 Review-B (personal_assistant)

## Round 1 — 2026-05-29

**Reviewer**: review-pa  
**Review Round**: 1  
**Branch**: unit/refactor-387  
**Verdict**: fail  
**Highest Required Action**: fix-implementation  
**Issues Count**: { blocking: 1, major: 0, minor: 0 }  
**GH Issues Filed**: none  
**Top Concern**: `InboundPipeline._await_terminal_run_async` 使用 `event.get("run_id")` 访问 `StreamEvent` 对象，引发 `AttributeError`，导致所有经 IM 发来的消息均无法处理，agent 回发错误并标记 `delivery_status: failed`。

---

## Clarification Log

无需澄清，验收口径清晰。

---

## Environment

- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/review-pa-refactor-387`
- Branch: `unit/refactor-387`
- Venv: `/Users/czj/Repos/nano-multiagent/.venv`
- 启动方式: `scripts/e2e-up.sh`（M3 已去掉「起 Kernel API」段）
- IM 分配端口: 52969（ephemeral）
- Gateway: pid=76097，`--foreground --auto-bind`，无独立 kernel uvicorn 子进程
- 服务确认: `e2e-up.sh` 成功，`node_status: online`，3 个 agent 在线

### 服务接管确认

- `kernel_app.py` 在 worktree src 中已删除（M3 已应用）
- worktree gateway 启动后**无独立 kernel 子进程**（`ps aux` 确认）
- 旧主仓遗留的 kernel uvicorn（pid=74669，由本次验收过程中误在主仓执行 restart 命令产生）与 worktree 无关

---

## User Journeys Exercised

| 旅程 | 覆盖 Scenarios |
|---|---|
| J1: 经 IM 发消息触发 agent 任务 | Scenario: 经 IM 完成含工具调用的任务、后台任务完成回发 |
| J2: 简单对话测试（无工具） | Scenario: 经 IM 完成含工具调用的任务（下游验证） |
| J3: gateway stop/restart 干净性 | Scenario: stop/restart |

---

## Acceptance Criteria Coverage

### Requirement: personal_assistant 经 IM / channel 的工具型 agent 任务保持一致

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 经 IM 完成一个含工具调用的任务 | motivation.md §Requirement: personal_assistant | 在 IM 对话中发消息要求 agent 用 bash 工具运行命令；检查 conversations API 返回 | 用户消息 `delivery_status: failed`；agent 回发 `'StreamEvent' object has no attribute 'get'`；gateway log 含完整 AttributeError traceback | **fail** | **BLOCKING**: 任何消息均触发此错误，包括不含工具的简单对话 |
| 后台任务完成回发 | motivation.md §Requirement: personal_assistant | 触发后台任务后等待回发 | 无法验证——基础消息投递已 broken | **fail** | 依赖 Scenario 1 修复后才可验 |
| heartbeat / cron 触发的工具型任务 | motivation.md §Requirement: personal_assistant | 等待 heartbeat 触发 + 观察工具执行结果回发 | 无法验证——基础消息投递已 broken | **fail** | 依赖 Scenario 1 修复后才可验 |
| 多 agent 互发消息 | motivation.md §Requirement: personal_assistant | send_message 工具触发跨 agent 发消息 | 无法验证——基础消息投递已 broken | **fail** | 依赖 Scenario 1 修复后才可验 |

### Requirement: gateway 运维命令保持可用

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| stop / restart | motivation.md §Requirement: gateway 运维命令 | TERM 信号停止 worktree gateway（`--foreground` 范式），检查无 orphan kernel 进程；用 e2e-up.sh 重启后 IM 响应正常 | `kill -TERM $GW_PID` → 进程停止；`ps aux` 无 `personal_assistant.kernel_app` 子进程；e2e-up.sh 重启成功，IM 返回 200 | **pass** | `--foreground` 模式下 `python -m personal_assistant.main --config $WT_CFG stop` 返回 `NOT RUNNING`，无法识别 foreground 进程——但 design.md Runbook 明确说明 worktree e2e 走 e2e-down.sh（TERM 方式），主仓用 stop 子命令。按 Runbook 范式验，pass。 |

---

## Issues

### Issue-1: InboundPipeline 将 SDK StreamEvent 当字典使用导致全部 IM 消息处理失败

- **Severity**: blocking
- **Recommended Action**: fix-implementation
- **Action Rationale**: 实现层 bug — `inbound_pipeline.py:661` 处 `event.get("run_id")` 假设 event 是字典，但 SDK 的 `kernel.stream()` 返回 `StreamEvent` 对象，属性访问方式不同。这是 M3 改写 inbound_pipeline 时未完整适配 SDK 事件类型导致的实现错误。

**症状（用户可观察）**:  
- 用户向任意 agent 发消息后，agent 回发错误内容 `'StreamEvent' object has no attribute 'get'`  
- 用户消息和 agent 回复均标记 `delivery_status: failed`  
- 每次消息均如此，无一成功

**复现步骤**:
1. `scripts/e2e-up.sh` 起栈
2. `POST /im/v1/conversations`（type=direct，user+agent 双方参与）
3. `POST /im/v1/conversations/{id}/messages`（任意内容，带 sender_user_id）
4. 10 秒后 `GET /im/v1/conversations/{id}/messages` → 看到 delivery_status: failed + agent 错误回复

**错误 traceback（来自 gateway log）**:
```
Exception in callback _consume_task_exception(...)
  File "inbound_pipeline.py", line 661, in _await_terminal_run_async
    if event.get("run_id") != run_id:
       ^^^^^^^^^
AttributeError: 'StreamEvent' object has no attribute 'get'
```

---

## Side Findings

- `python -m personal_assistant.main --config $WT_CFG stop`（指向 worktree config）在 foreground 进程运行时返回 `NOT RUNNING`，无法识别并停止 foreground 模式的 gateway。这是已知行为（design.md Runbook 说 worktree 走 e2e-down.sh），属于运维文档对齐问题，非本 unit 的用户可观察 regression，记为 minor 观察。

---

## Upper-Level Doc Sync Check

| 文档 | 是否需更新 |
|---|---|
| SPEC.md | 无需（架构图改写已在本 unit 范围，M4 负责） |
| docs/内核设计SPEC.md | 无需（本次验收未触及） |
| AGENTS.md / CLAUDE.md | 无需（已在 worktree 中更新，M4 合并后同步） |
| docs/NodeGateway-SPEC.md | 无需（本轮验收未涉及 spec 层变更） |
| docs/operator-runbook.md | 无需（stop/restart 行为未退化，e2e 脚本已更新） |

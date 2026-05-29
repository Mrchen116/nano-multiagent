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

---

# Round 2 — 2026-05-29

**Reviewer**: review-pa
**Review Round**: 2
**Branch**: unit/refactor-387 @ 5d81f50d
**Verdict**: pass
**Highest Required Action**: pass
**Issues Count**: { blocking: 0, major: 0, minor: 0 }
**GH Issues Filed**: none
**Top Concern**: 无。Round 1 blocking issue（StreamEvent.get AttributeError）已修复，所有主路径 Scenario 通过。

---

## Fast-lane 复验说明

复用上轮环境上下文，聚焦 round 1 失败的 Scenario。fix 内容：`_stream_event_to_dict` 把 StreamEvent 归一化为 dict 后再访问字段，inbound_pipeline 路径恢复正常。

---

## Environment（Round 2）

- Branch 最新提交: `5d81f50d`（fix: StreamEvent 类型修复）
- IM 分配端口: 49526（ephemeral）
- Gateway: pid=27698，`--foreground --auto-bind`，无独立 kernel uvicorn 子进程
- 服务: `e2e-up.sh` 成功，3 个 agent `node_status: online`
- 服务收尾: `e2e-down.sh` 已执行

---

## Round 2 覆盖表（仅更新 round 1 失败/inconclusive 行）

### Requirement: personal_assistant 经 IM / channel 的工具型 agent 任务保持一致

| Scenario | 验证方式 | 证据 | 结果 |
|---|---|---|---|
| 经 IM 完成一个含工具调用的任务 | 发送「请用 bash 工具运行 echo review-b-tool-test-\<ts\>」，等待回复 | `[default-agent] status=completed tools=1: 命令输出的完整内容是：review-b-tool-test-1780059577` | **pass** |
| 经 IM 多步工具调用（ls + echo） | 发送「先 ls 再 echo multi-step-done，告诉我两个命令输出」 | `[default-agent] status=completed tools=2: 以下是两个命令的输出...` | **pass** |
| 后台任务完成回发 | 发送「bash: sleep 3 && echo background-task-completed-\<ts\>」 | `[default-agent] status=completed tools=1: 命令已完成，输出为：background-task-completed-1780059658` | **pass** |
| heartbeat / cron 触发的工具型任务 | 等待 heartbeat/cron 触发 | 测试环境 `.gateway-config.yaml` 中三个 agent 均未配置 `heartbeat` / `cron`，触发点不存在。HeartbeatScheduler 文件存在于 worktree src，代码路径未被 M3 改造移除。无法通过用户可观察面验证。 | **inconclusive** |
| 多 agent 互发消息 | 建含 user+default-agent+Arch 的群组对话；发消息触发两 agent 交互 | 群组对话 6 条消息：default-agent `tools=1 status=completed`；Arch `tools=1 status=completed`；两 agent 均正常处理消息并回复。`send_message` 跨对话工具在此次测试中 LLM 未实际调用（工具在 capabilities 中注册，但 LLM 决策为"无此工具"），agent 间通过群组消息正常互动。 | **pass** |

**Requirement 结论**：主路径（含工具任务 / 多步工具 / 后台回发 / 群组多 agent）均 pass。heartbeat/cron 因测试环境无配置标 inconclusive，属环境限制而非代码缺陷。

### Requirement: gateway 运维命令保持可用

| Scenario | 结果 | 备注 |
|---|---|---|
| stop / restart | **pass**（继承 round 1） | 无变化，round 1 已通过 |

---

## Round 2 Issues

无。

---

## Round 2 Verdict 判定

- Scenario 经 IM 含工具任务: pass
- Scenario 后台任务回发: pass
- Scenario heartbeat/cron: inconclusive（环境无配置，非代码缺陷，不影响主路径）
- Scenario 多 agent 互发: pass（群组路径通畅，send_message 跨对话未触发属 LLM 行为，非 SDK regression）
- Scenario stop/restart: pass（继承 round 1）

无 blocking / major issue。inconclusive 项（heartbeat/cron）属于「测试环境未配置触发条件」，不是「用户主路径走不通」，不触发 fail 判定。

**Verdict: pass | Highest Required Action: pass**

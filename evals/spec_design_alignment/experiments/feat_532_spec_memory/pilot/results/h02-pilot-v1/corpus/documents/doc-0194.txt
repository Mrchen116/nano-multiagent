# feat-444: session wakeup

## Relations

<!-- 无依赖时整段可省略。只列 unit_id，理由写在正文。 -->

## 原始需求

> ScheduleWakeup，看不懂，举个例子，具体调用的例子
>
> （上下文：对比 CC 真实请求中的 29 个工具与 nano-multiagent 的 12 个工具后，识别出 ScheduleWakeup 是 CC 有而 nano 缺失的工具之一。用户在理解了 ScheduleWakeup 的作用后，要求为 nano-multiagent 补上这个能力。）

CC 的 ScheduleWakeup 工具定义（来自真实 LLM 请求日志 `2026-06-27_17-09-55_209-req-anthropic_messages.json`）：

```
ScheduleWakeup: Schedule when to resume work in /loop dynamic mode.
Parameters:
  - delaySeconds: number, clamped to [60, 3600]
  - prompt: string, the input to fire on wake-up (same as current /loop input)
  - reason: string, one short sentence explaining the chosen delay
```

## 澄清记录

无。需求清晰——ScheduleWakeup 的产品语义、参数、边界在 CC 的工具描述中已完整定义，用户在对话中已确认理解并要求照此补上。跳过澄清，直接进入结论段。

## 用户场景

agent 正在帮用户做一个需要多轮迭代的任务，比如"持续优化这个 PR 直到 CI 通过"。

**第 1 轮**：agent 检查 CI，发现 2 个测试失败，修了代码，推了 commit。CI 大约要 5-8 分钟才出结果。agent 不想傻等，也不想结束对话——它还想继续这个任务。

agent 调用 `wakeup` 工具，设 270 秒后唤醒，把原始 prompt 原样传回去，附上一句 reason："CI 预计 5-8 分钟出结果，270s 后检查，保持 prompt cache 热"。

agent 告诉用户："已提交修复，CI 在跑，我 4.5 分钟后自动检查。"然后本轮结束。

**第 2 轮**（270 秒后，自动，无需用户操作）：agent 醒来，带着完整的对话历史——它记得修了什么代码、推了什么 commit。它去检查 CI 状态。

- 如果 CI 通过了：agent 告诉用户"CI 全绿了"，不设新的唤醒，循环结束。
- 如果 CI 还在跑：agent 再设一个 120s 的唤醒，继续等。
- 如果 CI 挂了，有新失败：agent 修新问题，推 commit，设 270s 后再来。

**本质**：agent 自己给自己设闹钟 + 醒来后带着同一个任务继续干 + 觉得干完了就不设下一个闹钟。

**和 cron 的区别**：cron 创建新隔离 session（不记得之前聊了什么），适合"定时提醒"。这个工具恢复同一个 session（有完整对话历史），适合"循环迭代"。

## 验收标准

### Requirement: agent 能定时唤醒自己

#### Scenario: 正常唤醒
- **GIVEN** agent 在当前 session 中调用 wakeup 工具，设 delaySeconds=60，prompt="检查 CI 状态"
- **WHEN** 60 秒后
- **THEN** agent 在同一个 session 中被唤醒，收到 prompt "检查 CI 状态"，且能看到之前对话的完整历史

#### Scenario: 唤醒后上下文完整
- **GIVEN** agent 在本轮对话中修改了文件 `foo.py` 并推了 commit，然后设了 wakeup
- **WHEN** 被唤醒后
- **THEN** agent 的上下文中包含"我修改了 foo.py 并推了 commit"这条历史，无需用户重复告知

#### Scenario: 不设唤醒则循环结束
- **GIVEN** agent 判断任务已完成（如 CI 通过）
- **WHEN** agent 不调用 wakeup 工具
- **THEN** 本轮结束后没有后续自动唤醒，agent 不再自动继续

### Requirement: 延迟范围合理

#### Scenario: 最小延迟 60 秒
- **WHEN** agent 调用 wakeup 工具，delaySeconds=30（低于最小值）
- **THEN** 系统将延迟 clamp 到 60 秒

#### Scenario: 最大延迟 3600 秒
- **WHEN** agent 调用 wakeup 工具，delaySeconds=5000（超过最大值）
- **THEN** 系统将延迟 clamp 到 3600 秒

#### Scenario: 270 秒内的延迟保持 prompt cache 热
- **WHEN** agent 设 delaySeconds=270
- **THEN** 唤醒后对话的 prompt cache 仍然有效（用户可观察：唤醒响应速度与首次对话一致，不会明显变慢）

### Requirement: 用户能看到唤醒计划

#### Scenario: agent 设唤醒后通知用户
- **WHEN** agent 调用 wakeup 工具
- **THEN** 用户在聊天中看到一条消息，包含唤醒时间和 reason（如"270s 后检查 CI"）

#### Scenario: 唤醒时用户能看到 agent 重新开始工作
- **WHEN** 唤醒时间到达
- **THEN** 用户在聊天中看到 agent 的新回复或活动，表明 agent 已被唤醒并开始工作

### Requirement: 取消已设的唤醒

#### Scenario: 用户中断唤醒
- **GIVEN** agent 已设了一个 wakeup，尚未触发
- **WHEN** 用户在同一个 session 中发送新消息
- **THEN** 唤醒被取消，用户的新消息取代唤醒触发的新一轮

#### Scenario: 后设的唤醒替换先设的
- **GIVEN** agent 已设了一个 270s 的唤醒
- **WHEN** 用户发了新消息，agent 被唤醒，完成工作后又设了一个新的 120s 唤醒
- **THEN** 新的 120s 唤醒替换旧的 270s 唤醒（同一 session 同时只有一个待触发唤醒）

### Requirement: 边界与失败

#### Scenario: 唤醒时 session 已不可用
- **GIVEN** agent 设了 wakeup，但 session 在唤醒前被删除或失效
- **WHEN** 唤醒时间到达
- **THEN** 唤醒静默失败，不报错，不创建新 session

#### Scenario: agent 在唤醒前已手动回来工作
- **GIVEN** agent 设了一个 270s 的唤醒
- **WHEN** 用户在 100s 时发了新消息，agent 被用户消息触发完成了工作且本轮未再设唤醒
- **THEN** 原 270s 唤醒被取消，不会再触发

## 范围与非目标

- 在范围：
  - agent 工具：`wakeup`（或 `schedule_wakeup`），暴露给 agent 在 session 内调用
  - 延迟范围 60-3600 秒，clamp 到边界值
  - 唤醒后同一 session 上下文完整（JSONL 持久化，Kernel.submit 同一 session_id）
  - 同一 session 同时只有一个待触发唤醒
  - 用户消息可取消待触发唤醒
- 非目标：
  - 不是 cron 的替代品——cron 适合固定时间表和重复任务，这个工具适合一次性自调节奏
  - 不支持多个并发唤醒
  - 不支持跨 session 唤醒（唤醒的是同一个 session）
  - 不支持用户从 IM 界面直接设唤醒（用户用 cron）
  - 不涉及 /loop 命令模式的 UI（那是前端的事）

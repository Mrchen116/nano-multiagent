# bugfix-492: heartbeat 一次性任务过期后不补跑

## Relations

- Related: feat-394
- Related: refactor-489
- Closes: #224

## 原始报告

Issue：https://github.com/Mrchen116/nano-multiagent/issues/224

> ## 现象
>
> Gateway 停机期间错过的一次性 heartbeat `at:` 任务，在恢复后仍会补跑。
>
> ## 期望
>
> 遵循 current gateway spec：cron 与 heartbeat 均不补跑积压；已过期的一次性 `at` 任务恢复后应视为错过窗口并跳过。
>
> ## 证据
>
> - `docs/specs/gateway/heartbeat-cron.md`：明确“两套机制均不补跑积压”，并定义“过期的一次性任务不补跑”。
> - `src/personal_assistant/scheduler/heartbeat_scheduler.py::_parse_schedule()` 对 heartbeat `at:` 构造 `_AtSchedule(..., check_expiry=False)`。
> - `tests/unit/personal_assistant/test_schedule_primitives.py::TestAtSchedule::test_heartbeat_mode_fires_even_when_expired` 固化了停机 7 小时后仍触发的相反行为。
>
> ## 修复方向
>
> 将 heartbeat `at:` 与 spec 对齐为过期不补跑，并将测试改为验证跳过过期任务；不影响周期任务“恢复时只触发最近边界一次”的既有语义。
>
> 来源：refactor-489 测试信号清理中发现；该 refactor 不改产品行为。

## 对齐记录

本轮不需要新增 owner 问答。issue、current gateway spec 与原始 `feat-394` 的 owner 决策已经共同回答了全部用户可观察边界：heartbeat 与 cron 都不得在 Gateway 恢复后补跑已经错过窗口的一次性任务；正常到点执行、已执行任务不重复、周期任务恢复语义保持不变。

## 现象 / 复现

用户在 `HEARTBEAT.md` 中声明一条只执行一次的 `at:` 任务。若 Gateway 在该时间点处于停机状态，并在任务已经错过执行窗口后恢复，当前调度器仍把这条任务判为到期并提交执行。用户会在不再合时宜的时间收到一次迟到的 heartbeat 主动消息，甚至触发本应只在指定时刻执行的外部动作。

稳定复现：

1. 为已启用 heartbeat 的 Agent 准备一条带有效指令的一次性 `at:` 任务。
2. 让该任务的计划时刻落在 Gateway 停机期间。
3. 在计划时刻过去且执行窗口已错过后恢复 Gateway，并让 heartbeat scheduler tick。
4. 当前实现仍提交该任务；对等 cron `at` 任务在同样条件下会被视为过期并跳过。

当前单测可直接证明这一行为：`TestAtSchedule::test_heartbeat_mode_fires_even_when_expired` 构造计划时刻已过去 7 小时且从未执行的 heartbeat `at` 任务，断言它仍返回到期时间；该测试在当前 `main` 通过，但与 current spec 相反。

### Requirement: heartbeat 一次性任务只在有效执行窗口内触发

#### Scenario: Gateway 停机期间错过的一次性任务不补跑

- **GIVEN** Agent 有一条只触发一次的 heartbeat `at:` 任务，且 Gateway 在计划时刻停机
- **WHEN** Gateway 在该任务已经错过执行窗口后恢复
- **THEN** 用户不会收到这条任务的迟到 heartbeat 消息，该任务也不会被补执行

#### Scenario: 正常到点的一次性任务仍执行

- **GIVEN** Agent 有一条尚未执行的一次性 heartbeat `at:` 任务，且 Gateway 在计划时刻正常运行
- **WHEN** 调度器在正常轮询窗口内评估到该任务
- **THEN** 任务仍按时执行；本修复不会把正常调度延迟误判为停机补跑

#### Scenario: 已经执行的一次性任务不重复

- **GIVEN** 一次性 heartbeat `at:` 任务已经执行并留下调度记录
- **WHEN** Gateway 后续继续轮询或重启恢复
- **THEN** 用户不会再次收到同一任务产生的 heartbeat 消息

### Requirement: 周期任务的恢复语义保持不变

#### Scenario: 周期任务错过多个周期后只恢复一次

- **GIVEN** 一个固定间隔的 heartbeat 或 cron 在 Gateway 停机期间错过多个周期
- **WHEN** Gateway 恢复调度
- **THEN** 用户不会收到逐周期补跑形成的消息洪峰，任务仍只按既有语义推进到最近边界触发一次

## 根因

### 直接原因

共享调度原语 `_AtSchedule` 已具备过期窗口判断：计划时刻已过去、没有执行记录且超出正常轮询宽限时，返回空到期集合。cron `at` 任务使用这套默认语义。

heartbeat 的 `_parse_schedule("at", ...)` 却显式传入 `check_expiry=False`，关闭了同一个过期判断。因此只要 `last_due_at` 为空，无论计划时刻过去多久，`due_times_up_to()` 都会返回原计划时刻，HeartbeatScheduler 随后把它当作本 tick 应执行任务提交。

### 原始设计意图与必须保住的不变量

这项调度能力由 `feat-394` 重新设计。其 owner 对齐结论明确采纳“不重放错过的到期”：heartbeat 与 cron 两套机制都不补跑积压，过期 `at` 直接不跑。原始 spec 的验收场景逐字要求：“一条只触发一次、时间点已过的任务”在 Gateway 重启后“不会被补触发”。该结论现已归并为 current `docs/specs/gateway/heartbeat-cron.md` 的统一契约，并没有为 heartbeat 设例外。

修复必须保住：

- heartbeat 与 cron 对“错过窗口的一次性任务”采用同一用户语义；
- Gateway 正常运行时，一次性任务仍可容忍正常轮询延迟并触发一次；
- 已执行的一次性任务不重复执行；
- 固定间隔与 cron 表达式等周期任务仍保持“不逐周期补跑、恢复时最多推进一次”的既有行为；
- heartbeat 的 canonical 直聊上下文、静默 token、activeHours 和 per-task 子节律等其他行为不变。

### 缺陷形成与固化点

这不是 `refactor-489` 引入的新行为；该 refactor 只在测试信号审计时重新暴露了既有矛盾。

`feat-394` 的真实验收曾发现“过期 `at` 类一次性任务在 gateway 重启后被重新触发”，但当时证据和修复只落在 cron job 路径。后续 verification 也只引用 cron scheduler 的实现与测试来判定整个“过期 at 任务不补跑”场景 covered，没有单独验证 heartbeat `at:`。

commit `0b75e853dec318e51cd0cd3e7633db6185a8c2e0` 在抽取 heartbeat/cron 共享调度原语时，把这项不对称显式固化为 `check_expiry` 开关，并让 heartbeat 传 `False`；commit `a54a87d718d4bd99174d7daa77fc53a4d5ee2cf6` 随后新增了“heartbeat 过期仍触发”的正向测试。原本覆盖所有一次性任务的产品要求由此被实现和测试误缩窄成 cron-only 特例。

### 为什么这种错能进入主线

- 验收场景写的是统一的“一次性任务”，但缺陷复现只走 cron，修复与关闭证据没有分别覆盖 heartbeat 和 cron 两个消费者。
- verification 以 cron 单路径证据代表共享产品要求，未检查 heartbeat parser 是否采用同一过期语义。
- 调度原语去重时优先保持两份旧实现的行为差异，并新增模式开关和测试，而没有回到 `feat-394` spec 与 current spec 核对该差异是否被产品允许。

## 修复

## 验证

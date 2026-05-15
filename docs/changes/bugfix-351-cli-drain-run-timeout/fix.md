# bugfix-351: CLI drain_run 终态超时是硬墙钟上限而非空闲超时

## Relations

- Closes: #13

## 原始报告

> 用户给 Coding CLI 派一个稍长的任务(多轮工具调用 + 慢一点的模型),跑到 120s 时 REPL 直接报错退出:
>
> ```
> TimeoutError: run run_xxx did not reach terminal status in 120.0s
> State: failed | layer=runtime
> ```
>
> 此时 kernel 仍然活着、仍在持续发 LLM 请求 —— 任务没卡死,只是还没跑完。
>
> 见 GitHub issue #13:https://github.com/Mrchen116/nano-multiagent/issues/13

> 用户原话:"CLI drain_run 的 120s 终态超时是啥意思,用户发一个任务,能够运行两三个小时是很正常的呀。"

## 澄清记录

- Q1: run 真的卡死时(完全没有事件流出),CLI 该怎么办?
  A: 保留一个"空闲超时" —— 只要在阈值时间内没收到该 run 的任何事件才判定卡死并报错;事件持续流出就一直等。不设绝对墙钟上限。
- Q2: 空闲超时阈值设多长?
  A: 1800s(30 分钟)。要能覆盖慢模型的单次 LLM 调用 + 长时间静默的同步工具(如跑几分钟的 `pytest`/构建),宁可宽松。
- Q3: 这个阈值要不要做成可配(flag / 环境变量)?
  A: 不做可配,直接写死 1800s。

## 现象 / 复现

**现象**:在 Coding CLI(managed 模式)REPL 里派一个总时长会超过 120 秒的任务(典型:多轮工具调用 + 较慢的模型,或带 `bash_risk_gate` 这类每条 bash 命令前额外发一次 LLM 评估的阻塞 hook),任务运行到第 120 秒时 REPL 直接抛错退出:

```
TimeoutError: run run_xxx did not reach terminal status in 120.0s
Assistant: (empty)
State: failed | layer=runtime
Error: send failed: run run_xxx did not reach terminal status in 120.0s
```

此时 kernel 进程仍然存活、仍在持续向 LLM 代理发请求(连接端口持续变化)、事件仍在正常流式产出 —— 任务并没有卡死,只是**还没跑完**就被 CLI 端单方面判定超时。

**复现率**:100% —— 只要单个 user run 的总墙钟时长超过 `terminal_timeout`(当前 120s),无论中间事件是否在持续产出,必然触发。

**复现步骤**:
1. managed 模式起 CLI:`PYTHONPATH=<repo>/src python3 -m coding_cli.main --mode managed --base-url http://127.0.0.1:<port>`
2. 派一个会跑超过 120 秒的任务(例:在一个中等规模仓库里做多文件审计 + 多轮工具调用)
3. 观察:第 120 秒整,REPL 抛 `TimeoutError`,而 kernel 侧任务其实还在跑

## 根因

**直接原因**:`src/coding_cli/session_stream.py` 的 `drain_run()` 把超时实现成了**整个 run 的硬性墙钟上限**,而非"空闲/无活动超时":

```python
deadline = time.monotonic() + terminal_timeout   # 进入循环前算死一次
while time.monotonic() < deadline:                # 始终对照这个固定 deadline
    evt = self.poll(...)
    ...                                           # 收到事件也不更新 deadline
raise TimeoutError(...)
```

`deadline` 在进入循环前算死,之后无论收到多少事件都不再延后。即使事件一直在流式到达、agent 工作完全正常,只要墙钟过了 `terminal_timeout` 还没见到终态 `run_status`,就直接 `TimeoutError`。

`src/coding_cli/commands.py`(约第 420 行)把 `terminal_timeout=120.0` 写死传入,连个可调口子都没有。

**为什么这种错能进来**:

1. **命名误导**:`terminal_timeout` 字面像"等终态的耐心值"(无活动多久就放弃),但实现成了"从 run 开始算的总时长配额"。命名与实现语义不一致,review 时容易被名字带过。
2. **测试场景偏差**:CLI 的测试用例都是快速返回的纯后端/短任务,没有 >120s 的长任务用例 —— 在测试覆盖里 120s 永远够用,所以这个语义错误一直没机会暴露。直到接入真实 coding agent 长任务(多轮工具调用 + 慢模型)才触发。
3. **缺少对 coding agent 工作特征的建模**:coding agent 的真实任务跑几十分钟到几小时是常态,"run 总时长"本就不该有固定上限;该有的是"卡死检测",而卡死的判据是"持续无事件",不是"总时长超标"。

**目标行为**(供 worker 实施参考):`drain_run` 改为空闲超时 —— 每收到一个该 run 的事件就把 deadline 重置为 `now + 1800s`;只有连续 1800s 没有任何该 run 的事件才判定卡死并抛 `TimeoutError`。不设绝对墙钟上限,不做可配,`commands.py` 调用处同步改成传 1800s(或直接用新默认值)。

## 修复

<!-- 改了什么 + commits。worker 在 milestone 完成后补全。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。worker 补全。 -->

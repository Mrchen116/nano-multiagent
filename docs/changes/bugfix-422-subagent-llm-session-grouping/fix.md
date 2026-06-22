# bugfix-422: agent tool 子 agent 的 LLM 请求未与父 session 聚合到 LLM proxy session-inspector

## Relations

- Closes: #129
- Related: feat-337-cc-background-subagents

## 原始报告

> ## 现象
>
> 主 agent 调用 `agent` tool 创建子 agent 后，在 LLM proxy 的 session-inspector（`http://127.0.0.1:4000/ui/session-inspector`）中，子 agent 的 LLM 请求没有和主 agent 显示在同一个 session 下，而是单独出现在另一个 session 条目里。
>
> 对比：`skill/memory` 触发的 self-improvement review fork 能和主 agent 聚合在同一个 inspector session 中。
>
> ## 根因
>
> LLM proxy 按请求中的 session id 分组：优先读取 `X-Session-Id` / `x-session-id` / `session_id` header，或 `metadata.user_id` 里的 `session_id`，然后写入 `logs/session/<ts>_<session_id>/`。
>
> - self-improvement fork 通过 `AgentContextFork` 复用父 `session_id`，所以 LLM 请求 header 仍是父 session id。
> - `agent` tool 在 `src/agent/platform/tools/builtins/agent.py` 中为子 agent **新建独立 session**（`agent_session_id = sess_xxx`），并在 `runtime.run(agent_session_id, ...)` 时没有透传 `llm_session_id`，导致 `AgentLoop` fallback 到子 agent 自己的 session id，LLM proxy 把它当作新 session。
>
> ## 影响
>
> - 在 LLM proxy session-inspector 中无法把主 agent 和子 agent 的 LLM 调用串在一起看。
> - 同一个用户任务的 token 消耗、调用链被拆成两个 inspector session，调试和成本分析困难。
>
> ## 建议修复
>
> 让子 agent 的**本地 session id 保持独立**（继续用于 JSONL 存储、续传、`agent_id` 查找），但 LLM 请求层沿用父 session id：
>
> - 前台路径：`runtime.run(agent_session_id, ..., llm_session_id=ctx.session_id)`
> - 后台路径：`BackgroundSubagentRunner.start` 增加 `llm_session_id` 参数，并在 runner 内部传给 `runtime.run(..., llm_session_id=parent_session_id)`
> - 续传路径：`_resume_subagent` 同样透传 `llm_session_id=parent_session_id`
>
> 这样 LLM proxy 会把父子 agent 的 LLM 请求放在同一个 session 目录下，inspector 内通过 lane 区分，与 self-improvement fork 的行为一致。

## 澄清记录

- Q1: 修复范围怎么框——三条 subagent 启动路径（前台/后台/续传）全修，还是只修前台？
  A(原话): 三条路径全修
  Agent 解读: 前台 `runtime.run`、后台 `BackgroundSubagentRunner.start`、续传 `_resume_subagent` 都透传父 session id；self-improvement fork 本就正确，不动。

- Q2: 验收（fix.md 验证段）以什么为准来判定修复成功？
  A(原话): 单测断言为主
  Agent 解读: 以单测断言「三条路径传给 `runtime.run` 的 `llm_session_id` 等于父 session id」为主，LLM proxy session-inspector 父子聚合作为补充的手动实证。

## 现象 / 复现

调试者通过 LLM proxy 的 session-inspector（`http://127.0.0.1:4000/ui/session-inspector`）观察一次用户任务的 LLM 调用链时：

- 主 agent 调用 `agent` tool 创建子 agent（前台、后台、或对已存在子 agent 续传任一路径）。
- 子 agent 产生的 LLM 请求**不**出现在主 agent 所在的 inspector session 条目里，而是单独成为一个新的 session 条目。
- 后果：同一个用户任务被拆成两个 inspector session，token 消耗与调用链断裂，调试和成本分析困难。

对照基线（修复必须对齐的目标行为）：由 `skill/memory` 触发的 self-improvement review fork 经 `AgentContextFork` 复用父 `session_id`，其 LLM 请求始终聚合在主 agent 的同一 inspector session 下。`agent` tool 子 agent 应表现一致。

## 根因

LLM proxy 按请求里的 session id 分组（`src/agent/platform/llm/providers/translator.py` 读取 `X-Session-Id` 等 header / `metadata` 里的 session_id，写入 `logs/session/<ts>_<session_id>/`）。决定这个 header 取值的是 `AgentLoop.run()` 的 `session_id=llm_session_id or state.session_id`（`src/agent/core/agent/loop.py`）——即 `llm_session_id` 显式给了就用它，否则 fallback 到本地 session id。

- self-improvement fork 不触发本 bug：`make_fork_conversation()`（`src/agent/core/agent/context_fork.py`）直接把 `AgentState.session_id` 设为父 session id，LLM 请求天然带父 id。
- `agent` tool 触发本 bug：它为子 agent **新建独立 session**（`agent_session_id`，用于 JSONL 存储、续传、`agent_id` 查找——这是有意设计），但三条启动路径调用 `runtime.run(agent_session_id, ...)` 时都**没有透传 `llm_session_id`**，于是 `AgentLoop` fallback 到子 agent 自己的 session id，proxy 据此判为新 session。
  - 前台：`src/agent/platform/tools/builtins/agent.py` `_run_foreground()` 的 `runtime.run(...)`。
  - 后台：`_run_background()` 经 `BackgroundSubagentRunner.start()` → `RuntimeRunner.start()` → `runtime.run(...)`，该链路根本没有 `llm_session_id` 形参可透传。
  - 续传：`_resume_subagent()` 走与后台相同的 `start()` 链路。

**为什么这种缺陷能进来**：`runtime.run` 自始支持 `llm_session_id`，但它是为 fork 路径设计的；`agent` tool 走的是「新建独立 session」路径，引入时（feat-337 起的 background subagent + 后续前台/续传扩展）没有意识到「本地 session id 独立」与「LLM 请求层 session id 复用父」是两件需要分别处理的事，于是只设置了前者。`runtime.run` 与 `BackgroundSubagentRunner.start` 的 `llm_session_id` 默认 `None`（静默 fallback）让缺失不报错，缺陷得以无声进入。

**修复必须保住的不变量**：子 agent 的**本地 session id 必须保持独立**——它用于子 agent 自己的 JSONL 存储、续传、`agent_id` 查找；本修复只在 **LLM 请求层**复用父 session id，绝不能把子 agent 的本地 session id 改成父的（那会破坏 JSONL 隔离与续传）。`parent_session_id`（已有，用于子 agent JSONL 路径解析）与本次新增的 `llm_session_id`（LLM 请求层覆盖）是两个独立维度，不可混淆。

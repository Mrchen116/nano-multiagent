# bugfix-412: max_tool_calls 默认硬限 64 + compaction 判据字符估算失效

## Relations

- Closes: #102
- Closes: #103

---

## 原始报告

Issue #102（原话）：

> `max_tool_calls` 默认 64 在内核 core 层硬限制所有消费者，应默认不限制（仅 SDK 显式传入时才约束）
>
> 个人助手 agent 做稍大一点的任务（如 review 一个 worktree 的代码、多步探索）时，频繁撞 `RuntimeError: max_tool_calls exceeded` 导致 run 失败——单条用户消息触发的一个 run，累计调用工具超过 **64 次**就被内核强制终止。
>
> dogfood 实例：让 agent review 一个 worktree 的代码，它逐个读文件/列目录，64 次工具调用还没看完就撞上限、run 失败（Gateway 日志 `run_failed | error='max_tool_calls exceeded'`）。

Issue #103（原话）：

> 会话 context 已涨到 **226.2k tokens / 112%**（前端显示），仍不触发自动压缩（compaction）。预期早该在 ~196k 触发 THRESHOLD 压缩，结果一路涨过模型窗口。

---

## 现象 / 复现

**Bug 1（#102）**：让个人助手 agent 处理需要 >64 次工具调用的任务（如"review 这个 worktree 的代码"），run 在第 65 次工具调用时抛 `PolicyViolation: max_tool_calls exceeded` 失败。Gateway 日志可见 `run_failed | error='max_tool_calls exceeded'`。所有产品均受影响（无任何消费者覆盖此默认值）。

**Bug 2（#103）**：让 agent 做大量工具调用 + 读代码任务，前端 context 涨过 100%（模型真实 usage 已超阈值）仍不触发自动压缩。会话一路涨到模型硬上限才被动 OVERFLOW 或请求失败。

两个 bug 在同一场景下复合触发：大型多步任务先可能被 Bug 1 打断；没被打断的会话则因 Bug 2 导致 context 超窗后自动压缩形同虚设。

---

## 根因

### Bug 1：`max_tool_calls` 默认值方向反了

`src/agent/core/agent/policies.py:17`：

```python
max_tool_calls: int = 64
```

`ensure_tool_calls_allowed`（`policies.py:55`）直接判 `tool_call_count > self.max_tool_calls`，没有 `<= 0 = 不限` 的逃逸逻辑——而同文件里 `truncate_history` 对 `max_context_messages` 已有 `if self.max_context_messages <= 0: return messages` 的"0 = 不限"语义，两者不对称。

全仓无任何消费者（`agent.sdk`、`coding_cli`、`personal_assistant`）覆盖 `max_tool_calls` 默认值（grep 确认），所有 run 实际跑的是写死的 64。

**原始设计意图**：`AgentPolicies` 是消费者按场景注入的约束（`loop.py:74` 收 `policies` 参数，`loop.py:90` `policies or AgentPolicies()`），本来就预留了覆盖路径。`max_tool_calls=64` 是占位默认值，从未有产品主动传过，变成了实际天花板——设计意图是"消费者自定义上限"，现状是"core 替所有人套了一个魔数"。

**修复必须保住的不变量**：`ensure_tool_calls_allowed` 仍须在消费者显式传正整数时正常限制；`0` 改为"不限"而非"立即触发"；修后 `max_turns=10_000` 依旧是防失控兜底（不依赖 `max_tool_calls`）。

### Bug 2：compaction 触发判据用字符粗估，漏掉 `tool_calls` 字段，且估算系数偏低

`loop.py:669 _should_compact` 调的是 `estimate_llm_context_tokens`（`prompting.py:278`）。

两处低估：

1. `_estimate_text_tokens`（`prompting.py:311`）公式为 `(len(normalized) + 7) // 8`，即 chars/8——比 `/4` 更激进的低估，代码和中文 CJK 的真实 token 密度远高于此。
2. `estimate_llm_context_tokens` 只遍历 `msg.content`，完全不遍历 `msg.tool_calls`（assistant 消息的工具调用参数）——大量工具调用场景下这部分 token 直接被漏算。

**关键抓手**：`loop.py:470` 每轮 `turn_end` 已拿到模型返回的真实 `prompt_tokens`（`turn_usage.prompt_tokens`），却未用于驱动 compaction——直接用它替换字符估算可从根本上消除误差。

**修复必须保住的不变量**：首轮（尚无 usage 历史）或 usage 缺失时需兜底；compaction 触发后 session 摘要写入、后续 context 正常继续——这是 compaction 机制原始意图，修复只动"何时触发"判据，不改"触发后做什么"逻辑。

---

## 修复

<!-- 改了什么 + commits。worker 回填。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。worker 回填。 -->

# bugfix-357: 聊天消息「已用上下文」在含 tool call 的 turn 被多计

## Relations

- Related:

## 原始报告

> http://127.0.0.1:8011/chat/40b4d607e74c422ea1d160942fd5e406
> [Image #1] 为什么上下文还少了。中间应该没有触发压缩，你看一下日志或者说一些记录。看一下是为什么发生这个情况。

截图中同一会话相邻两条 agent 消息：
- 「执行成功！输出了"Hello, World!"」：输出 78 / 总计 11,343 / 已用上下文 **11,265 / 200k (6%)**
- 「谢谢！很高兴能帮到你」：输出 15 / 总计 5,647 / 已用上下文 **5,632 / 200k (3%)**

用户疑惑：会话单调增长且未触发压缩，为什么"已用上下文"反而从 11,265 跌到 5,632。

诊断结论（详细对账见本会话上文）：会话上下文实际单调增长（DB 中 `prompt_tokens` 1,840 → 5,632 → 5,775），LLM proxy 日志里**从未出现过 11,265 这个 `prompt_tokens` 值**——它是 `src/agent/core/agent/loop.py:763` `_accumulate_usage()` 把本 turn 内多次 LLM round-trip 的 `prompt_tokens` 累加得到的虚构值。带 tool call 的 turn 有 ≥2 次 round-trip，prompt 被重复累加；无 tool call 的 turn 只有 1 次 round-trip，等于真实 prompt。视觉上就表现为"上下文跌落"。

## 澄清记录

- Q1: 修复语义——`context_used` 应取本 turn 最后一次 LLM call 的 `prompt_tokens`（覆盖），`output` 仍累加，对吗?
  A(原话): 对

- Q2: DB 里已存的错误 `context_used` 是否回填?
  A(原话): 对，开发态。不修过往

- Q3: 修复范围——只改 kernel 累加逻辑还是顺手扫其他入口? 字段语义改了之后相关注释要不要更新?
  A(原话): 注释有错误也要更新
  Agent 解读: 范围 = 改 kernel 累加点 + 修正所有写错了字段语义的注释/docstring；不改 wire format、不改前端、不改 schema、不回填历史。

## 现象 / 复现

在任意 chat 会话里发一轮**带 tool call** 的消息（例：让 agent 跑一段 bash），再发一轮**无 tool call** 的纯对话消息（例：说"谢谢"）。展开两条 agent 消息底部的 token 详情，会看到：

- 带 tool call 那条：「已用上下文」明显高于会话实际累计 history（如本 issue 截图里的 11,265）
- 紧接着无 tool call 那条：「已用上下文」回落到接近真实 history 大小（如 5,632）
- 期间 `context_window` 未达阈值，**未触发任何压缩**

直觉上"上下文跌了一半"。

## 根因

`src/agent/core/agent/loop.py:763` `_accumulate_usage()` 把本 turn 内每次 LLM round-trip 的 `prompt_tokens` 和 `completion_tokens` 一并累加：

```python
return TokenUsage(
    prompt_tokens=current.prompt_tokens + update.prompt_tokens,
    completion_tokens=current.completion_tokens + update.completion_tokens,
    ...
)
```

累加后的 `prompt_tokens` 经 `turn_end` payload 透传到 `src/IM/ws/gateway_handler.py:1636` 被写成 `TokenUsage.context_used`，最终在前端 token chip 渲染为「已用上下文」。

`completion_tokens` 累加是对的（每次 round-trip 生成的都是新内容）；`prompt_tokens` 累加是错的——同一份会话 history 在 N 次 round-trip 里被重发了 N 次，累加等于把同样的上下文算了 N 遍，没有物理意义。

为什么这种错能进来：
1. `_accumulate_usage` 的命名暗示"两类都该累加"，没人质疑 `prompt_tokens` 是否该累加。
2. 字段名 `context_used` 在 kernel→IM→frontend 的传递链路上没有任何地方写明"它代表 turn 收尾时上下文的真实占用"——既无 docstring 也无类型注释，于是这个语义错配能从 kernel 一路滑到 UI。
3. 现有测试只对单 LLM call 的 turn（无 tool call）断言 token_usage，未覆盖多 round-trip 场景，所以累加错误从未被回归住。


## 修复

修改 `src/agent/core/agent/loop.py` 中的 `_accumulate_usage` 函数：

- `prompt_tokens`：改为**覆盖**（取最后一次 roundtrip 的值）。同一 turn 内每次 roundtrip 发给 LLM 的 prompt 包含同一份会话上下文快照，多次累加等于重复计算同一份数据。最后一次 roundtrip 的 `prompt_tokens` 才是 turn 结束时真实的上下文占用。
- `completion_tokens`：保持**累加**。每次 roundtrip 生成的是独立的新内容，累加有物理意义。
- `total_tokens`：重算为 `last_prompt_tokens + accumulated_completion_tokens`，保持 `context_used + output = total` 的同构关系。

同时为 `_accumulate_usage` 补充了详细 docstring，说明两类 token 不同的累加语义及其原因，防止将来误改回去。

## 验证

新增两个回归测试（`tests/unit/test_agent_loop.py`）：

1. **`test_loop_accumulates_usage_across_multiple_model_calls`**（更新现有测试断言）：两轮 roundtrip，验证 `prompt_tokens` 取最后值（80），`completion_tokens` 累加（22），`total` 重算（102）。
2. **`test_loop_prompt_tokens_tracks_last_roundtrip_not_sum`**（新增专项回归）：三轮 roundtrip，验证 `prompt_tokens == 220`（最后值，非 200+210+220=630），`completion_tokens == 19`（5+6+8），`total == 239`（220+19）。

两个测试在修复前均红，修复后均绿。全量单元测试（1557 个）通过，无新增失败。

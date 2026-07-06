# bugfix-453: Multi-tool response shows duplicate thinking rows

## Relations

- Related: feat-439
- Related: bugfix-373
- Related: bugfix-375
- Closes: #176

## 原始报告

> http://127.0.0.1:50796/chat/096b4947494e4081adf0b2c1fb6a9bf7 最后一个气泡，有三个一模一样的thinking。这肯定是bug吧

> 我不懂你的说法，一轮llm请求只会有一个thinking，现在是不是一轮输出了三次？如果两轮llm请求，thinking内容是一样的，那没问题。

> 这个bug，提个issue

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 现在开始解你刚刚提的issue

> Issue: https://github.com/Mrchen116/nano-multiagent/issues/176

## 澄清记录

- Q1: 这个 bugfix 的范围是不是只处理“内部 Web IM 过程区重复展示同一份 thinking”，不顺手改外部 IM、飞书授权卡、或模型历史回传策略？
  A(原话): 是，不做后向兼容
  Agent 解读: 本 unit 聚焦内部 Web IM 过程区重复 thinking；外部 IM、飞书授权卡不在本期内。`不做后向兼容` 的具体含义需继续确认。

- Q2: 你说的“不做后向兼容”具体指哪一层？
  A(原话): 就是不用考虑修复，之前已经产生的重复
  Agent 解读: 本 unit 不迁移、不清洗、不补救历史上已经写入的重复 thinking；只要求修复后新产生的过程区不再出现同类重复。

## 现象 / 复现

内部 Web IM 的 agent 气泡过程区用于展示本轮运行过程：思考段与工具调用按真实先后次序混排，用户可以展开每段思考和工具详情。当前契约要求「一轮带多段思考、多次工具调用」时，用户看到的是按真实时序混排的过程时间线；外部 IM 不展示 thinking。

现场复现来自 `unit/feat-447` live worktree 的会话：

- 页面：`http://127.0.0.1:50796/chat/096b4947494e4081adf0b2c1fb6a9bf7`
- agent message：`ce1c6fd077904a8c9e447864299a106e`
- 用户可见症状：最后一个 agent 气泡的过程区里出现多条完全一样的 thinking 行，其中 `seq 6/7/8` 是三条相同文本。

已查到的事件流事实：

```text
seq 2,3    same text: "Good, I have the feishu-doc skill..."
seq 6,7,8  same text: "The feishu-cli command is not found..."
seq 14,15  same text: "The project has FeishuAdapter code..."
```

关键判断：`seq 6/7/8` 中间没有 tool result 边界，不符合「两轮 LLM 请求碰巧 thinking 一样」的可接受情况。

本期范围只覆盖内部 Web IM 过程区对新消息的展示/持久化正确性：修复后，同一轮 LLM response 里一份 thinking 搭配多个 tool calls 时，用户只应看到一条 thinking 过程项；如果确实是多轮 LLM request 各自产生了相同文本的 thinking，仍可显示为多条。历史上已经落库的重复 thinking 不做迁移、清洗或补救。外部 IM thinking 展示、飞书授权卡片、以及旧消息数据修复不属于本 unit。

LLM proxy 现场证据显示 `2026-07-06_16-41-59_274-non-stream-res-anthropic_messages.json` 是一轮 LLM 响应：

```text
choices len = 1
reasoning len = 533
tool_calls = [
  tool_QiVCyctCiIKalTp7IpSu0KRx bash,
  tool_f4MTev5sJvqq7sLMLfYgDYV6 bash,
  tool_UIN3hlFhq3BIcQZcX0QUBn2m bash
]
```

但内核 session 持久化为三条连续 assistant turn，三条都带同一个 reasoning 文本和同一个 reasoning signature 前缀：

```text
08:42:17 msg_0252357d88338bf7 -> tool_QiVC... bash  reasoning_signature p9Xj+mbP16mUy95jPgm4ULzu
08:42:17 msg_5ed7b3cbbad8a912 -> tool_f4M...  bash  reasoning_signature p9Xj+mbP16mUy95jPgm4ULzu
08:42:19 msg_b21cc92eae2b06a4 -> tool_UIN...  bash  reasoning_signature p9Xj+mbP16mUy95jPgm4ULzu
```

所以这不是模型一轮生成了三份 thinking，也不是三轮独立 LLM 请求各自生成同样 thinking；而是一轮「一个 thinking + 多个 tool_calls」的响应在展开为多条 assistant tool-call 消息时，把同一份 thinking 重复暴露给了用户可见过程时间线。

## 根因

原始设计意图来自 `feat-439-im-cache-hit-and-thinking`：内部 Web IM 不再只展示工具调用，而是展示「过程时间线」，把 thinking segments 和 tool calls 按真实到达顺序混排；纯 thinking 回合不应产生空正文气泡；历史回看应和实时展示一致。这个能力必须保住的不变量是：

- 用户看到的过程区应反映真实运行过程，而不是内部展开结构造成的重复项。
- 同一轮里真实存在的多段 thinking 不能丢。
- 无 thinking 的轮次不显示 thinking 空壳。
- 外部 IM 不展示 thinking。

相关历史约束来自 `bugfix-373` / `bugfix-375`：开启 thinking 的 Anthropic/Kimi 类上游要求 assistant tool-call 历史能 round-trip `reasoning_content` / `reasoning_signature`，否则后续请求会被拒绝。`bugfix-373` 后续记录还特别指出：一个 assistant 轮可能返回 `thinking + 多个 tool_use`，拆成多条独立 assistant 消息后，历史回传层面不能简单丢掉 tool-call message 的 reasoning。这个约束属于后续设计必须保住的不变量；本 bug 的用户可见问题是「同一份历史回传所需 reasoning 被重复当作多段用户可见 thinking 展示」。

当前根因链路：

1. LLM provider 收到一轮响应：一个 reasoning/thinking block + 多个 tool calls。
2. provider / agent loop 为每个 tool call 产出独立 assistant message，以支撑工具执行和历史回传。
3. 每条 assistant message 都携带同一份 `reasoning_content` / `reasoning_signature`。
4. Gateway 的 IM observer 对每个 `assistant_message.reasoning_content` 都转发一条 `thinking_segment`。
5. IM repository 为每条 thinking append 分配新的 process `seq`。
6. 前端按 `seq` 去重和排序；因为重复 thinking 拥有不同 `seq`，所以用户看到多条完全一样的 thinking。

为什么这种错能进来：

- `feat-439` 的过程时间线把「内部历史回传需要保留 reasoning」和「用户可见 thinking 过程项」接到了同一字段上。
- 既有前端/IM 幂等只防「同一 seq 重放」，没有覆盖「同一 LLM response 的同一 reasoning 被展开成多个不同 seq」。
- 旧 `bugfix-373` 为了上游兼容强调了多 tool-call message 都要携带 reasoning；后续展示层没有区分「历史回传 metadata」与「用户可见过程事件」。

## 修复

## 验证

# bugfix-490: 并行 tool_result 上线格式拆成多条 user

## Relations

- Closes: #226
- Related: bugfix-375
- Refs: #43

## 原始报告

> /change-spec-author 修这个问题

（对话上下文指向 GitHub issue #226：并行 `tool_use` 的 `tool_result` 被拆成多条 user 消息，Anthropic/DeepSeek 拒请求。）

Issue：https://github.com/Mrchen116/nano-multiagent/issues/226

> Agent 一轮里发出多个并行 `tool_use` 时，历史被序列化成：
> 1. `assistant`：两个 `tool_use`（A、B）
> 2. `user`：只有 `tool_result` A
> 3. `user`：只有 `tool_result` B
>
> DeepSeek Anthropic 兼容接口（以及 Anthropic 规范）要求：紧跟在含多个 tool_use 的 assistant 之后，下一条消息必须立刻包含全部对应 tool_result。拆成两条 user 会 400：
> `tool_use ids were found without tool_result blocks immediately after: call_01_...`
>
> Gateway 侧表现为：`⚠️ 模型调用失败: anthropic: stream ended without terminal event`，会话卡住/后续 hi 也失败。

现网证据：`LLM_Bridge` raw `2026-08-03_16-29-25_434-*-anthropic_messages.json`；飞书 / `forall · feishu` 在并行 `read` 后会话中毒，清 session 前无法再正常回复。

## 澄清记录

- Q1: 对已经中毒的旧会话要怎样？本期是否包含自动改写/自愈历史？
  A(原话): 好
  Agent 解读: 同意推荐——本期只保证新产生的并行 tool 轮次上线格式正确；已中毒 session 仍靠清 session / 开新聊，不做自动改历史。

- Q2: Anthropic Messages 协议上游是否一律合成一条 user（含 DeepSeek / Kimi / 真 Anthropic）？
  A(原话): 好
  Agent 解读: 同意推荐——一律按协议合并，不按上游容忍度分支。

- Q3: 用户从哪几个入口验收「并行工具之后下一句还能正常聊」？
  A(原话): 对。
  Agent 解读: 同意推荐——凡走同一 Agent 会话的入口都算（Web IM 直连、飞书及影子会话、本机 Coding CLI）；同一「先并行工具 → 再发一句」即可，不要求每个入口各写一套专项旅程。

## 现象 / 复现

### Requirement: 并行工具之后下一轮仍可对话

#### Scenario: 并行工具后用户再发一句
- **GIVEN** Agent 上一轮对模型发出了含多个并行 `tool_use` 的回复，且各工具已执行完毕
- **WHEN** 用户在同一会话再发一条普通消息（Web IM / 飞书 / Coding CLI 任一入口）
- **THEN** Agent 能正常完成模型调用并给出可见回复
- **AND** 用户看不到因本问题上线格式错误导致的「模型调用失败」类终态

#### Scenario: 已中毒旧会话不在本期自愈范围
- **GIVEN** 会话历史里已经留下「多条连续仅含单个 tool_result 的 user」且上游曾因此拒请求
- **WHEN** 用户继续在该旧会话发消息
- **THEN** 本期不要求系统自动改写/修复该历史
- **AND** 运维仍可通过清 session / 开新聊恢复（与现网止血一致）

### 复现要点（现网曾现）

1. 使用走 Anthropic Messages 协议且严格执行 pairing 的上游（如 DeepSeek `deepseek-v4-flash`）。
2. 让 Agent 一轮内并行调用 ≥2 个工具（例如连续 `read` 两个文件）。
3. 再发一句简单追问 → 上游 400 / Gateway 报模型调用失败；之后同会话持续失败直至清 session。

## 根因

### 直接原因

发给 Anthropic Messages API 的 `messages` 在「一条 assistant 含多个 `tool_use`」之后，把每个 `tool_result` 拆成**独立的连续 `user` 消息**。严格上游要求：紧跟的那一条 `user` 的 `content` 必须立刻包含全部对应 `tool_result` block。拆条即 400，Gateway 表现为模型调用失败；失败轮次写入会话后，后续轮次继续带毒历史。

### 为什么这种错能进来

1. **内部历史与上线格式未分层**：内核可用多条 `role=tool` 消息表达并行结果；Anthropic mapper 将每条一对一映成一条 `user`，**发请求前没有** Claude Code 式的「连续 tool_result user → 合成一条」规范化。
2. **`bugfix-375` 修了另一半配对、并验收了当前上线形态**：该 unit 保证并行 `tool_use` 落在同一条 assistant（Issue #43），其 e2e 证据明确接受 `msg[2]/[3]/[4]` 各为一条 tool_result user。当时默认上游（如 Kimi）能容忍或服务端合并连续 user，缺陷被掩盖。
3. **换严格上游才爆**：DeepSeek Anthropic 兼容端严格执行 immediately-after 约束后，同一形态稳定复现。

### 原始设计意图与必须保住的不变量（来自 bugfix-375 / 并行工具）

- **本来要达成**：同一轮多个并行 `tool_use` 与各自 `tool_result` **ID 配对完整**；thinking/signature 可 round-trip；并行工具可执行。
- **修复必须保住**：
  - 并行 `tool_use` 仍在同一条 assistant（不要退回 bugfix-375 之前的切开）。
  - 每个 `tool_use` 仍有对应 `tool_result`（配对不丢）。
  - 用户在 IM/飞书看到的工具时间线等**可观察展示**不因「上线合并」而少工具或错序（合并是发模型前的协议层，不是阉割并行工具）。
- **本期非目标**：自动修复已中毒旧 session；按上游品牌分支不同上线格式。

### 回归引入点

- 功能侧：并行工具 + Anthropic mapper「每 tool 一条 user」长期存在；`bugfix-375` 将「N 条 tool_result user」固化为已验收形态。
- 暴露侧：生产改用 DeepSeek Anthropic 兼容模型后用户可观察失败。

## 修复

<!-- 改了什么 + commits。由 worker / orchestrator 回填。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。由 worker / orchestrator 回填。 -->

# bugfix-376: deep agentic 任务在工具调用深度增加后被 kimi 以 tool_call_id 未配对拒绝、会话中断

> **SUPERSEDED / 已折叠**：本 unit 经复现 + RCA 后，结论是该 `read:N` 错误是 RC1（`get_completed_results` 对 safe executing 工具不 break 导致并行 tool_result 乱序）的内存层缺陷，与历史重建无关。修复（RC1 + reasoning 跨持久化保真）已**折叠进 bugfix-375 / PR #44**，不单独走。本文件保留作为复现与 RCA 的考古记录。详见 `docs/changes/bugfix-375-thinking-signature-roundtrip/fix.md`。

## Relations

- Refs: #43
- Related: bugfix-375（同一症状残留：375 修通 thinking signature round-trip + 主交互路径并行 tool_result 成组；本 unit 处理深度增加后仍被上游拒的残留）

## 原始报告

bugfix-375 收尾时，对深度多轮任务做 e2e，发现一类与 thinking 无关的中断。用户在对话中要求把它单独立 unit：

> 中途可能还会找到很多bug，那就继续新开unit，继续修

> 76是啥 …（确认 bugfix-376 是收尾 #43 残留的下一个修复单元）

> ok，继续

关联 GitHub Issue #43（用户提供）及我在其下的调查 comment：
> https://github.com/Mrchen116/nano-multiagent/issues/43#issuecomment-4500022025

## 澄清记录

- Q1: 既然事后日志看载荷合法、疑似上游，这个 unit 的"修好"以哪个为准（自愈出结果 / 还是先坐实根因）？
  A(原话): 你不要问我，你自己去想。我认为你是应该先去复现这个问题。复现了之后再明确到底是哪的问题。LLM proxy和kimi本身不太可能有问题。因为这两个东西都长期被使用，非常的稳定。

  Agent 解读: 方法定死——**先做确定性复现，再定位**，不预设上游。LLM proxy 与 kimi 都是长期使用、非常稳定的外部系统，不应作为首要怀疑对象；因此根因极大概率在**我们这侧**（agent 历史拼装 / 并行 tool_result 顺序 / 序列化边界）。我此前基于事后日志"载荷合法→疑似上游"的结论是过度推断，作废，以复现结果为准。

## 现象 / 复现

让 agent 跑**深度多轮工具任务**（如 deep bug-finding：反复 gh/git/read），或 gateway heartbeat 触发的后台 agent 会话，在工具调用累积到一定深度后，某一轮把历史回传给 kimi K2.6（anthropic provider）时被上游拒：

```
an assistant message with 'tool_calls' must be followed by tool messages
responding to each 'tool_call_id'. The following tool_call_ids did not have
response messages: read:N   （或 bash:N，工具名:序号）
```

该轮返回错误、无内容，会话**中断**：用户拿不到最终答案。

bugfix-375 e2e 中**间歇**出现，已知样本：`sess_8d077ecc`(read:7)、raw `16-03-58`/`16-07-18`(bash:9)、`21-43-10`(read:10，375 收敛后的 heartbeat 轮)。**目前不是确定性复现**——这正是本 unit 第一步要解决的。

**复现要求（本 unit 的第一道工序，先于任何修复）**：
1. 构造一个能**稳定/高概率触发**该拒绝的最小 e2e（固定的深度多轮工具任务 + 开 thinking 的 kimi K2.6），记录触发时的工具调用深度与并行情况。
2. 复现命中时，**抓实时的 upstream-req / upstream-res 原始字节**（不靠事后归一化日志），逐条核对被点名的那个 `read:N/bash:N` 在真正发出去的载荷里到底对应哪个 assistant tool_use、它的 tool_result 是否真的缺失/错位。
3. 用复现把"问题在哪"坐实到具体一层（我们的历史拼装 / 序列化 / 并行顺序，或——只有在前述被证伪后才考虑——上游），再进入修复。

## 根因

**未确认，待复现坐实，不预设。** 现有证据与判断：

- bugfix-375 期间的事后日志（normalized session log + raw upstream-req）显示我们发出的载荷**看起来**合法（assistant↔tool_result 交替配对、id 均为 UUID、无缺失），`read:N/bash:N` 仅出现在上游 error 文本里、不是我们生成的 id（我们只生成 `call_xxx` / `tool_use_{index}`）。
- **但**：LLM proxy 与 kimi 都是长期使用、非常稳定的系统，不应先怀疑；据此，"事后日志看着合法→上游问题"是**不可靠推断**（事后日志可能掩盖了真正发出的瞬时载荷、重试、并行竞态等）。
- 因此根因**极大概率在我们这侧**，重点怀疑对象：
  - `loop.py` / StreamingToolExecutor 的**并行 tool_result** 写入顺序与成组（375 的 911d1bab 改过这里，可能只覆盖了一部分；heartbeat/background 可能走了未覆盖的分支）；
  - 历史序列化在某些深度/并发下把某个 tool_use 与其 tool_result 拆散或错配，而事后归一化日志把痕迹抹平了。
- **结论先放空，由确定性复现 + 实时原始字节来定**。修复落在被复现坐实的那一层。

## 修复

<!-- worker 回填 -->

## 验证

<!-- worker 回填 -->

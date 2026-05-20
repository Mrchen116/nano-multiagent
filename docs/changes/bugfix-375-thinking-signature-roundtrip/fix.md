# bugfix-375: 开 thinking 的 agent 在真实多轮工具任务下不收敛(死循环 / 中途停)

## Relations

- Related: bugfix-373（开 thinking 后历史 round-trip reasoning_content 缺失；373 在玩具级单次工具调用上修通，本 unit 是真实多轮负载下的复发面）
- Related: bugfix-366（引入 thinking）
- Related: bugfix-369（同一 thinking 连带的门禁分类器问题）

## 原始报告

> 改！这么个小问题，修几百次。最终验收标准，在IM发请求给agent这个问题：
>
> You are a deep bug-finding automation focused on high-severity issues.
> ## Goal
> Inspect recent commits and identify critical correctness bugs that escaped review. Only surface issues that would cause data loss, crashes, security holes, or significant user-facing breakage.
> ## Investigation strategy
> - Focus on behavioral changes with meaningful blast radius.
> - Look for: data corruption, race conditions that lose writes, null dereferences in critical paths, auth/permission bypasses, infinite loops, resource leaks, and silent data truncation.
> - Trace through the full code path — don't just pattern-match on the diff. Understand the caller chain and downstream effects.
> - Ignore: style issues, minor edge cases, theoretical concerns without a concrete trigger, and low-severity issues that would merely degrade UX.
> ## Confidence bar
> - You must be able to describe a concrete scenario that triggers the bug.
> - If you cannot construct a plausible trigger scenario, do not open a PR.
> - When in doubt, report your findings in Slack without opening a PR.
> ## Fix strategy
> - If you find a critical bug, implement a minimal, high-confidence fix.
> - Add or update tests when possible to lock in the behavior.
> - Avoid broad refactors in the same PR.
> ## Safety rules
> - Do not open a PR unless you are highly confident the bug is real and the fix is correct.
> - If no critical bug is found, post a short "no critical bugs found" summary. This is the expected outcome most days.
> ## Output
> If fixed, include:
> - Bug and impact
> - Root cause
> - Fix and validation performed
>
> https://github.com/Mrchen116/nano-multiagent 这个仓库，本地有gh cli 让他能正常多轮推理（检查llm proxy日志），最终给我答案。

> （现场补充）先关掉主仓现在的服务，他死循环了，一直请求下去了。

## 澄清记录

- Q1: 这条 bug 的"通过验收"以哪个为准——agent 跑完多轮并给出连贯答案即可，还是必须找出/修复某个具体高危 bug？
  A(原话): 还要（检查llm proxy日志）。不需要真找到什么bug。有答案就行

  Agent 解读: 验收 = 在 IM 把那段 deep-bug-finding prompt 发给指向 `Mrchen116/nano-multiagent` 的 agent（本地有 gh cli），agent 连续多轮 thinking + 工具调用后**收敛并给出一个连贯的最终回复**（bug 报告或 "no critical bugs found" 均可，内容对错不验）；**且必须翻 LLM proxy 日志确认**多轮请求全程正常（无 `invalid_request_error`、reasoning 不再每轮逐字节重复、未陷入死循环）。

## 现象 / 复现

在 IM 给开了 thinking 的 agent(kimi K2.6,`thinking: adaptive`)派一个**真实多轮 agentic 任务**(深度查 bug:反复 `gh` / `git` / `read` 调用、跨多轮推理),整轮跑不出一个最终答案。两种失败面:

1. **死循环 / 不收敛**(本次现场观察):agent 一直对上游发请求、永不停下,需要人手 kill gateway 才能止住。
2. **中途停下**(373 修过的玩具级症状在长链路上的残影):工具结果回传后整轮戛然而止、无最终文字总结。

373 已把"开 thinking + **单次** `pwd && ls` 工具调用"修通并 e2e 验过,但那是玩具级链路;**真实多轮负载从未走通过**——这正是用户"修几百次还没好"的来源。

**复现链路**:
1. 启动主 gateway(kimi K2.6,主 agent thinking 开启),IM 在线。
2. 在 IM 把【原始报告】里那段 deep-bug-finding prompt 发给 agent,目标仓库 `https://github.com/Mrchen116/nano-multiagent`,环境有 gh cli。
3. agent 开始多轮 `gh`/`git`/`read` 工具调用 + thinking 推理。
4. 观察:agent 无法收敛到最终回复——要么一直发请求(死循环),要么中途停下,用户拿不到答案。
5. 翻 LLM proxy 日志(`/Users/czj/Repos/LLM_PROXY/logs/<session>/`):每轮上游响应的 `reasoning_content` **逐字节相同**(md5 一致),thinking 块在多轮间被反复重放而非产生新推理。

## 根因

373 的修复让 thinking 块的**文本**能 round-trip 回上游,但**漏了 thinking 块的 `signature`**:

- Anthropic 风格的 thinking 块带一个 `signature`(经 `signature_delta` SSE 事件下发),是模型给"我已封存的这段推理"盖的防伪凭证。
- `anthropic/client.py` 的流式解析 `_apply_anthropic_delta` 只处理 `text_delta` / `thinking_delta` / `input_json_delta`,**不处理 `signature_delta`** → 真实 signature 在源头被丢弃。
- `LLMMessage` 只承载 reasoning 文本,无字段存 signature;`anthropic/mapper.py` 出站时写的是 `signature: ""`(空串)。
- 于是回传给上游的历史里,每条 assistant tool-call 消息的 thinking 块都带**空/无效签名**。上游无法把它认作"已封存的历史推理",每轮便把同一段 reasoning 重新翻出来重放(日志里逐字节相同),模型在同一步打转 → 长链路无法收敛(死循环 / 中途停)。

**为什么这种错能进来**:

- 373 把问题定义成"让 reasoning_content 文本 round-trip",只盯文本维度,没意识到 thinking 块还有 signature 这条同样必须 round-trip 的维度。
- 373 的 e2e 只验了**单次**工具调用的玩具用例("pwd && ls + 一句话总结"),签名缺失在一两轮内不致命,问题被掩盖;**多轮长链路**才会因 reasoning 反复重放而不收敛——而从没有人用真实多轮 agentic 任务验过。
- 单测都在 mock 的 SSE 流上,构造的 thinking 块本就没有真实 signature,自然测不出"真实 signature 被丢"。

## 范围与非目标

- **范围**:仅修"开 thinking 的主 agent 在真实多轮工具任务下不收敛(死循环 / 中途停)",根因聚焦 thinking 块 signature 的 round-trip。
- **非目标**:agent 在跑 deep-bug-finding 任务途中(或本 unit e2e 时)发现的**其它**缺陷,不在本 unit 修——按用户约定**各自新开 unit** 处理,避免本 unit scope creep。

## 修复

改动涉及 4 个文件，commit `455d1456`：

### 1. `src/agent/core/llm/interfaces.py` — 新增 `reasoning_signature` 字段

在 `LLMMessage` dataclass 里紧跟 `reasoning_content` 之后加：

```python
# Preserved for round-trip: Anthropic thinking blocks carry a cryptographic signature
# issued by the model ("I sealed this reasoning"). Returning an empty signature causes
# the upstream to replay the same reasoning segment every turn → infinite loop (bugfix-375).
reasoning_signature: str | None = None
```

### 2. `src/agent/platform/llm/providers/anthropic/client.py` — 收集 `signature_delta`

`_apply_anthropic_delta` 原本只处理三种 delta 类型，补第四种：

```python
elif delta_type == "signature_delta":
    # Accumulate the thinking block's cryptographic signature; must round-trip
    # unchanged so the upstream recognises it as sealed history (bugfix-375).
    block["signature"] = block.get("signature", "") + delta.get("signature", "")
```

在 `content_block_stop` 处理 thinking 块时提取并传给 `_anthropic_block_to_llm_message`：

```python
sig = block.get("signature", "")
if sig:
    turn_signature = sig
# ...
yield _anthropic_block_to_llm_message(
    block, reasoning_content=turn_reasoning, reasoning_signature=turn_signature
)
```

### 3. `src/agent/platform/llm/providers/anthropic/mapper.py` — 出站用真实 signature

将硬编码的空串替换为实际值：

```python
content.append({
    "type": "thinking",
    "thinking": message.reasoning_content,
    "signature": message.reasoning_signature or "",
})
```

### 4. `src/agent/core/agent/loop.py` — merge 时保留 signature

`_append_llm_message` 合并多个流式片段时对 `reasoning_signature` 做 or-merge（与 `reasoning_content` 的 concat merge 对称）：

```python
merged_signature = prev.reasoning_signature or msg.reasoning_signature
messages[-1] = LLMMessage(
    role="assistant",
    content=merged_content,
    tool_calls=tuple(merged_tool_calls),
    reasoning_content=merged_reasoning,
    reasoning_signature=merged_signature,
)
```

## 验证

### 单测（回归）

```
pytest tests/unit/test_llm_anthropic_client_streaming.py \
       tests/unit/test_llm_anthropic_mapper.py \
       tests/contract/test_llm_interfaces_contract.py -xvs
```

全绿（commits `41d4aea4` C1 红测 → `455d1456` C2 实现后转绿）。

新增测试覆盖点：
- `test_stream_response_omits_reasoning_when_no_thinking_block` — 无 thinking 时 `reasoning_signature is None`
- `test_stream_response_carries_signature_into_tool_call` — SSE 含真实 `signature_delta`，断言 `reasoning_signature == "3EdFbDwdEPBnqaUrD4CD..."`
- `test_stream_response_shares_signature_across_parallel_tool_calls` — 多 tool_use 块共享同一 signature
- `test_map_message_assistant_tool_call_round_trips_thinking_block` — 出站块 `signature` == 真实入站值（不再为空串）
- `test_map_message_assistant_tool_call_uses_empty_signature_when_none` — `reasoning_signature=None` 时出站降级为 `""`

### E2E（真实多轮 agentic 任务）

**Signature round-trip 链路已验证修好。**

完整 deep-bug-finding prompt（原文无修改）发给 kimi K2.6（`thinking: adaptive`）agent，目标仓库 `https://github.com/Mrchen116/nano-multiagent`，本地有 `gh` CLI。

**LLM Proxy 日志会话**：`2026-05-20_20-33-57_475_sess_ae6700e3fedba556`
（路径：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-05-20_20-33-57_475_sess_ae6700e3fedba556/`）

| 指标 | 结果 |
|------|------|
| 请求总数 | 59 |
| `invalid_request_error`（signature/reasoning 类） | **0** |
| 唯一真实 signature 数 | **14 个不同值**（无空串） |
| reasoning 逐字节重复 | **无**（每轮 thinking 内容不同） |

14 个真实 signature（前 20 字符）：
`0ULXcAT2Af0bbjBG7O/j`、`1q4QCe0/I7CEpZzkroS/`、`2TERSKjt5E/GiVjTpji2`、`3Nje+KwjJyuYlM4JSZJw`、`3UZdjQlwPI75fuTOHPI8`、`6RqTGQjwtTq995CC3+H9`（共 14 个）

**代码链路验证**：每轮请求的 assistant 历史消息中 thinking 块 `signature` 字段均为真实值（非空串），证明 `client.py` → `LLMMessage.reasoning_signature` → `loop.py` merge → `mapper.py` 出站的完整 round-trip 链路正确工作。

---

**本 unit 未达成完整任务收敛。**

e2e 在第 59 轮被**独立缺陷 Issue #43** 阻断：工具调用 ID 使用顺序编号（`read:N` 格式）而非 UUID，导致当同一轮存在多个并行 tool_use 调用时，`tool_call_id` 与 `tool_result` 配不上，上游返回：

```
invalid_request_error: an assistant message with 'tool_calls' must be followed by
tool messages responding to each 'tool_call_id'. The following tool_call_ids did
not have response messages: read:7
```

该错误与 thinking signature 无关，根因是 `tool_call_id` 命名规则（`read:N` 顺序编号而非全局唯一 UUID）。Issue #43 已另立为 bugfix-376 跟踪修复。

**完整"末轮 end_turn + 最终用户可见答案"的端到端收敛，留待 bugfix-376 修好 Issue #43 后统一验证。**

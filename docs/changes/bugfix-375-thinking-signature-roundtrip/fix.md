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

**调查中发现：该症状由两个 co-root-cause 共同造成**，单独修任何一个均不足以让真实多轮任务收敛：

- **(A) Signature round-trip 丢失**（上述，commit `455d1456`）：每轮 thinking 块带空/无效签名，上游逐轮重放同一段 reasoning → 死循环。
- **(B) 并行 tool_result 写入顺序错误（Issue #43，commit `911d1bab`）**：`loop.py` 的 `StreamingToolExecutor` 在 stream 尚未结束时调用 `get_completed_results()` 并立即将 tool_result 写入 `llm_messages`，导致同一轮的多个并行 tool_use 块被 tool_result 切分到不同的 assistant 消息里，`tool_call_id` 与 `tool_result` 配不上，上游返回 `invalid_request_error: tool_call_ids did not have response messages: read:N`。

两者同时存在时，(A) 使早期轮次陷入 reasoning 死循环，(B) 使多工具并行轮次被上游拒。修复必须同时覆盖两处。

## 范围与非目标

- **范围**：修"开 thinking 的主 agent 在真实多轮工具任务下不收敛（死循环 / 中途停）"，覆盖 co-root-cause A（signature round-trip）、co-root-cause B（并行 tool_result 顺序乱序 = Issue #43 的 read:N/bash:N，含 heartbeat 路径；bugfix-376 已折叠进本 unit）、co-root-cause C（reasoning 跨持久化恢复保真）。
- **非目标**：agent 在跑任务途中发现的其它无关缺陷不在本 unit 修。

## 修复

> **追加（co-root-cause D，thinking 相关）**：本 unit 收尾的真 e2e（deep bug-finding，跨重启续跑）中，agent 自己挖出并经核实属实的一处同类缺陷——`runtime.py` 的 `_fork_locked`（session fork 路径）用手写逐字段 `Message(...)` 重建，**漏拷 `reasoning_content` / `reasoning_signature`**：fork 一个开 thinking 的 session 后，所有 assistant 的 thinking 块被丢，fork 的下一轮被上游以 `reasoning_content is missing` 拒、会话不可用。与 bugfix-377 修的 `_strip_fork_conversation` 同一"手写重建漏字段"反模式，按用户要求并入本 thinking unit。修法：改用 `dataclasses.replace(msg, …)` 只重新打戳 fork 专属字段、保全其余全部字段；红测 `tests/unit/test_fork_session.py::test_fork_preserves_reasoning_content_and_signature`（改前 red：fork 后 reasoning 为空 / 改后 green）。

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

### 5. `src/agent/core/agent/loop.py` — 并行 tool_result 延迟写入（co-root-cause B，Issue #43，commit `911d1bab`）

**问题**：`StreamingToolExecutor.get_completed_results()` 在 stream 循环体内被调用，先完成的 tool 会被立刻写入 `llm_messages`。当同一轮 LLM 响应包含多个并行 tool_use 块时，后续 tool_use 块尚未从 stream 中 yield 出来，已写入的 tool_result 就将这些 tool_use 块切断到不同的 assistant 消息——导致 `tool_call_id` 与 `tool_result` 配不上，上游返回 `invalid_request_error`。

**修复**：把 stream 循环体内的 `get_completed_results()` 改为只 yield UI 消息并暂存到 `early_tool_results`，**不写 `llm_messages`**；待整个 stream 结束后，再将 `early_tool_results` 统一 flush 进 `llm_messages`，确保所有并行 tool_use 块已落入同一条 assistant 消息后再追加对应的 tool_result。

### 6. co-root-cause C（持久化层并行 tool_use group 丢失，commit `5f13a039`）

**问题（event replay 后新发现）**：RC1+RC2 修复后，内存层（`llm_messages`）的 tool_use 配对正确，但 JSONL 持久化层仍有问题：同一轮 stream 里每个流式 assistant chunk 产生独立 `Message`，且 `group_id = message_id`（各自不同）。JSONL reload 时 `build_chat_messages` 无法把这些 Message 正确重组——`_merge_adjacent_assistant` 只合并连续相邻，tool_result 行夹在中间就断开了，导致恢复后上游仍报 `tool_call_ids did not have response messages`。

**双向修复**：

**6a. `loop.py` — 共享 `turn_assistant_group_id`**：stream 循环开始时分配一个 `turn_assistant_group_id`，同一轮所有 assistant_msg 共享该 group_id（而非每条自己的 message_id），JSONL 里同轮所有 assistant 行都携带相同 group_id。

**6b. `prompting.py` — `_coalesce_assistant_group`**：`build_chat_messages` 在转换 history_messages 为 LLMMessage 之前，先调 `_coalesce_assistant_group`：按 group_id 把同组 assistant Message 行合并为一行（累积 tool_calls，保留 reasoning_content/signature），再走 `_merge_adjacent_assistant`。恢复后所有并行 tool_use 正确还原为单条 assistant LLMMessage，tool_result 配对完整。

```python
# stream 循环体内：只 yield UI 消息，defer LLM history 写入
early_tool_results: list[ToolResult] = []
# ...（stream loop）
if executor is not None:
    for result in executor.get_completed_results():
        all_tool_results.append(result)
        yield self._build_tool_result_message(result, ...)
        early_tool_results.append(result)          # 暂存，不写 llm_messages

# stream 结束后：统一 flush
for result in early_tool_results:
    _append_llm_message(llm_messages, self._build_llm_tool_result_message(result))
# 再处理尚未完成的剩余 tool
async for result in executor.get_remaining_results():
    ...
    _append_llm_message(llm_messages, self._build_llm_tool_result_message(result))
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

### C1 E2E（RC1 FIFO 验证：live streaming 并行 tool_use 正确配对）

**设置**：API 进程端口 49186（PID 28642），session `sess_b54061b526c22fe3`，模型 `kimiCoding:K2.6`（thinking: adaptive），任务"并行 read 3 文件"。

**raw upstream-req**：`2026-05-21_01-01-50_400-upstream-req-anthropic_messages.json`

| 消息 | 内容 | 关键字段 |
|------|------|----------|
| msg[0] user | 并行 read 指令 | — |
| msg[1] assistant | thinking（sig_len=4340）+ 3 × tool_use | `tool_Gyo3Zk...`, `tool_1qoo9g...`, `tool_mxQyQh...` |
| msg[2] user | tool_result | `tool_Gyo3Zk...` ✓ |
| msg[3] user | tool_result | `tool_1qoo9g...` ✓ |
| msg[4] user | tool_result | `tool_mxQyQh...` ✓ |

`invalid_request_error`：**0**。`stop_reason=end_turn`。

**历史 `read:N/bash:N` 形式错误归 RC1 乱序**，RC1 fix（`f7d685db`）后消除。

---

### C2 E2E（RC3 验证：跨进程重启后 3 个并行 tool_use 正确恢复）

**第一次 run**（进程 PID 28642，端口 49186，session `sess_b54061b526c22fe3`）：并行 read 3 文件完成，JSONL 写入 3 条 assistant 行全部共享同一 `group_id=msg_d77c3f9f93a39ce8`（RC3 fix 生效），reasoning_signature sig_len=4340（非空）。

**kill 进程 → 新进程**（PID 28642→新 PID，端口 49344）恢复 session。

**raw upstream-req**：`2026-05-21_01-11-32_642-upstream-req-anthropic_messages.json`

| 消息 | 内容 | 关键字段 |
|------|------|----------|
| msg[0] user | 原始并行 read 指令 | — |
| msg[1] assistant | thinking（sig_len=4340）+ **3 × tool_use**（正确合并） | `tool_Gyo3Zk...`, `tool_1qoo9g...`, `tool_mxQyQh...` |
| msg[2] user | tool_result | `tool_Gyo3Zk...` ✓ |
| msg[3] user | tool_result | `tool_1qoo9g...` ✓ |
| msg[4] user | tool_result | `tool_mxQyQh...` ✓ |
| msg[5] assistant | thinking（sig_len=4340）+ text（总结） | — |
| msg[6] user | 旧第二轮 user（来自历史） | — |
| msg[7] assistant | thinking + tool_use bash | — |
| msg[8] user | tool_result bash | — |

`invalid_request_error`：**0**（RC3 前此处出现 `read:1` 错误，RC3 后清零）。`stop_reason=end_turn`。

**结论**：
1. 3 个并行 tool_use 恢复后正确合并进同一条 assistant 消息（`_coalesce_assistant_group` 按 group_id 合并）——**tool_call_ids 配对完整**。
2. 所有 assistant thinking 块 sig_len=4340（非空）——**`reasoning_content is missing` 不再出现**。
3. 跨进程重启后会话继续收敛到 end_turn。

---

### E2E（真实多轮 agentic 任务）

完整 deep-bug-finding prompt（原文无修改）发给 kimi K2.6（`thinking: adaptive`）agent，目标仓库 `https://github.com/Mrchen116/nano-multiagent`，本地有 `gh` CLI。两处 co-fix（`455d1456` signature chain + `911d1bab` defer parallel tool_result）均已生效。

**主证据**：`2026-05-20_21-25-52_261_sess_5506c97c418635cc`

| 指标 | 结果 |
|------|------|
| 主任务请求总数 | 169 |
| `invalid_request_error`（主交互路径） | **0** |
| 唯一真实 signature 数 | **28 个不同值**（无空串） |
| 最后一轮 stop_reason | **`end_turn`** |
| agent 最终答案 | 连贯 bug 报告（2125 字），含 root cause + fix 建议 |

两处 co-fix 同时生效后，169 轮主任务全程 0 个 `invalid_request_error`，多轮 thinking + 工具调用收敛到 end_turn + 连贯最终答案。

**辅证（signature round-trip 链路独立验证）**：`2026-05-20_20-33-57_475_sess_ae6700e3fedba556`（59 req，14 个唯一 signature，0 error）——更早的短链路验证，单独证明 `client.py` → `LLMMessage.reasoning_signature` → `loop.py` merge → `mapper.py` 出站的完整 round-trip 链路正确工作，每轮请求的 assistant 历史消息中 thinking 块 `signature` 字段均为真实值（非空串）。

**Heartbeat read:10 归因（RCA 修正，bugfix-376 折叠）**：`sess_5506c97c` 第 170 轮 heartbeat 触发的 `tool_call_ids did not have response messages: read:10`，经 raw upstream-req 逐条坐实，根因是 **RC1**（`get_completed_results` 对 safe 且 executing 的工具不 break，导致并行 tool_result 写入 llm_messages 乱序、被切到不同 assistant 消息）。heartbeat 走普通 `AgentLoop.run()` 内存累积、**不走** context_fork 或单独消息构建路径，与前台代码路径一致。`911d1bab` 只 defer、不保证顺序；**RC1 的 FIFO break（本 PR 已自折叠的 bugfix-376 cherry-pick 进来）才彻底解决，并直接覆盖 heartbeat**。C1 e2e（raw `2026-05-21_00-52-35`）实证：一条 assistant 3 个并行 tool_use 全部正确配对、0 error、收敛。PR 仍 Refs #43（不 Closes）——已修主交互 + heartbeat 的 read:N 乱序，保守保留 issue 由人确认是否还有其它面向。

---

### 持久化保真（bugfix-376 折叠，co-root-cause C）

**问题（RCA from bugfix-376）**：heartbeat/background session 重建历史时，`reasoning_content`/`reasoning_signature` 和并行 `tool_use↔tool_result` 配对的错误根源在**持久化层**——

1. `Message` dataclass 没有 `reasoning_content`/`reasoning_signature` first-class 字段，loop.py 构造 `assistant_msg` 时只能丢弃。
2. `_message_to_entry`（runtime.py）不把 reasoning 写进 JSONL，JSONL 里永远没有这两个字段。
3. `jsonl_store._to_message` 读 JSONL 时不还原 reasoning，`build_chat_messages` 构造 `LLMMessage` 时没有传 reasoning 字段——任何跨 restart 的 session resume（heartbeat 新 session 也包含）都会遭遇 `reasoning_content is missing`。

**修复（commits see below）**：

| 文件 | 改动 |
|------|------|
| `src/agent/core/types.py` | `Message` 添加 `reasoning_content: str \| None = None` 和 `reasoning_signature: str \| None = None` 两个 first-class 字段 |
| `src/agent/core/agent/loop.py` | 构造 `assistant_msg` 时从 `llm_msg.reasoning_content/reasoning_signature` 注入 |
| `src/agent/core/agent/runtime.py` | `_message_to_entry` 写出 `reasoning_content`/`reasoning_signature` 到 JSONL 顶层字段 |
| `src/agent/core/session/jsonl_store.py` | `_to_message` 从 JSONL 顶层还原两个字段到 `Message` |
| `src/agent/core/session/entries.py` | `message_from_turn_entry` 还原 `tool_call_id`/`group_id`/reasoning 字段（之前只还原 message_id/role/content） |
| `src/agent/core/session/manager.py` | `_build_turn_metadata` 把 `reasoning_content`/`reasoning_signature` 包入 metadata（供 `list_entries` 路径使用） |
| `src/agent/core/agent/prompting.py` | `build_chat_messages` 从 `Message.reasoning_content/reasoning_signature` 传给 `LLMMessage` |

**新增测试**：

- `tests/unit/test_session_persistence_fidelity.py`（10 个单测）
  - `TestReasoningPersistence`：`_message_to_entry` 写出字段；`Message` first-class 字段存在；`_roundtrip` 后 `Message.reasoning_*` 完整；`build_chat_messages` 传出 reasoning；无 reasoning 时入口/出口均为 None。
  - `TestToolResultPairingFidelity`：`tool_call_id` 写出到 JSONL；restore 后 `Message.tool_call_id` 正确；并行 tool_results 两个 `call_id` 均出现在 `build_chat_messages`；`tool_calls` metadata 经 roundtrip 后 `LLMMessage.tool_calls` 非空且 `call_id` 匹配。

- `tests/unit/test_jsonl_store_dag_recovery.py`（+2 个真实文件 roundtrip 测）
  - `test_reasoning_fields_survive_jsonl_roundtrip`：写入带 `reasoning_content`/`reasoning_signature` 的 JSONL 行，`store.load()` 后断言两字段完整还原。
  - `test_tool_call_id_survives_jsonl_roundtrip`：写入两条并行 tool_result，`store.load()` 后断言两个 `tool_call_id` 均存在。

**E2E（跨持久化边界，process restart）**：

session `sess_ca5befc8a84d1750`，模型 `kimiCoding:K2.6`（thinking: adaptive）。

**第一次 run**（API 进程 pid 97778，端口 60449）：
- 发送"Run bash: echo hello world"
- agent 用 `bash` 工具调用并收敛到 `end_turn`
- JSONL（`.nano/sessions/sess_ca5befc8a84d1750.jsonl`）中 assistant 消息带 `reasoning_content` 和 `reasoning_signature`（两条都有）

**进程重启**：kill pid 97778，在新端口 61164 起新 API 进程（pid 1221），session JSONL 保留。

**第二次 run**（新进程）：
- 发送"Now run bash: echo session_restored_ok"
- LLM proxy raw req `2026-05-21_00-40-15_788-upstream-req-anthropic_messages.json`

恢复历史验证（5 条消息）：

| 消息 | 内容 | 关键字段 |
|------|------|----------|
| msg[0] user | "Run bash: echo hello world..." | — |
| msg[1] assistant | THINKING + tool_use bash | sig_len=**4340**（非空），tool_use_id=`tool_j5XzvHPe0ssl0qkLkIVM4d6O` |
| msg[2] user | tool_result | tool_use_id=`tool_j5XzvHPe0ssl0qkLkIVM4d6O`（**配对完整**） |
| msg[3] assistant | THINKING + text | sig_len=**4340**（非空） |
| msg[4] user | "Now run bash: echo session_restored_ok" | 新 user 消息 |

`invalid_request_error`：**0**。第二次 run `stop_reason=end_turn`，输出：`"Confirmed. The command ran and output: session_restored_ok"`。

**结论**：跨进程重启后，恢复的历史里：
1. 所有 assistant thinking 块均带真实 signature（sig_len=4340，非空串）——**`reasoning_content is missing` 不再出现**。
2. tool_use↔tool_result 配对完整——**`tool_call_ids did not have response messages` 不再出现**。
3. 会话继续正常收敛到 `end_turn`。

### Permission ask → approve → resume thinking 路径

**会话**：`2026-05-20_22-02-12_463_sess_ce88159dc3e47c86`，IM `http://127.0.0.1:54217`，对话 `a52669838fba4b13bd6674e16171460e`

**触发步骤**：向 agent 发送任务"将注释写入 `~/.bashrc`"。`~/.bashrc` 在 `DANGEROUS_FILES` 名单中，`WriteTool.check_permissions` 返回 `behavior="ask", type="safety_check"`，auto_mode_gate Step 2 直接发出 permission ask，**不经过** classifier（safety_check 类型绕不过）。

**Permission request**（消息 id `5f4aed11174249d0b863c58a933f440c`）：
```json
{
  "request_id": "b32be46d-85a6-4e0e-8f13-7f6035eaf511",
  "tool_name": "write",
  "tool_input": {"path": "~/.bashrc", "content": "# test by kimi-agent\n"},
  "question": "Allow write? Writing to ~/.bashrc requires explicit confirmation (sensitive system file or directory)",
  "status": "pending"
}
```

**批准**：`POST /im/v1/conversations/.../permissions/b32be46d-85a6-4e0e-8f13-7f6035eaf511` `{"decision": "allow_once"}` → `{"status":"forwarded"}`

**恢复后验证**（proxy req `2026-05-20_22-15-58_086-req-anthropic_messages.json`）：

| 指标 | 结果 |
|------|------|
| permission ask 前的 thinking sig_len（msg[23]） | **4340**（非空） |
| permission ask 前的 thinking sig_len（msg[25]） | **4340**（非空） |
| 批准后新请求 `invalid_request_error` | **0** |
| 批准后 stop_reason | **`end_turn`** |
| agent 最终答案 | "Done — `~/.bashrc` didn't exist, so I created it with `# test by kimi-agent` at the end." |

**结论**：permission ask → 批准 → resume 全链路正确——恢复后请求历史中 thinking 块 signature 完整保留，**0 个 invalid_request_error**，agent 正常收敛到 end_turn。

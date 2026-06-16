# bugfix-416: 群聊 fan-out NO_REPLY 泄漏 + 超时 bash 在 IM 丢命令/description

本 unit 打包两个相互独立、但同属 IM 消息链路「收尾接缝漏处理」的小修。两者根因无关，
合在一个 lite unit 只为省一次仪式；修复时各自独立。

## Relations

- Closes: #107
- Closes: #111
- Related: #110   # 三者源自同一次群聊/工具事故链；#110（会话锁死 / watchdog 重设计）体量大，单独走 full 流程，不在本 unit。

## 原始报告

### #107 — 群聊 agent 互相 @ 的 fan-out 回复 NO_REPLY 未被抑制，字面量泄漏进气泡

> 群聊里 agent 之间互相 @ 触发（agent-to-agent fan-out）后，其中一个 agent 判断「不用再接话」
> 输出协议哨兵 `NO_REPLY`，本应被吞掉，但 `NO_REPLY` 字面量直接进了会话气泡显示出来。
>
> 复现会话：`type=group`（"default-agent, Arch"），两个 agent 互相 @ 做完 Markdown 示范后，
> 落库出现一条 `agent | NO_REPLY` 消息。
>
> 设计原意（`src/personal_assistant/product.py:166` 的 prompt「群聊里不用回复就输出 NO_REPLY」）
> 是要它被静默抑制、不投递。

（完整三路径表与建议修法见 issue #107 正文。）

### #111 — 超时的 bash 在 IM 丢失命令/description，只剩「bash Timed out」

> 当一个 bash 工具因超时被收口时，IM 里只显示一个红 ×「bash Timed out」，丢失了命令和
> description——而正常完成的 bash 会显示 description（如「Run full frontend test suite」）
> + 完整命令 + `exit 0`。用户无法知道到底是哪条命令超时了。
>
> 触发它的「为什么会超时」是 #110（watchdog 误杀长工具）；本 issue 只管「超时态在 IM 的
> **展示**为什么丢字段」，是独立的展示 bug。

（完整根因两层分析见 issue #111 正文。）

## 现象 / 复现

### ① #107：群聊 fan-out 的 NO_REPLY 泄漏进气泡并落库

- 群聊（≥2 个 agent）里，用户 @ agent A；A 的回复里 @ 了 agent B，把 B 拉起（agent-to-agent
  fan-out）。
- B 判断不用接话，按 prompt 约定输出哨兵 `NO_REPLY`。
- 预期：B 这条被静默抑制，不投递、不落库（与「用户直接 @ 的 agent 输出 NO_REPLY」一致——
  那条主路径已正确抑制）。
- 实际：B 这条 `NO_REPLY` 字面量直接落库、点进 thread 气泡照常显示一条 `agent | NO_REPLY`。
- 旁证错觉：会话列表的 preview 摘要里看不到 `NO_REPLY`（IM 侧 `_is_no_reply_protocol_token`
  只把它从列表预览摘要抹掉，不拦消息体），所以容易误以为已被抑制；点进 thread 才暴露。

### ② #111：超时 bash 在 IM 只剩红 ×「bash Timed out」，命令与 description 全丢

- 正常完成的 bash 气泡：显示 description（如「Run full frontend test suite」）+ 完整 command
  + `exit 0`。
- 同一条 bash 若因超时被 watchdog 收口：气泡只剩一个红 ×「bash Timed out」，command 和
  description 全部消失。
- 后果：用户看不出到底是哪条命令超时，无法判断该重试、该改超时、还是该排查命令本身。

## 根因

### ① #107：群聊三条 agent 文本投递路径，只有主路径做了 NO_REPLY 抑制

群聊里 agent 文本有三条投递路径，抑制只落在第一条：

| 路径 | 位置 | 触发场景 | 是否抑制 NO_REPLY |
|---|---|---|---|
| 主同步回复 | `inbound_pipeline.py:351` | 用户直接 @ 的 agent 的最终回复 | ✅ `_should_suppress_no_reply`（:601，群聊 + `_is_no_reply_token` :592） |
| 流式 other-origin | `inbound_pipeline.py:313-319` `_on_other_event` | agent A 回复里 @ 了 B，B 被拉起的流式 `assistant_message` | ❌ 只判 `content.strip()` 非空就 `send_text` |
| background 中继 | `inbound_pipeline.py:784-799` `_relay_bg_run_output` | BACKGROUND_TASK origin 的 `assistant_message` | ❌ 只判 `content.strip()` 非空就 `bg_reply_sender` |

**原始设计意图**：NO_REPLY 群聊静默边界由 commit `f19a047f`（"close NO_REPLY group relay
silence boundary"，M140）引入——群聊里 agent 输出 NO_REPLY 表示「我不接话」，应被静默吞掉、
绝不投递给用户。

**为什么这种错能进来**：M140 把抑制 helper（`_is_no_reply_token` / `_should_suppress_no_reply`）
只接在「主同步回复」这一条路径上；流式 other-origin 与 background 中继两条 fan-out 路径是后续
为 agent-to-agent / BACKGROUND_TASK 场景陆续加的（`_on_other_event`、bugfix-404 的 `_relay_bg_run_output`），
各自独立判「strip 非空就发」，没有回头复用抑制 helper。抑制逻辑分散在调用点而非收敛在一处公共
出口，新增投递路径时就漏接。

**修复必须保住的不变量**：
1. 群聊里任何 agent 文本投递路径，输出哨兵（`NO_REPLY` / `HEARTBEAT_OK`，由 `_is_no_reply_token`
   :592 统一识别）都不得投递、不得落库。
2. 非哨兵内容、以及单聊场景的正常回复不受影响（不能为了消症状把 fan-out 路径整个静音）。

**修法决策（写死，worker 照此实现，勿即兴选别的层）**：

抑制收敛在 **pipeline 应用层**，不下沉到出口、也不在两处调用点各写一个 `if`：

- ❌ **不下沉到 `OutboundRouter.send_text`**（`outbound_router.py:15`）。它是纯传输出口，只认
  channel / reply_context，不懂 agent 协议哨兵、不知道 is_group——把 `NO_REPLY` 判断塞进去是
  分层倒置（传输层去懂应用协议），且 `bg_reply_sender` 是另一个独立出口（`main.py:3745`，跨 SSE
  循环走不同通道），下沉也覆盖不到它。两个出口分立有其传输理由，不强行合并。
- ❌ **不在 `_on_other_event`（:313-319）和 `_relay_bg_run_output`（:784-799）各加一个 `if`**。
  那是第三次打补丁——抑制判断仍分散在调用点，下次再加第四条投递路径照样漏（本 bug 的成因正是
  抑制分散）。
- ✅ **泛化已有的抑制守卫为单一判断点，三条路径统一调用**：
  - 把 `_should_suppress_no_reply`（:601，现签名 `(message, *, reply_text)` → `message.is_group
    and _is_no_reply_token(reply_text)`）泛化为不依赖 `message` 的形式，例如
    `_should_suppress_no_reply(reply_text: str, *, in_group: bool) -> bool`，内部仍是
    `in_group and _is_no_reply_token(reply_text)`。不依赖 `message` 是因为 background 中继路径
    跨 SSE 循环、手里不一定持有原 `InboundMessage`。
  - 三条路径在各自 send 前都过这个守卫：主路径传 `in_group=message.is_group`；fan-out 两路
    （`_on_other_event` / `_relay_bg_run_output`）agent-to-agent 隐含群聊上下文（单聊不存在
    agent 互相 @），传 `in_group=True`。
  - 在该守卫的 docstring 写明「任何新增的 agent 文本投递路径必须经此守卫」，把「单一判断点」做成
    可被后人看见的约束，而不只是当下三处恰好都调了。
- 主路径现有的 `suppressed_by=no_reply_token` lifecycle 标记（:356）行为保留；fan-out 两路被
  抑制时直接 `return`/跳过即可，无需补 lifecycle（它们本就没有对应的 lifecycle 卡）。

### ② #111：reconcile 收口在飞 tool_call 时丢了 input，前端空 input 又覆盖已有命令

两层叠加：

**后端**——in-flight tool_call 跟踪只存了工具名：

```python
# src/personal_assistant/main.py:3501
running_tool_calls.setdefault(run_id, {})[call_id] = tool_name   # 只记 name，丢了 input
```

watchdog reap 走 `run_terminal_reconcile`（`main.py:3639`），收口时只能拼出 name+status+reason，
硬塞空 input：

```python
# src/personal_assistant/main.py:3657-3663
"tool_call": {"id": stuck_call_id, "name": stuck_name,
              "status": "failed", "reason": reason, "input": {}}
```

**前端**——reducer 合并时空 input 覆盖掉已有命令：

```ts
// src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts:41
const merged = ... { ...t, ...next }   // next.input = {} 覆盖掉 upsert 时存进 state 的真实 input
```

upsert 阶段（tool_start，`main.py:3514` 已带完整 `input`）前端本已拿到命令，是 reconcile 这条
空 `input:{}` 合并上来把它抹了 → 只剩「bash Timed out」。

**原始设计意图**：
- `feat-409`（im-tool-call-display）：工具调用经 `tool_call_upserted` / `tool_call_completed`
  两个流式事件下发，`input` 里带 `command`/`description`/`timeout`，正常态据此渲染命令与
  description。
- `bugfix-410-M2 R3`（#97，unattended-toolcall-robustness）：run 异常终止（watchdog 超时 /
  崩溃 / 中断）时，在飞 tool_call 收不到 tool_end 会永远转圈；reconcile 用 `running_tool_calls`
  把每条在飞 call 收口成 `status=failed`，止住转圈。

**为什么这种错能进来**：bugfix-410 的 reconcile 目标只是「止转圈」，跟踪结构当时只需要 name +
status 就够，没把 feat-409 已经流过的 `input` 一并记下来；于是异常收口态天然比正常态少了
`input`。前端 reducer 又是无差别浅合并（`{...t, ...next}`），把收口事件的空字段当成「新值」覆盖了
upsert 阶段的真实值——两层都默认「后到的事件字段更全」，而 reconcile 恰好是个「字段更少」的事件。

**修复必须保住的不变量**：
1. bash（及任何工具）超时/异常收口后，IM 气泡仍展示其 command / description，与正常态一致，
   只是状态为失败 + reason。
2. reconcile 止转圈的既有行为不退化（在飞 call 仍被收口为 failed，不再永久 running）。
3. 任何「收口事件少带字段」都不得抹掉已展示的非空内容（前端兜底，防同类问题再发）。

## 修复

<!-- milestone 完成后由 worker 回填：改了什么 + commits。 -->

## 验证

<!-- milestone 完成后由 worker 回填：修前能复现 → 修后不能；相关功能回归正常。 -->

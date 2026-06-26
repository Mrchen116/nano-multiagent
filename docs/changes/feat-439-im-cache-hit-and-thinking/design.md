# feat-439 设计文档：IM 展示缓存命中率 + 内部 IM 展示 LLM thinking

> 对应需求：`spec.md`（门禁 1 已过）。本文只写「怎么做」，不重复「做什么」。
> Unit branch: `unit/feat-439` (will be created by orchestrator)

## Changelog

<!-- 实施期偏差由 orchestrator/worker 维护；对齐期推翻直接原地重写。 -->

## 1. 背景与目标

两个相互独立的展示增强，落在内部 Web IM：

1. **缓存命中率**：token 气泡详情面板新增「缓存命中 X (Y%)」一行，口径为**整轮累计**（spec Q1=B）。数据已被上游 provider 返回，只是当前在解析层被丢弃。
2. **内部 IM 展示 thinking**：助手气泡里把整轮多段 thinking 与工具调用按时序混排进可折叠「过程」盘；外部 channel 不带 thinking。

两件事**没有公共改动文件**，可拆成两条互不依赖的垂直切片（见 §3）。

### 两个必须先讲清的架构事实（决定 thinking 方案）

#### 事实 A：一个气泡 = 一个 turn = **多次** LLM 请求，每次各自带 thinking

用户看到的「一个助手气泡」并不是一次模型调用，而是一个 turn 内的**多次 LLM roundtrip**。内核 `loop.py:390-404`：turn 里每个回合都新建一个 assistant `Message`，各自带 `content`（可能为空）+ 各自的 `reasoning_content`；同 turn 所有 message 共享一个 `group_id`（首条 message 的 id）。`message_end` hook 对**每个回合**都 fire（`loop.py:626-639`）。

→ **思考天生是「整轮 N 段」，不是一段**。典型一轮「思考→调3个工具→再思考→回答」就有 2-3 段思考，分散在多个回合上。

而这些回合现在如何落进一个气泡？Gateway `main.py:3382-3384`：

```python
content = str(event.get("content") or "").strip()
if not content:
    return None        # ← 空正文回合被整段丢弃
```

绝大多数「思考+调工具但不输出正文」的回合 `content=""`，被这里丢掉；turn 开始的占位气泡（`main.py:3278` turn_start）装下所有工具调用 + 最终带正文回合的文字，于是整轮塌缩成**一个气泡**（仅当出现 textA→tools→textB 两段带正文回合才 roll 第二气泡，`main.py:3476-3484`）。

→ **后果**：这些被丢弃回合上的 `reasoning_content` 现在根本到不了 IM。原设计「reasoning 搭单条 assistant_message 透传」对它们是空操作，会丢掉大部分思考。

#### 事实 B：内核事件管线是**消息级、非 token 级**

`realtime_stream.py` 事件词表只有 `turn_start / assistant_message / tool_start / tool_end / turn_end`，无 token delta（gateway 的 `kind=message_delta` 的 `delta_text` 装整段 content，不是 token 增量）。连普通文本都不是逐字流式。为 thinking 单造 token 流式 = 给整个 hub 新建 token streaming，是独立大工程，不进本 feat。

#### 推论（合二为一）：thinking 渲染为「过程时间线」

由 A + B，thinking 的正确模型不是「正文上方一个会逐字滚动的块」，而是：**把整轮多段 thinking 与工具调用按真实时序混排进同一个可折叠「过程」盘**（思考①→工具a→工具b→思考②→…→正文）。它沿用现有 `chat-tool-calls` 折叠盘形态，把「工具调用」面板升级为「过程」时间线。每段思考整段到达、可展开/收起回看；本轮无思考则不出现 💭 行。原型 `prototype.html` 已按此重做并真渲染核对（浅色主题 + 时序混排）。

⚠️ 这调整了 spec 场景 B 的三处措辞：①「正文上方」→ 收进气泡内「过程」盘；②「逐字实时滚动」→ 整段到达；③隐含的「一段思考」→ 整轮多段。delta-spec（§4）按调整后行为写；**spec.md 场景 B 需回 change-spec-author 同步**（见 §5 R1）。

---

## 1.9 现状分析（决策的事实基础）

**涉及范围（沿调用链）**：
- 缓存命中率链路：`agent/core/types.py:TokenUsage` → `anthropic/client.py:_parse_anthropic_usage` / `openai_compat/client.py:_parse_openai_usage`（现状只取 input/output，缓存字段被丢）→ `agent/core/agent/loop.py:_accumulate_usage`（1044-1050，prompt 取快照、completion 累加）→ `personal_assistant/config/local_store.py:_build_token_usage/_encode/_decode`（透传）→ `IM/domain/models.py:TokenUsage`、`IM/api/ws/event_types.py:token_usage_to_dict` → 前端 `chat-types.ts:TokenUsage`、`token-chip.tsx`（详情面板渲染输出/总计/已用上下文）。
- thinking 链路：`anthropic/client.py:177-184`（thinking 累积进 turn_reasoning，最终落到 `loop.py:402` 的 `Message.reasoning_content`）→ `loop.py:626-639` message_end hook（**不带 reasoning**）→ `realtime_stream.py` assistant_message → `personal_assistant/main.py` observer（**`3382-3384` 丢空正文回合**）→ IM messages 表 / repositories / event_types → 前端 `tool-calls-panel.tsx`（现有折叠盘）、`message-pane.tsx`。

**关键约束（既有架构）**：
- 产品包（CLI / Gateway）只能 import `agent.sdk`，不碰 core/platform 内部；本 unit 内核改动经 `agent.sdk` 暴露的事件透传，CLI 侧需确认忽略新增可选字段、无回归。
- IM 不调用 agent，只经 Gateway 中继；thinking/cache 数据均走既有 `node.streaming_delta` 透传范式（对齐 tool_call/usage 既有做法）。
- `prompt_tokens` 语义是「最后一次请求快照」，驱动「已用上下文」气泡，**不可改/不可累加**（决策 1/3 的硬约束）。

**可复用的既有能力**：
- 折叠盘形态 `chat-tool-calls`（`tool-calls-panel.tsx` + global.css）—— 决策 4 直接**扩展**它为「过程」时间线，不另造一套折叠交互。
- usage 透传链（`_build_token_usage`/`token_usage_to_dict`/前端 `TokenUsage`）已成型，M1 只在每一跳加两个可选字段即可。

**契约层 grounding 结论**：`docs/specs/{kernel,gateway,im}/spec.md` 与代码一致，无 drift；本 unit 为纯增量（ADDED）。

**值得注意的历史**：token 气泡的「总计/已用上下文/快照口径」由 bugfix-390 / feat-414 / M17 等奠定（见 `token-chip.tsx` 注释 R4/f1cc8881），决策 1/3 严格沿用其「completion 累加、prompt 快照」规矩。工具展示链曾因只测 presenter 未验 UI 出过 false-fix（bugfix-427），故 R4 强调真栈验。`spec.md` 误标的「Related: feat-438」实为群聊设置，收尾改正。

## 2. 关键设计决策

### 决策 1：`cache_read_tokens` + `cache_total_input_tokens` 两个字段贯穿 TokenUsage

**问题**：上游 usage 真实带缓存字段（Anthropic `cache_read_input_tokens`/`cache_creation_input_tokens`、OpenAI `prompt_tokens_details.cached_tokens`），但 provider 解析层只取 input/output 就丢了。要算命中率，必须把缓存信息一路带到前端。

**为什么是这两个字段、而不是只加一个 `cache_read`**：命中率 = 命中 ÷ 总 input，分子分母都得带。但**现有 `prompt_tokens`（→IM `context_used`「已用上下文」）的语义是「最后一次请求的快照」，绝不能改**（改了「已用上下文」气泡就错）。所以分母不能复用 `prompt_tokens`，要单独带一个「本次总 input」字段，且在 provider 层把两家 provider 的口径**归一**，这样累计才一致。

**Before** (`agent/core/types.py:10-16`):
```python
@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

**After**:
```python
@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    # 缓存命中率用：cache_read = 命中缓存读取的 input（分子）；
    # cache_total_input = 本次总 input 含命中部分（分母），已在 provider 层跨家归一。
    # 与 prompt_tokens 分开：prompt_tokens 是「最后快照」驱动 context_used，不可累加。
    cache_read_tokens: int = 0
    cache_total_input_tokens: int = 0
```

**理由**：默认值 0 → 不带缓存的 provider/旧持久化数据天然兼容；两字段语义自解释，避免 qwen 版「分母用 prompt_tokens」的口径错。

---

### 决策 2：provider 层归一缓存口径（修正 qwen 公式的两处 bug）

**问题**：qwen 版公式 `cache_read /(cache_read + prompt_tokens)` 对两家 provider 都错——Anthropic 漏了 `cache_creation`；OpenAI 的 `prompt_tokens` **已含** cached，再加一遍 = 重复计、命中率虚低。根因是没意识到两家 provider 的 `input` 口径不同（Anthropic 的 `input_tokens` **不含**缓存，OpenAI 的 `prompt_tokens` **含**缓存）。

**方案**：在各自 `_parse_*_usage` 里算出归一后的 `cache_read_tokens` 与 `cache_total_input_tokens`，让下游只做无脑累加 + 相除。

**Before** (`anthropic/client.py` `_parse_anthropic_usage`，现状把缓存并丢):
```python
def _parse_anthropic_usage(usage):
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    return TokenUsage(input_tokens, output_tokens, input_tokens + output_tokens)
```

**After**:
```python
def _parse_anthropic_usage(usage):
    input_tokens = usage.get("input_tokens", 0)              # 不含缓存
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    return TokenUsage(
        prompt_tokens=input_tokens,                          # 语义不变，仍是快照来源
        completion_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cache_read_tokens=cache_read,
        cache_total_input_tokens=input_tokens + cache_read + cache_creation,  # 归一：总 input
    )
```

**After** (`openai_compat/client.py` `_parse_openai_usage`):
```python
def _parse_openai_usage(usage):
    prompt_tokens = usage.get("prompt_tokens", 0)            # 已含 cached
    completion_tokens = usage.get("completion_tokens", 0)
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cache_read_tokens=cached,
        cache_total_input_tokens=prompt_tokens,              # 归一：prompt_tokens 本身即总 input
    )
```

**理由**：归一动作收敛在 provider 层（本就是「贴上游差异」的地方），下游 loop/IM/前端对两家 provider 写一份逻辑。命中率 = `cache_read_tokens / cache_total_input_tokens`，两家口径一致。

---

### 决策 3：`_accumulate_usage` 里缓存字段**累加**（对齐 spec Q1=B 整轮口径）

**问题**：一个气泡 = 一个 turn = 多次 roundtrip。`prompt_tokens` 取最后快照（现状），但命中率要整轮累计，缓存两字段必须**求和**——否则分子累计、分母快照，口径打架（正是 qwen 版的 C2 缺陷）。

**Before** (`loop.py:1044-1050`):
```python
accumulated_completion = current.completion_tokens + update.completion_tokens
return TokenUsage(
    prompt_tokens=update.prompt_tokens,                      # 最新快照
    completion_tokens=accumulated_completion,
    total_tokens=update.prompt_tokens + accumulated_completion,
)
```

**After**:
```python
accumulated_completion = current.completion_tokens + update.completion_tokens
return TokenUsage(
    prompt_tokens=update.prompt_tokens,                      # 最新快照（不变）
    completion_tokens=accumulated_completion,
    total_tokens=update.prompt_tokens + accumulated_completion,
    cache_read_tokens=current.cache_read_tokens + update.cache_read_tokens,            # 累加
    cache_total_input_tokens=current.cache_total_input_tokens + update.cache_total_input_tokens,  # 累加
)
```

**理由**：完全沿用现有 docstring 立的规矩（completion 累加、prompt 快照），缓存归入「累加」一类，语义自洽。前端命中率 = `Σcache_read / Σcache_total_input`，即整轮口径。

> 透传链路（无逻辑、纯加字段）：`local_store.py:_build_token_usage`(728) 把这两个字段映射进 IM `TokenUsage` → `_encode/_decode_token_usage`(718) JSON 编解码 → IM `domain/models.TokenUsage`(233) 加字段 → `event_types.token_usage_to_dict`(57) 带出 → 前端 `chat-types.TokenUsage`(100) 加可选字段。详见 §3 M1 范围。

---

### 决策 4：每回合 thinking 作为「过程项」按时序流到气泡，渲染为过程时间线

**选了**：把 thinking 当成与工具调用并列的「过程项（process item）」，**每个 LLM 回合**各自的 `reasoning_content` 都带出来、附在所属气泡上，并保留它相对工具调用的时序；前端把思考段 + 工具调用合并成一条「过程」时间线渲染。内外区分只落在渲染端。

**为什么不是原方案（reasoning 搭单条 assistant_message 透传一个字段）**：按 §1 事实 A，一个气泡含多回合、多段思考，且空正文回合在 `main.py:3383` 被丢——单字段方案会丢掉大部分思考、也无从表达「思考①在工具 a 之前、思考②在工具 a 之后」的时序。所以数据结构必须承载**多段 + 时序**，不是一个标量字段。

**四处断链 + 对应改法**：

1. **内核 client 不 emit thinking**（`anthropic/client.py:177-184`：thinking 块累积进 `turn_reasoning`，`content_block_stop` 时 `continue` 跳过）。`reasoning_content` 最终是落到了 `Message` 上（`loop.py:402`），所以**接收/持久化不用动**（符合 spec「不改 thinking 接收与持久化」）；要动的是把它**暴露到事件**。

2. **`message_end` hook 不带 reasoning**（`loop.py:626-639`）。补带 `reasoning_content`：

   ```python
   await self._dispatch_observe_async("message_end", {
       ...,
       "content": msg.content,
       "reasoning_content": msg.reasoning_content,   # 已具备，只是没带进事件
       "role": msg.role,
   }, hook_ctx)
   ```

3. **Gateway 丢空正文回合**（`main.py:3382-3384`）。这是关键改动：当回合**无正文但有 reasoning** 时，不能再 `return None` 丢弃，而要把这段 thinking 作为「过程项」转发到当前气泡（不 roll 新气泡、不产生空正文气泡）。带正文回合则照旧转发正文，同时附带本回合 reasoning。每个过程项带一个**时序序号**（由 gateway 按 kernel 回合 + 工具到达顺序单调递增赋予），让前端能把思考段插到正确的工具之间。

   > 时序的事实基础：gateway observer 已逐事件顺序处理同一 run 的 `assistant_message` / `tool_start` / `tool_end`（`main.py:3279-3282`），按到达顺序赋单调序号即得真实时序，无需新增内核时间戳。

4. **IM / 前端无承载结构**。IM 给 message 持久化一组有序「思考段」（每段：序号 + 文本），与既有 `tool_calls` 并存；前端把两者按序号 merge 成一条时间线，复用 `chat-tool-calls` 折叠盘升级为「过程」盘（见原型）。

**理由**：数据模型贴合「turn=多回合、每回合可有思考」的真实结构（§1 事实 A）；不造 token streaming（事实 B）；内外区分天然——数据无条件流到 IM 并持久化，外部 channel 出站序列化本就只取正文，不带过程项。无思考回合 = 无思考段 → 过程盘只有工具或整轮无过程项，空态自然成立。

> ⚠️ 本决策把工具面板升级为过程面板，触及 `tool-calls-panel.tsx`，但仍只属 M2 范围、与 M1 零交集（M1 不碰前端消息渲染，只碰 `token-chip.tsx`）。

---

## 3. Milestone 拆分

两条**完全解耦、可并行**的垂直切片——不同文件、无共享改动、互不依赖。每条自带后端→前端全链路，单独可上线、可验收。

| ID | 标题 | 依赖 | 并行组 | 范围（文件） | 退出标准（[reviewer] 旅程 / [worker] 实现层） |
|---|---|---|---|---|---|
| feat-439-M1 | cache-hit-rate | — | A | 后端：`agent/core/types.py`、`anthropic/client.py:_parse_anthropic_usage`、`openai_compat/client.py:_parse_openai_usage`、`agent/core/agent/loop.py:_accumulate_usage`、`personal_assistant/config/local_store.py:_build_token_usage/_decode_token_usage(+_encode)`、`IM/domain/models.py:TokenUsage`、`IM/api/ws/event_types.py:token_usage_to_dict`（+REST 侧 `messages.py` 若有第二序列化路径）；前端：`chat-types.ts:TokenUsage`、`token-chip.tsx` | `[reviewer]` 长对话点开 token 气泡详情看到「缓存命中 X (Y%)」行、值在 0–100%（覆盖 im Scenario「有命中」）；短新对话显示 `0 (0%)`（覆盖「无命中」）。<br>`[worker]` `_parse_anthropic_usage`/`_parse_openai_usage` 两家缓存字段解析 + 跨家归一单测；`_accumulate_usage` 缓存两字段累加、prompt 仍取快照单测；`token_usage_to_dict` 带字段单测；前端 token-chip 渲染命中行 + 0% 空态单测；golden 若覆盖 TokenUsage 序列化则同步更新；CLI 侧 contract/单测无回归 |
| feat-439-M2 | thinking-process-timeline | — | A | 内核：`agent/core/agent/loop.py`（message_end payload 补 reasoning_content）、`agent/platform/hooks/builtins/realtime_stream.py`（assistant_message 带 reasoning）；gateway：`personal_assistant/main.py` observer `assistant_message` 分支（**空正文有 reasoning 的回合不再丢弃**，作为带序号过程项转发）；IM：`IM/infra/db.py`（messages 表加思考段存储）、`IM/domain/models.py:Message`、`IM/infra/repositories.py`、`IM/application/event_bridge.py`、`IM/api/ws/event_types.py`；前端：`chat-types.ts:Message`（thinking 段 + 序号）、`tool-calls-panel.tsx`（升级为过程时间线，thinking+tool 按序 merge）、`message-pane.tsx`（接线） | `[reviewer]` 带 thinking 模型跑一轮多工具对话，气泡内「过程」盘按真实时序出现「思考①→工具…→思考②→…」、逐段可展开/收起、刷新历史仍可展开（覆盖 im Scenario「一轮含多段思考与工具调用」「思考整段可展开回看」）；无思考回合不出现 💭 行（覆盖「无思考」空态）；外部 channel 同条只见正文（覆盖「外部 channel」）。<br>`[worker]` message_end/assistant_message 带 reasoning 单测；observer 对「空正文+有 reasoning」回合转发为过程项且赋单调序号、对「空正文+无 reasoning」仍丢弃单测；repo 思考段持久化往返单测；event payload 带字段单测；前端过程盘按序号 merge 渲染单测（多段思考+工具交错 / 无思考 / 展开收起）；CLI 侧忽略 reasoning 字段无回归 |

> 拆分理由（呼应「milestone 间不要耦合」）：两特性逻辑独立、垂直切片各自后端→前端闭环，做成两条而非「后端 M / 前端 M」（后者会让前端 milestone 依赖后端类型先落地，引入串行依赖）。前端零交集（M1 只碰 `token-chip.tsx`，M2 只碰 `tool-calls-panel.tsx`/`message-pane.tsx`）。
>
> **⚠️ 自检修正（原 design 误称「零公共改动文件」）**：M1、M2 **共享两个 IM 文件**——`IM/domain/models.py`（M1 改 `TokenUsage`、M2 改 `Message`，两个不同类）与 `IM/api/ws/event_types.py`（M1 改 `token_usage_to_dict`、M2 改 message payload builders，两个不同函数）。符号不重叠、均为 additive，worktree 并行后是 trivial additive merge。两条仍归并行组 A 并行；**若 orchestrator 要零冲突，让 M1 先合 unit 分支、M2 起 worktree 时 rebase 即可**（无逻辑依赖，仅文件级 additive 撞行）。

---

## 4. delta-spec（对长青契约层的增量）

> 用用户世界语言写，收尾由 orchestrator 并进 canonical `docs/specs/<包>/spec.md`。

### kernel（`docs/specs/kernel/spec.md`）

**Requirement: 缓存使用量随 token 用量一并对外**
- **Scenario：一轮含多次模型调用**
  - **WHEN** 一次助手回复完成
  - **THEN** 对外的 token 用量里，命中缓存的输入量与可用于计算命中率的总输入量，是这一轮所有模型调用的累计值

**Requirement: 每次模型调用的思考内容随其回合对外**
- **Scenario：一轮含多次模型调用、各自有思考**
  - **WHEN** 一轮助手回复完成、其中多次模型调用各自产生了思考
  - **THEN** 对外可观察到这一轮的多段思考，各段保留其相对于工具调用的先后次序
- **Scenario：某次模型调用无思考**
  - **WHEN** 某次模型调用没有产生思考内容
  - **THEN** 对外不为该次调用产出思考段

### gateway（`docs/specs/gateway/spec.md`）

**Requirement: 整轮多段思考按时序中继到 IM**
- **Scenario：含多段思考的一轮回复**
  - **WHEN** 一轮带多段思考的助手回复经 Gateway 中继（含只思考、不输出正文的回合）
  - **THEN** IM 收到的该轮消息包含全部思考段，且每段带可还原其与工具调用时序的次序信息

### im（`docs/specs/im/spec.md`）

**Requirement: token 气泡展示整轮缓存命中率**
- **Scenario：有命中**
  - **WHEN** 用户点开一条助手回复的 token 气泡详情
  - **THEN** 看到「缓存命中」一行，含命中量与百分比（整轮累计口径）
- **Scenario：无命中**
  - **WHEN** 本轮无任何缓存命中且用户点开详情
  - **THEN** 「缓存命中」行仍显示，值为 0 (0%)

**Requirement: 内部 IM 把思考与工具调用展示为过程时间线、外部不展示**
- **Scenario：内部 Web IM 一轮含多段思考与工具调用**
  - **WHEN** 一轮带多段思考、多次工具调用的助手回复在内部 Web IM 展示
  - **THEN** 气泡内有一个可折叠「过程」盘，把多段思考与工具调用按真实先后次序混排；每段思考可展开读完整内容、可收起；历史回看仍可展开
- **Scenario：内部 Web IM 无思考**
  - **WHEN** 助手回复本轮无任何思考
  - **THEN** 过程盘里不出现思考行（无思考不留空壳）
- **Scenario：外部 channel**
  - **WHEN** 同一条回复送达外部接入的 IM
  - **THEN** 只显示正文、不含任何思考

### cli — no spec delta

CLI 经 `agent.sdk` 消费同一批事件，但本 unit 新增的 reasoning / cache 字段对 CLI 是「忽略未知字段」——CLI 对外行为不变，故不产 cli delta-spec（仅需 R3 的回归测确认无破坏）。

> 落盘文件：`specs/kernel/spec.md`、`specs/gateway/spec.md`、`specs/im/spec.md`（本节内容的迷你 canonical 形式，供收尾软对账）。

---

## 4.5 Runbook for Reviewer

本 unit 改了内核事件 / Gateway 中继 / IM 持久化 / 前端渲染，**reviewer 必须端到端真栈验**（改了客户端面，须真驱动 Web IM）。涉及三个常驻服务，按 AGENTS.md「运行时服务并行启动」起：

- **IM**（uvicorn）：
  - 启：`IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing" PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 8011`（worktree 走 ephemeral 高位口）
  - 健康：`curl -s http://127.0.0.1:8011/im/v1/health`（或前端 `http://127.0.0.1:8011/` 能登录）
  - 停：kill 对应 pid
- **Gateway**（个人助手 Node）：
  - 启：`PYTHONPATH=src python -m personal_assistant.main --config <worktree>/.gateway-config.yaml --im-service-url http://127.0.0.1:<IM_PORT> --foreground --auto-bind`
  - 健康：Gateway 日志出现 agent 绑定 + IM 在线；Web IM 里 agent 节点显示 online
  - 停：`stop_pidfile .gateway.pid`（--foreground 范式）
- **前端**（Vite，仅需看 UI 时）：`cd src/IM/frontend && npm run dev`（或用已构建 dist）

**驱动方式**：登录测试账号（nano/nano1234），与一个**带 thinking 的模型**（如 K2.6）的 agent 对话，发一条会触发多次工具调用的请求；
- M1 验收：点开助手回复 token 气泡详情，看「缓存命中 X (Y%)」行（长对话验非 0%、短新对话验 0% 空态）。命中数据真实性可对 `~/Repos/LLM_PROXY/logs/<session>/` 的上游 usage 核对。
- M2 验收：看气泡内「过程」盘按时序混排「思考①→工具…→思考②→…」，逐段展开/收起，刷新页面历史仍可展开；换不带思考的回合确认无 💭 行。

> 一键起停可用 `./scripts/e2e-up.sh` / `e2e-down.sh`（已打包端口分配 / config 隔离 / auto-bind）。

## 5. 风险与回滚

- **R1（spec 场景 B 需同步，需用户知情）**：调研后 thinking 的真实形态与 spec 场景 B 三处不符，已据 §1 调整为「过程时间线」：①「正文上方一个思考块」→ 收进气泡内「过程」盘、与工具混排；②「逐字实时滚动」→ 整段到达（事件管线无 token 流式）；③隐含「一段思考」→ 整轮多段（一个气泡=多回合）。delta-spec（§4）已按调整后行为写。**`spec.md` 场景 B 文字仍是旧描述，需回 `change-spec-author` 同步**（门禁硬规则：design 不擅改用户场景）。若坚持逐字滚动，需另立 unit 给整个 hub 建 token 级流式。
- **R2（口径正确性）**：命中率口径正确性靠 `_accumulate_usage` + `_parse_*_usage` 单测固化（两家 provider 各一组），避免再次出现 qwen 式分母错。golden/快照若覆盖 TokenUsage 序列化，新增字段可能触发 golden 漂移——M1 需同步更新 golden。
- **R3（内核改动面）**：M2 触及内核 `loop.py` / `realtime_stream.py`（两个产品共享）。改动是「在事件 payload 增加可选 reasoning 字段」，CLI 消费者忽略未知字段即可，不破坏 CLI；但需跑 CLI 侧 contract/单测确认无回归。
- **R4（gateway 不再丢空正文回合）**：决策 4 改了 `main.py:3382-3384` 的丢弃逻辑——空正文**且无 reasoning** 的回合仍要丢（避免空气泡），只放行「空正文但有 reasoning」的回合作为过程项。必须用真栈核对：不冒出空正文气泡、过程项序号与工具时序一致。这条只有 live 真栈能暴露（参考工具展示链 false-fix 教训）。
- **回滚**：两条切片独立，任一可单独回滚。字段均带默认值（缓存 0 / reasoning None），回滚后旧前端忽略新字段、旧数据读新代码走默认值，无数据迁移风险（messages 表加列是加法变更，回滚保留空列即可）。
- **遗留修正**：`spec.md` 的「Related: feat-438」为误标（feat-438 实为 IM 群聊设置），M1/M2 收尾时一并改正。

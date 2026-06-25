# bugfix-433: 打通用户图片输入端到端送达 + 跨轮持久化 — 技术方案

> 对齐: incident.md v2（grounding 修订后）
> Unit branch: `unit/bugfix-433` (will be created by orchestrator)

## Changelog

## 现状分析

调研围绕「用户图片从 IM 输入 → 送达 LLM → 落盘 → 跨轮回放」整条链路，三处断点均逐处核实源码。

### 涉及范围

| 文件 | 当前职责 | 本 unit 要改的点 |
|---|---|---|
| `src/agent/core/agent/state.py` | `parse_input_parts`/`render_user_text`：解析 image part、渲染纯文本 | `render_user_text` 把 image 丢成 `[image:placeholder]`（断点1）；需保留图片块供下游构造 |
| `src/agent/core/agent/loop.py:230` | `_execute_loop` 调 `build_chat_messages(history, user_text)` | 只传 `user_text`，当前轮图片无通道（断点1）；需把当前 user 的结构化 parts 透传 |
| `src/agent/core/agent/prompting.py:48` | `build_chat_messages`：history+当前 user → `LLMMessage` | 当前 user 与历史都只产 `content:str`；需在有图时产 `content:list[dict]` |
| `src/agent/core/types.py:19` | `Message`（仅 `content:str`） | 增结构化 `parts` 字段承载图片（断点2） |
| `src/agent/core/agent/runtime.py:518,2121` | 构造 user `Message`、`_message_to_entry` 落盘 | user_msg 落 parts；`_message_to_entry` 写 `entry.parts` |
| `src/agent/core/session/jsonl_store.py:754` | `_to_message`：entry → `Message`（只读 content） | 读回 `entry.parts` 还原 `Message.parts`（断点2，消除悬空双轨） |
| `src/agent/platform/llm/providers/anthropic/mapper.py:147` | user 分支硬编码 `[{type:text}]` | 支持 `content:list` 的 image 块（断点3，复用 `_to_anthropic_image_part`） |
| `src/agent/platform/llm/providers/openai_compat/mapper.py:104` | user 分支原样透传 content | 支持 image 块 → `{type:image_url,image_url:{url}}` |
| `src/personal_assistant/gateway/inbound_pipeline.py:276` | attachment → `{type:image, image_url: <IM HTTP URL>}` | 入站把 IM HTTP URL 下载转 base64 data URL（决策1） |

### 既有约束

- **依赖方向**：`core` 不做 IO（持久化经 `platform/persistence`）；`platform → core`；产品（gateway）只 import `agent.sdk`。→ 图片下载（IO）不能放 core，落在 gateway 入站边界。
- **`LLMMessage.content` 已是 `str | list[dict[str,Any]]`**（`src/agent/core/llm/interfaces.py`）——结构化内容无需改类型签名，顺势使用。
- **纯文本逐字节不变**：现有文本 session 的 JSONL 落盘与重建结果不得因引入结构化内容而漂移（不变量1）。
- **JSONL entry 已写 `parts`**（`manager.py:193`），只是回放 `_to_message` 不读——双轨悬空的物理证据，修复即「让回放消费它」。

### 可复用能力

- **`_to_anthropic_image_part`**（`anthropic/mapper.py:213-251`）：已能把 image part 转 Anthropic `image` 块，**已支持 `data:` base64 URL**；对 HTTP URL 返回 `None`。→ 决策1 让图片在入站即成 data URL，此函数直接复用，mapper 改动最小。
- **`_normalize_tool_result_parts`**（anthropic）/`_normalize_tool_output_parts`（openai_compat）：tool-result image 块映射范式，user 分支照此扩展。
- **PA `httpx`**：`send_message.py`/`im_auth_client.py` 已用 httpx + 持有 IM token → 入站下载 attachment 复用。

### 相关历史

- **feat-330**（JSONL storage + `InputPart.image_url`）：引入图片解析但未闭合送达/持久化——本 bug 的源头 unit。
- **feat-340**（IM 原生 agent）：IM 图片上传 → attachment → 入站 image part 这条产品链路的来源。
- **PR #145 / bugfix-431**（`/stop` 改 append_message）：review 中暴露 parts 悬空双轨，触发本 unit 立项。

## 架构总览

修复把断裂的三处接上，并让图片以 **base64 data URL** 形态贯穿内核（自包含、不依赖 IM URL 存活）。

**改动落点（静态结构）**：

```mermaid
graph TB
  subgraph IM["IM 服务"]
    UP["attachment 上传<br/>(HTTP URL, image/*)"]
  end
  subgraph GW["personal_assistant (gateway)"]
    IB["inbound_pipeline<br/>★决策1: HTTP URL→base64 data URL"]
  end
  subgraph CORE["agent.core (纯逻辑, 不 IO)"]
    ST["state.render_user_text<br/>★断点1: 保留图片块"]
    PR["prompting.build_chat_messages<br/>★当前+历史 user → content:list"]
    MSG["types.Message<br/>★断点2: +parts 字段"]
    JS["jsonl_store._to_message<br/>★断点2: 读回 parts"]
  end
  subgraph PLAT["agent.platform (接环境)"]
    AM["anthropic/mapper user 分支<br/>★断点3: 复用 _to_anthropic_image_part"]
    OM["openai_compat/mapper user 分支<br/>★断点3: image_url 块"]
  end
  UP --> IB --> ST --> PR --> AM
  PR --> OM
  MSG -.持久化/回放.-> JS --> PR
```

**before/after 一句话**：before — 图片在 `render_user_text` 即丢成占位符，既不送达也不落盘；after — 图片在入站化为 data URL，随当前 user 消息构造成结构化 content 送达 provider，并随 `Message.parts` 落盘、回放时还原，跨轮可见。

## 关键决策

### 决策 1: 图片在 gateway 入站边界把 IM HTTP URL 下载转 base64 data URL，内核全程只见 data URL

**选了「入站转 base64」**（图片获取这件 IO 放在 gateway，core/mapper 保持纯净）。

- **理由**：IM 托管 URL 对真实 LLM provider 不可达（内网/localhost，proxy 转发给远端模型时取不到）；base64 data URL 自包含，落盘后不依赖 IM URL 存活（对齐 Claude Code 存 base64）；`_to_anthropic_image_part` 已支持 data URL，内核改动面最小；满足 core 不 IO 约束。
- **拒绝**：让 HTTP URL 一路存历史、由 mapper 送达时下载——违反 core 不 IO，URL 失效则历史不自包含，mapper 纯函数性被破坏。
- **风险**：base64 使 JSONL 历史膨胀（见风险段）；入站下载失败需降级（决策5）。

### 决策 2: 当前轮图片送达——`build_chat_messages` 接收当前 user 的结构化 parts，有图时产 `content:list`，无图保持 `content:str`

**选了「按需结构化」**（无图片的消息内容形态逐字节不变）。

- **理由**：`LLMMessage.content` 已支持 `list[dict]`，顺势用；无图走 `str` 分支保证纯文本 session 零扰动（不变量1）；当前轮图片从 `state` 透传到 `build_chat_messages`，补上断点1 缺的通道。
- **拒绝**：在 `render_user_text` 内塞图片——它产出 `str`，承载不了结构化块。
- **风险**：`build_chat_messages` 签名变化，所有调用点需同步（grep 收敛）。

### 决策 3: provider mapper 的 user 分支支持 `content:list` 的图片块，复用既有 image 转换

**选了「user 分支照 tool-result 范式扩展」**。

- **理由**：Anthropic 复用 `_to_anthropic_image_part`（data URL 直通）；OpenAI-compat 产 `{type:image_url,image_url:{url}}`（OpenAI 原生支持，data URL 亦可）；与既有 tool-result image 映射同构，行为可预期。
- **拒绝**：只改一个 provider——两个 provider 都在用，漏一个则该 provider 下图片仍不可见。
- **风险**：两个 mapper 各有格式差异，需各自单测覆盖。

### 决策 4: 持久化回放——`Message` 增 `parts` 字段承载结构化内容，`content:str` 降为纯文本投影，回放消费 parts（消除双轨）

**选了「Message 加 parts，回放读它」**（parts 从悬空字段升为图片的权威表示）。

- **理由**：`content:str` 假设贯穿 reasoning/tool/compaction/provider-error 太多处，全改成 blocks 数组（CC 模型）风险巨大；保留 `content:str`（纯文本投影，给检索/日志/纯文本 fallback）+ 新增 `parts`（结构化权威）是最小侵入。JSONL entry 已写 `parts`，本决策让 `_to_message` 读回它——双轨从此「写且读」、一致。
- **拒绝**：content 直接变 blocks 数组——侵入面与回归风险不可控；维持双轨写而不读——正是 bug 本身。
- **风险**：`Message` 是 frozen dataclass，加字段须全构造点默认 `parts=None`；回放重建顺序/parent 链不得受影响（不变量3）。

### 决策 5: 异常图片（下载失败/超大/损坏）对用户明确报错，不静默占位

**选了「显式告知用户图片未送达 + 原因 + 建议，不把假占位喂给模型」**（对齐 CC：`imageResizer.ts:438,586` 抛 `ImageResizeError` 带用户文案，绝不静默）。

- **理由**：静默塞占位符隐藏了「图片是否进了 LLM」，且会诱导 agent 对着不存在的图编造内容——这是产品级坏设计（用户 review 指出）。失败必须对用户透明：图片处理失败时，gateway 向用户回发明确提示（这张图未送达模型 + 原因 + 可操作建议），且**不把伪造的图片占位送进模型**。
- **拒绝**：① 静默降级为 `[图片无法加载]` 文本块喂模型——隐藏错误、诱发编造；② 直接抛异常中断整轮——用户只看到崩溃，同样不知情。两者都不诚实。
- **实现指引（沿用既有「用户可见、模型不可见」通道）**：本仓已有该模式——`is_provider_error=True` 的合成 assistant 消息会持久化供 IM/CLI 显示，但 `build_chat_messages`（`prompting.py:62-66` `_is_provider_error` 过滤）在发模型前剔除它，**不进 LLM context**。注释自证「mirrors CC isSyntheticApiErrorMessage / normalizeMessagesForAPI」。这正是 CC 对图片失败文案的处理：`ImageResizeError` → `createAssistantAPIErrorMessage`（`isApiErrorMessage:true`）→ `normalizeMessagesForAPI` 过滤不发 API、仅 UI 显示。决策5 的失败提示**复用这条 `is_provider_error` 通道**：用户在 IM 看到「这张图未送达模型 + 原因 + 建议」，模型上下文里既无该图也无该错误文案（不喂假占位、不污染上下文）。
- **风险**：超大图阈值取值留 worker（参照 provider 限制，不在 spec 锁定）。失败发生在入站 base64 转换（决策1）或 mapper 送达前的校验处，须把失败信号经 `is_provider_error` 合成消息传回用户，而非在 core 静默吞掉。

## 接口与数据流

**主流程时序（用户发图 → 当前轮送达 → 落盘 → 下一轮回放）**：

```mermaid
sequenceDiagram
  participant U as 用户(IM)
  participant GW as inbound_pipeline
  participant K as Kernel.submit
  participant RT as runtime/_execute_loop
  participant BCM as build_chat_messages
  participant MAP as provider mapper
  participant LLM as provider

  U->>GW: 图片(HTTP URL)+文字
  GW->>GW: 决策1 下载→base64 data URL
  GW->>K: submit(parts=[text, image(data URL)])
  K->>RT: parse_input_parts → InputPart(image_url=data URL)
  Note over RT: 决策2 当前 user 结构化 parts 透传
  RT->>RT: user_msg.parts = [text, image]  (决策4 落盘 entry.parts)
  RT->>BCM: build_chat_messages(history, 当前 user parts)
  BCM->>MAP: LLMMessage(content=[text块, image块])
  MAP->>LLM: 决策3 user 分支 → image block 送达
  Note over RT: ——下一轮——
  RT->>BCM: 历史含上轮 user_msg(parts 有 image)
  BCM->>MAP: 历史 user → content:list(还原 image 块)
  MAP->>LLM: 跨轮图片可见
```

**关键接口形态（只写"长什么样、谁调谁"，代码留 worker）**：

- `build_chat_messages(*, history_messages, user_text, user_parts=None)` — 新增 `user_parts`（当前轮结构化 parts）。`user_parts` 含 image → 当前 user `LLMMessage.content` 为 list；否则 `content=user_text`（保持现状）。历史侧：遍历 `Message`，`m.parts` 含 image → list content，否则 `m.content`。
- `Message`（types.py）增 `parts: tuple[Mapping[str,Any], ...] | None = None`。`_message_to_entry` 写 `entry["parts"]`（已有该键）；`_to_message` 读 `entry.get("parts")` → `Message.parts`。
- image 块统一形态：`{"type":"image","image_url":"data:<mime>;base64,<...>"}`（内核内规范，mapper 据此映射）。
- mapper user 分支：`content` 为 list → 逐块（text→text block，image→provider 各自 image 形态）；为 str → 维持现状。

## 契约层增量 (delta-spec)

- kernel: `specs/kernel/spec.md` — 经 `agent.sdk`（submit/append_message）携带 image part 的消息，图片送达模型且随会话历史保留、后续 turn 仍可见。
- gateway: `specs/gateway/spec.md` — 用户经 IM 发送图片，agent 当轮即可看到、后续轮追问仍可见。
- im: no spec delta（IM 上传/attachment 行为不变）。
- cli: no spec delta（无图片输入路径）。

## 风险与回退

- **JSONL 历史膨胀**：base64 图片进 transcript 使会话文件显著增大（一张图数百 KB）。对齐 CC 现状，本 unit 接受；缓解：决策5 超大图对用户明确报错（不送达）+ 未来可优化为 side-store 引用（非本 unit）。回退：若膨胀不可接受，回退到「历史只存占位、仅当前轮送达」的半程方案（仍优于现状）。
- **入站下载依赖 IM 可达 + token**：gateway 下载 attachment 需 IM 在线且 token 有效。缓解：决策5 失败时向用户明确报错（图片未送达模型），不静默、不中断、不喂假占位给模型。
- **纯文本 session 漂移（不变量1）**：`Message.parts` 默认 None、`build_chat_messages` 无图走原 str 分支——无图路径必须与改前逐字节一致，由 worker 用既有持久化/回放测试 + golden 守。
- **两 provider 格式分叉**：Anthropic（base64 source）与 OpenAI（image_url）格式不同，各自单测覆盖；data URL 对两者都适用降低分叉风险。
- **回退总策略**：改动集中在「图片有无」的分支上，纯文本路径不变，单 unit 可整体 revert 回退到现状（图片不可见，但无其它回归）。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM | `stop_pidfile .im.pid`（worktree e2e）/ 主仓用户自管 | `IM_JWT_SECRET=<unit随机串> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port $IM_PORT > .im.log 2>&1 & echo $! > .im.pid` | `curl -s 127.0.0.1:$IM_PORT/ ` 返回前端；登录 nano/nano1234 |
| Gateway | `stop_pidfile .gateway.pid`（--foreground 起的） | `PYTHONPATH=src python -m personal_assistant.main --config "$WT_CFG" --im-service-url http://127.0.0.1:$IM_PORT --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 无 error；IM 里 agent 在线 |

> reviewer 旅程：登录 IM → 给 agent 发一张图 + 问题（验当前轮可见）→ 同会话下一轮只发文字追问该图（验跨轮）→ 另发纯文本多轮（验无回归）→ 发一张异常图（验不崩）。

## Milestones

单 M1：端到端垂直切片（用户图片当前轮 + 跨轮可见）。链路虽跨 core/platform/gateway，但是一条不可横切的垂直通路（横切成 core/mapper/gateway 会让每段都不可独立交付、且互相阻塞，违反 §4.3）。估算 ~400-600 行，单 worker 窗口内可完成；内部用 roadpoint R1（当前轮送达）/R2（持久化回放）/R3（gateway base64 边界 + e2e）推进。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-433-M1 | image-end-to-end | — | A | `src/agent/core/agent/{state,prompting,loop,runtime}.py`、`src/agent/core/types.py`、`src/agent/core/session/jsonl_store.py`、`src/agent/platform/llm/providers/{anthropic,openai_compat}/mapper.py`、`src/personal_assistant/gateway/inbound_pipeline.py`、相关 tests | `[reviewer]` 用户发图当轮 agent 即可作答（Req-当前轮可见/Scenario-单轮发图即问、单轮发多张图）<br>`[reviewer]` 上轮发图、下轮只发文字仍可追问（Req-跨轮保留/Scenario-上一轮发图下一轮追问）<br>`[reviewer]` 纯文本多轮对话与修复前无可观察差异（Req-纯文本不受影响）<br>`[reviewer]` 异常图片：用户收到「未送达模型 + 原因 + 建议」明确提示、对话不崩、agent 不对该图编造（Req-异常图片明确告知用户）<br>`[worker]` 新增端到端往返单测「发图→送达 provider mapper→落盘 entry.parts→重建 Message.parts→下一轮含 image 块」全绿<br>`[worker]` Anthropic / OpenAI-compat mapper user 分支 image 块映射各有单测<br>`[worker]` 纯文本 session 持久化/回放既有测试 + golden 不回归<br>`[worker]` `pytest -m "not e2e"` 全绿、ruff check + format clean |

依赖图：单 milestone，无需。

# Design 评审：feat-439

**结论**：Issues Found（2 CRITICAL，均在 M1）

> 评审者：change-design-reviewer（独立视角，只读不改）。
> 范围：design.md + spec.md + specs/{kernel,gateway,im}/spec.md。
> 核实方法：现状断言全部从生产调用路径正向追源码核对（非逐行核 design 引用）。

---

## 核实台账（逐条核过的承重原子；结论附证据）

### M1 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| TokenUsage 当前三字段 prompt/completion/total | 读 types.py | ✓ `agent/core/types.py:11-16` |
| provider 解析层「只取 input/output 就丢缓存」 | 追两家 `_parse_*_usage` | ✗ **半错**：Anthropic 现状已读 `cache_read_input_tokens`/`cache_creation_input_tokens` 并折进 prompt（`anthropic/client.py:317-326`）；仅 OpenAI 确实丢 `cached_tokens`（`openai_compat/client.py:297-313`，未读 `prompt_tokens_details`） |
| 「prompt_tokens 语义=最后请求快照、纯 input、绝不能改」（决策 1/3 硬约束） | 读 anthropic 现状 prompt_tokens 构成 | ✗ Anthropic 现状 `prompt_tokens = input + cache_creation + cache_read`（`client.py:326`）——已含缓存，**不是纯 input**。决策 2 的 After 却把它改回纯 `input_tokens` → 见 C1 |
| `_accumulate_usage`：prompt 取最新快照、completion 累加 | 读 loop.py | ✓ `loop.py:1020-1050`，与 design Before 一致 |
| 透传链含 `local_store.py:_build_token_usage/_encode/_decode_token_usage` | grep PA 包 | ✗ **不存在**：`local_store.py` 无任何 token usage 处理（grep 仅命中 node/auth token）。真实 gateway 透传点是 `personal_assistant/main.py:3596-3622`，直接从 turn_end `usage` 事件构建 `token_usage_payload`，**只读 prompt/completion** → 见 C2 |
| 内核 turn_end → 事件 usage 透传 | 读 realtime_stream on_turn_end | ✓ `realtime_stream.py:172-174` `payload["usage"]=dict(usage)` 整体复制，cache 字段会自动随上游 dict 流过（此跳透明，非缺口） |
| IM domain TokenUsage / event_types token_usage_to_dict 存在 | grep IM | ✓ `IM/domain/models.py:227`、`IM/api/ws/event_types.py:73` |
| 前端 token-chip.tsx 存在且渲染详情 | 查文件 | ✓ `IM/frontend/src/features/chat/v2/components/token-chip.tsx` |

### M2 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 一气泡=一 turn=多 roundtrip，每回合新建 assistant Message 带各自 reasoning、共享 group_id | 读 loop.py 主循环 | ✓ `loop.py:361-411`：每 `llm_msg` 建 Message（`content or ""`）、`reasoning_content=llm_msg.reasoning_content`（402）、`group_id=turn_assistant_group_id`（398）；终态 usage-only 消息 `continue` 不建 Message（380-383） |
| message_end hook 每回合 fire 但不带 reasoning | 读 dispatch | ✓ `loop.py:408`（每 assistant_msg 调）+ `626-639`（payload 仅 content/role，无 reasoning） |
| realtime_stream assistant_message 不带 reasoning；事件词表无 token delta | 读 realtime_stream | ✓ `realtime_stream.py:50-60`（payload 无 reasoning）；词表仅 assistant_message/tool_start/tool_end/turn_end |
| thinking 累积 turn_reasoning 最终落 `Message.reasoning_content`（接收/持久化已具备，不需动） | 读 client 流解析 | ✓ `anthropic/client.py:122-134` turn_reasoning 注释 + `loop.py:402` 落字段 |
| gateway 空正文回合 `return None` 丢弃 | 读 observer | ✓ `personal_assistant/main.py:3382-3383` `content=...strip(); if not content: return None` |
| observer 逐事件顺序处理同 run（赋单调序号的事实基础） | 读 observer 文档/分支 | ✓ `main.py:3275-3282` 单 observer 顺序翻译 assistant_message/tool_start/tool_end，可按到达序赋号 |

### 决策

| 决策 | 四问 | 结论 |
|---|---|---|
| 决策 1：两字段 cache_read + cache_total_input 贯穿 | 拍死/自洽/有据 | ⚠ 字段必要性成立（整轮累加需独立载体，prompt_tokens 是快照无法重建求和），但**理由表述错**：现状 prompt_tokens 逐请求即等于 cache_total_input（两家都已含缓存），真实差异只在「快照 vs 求和」聚合，不在「prompt_tokens 不含缓存」。理由 muddled 牵出 C1 |
| 决策 2：provider 层归一缓存口径 | 自洽？ | ✗ Anthropic After `prompt_tokens=input_tokens` 与现状（含缓存）冲突，且与决策 1/3「prompt_tokens 不可改」**自相矛盾** → C1 |
| 决策 3：`_accumulate_usage` 缓存字段累加 | 自洽/有据 | ✓ 沿用现有 completion-累加/prompt-快照规矩，缓存归入累加类，Q1=B 整轮口径自洽 |
| 决策 4：thinking 作过程项按时序流入气泡、渲染过程时间线 | 完整/数据流闭合 | ✓ 四处断链（client emit→message_end→gateway 不丢→IM/前端承载）逐处对得上真实代码；多段+时序数据模型贴合事实 A；不造 token 流式贴合事实 B；内外区分落渲染端 |

### spec 约束

| 约束 | 核 | 结论 |
|---|---|---|
| Q1=B 整轮累计口径 | design 落点 | ✓ 决策 3 累加 |
| Q2 多段思考按时序 | design 落点 | ✓ 决策 4 + delta |
| 场景 A 缓存命中（含 0% 空态） | 覆盖 | ✓ 决策 1-3 + im delta |
| 场景 B 思考过程展示 | 覆盖/不冲突 | ⚠ design 偏离 spec 原文三处（「正文上方」「逐字实时滚动」「一段思考」「范围: 流式实时显示」），**已在 R1 显式 flag 需回 change-spec-author 同步**；属已披露门禁项，非隐藏冲突 → 见 Note |
| 非目标「不改 thinking 接收与持久化」 | 不越界 | ✓ 决策 4 #1 明确接收/持久化不动，只暴露到事件 |
| 外部 channel 不暴露 thinking | 覆盖 | ✓ im delta「外部 channel」+ 渲染端区分 |

### delta-spec

| 条目 | 锚 canonical / 用法 / THEN 可观察 | 结论 |
|---|---|---|
| kernel ADDED（缓存用量、每回合思考对外） | canonical 有无被改既有项 | ✓ canonical kernel 无对应既有 requirement，真·平行新增，ADDED 正确；THEN「对外可观察」=sdk 消费者视角，无内部符号断言 |
| gateway ADDED（多段思考按时序中继） | 同上 | ✓ ADDED 正确；THEN 写「IM 收到的消息含全部思考段」=中继可观察结果，红线干净 |
| im ADDED（缓存命中率行、过程时间线） | 同上 | ✓ canonical im 无 token 气泡内容契约可被顶替，ADDED 合理；THEN 全为用户可观察 |
| cli no spec delta | 显式注明？ | ✓ §4 明确「忽略未知字段、对外行为不变」 |

### milestone

| 原子 | 核 | 结论 |
|---|---|---|
| M1 cache-hit-rate | 垂直 vs 横切 | ✓ 后端→前端端到端垂直切片，独立可上线 |
| M2 thinking-process-timeline | 垂直 vs 横切 | ✓ 同上 |
| M1/M2 并行组 A 范围无交集 | 比对文件列表 | ⚠ 共享 `IM/domain/models.py`、`IM/api/ws/event_types.py`（不同类/函数、additive）。design 已自检披露并给缓解（M1 先合、M2 rebase）→ W1 |
| 退出标准两轨 [reviewer]/[worker] | 齐/可验 | ✓ 两条均含可观察旅程 + 实现层单测，引 delta Scenario |

---

## 架构进攻（四角度逐个走）

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 缓存口径归一放 provider 层、累加放 core loop | ✓ 走完无存活发现：归一收敛在「贴上游差异」的 provider 层、累加在 core，方向 `platform→core` 不破依赖；M2 helper 无新跨层 |
| 该不该存在 | 新增 `cache_total_input_tokens` 字段（逐请求值=现状 prompt_tokens） | ✓ 删除测试不通过删除：整轮命中率分母需「逐请求 input 求和」，而 prompt_tokens 被快照（决策 3），无法从快照重建求和——字段承载不同聚合，非冗余。但**逐请求同值**这一事实正是 design 决策 1 理由表述错的来源（牵出 C1） |
| 深还是浅 | 决策 4 复用 `chat-tool-calls` 折叠盘升级为「过程」盘 | ✓ 深复用既有折叠交互，不另造一套；无浅封装/重造轮子 |
| 治本还是补丁 | M2 gateway 不再丢「空正文+有 reasoning」回合 | ✓ 治本：从「事件被源头丢弃」正面解决，非渲染端打补丁。反观 M1 决策 2 anthropic 改 prompt_tokens=纯 input 属误改（见 C1），但那是错误不是补丁 |

---

## Issues（按 CRITICAL > WARNING 排序）

- **[CRITICAL] [决策 2 / 现状断言 prompt_tokens]**：Anthropic 现状 `prompt_tokens = input + cache_creation + cache_read`（`anthropic/client.py:326`，已含缓存，驱动「已用上下文」context_used）。决策 2 的 After 把它改为 `prompt_tokens=input_tokens`（纯 input），且注释自称「语义不变」。这会让长对话里 context_used 从含缓存的真实上下文（如 190k）塌缩到非缓存增量（可能几 k），**直接回归 bugfix-390/feat-414 立的「已用上下文」气泡**，且与决策 1/3 自己写的「prompt_tokens 不可改」**自相矛盾**。worker 照抄 After 即引入回归；遵守约束又得弃 After 代码——无论哪条都被迫猜。
  - 修：After 保持 `prompt_tokens = input_tokens + cache_creation + cache_read` **不变**，只追加 `cache_read_tokens=cache_read`、`cache_total_input_tokens=input_tokens + cache_read + cache_creation`。并改正现状分析对 Anthropic「丢缓存/纯快照」的断言（OpenAI 才真丢 cached）。

- **[CRITICAL] [现状断言透传链 / M1 范围]**：design §1.9 与 §3 M1 范围把 gateway 透传点写成 `personal_assistant/config/local_store.py:_build_token_usage/_encode/_decode_token_usage` ——**这些函数/逻辑在 local_store 中不存在**（该文件无任何 token usage 处理）。真实透传点是 `personal_assistant/main.py:3596-3622`：它从 turn_end `usage` 事件**显式只读 prompt/completion** 重建 `token_usage_payload`，**无条件丢弃任何 cache 字段**。而 main.py **不在 M1 范围内**。后果：worker 按范围改完 TokenUsage + provider + IM + 前端、单测全绿，但 gateway 这一跳把 cache 字段拦掉，IM/前端永远拿不到 → 命中率恒显示 `0 (0%)`，线上失效。这是典型「叶子全对、路径错」陷阱。
  - 修：M1 范围去掉 local_store 那项，加入 `personal_assistant/main.py:3596-3622 token_usage_payload`（补读 `cache_read_tokens`/`cache_total_input_tokens` 并带进 payload）；同步核 IM 侧从 node delta 落库到 `token_usage_to_dict` 全链确无第二个「只读 prompt/completion」的拦截点。

- **[WARNING] [并行组 A 范围交集]**：M1、M2 共享 `IM/domain/models.py`、`IM/api/ws/event_types.py`（改不同类/函数、均 additive）。两 worker 在并行 worktree 同改同文件，合并必撞（即便 trivial）。design 已自检披露并给「M1 先合 unit 分支、M2 起 worktree 时 rebase」的缓解。不改不会让方案站不住，但 orchestrator 须知情：要么按 design 建议串行化 M1→M2，要么接受一次 additive 冲突手解。**并行组「无交集」的字面承诺不成立**，按披露的缓解走即可。

## Note（门禁项，需用户/orchestrator 知情）

- **[场景 B 偏离 / R1]**：design 已正确识别 spec 场景 B 三处措辞（「正文上方一个思考块」「逐字实时滚动」「一段思考」+ 范围段「流式实时显示」）与调研后真实形态不符，改为「过程时间线」，并显式标注 **`spec.md` 场景 B 需回 `change-spec-author` 同步**（design 不擅改用户场景）。这是该有的处理，非缺陷；但意味着进 orchestrator 前应先完成 spec 同步这道门禁，否则 spec 与 delta-spec 长期不一致。评审不阻断，提示按 R1 闭环。

## Recommendations（不阻断）

- **决策 1 理由精确化**：把「分母不能复用 prompt_tokens（因其语义不含缓存/是快照）」改写为真实理由——「prompt_tokens 按整轮取最后快照，命中率分母要整轮所有请求 input 求和，快照无法重建求和，故需独立累加字段」。逐请求两者同值这一事实若写清，可避免 C1 那类误改重演。
- **mapper.py 重复解析**：两家 provider 各有第二份 `_parse_*_usage`（`*/mapper.py`，服务非流式 `map_generate_response`）。生产 `generate()` 仅走流式（client.py 的 `_stream_response`），`from_provider_response` 无生产调用方，故 design 仅改 client.py 对生产正确；但 mapper 版逻辑相同、可能被单测/golden 覆盖，建议同步加 cache 字段或在 design 注明「只改 client.py 的依据（mapper 非生产路径）」，避免两份口径漂移。

---

### 给作者的话

主体设计扎实：决策 4 的「过程时间线」对事实 A/B 的推导、四处断链定位、垂直切片拆分、delta-spec 用法都经得起核。**但 M1 有两处会让 worker 实质走偏的 CRITICAL，都源于 M1 现状分析没从生产路径正向追源码**：

1. Anthropic 现状 prompt_tokens 已含缓存，决策 2 的 After 会误改它、回归 context_used（且自相矛盾）；
2. M1 透传链命名的 `local_store._build_token_usage` 不存在，真实拦截点 `main.py` token_usage_payload 被排除在范围外，会让 cache 字段到不了前端。

建议回 `change-design-author` 修这两处（重写决策 2 的 anthropic Before/After + 改正现状分析 prompt_tokens 构成；把 M1 范围的 local_store 换成 `personal_assistant/main.py:3596-3622`），并按 W1 与 orchestrator 对齐 M1/M2 串行化、按 Note 闭环 spec 场景 B 同步。改完即可进 orchestrator。

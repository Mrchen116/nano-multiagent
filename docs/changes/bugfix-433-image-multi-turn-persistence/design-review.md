# Design 评审:bugfix-433-image-multi-turn-persistence

**结论**:Issues Found

独立复核了 design.md + incident.md + kernel/gateway 两份 delta-spec,逐条追源码核实。方案主干（三处断点定位、base64 入站归属、parts 升为权威表示、单 M1 垂直切片）扎实且架构归属正确;但有 **2 个 CRITICAL** 会让 worker 按字面实施时漏掉一条 spec 明列的场景、或重新引入上下文污染——均源于 design 的数据流模型把「用户输入 → 模型」当成一条线性通路,而生产路径上存在一个 design 完全未提及的中途分叉(M246 多部件展开)。

**核实台账**(逐条核过的承重原子;结论附证据):

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状:`render_user_text` 把 image 丢成 `[image:placeholder]` | 读 state.py | ✓ 成立(`state.py:101-102`,image_url 当场弃) |
| 现状:loop 调 `build_chat_messages` 只传 user_text | 读 loop.py | ✓ 成立(`loop.py:231-234`,无 parts 通道) |
| 现状:`build_chat_messages` 当前 user 只产 `content:str` | 读 prompting.py | ✓ 成立(`prompting.py:90` `content=user_text`) |
| 现状:`Message` 仅 `content:str` | 读 types.py | ✓ 成立(`types.py:26`,无 parts 字段) |
| 现状:runtime 构造 user_msg `content=user_text`、`_message_to_entry` 落盘 | 从 submit 正向追 | ✓ 成立(`runtime.py:523-528` / `2157`) |
| 现状:`_to_message` 只读 content | 读 jsonl_store | ✓ 成立(`jsonl_store.py:758`,不读 parts) |
| 现状:anthropic mapper user 分支硬编码 text | 读 mapper | ✓ 成立(`anthropic/mapper.py:147-151`) |
| 现状:openai_compat user 分支原样透传 | 读 mapper | ✓ 成立(`openai_compat/mapper.py:104-105`) |
| 现状:inbound 把 attachment 转 `{image,image_url:HTTP URL}` | 读 inbound_pipeline | ✓ 成立(`inbound_pipeline.py:281-291`;行号 276→实际 281,无碍) |
| 既有约束:`LLMMessage.content` 已 `str\|list[dict]` | 读 interfaces.py | ✓ 成立(`interfaces.py:24`) |
| 可复用:`_to_anthropic_image_part` 支持 data URL | 读 mapper | ✓ 成立(`anthropic/mapper.py:216-251`,HTTP URL 返回 None) |
| 既有约束:JSONL entry「已写 parts」 | 追两条写路径 | ⚠ **半成立**:仅 `append_turn_message` 写 parts(`manager.py:192-193`);submit 用的 `_message_to_entry` **不写 parts**。design line 162「`_message_to_entry` 写 entry["parts"]（已有该键）」措辞错——该键在 `_message_to_entry` 现状不存在 |
| **(漏列现状)** M246 多部件展开在 loop 前裂解 input_parts | 从 submit 正向追到 loop | ✗ **致命漏列**:`runtime.py:538-558`,`len(input_parts)>1` 时把除最后一个外的所有 part 经 `render_user_text` 渲成占位文本塞进 loop_history,只有最后一个 part 作为 `effective_input_parts` 进 loop。design 的 §涉及范围 与时序图完全未提此分叉 |
| 决策1:入站转 base64,core/mapper 纯净 | 核落点 + 依赖方向 | ✓ 拍死、落点正确(`inbound_pipeline.py`)、满足 core 不 IO |
| 决策2:`build_chat_messages` 收 user_parts,有图产 list | 核数据流闭合 | ✗ 数据流**不闭合**:loop 拿到的是 M246 裂解后的 `effective_input_parts`(仅末 part),多图时前面的图已是占位文本。详见 CRITICAL-1 |
| 决策3:两 provider user 分支支持 image 块 | 核覆盖 + 复用 | ✓ 拍死、两 provider 全覆盖、复用既有 image 转换 |
| 决策4:Message 加 parts、回放消费、content 降为投影 | 核落点全 | ✓ 覆盖 types/`_message_to_entry`/`_to_message`,消除双轨;须注意 `_message_to_entry` 是**新增** parts 写(非现状已有) |
| 决策5:异常图本轮停下、回发 is_provider_error 合成消息 | 追 gateway 持久化通道 | ✗ 数据流**不闭合**:gateway 唯一可达的 `append_message`→`append_turn_message` **不把 is_provider_error 写进 entry**(`manager.py:185-197` 白名单无此键),回放过滤拿不到该标记。详见 CRITICAL-2 |
| spec Req「当前轮可见/单轮发图即问」 | 找落点 | ✓ 决策1-3 覆盖(单图:inbound 把 image 排在末 part,经 M246 恰好作为 effective 存活) |
| spec Scenario「单轮发多张图」 | 找落点 | ✗ **未覆盖**:M246 把前面的图渲成占位,只末图送达。见 CRITICAL-1 |
| spec Req「跨轮保留/上轮发图下轮追问」 | 找落点 | ✓ 决策4 覆盖(parts 落盘 + `_to_message` 读回 + history 侧产 list) |
| spec Req「纯文本不受影响」 | 找落点 + 不变量 | ✓ parts 默认 None 走原 str 分支,golden 守(风险段 + 不变量1) |
| spec Req「异常图明确告知、不静默、不编造、不崩」 | 找落点 | ✓ 语义被决策5 覆盖,但实现机制有 CRITICAL-2 的闭合缺口 |
| 澄清 Q2:coding_cli 非目标 | 核是否越界 | ✓ 未触 coding_cli |
| 澄清 Q6:异常图不静默、对齐 CC 硬停 | 核决策5 对齐 | ✓ 决策5 与 Q6 用户拍板一致(本轮不调模型、明确报错) |
| 非目标(旧会话迁移/压缩选型/其它模态) | 核是否夹带 | ✓ 未夹带(压缩明列为可选增强,不锁) |
| delta kernel:ADDED「图片送达+保留」 | 锚 canonical/用法 | ✓ ADDED 正确(incident:97 证 kernel spec 从未定义图片,真平行新增,非 MODIFIED) |
| delta gateway:ADDED「IM 发图当轮+跨轮」 | 锚 canonical/用法/主语 | ✓ ADDED 正确,主语=用户,符合 gateway 消费者视角 |
| delta im/cli:no spec delta | 核理由 | ✓ IM 上传不变、CLI 无图片输入路径,显式注明 |
| Milestone:单 M1 端到端垂直切片 | 垂直 vs 横切 | ✓ 正确垂直切;明确论证不可横切成 core/mapper/gateway |
| Milestone 退出标准两轨 | 核 reviewer/worker 轨可验 | ✓ 两轨齐、引 spec Scenario、worker 轨可执行 |

**架构进攻**(四角度逐个走):

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 图片下载 IO 放 gateway 入站、core 只见 data URL | ✓ 走完无存活发现:归属正确,符合 `platform→core`、产品只 import sdk、core 不 IO 的硬规则;无反向依赖 |
| 该不该存在 | 新增 `Message.parts` 字段 / base64 内核内规范形态 | ✓ 走完无存活发现:parts 是消除「写而不读」双轨的必需权威表示(删除测试:删了就退回 bug 本身);data URL 自包含、对齐 CC,非假想抽象 |
| 深还是浅 | 复用 `_to_anthropic_image_part` / tool-result image 范式 | ✓ 走完无存活发现:复用既有同类能力,未重造轮子,封装非浅 |
| 治本还是补丁 | 决策5 「校验统一 gateway 入站、mapper 不校验」 | ⚠ 方向治本(失败前置拦截、mapper 保纯),但**落地机制是补丁**:借用 in-run 的 is_provider_error 通道却未核实该通道经 gateway append 路径不可达(见 CRITICAL-2)。若按字面实现,等于在共享持久化设施上叠了一个静默失效的特例——债会在「异常图后下一轮」才暴露 |

**Issues**(按 CRITICAL > WARNING 排序):

- **[CRITICAL] [现状分析 / 决策2 / spec Scenario 单轮发多张图]:M246 多部件展开未被纳入数据流模型,多图场景无法满足。**
  生产 submit 路径在进 loop 前有一道 design 完全未提的分叉:`runtime.py:538-558`,当 `len(input_parts)>1` 时,除最后一个 part 外的所有 part 经 `render_user_text` 被渲成 `[image:placeholder]` 文本、塞进 loop_history,只有最后一个 part 作为 `effective_input_parts` 进 loop。inbound 把图片统一排在 text 之后(`inbound_pipeline.py:278-291`),所以**单图**(parts=[text,image])恰好让 image 成为末 part 存活;但**多图**(parts=[text,img1,img2])下 img1 会被渲成占位文本——`spec Scenario「单轮发多张图」` 与 kernel/gateway delta 的「全部图片可见」据此**不可达**。
  不改→下游坏事:worker 按 §涉及范围(只列 runtime.py:518/2121,未列 538-558)+ 时序图实施,会把 `effective_input_parts` 直接 thread 给 `build_chat_messages`,单图 e2e 全绿、多图静默丢图;reviewer 走「单轮发多张图」旅程才发现,退回返工。
  建议:design 必须把 M246 展开纳入决策2 的数据流——要么让 M246 的 extra_messages 也携带结构化 parts(非占位文本),要么对含 image 的多部件输入绕过/改造 M246 文本裂解。请在 §现状分析补这条断言、在决策2 明确处理方式。

- **[CRITICAL] [决策5 / 接口与数据流]:失败提示「回发 is_provider_error 合成消息、回放被过滤」的数据流不闭合。**
  决策5 与「接口与数据流」段(line 118/165)指明失败提示「作为 `is_provider_error=True` 合成 assistant 消息回发……回放时被 `prompting._is_provider_error` 过滤、不进模型」。但 gateway 唯一可达的持久化入口 `kernel.append_message → service.append_message → manager.append_turn_message`,其 entry 写出白名单(`manager.py:185-197`)**不含 is_provider_error**——该标记在写盘时被静默丢弃。现状能写 is_provider_error 的只有 in-run 的 `_message_to_entry`(`runtime.py:2177`),而它只在模型运行内(ModelError 时)可达,正好是决策5「不 submit 模型」要避开的路径。
  不改→下游坏事:worker 按字面用 `append_message(metadata={"is_provider_error":True})`,标记落盘丢失,该失败文案**不会**被回放过滤,下一轮作为普通 assistant 消息污染 LLM 上下文(模型看到「这张图片太大了…」并可能据此误答)。「异常图后下一轮」才暴露,e2e 若不覆盖该序则漏网。
  建议:二选一并写进决策5——(a) 失败提示**仅 outbound 展示、不持久化**(因本轮未 submit,user 图片消息本就未落盘,历史天然干净,无需过滤,最简且自洽);或 (b) 显式把 `append_turn_message` 写路径扩成持久化 is_provider_error,并把 `manager.py`/`service.py` 纳入 §涉及范围。当前「复用既有通道」措辞不成立,须纠正。

- **[WARNING] [现状分析 line 31/162]:「JSONL entry 已写 parts(已有该键)」对 submit 路径是错的。**
  parts 仅 `append_turn_message` 写(`manager.py:193`);submit 用的 `_message_to_entry` 现状**不写 parts**。决策4 在 §涉及范围(line 20)正确把它列为要改点,但 line 162「(已有该键)」的措辞可能让 worker 误以为 `_message_to_entry` 无需动。
  不改→下游坏事:worker 漏改 `_message_to_entry` 的 parts 写出,submit 路径图片不落盘、跨轮丢失(跨轮场景挂)。把 line 162 措辞改为「`_message_to_entry` **新增** parts 写出(仅当 parts 非空,守纯文本 golden)」即可。

**Recommendations**(不阻断门禁,作者自行取舍):

- kernel delta-spec Scenario 的 THEN「发往模型的请求里包含对应的图片内容」略偏实现可观察(消费者是 sdk 调用方,「请求内容」非其直接可观察面)。可改为消费者可观察的措辞(如「该图片送达模型并在后续轮重建历史时仍作为图片内容可见」),与 gateway delta 的「agent 当轮基于图片作答」对齐。
- 决策5 的自动压缩明确标为 worker 增强项、核心契约是「无法送达→停下报错」——边界清晰,保留即可。

# Design 评审:bugfix-433-image-multi-turn-persistence（第 3 轮 · 复审定稿）

**结论**:Approved

三轮评审全部 CRITICAL/WARNING 已闭合,主干设计无架构层缺陷,可进 `change-orchestrator`。

## 闭环记录

**第 1 轮(2 CRITICAL + 1 WARNING)→ 已修:**
- CRITICAL-1（M246 多部件展开未纳入数据流,多图丢图）:§涉及范围补列 `runtime.py:538-558`;决策2 显式新增 M246 段,修法为「extra_message 的 image part 构造带 `Message.parts`,经 history 侧 `build_chat_messages` 还原」(与决策4 同一通道);时序图加注;kernel delta 新增「单条消息含多张图片时全部送达」;Milestone 退出标准加多图单测。✓
- CRITICAL-2（失败提示「is_provider_error 合成消息回放过滤」数据流不闭合——append 路径白名单静默丢标记）:决策5 改为「仅 outbound 展示、不持久化进 kernel 历史」,并写明根因(`manager.py:185-197` 不含该键)。✓
- WARNING（line 162「已有该键」误述）:改为「`_message_to_entry` **新增** parts 写出(现状不写)」。✓

**第 2 轮(1 CRITICAL + 1 WARNING,均为 CRITICAL-2 修订未传播干净)→ 已修:**
- CRITICAL（kernel delta Scenario「图片无法获取时显式报失败」与决策5 打架——内核不再产失败信号)：该 Scenario 已从 `specs/kernel/spec.md` **撤除**,替换为说明性 note(line 32),明确「失败契约属 gateway 入站职责……内核不产出失败信号」,并指向 gateway delta 的对应 Scenario。✓
- WARNING（决策5 line 129 风险 bullet 仍引用旧 is_provider_error 机制,自相矛盾)：line 129 已改为「经 outbound 直接回发用户、不写 kernel 历史,core 全程不接触失败图(……不再用 is_provider_error 持久化)」,与 line 119 一致。✓

**第 3 轮复核(本轮)：**
- 全仓搜 `is_provider_error`:design.md 仅剩 line 119/129 两处,均为「解释为何**不用**它」的语境,无任何「使用它」的残留措辞。✓
- kernel delta 失败 Scenario 确已撤、note 到位;失败契约单一归属于 gateway delta。✓

## 最终核实台账(承重原子,全 ✓)

| 维度 | 结论 + 证据 |
|---|---|
| 现状断言（断点1/2/3、双轨、M246） | ✓ 逐条追源码核实(`state.py:101`/`loop.py:231`/`prompting.py:90`/`types.py:26`/`jsonl_store.py:758`/两 mapper user 分支/`inbound_pipeline.py:281`/`runtime.py:538-558`) |
| 决策1 入站转 base64 | ✓ 归属正确(IO 落 gateway,满足 core 不 IO),复用 `_to_anthropic_image_part` data URL 直通 |
| 决策2 当前轮结构化 + M246 携带 parts | ✓ 数据流闭合,多图全送达 |
| 决策3 两 provider user 分支 image 块 | ✓ 照 tool-result 范式扩展,各自单测 |
| 决策4 Message+parts 回放消费 | ✓ 消除「写而不读」双轨,纯文本 golden 守 |
| 决策5 异常图 gateway 入站硬停 + outbound-only | ✓ 数据流闭合(未 submit→历史干净→无需过滤),失败契约单一归属 gateway |
| spec 覆盖(当前轮/多图/跨轮/纯文本/异常图) | ✓ 五条 Requirement 全有落点,与澄清 Q2/Q6 一致 |
| delta-spec(kernel/gateway ADDED;im/cli no delta) | ✓ 用法正确、THEN 消费者可观察、失败契约不在 kernel 重复 |
| Milestone 单 M1 垂直切片 + 两轨退出标准 | ✓ 非横切、可验、引 spec Scenario |

## 架构进攻(四角度,全 ✓)

| 角度 | 发现 |
|---|---|
| 归属 | ✓ 图片 IO 归 gateway、core 纯净;失败处理彻底归 gateway 入站,内核不背中途回退——符合 `platform→core`、产品只 import sdk 硬规则,无反向依赖 |
| 该不该存在 | ✓ `Message.parts` 是消除双轨的必需权威表示(删除测试:删了即退回 bug);base64 data URL 自包含、对齐 CC,非假想抽象 |
| 深还是浅 | ✓ 复用 `_to_anthropic_image_part` / tool-result image 范式,未重造轮子 |
| 治本还是补丁 | ✓ 决策5 outbound-only 失败处理归属干净,非补丁 |

## Recommendations(不阻断,worker 落地注意)

- M246 路径的 extra image Message:其 `content` 投影可留占位或空串,但 `build_chat_messages` history 侧须以 `m.parts` 为准(决策2 line 91/接口 line 163 已述),worker 实现时确保 list content 优先于 content 投影。
- 决策5 自动压缩明列为 worker 增强项,核心契约「无法送达→停下报错」必须落地;压缩可后补。

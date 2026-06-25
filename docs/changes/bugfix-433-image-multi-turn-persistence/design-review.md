# Design 评审:bugfix-433-image-multi-turn-persistence（第 2 轮 · 复审修订）

**结论**:Issues Found(1 CRITICAL + 1 WARNING,均为上轮 CRITICAL-2 修订未传播干净的残留矛盾)

第 1 轮两个 CRITICAL 的**主干修法已闭合**,做得对:
- CRITICAL-1（M246 多图丢图）:§涉及范围 line 20 补列 `runtime.py:538-558` + M246 处理点;决策2 line 91 显式新增 M246 段并给修法(image part 构造带 `parts` 的 extra_message,经 history 侧 `build_chat_messages` 还原);时序图 line 151 加注;kernel delta 新增 Scenario「单条消息含多张图片时全部送达」;Milestone 退出标准加「多图单测」。机制自洽——与决策4 同一 parts 通道,多图全部送达。✓
- CRITICAL-2（失败提示数据流不闭合）:决策5 line 119 重写为「仅 outbound 展示、不持久化进 kernel 历史」,并解释原 is_provider_error 措辞为何不成立;接口段 line 167 同步。机制自洽——本轮未 submit 故历史天然干净,无需回放过滤。✓
- 上轮 WARNING（line 162「已有该键」误述）:line 164 已改为「`_message_to_entry` **新增** parts 写出（现状不写）」。✓
- 上轮 Recommendation（kernel delta THEN 偏实现）:Scenario「当轮模型即可见」THEN 已改为消费者可观察「模型据其内容作答」。✓

但 CRITICAL-2 的修订**只改了决策5 正文与接口段,漏了两处仍引用旧 is_provider_error 机制的地方**,二者现在与已纠正的 line 119 直接打架。

**核实台账**(本轮只复核「改动点 + 受改动牵连处」,未变动且上轮已 ✓ 的原子不再重列):

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 决策2:M246 多部件展开携带结构化 parts | 核修法是否闭合多图 | ✓ line 91 修法正确:extra_message 带 `Message.parts`,history 侧 `build_chat_messages`(line 163)读 `m.parts`→list content,多图全送达;与决策4 同机制 |
| §涉及范围含 M246 落点 | 核 worker 是否会漏 | ✓ line 20 列 `runtime.py:518,538-558,2121` 并注明「M246 展开时 image part 构造带 parts 的 Message」 |
| 决策5:失败提示 outbound-only 不持久化 | 核数据流是否闭合 | ✓ line 119/167 自洽:未 submit→历史干净→无需过滤;并明示原 append 路径丢 is_provider_error 的根因 |
| 决策5 line 129 风险 bullet | 与 line 119 比对一致性 | ✗ **残留矛盾**:仍写「失败信号经 `is_provider_error` 合成消息传回用户」,正是 line 119 已判「不成立」并弃用的旧机制 |
| kernel delta Scenario「图片无法获取时显式报失败」 | 与决策5 比对 + 锚实现 | ✗ **契约与决策打架**:line 32-35 仍要求「**内核**以可观察的失败信号告知消费者」,但决策5 已把失败判定全部前移到 gateway 入站、`submit` 前拦截、「失败路径在 gateway 闭合,不进 core」「mapper 不校验」。内核根本不会收到无法解析的图片,也无任何机制产出该信号 |
| kernel delta 新增「多图全部送达」 | 核是否覆盖 CRITICAL-1 | ✓ line 15-17 覆盖,主语=消费者,THEN 可观察 |
| gateway delta「异常图片本轮停下、告知用户、可重发」 | 核失败契约归属 | ✓ 失败契约正确落在 gateway delta(与决策5 一致),这恰恰反证 kernel delta 的同类场景是错放的孤儿 |
| `_message_to_entry` 新增 parts(仅非空) | 核 golden 守护 | ✓ line 164 明确「仅当 parts 非空,守纯文本 golden」 |

**架构进攻**(本轮无新增/搬动模块,仅复核 CRITICAL-2 修法的归属):

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 治本还是补丁 | 决策5 改为 gateway outbound-only 失败 | ✓ 走完无存活发现:失败处理彻底归于 gateway 入站(IO/校验所在层),内核不背中途回退,归属比上轮的「借 in-run is_provider_error 通道」更干净。**但**该归属调整要求把失败契约从 kernel delta 撤到 gateway delta——见 CRITICAL,未撤干净就是债 |
| 归属/该不该/深浅 | 其余 | ✓ 走完无存活发现(同第 1 轮) |

**Issues**(按 CRITICAL > WARNING):

- **[CRITICAL] [kernel delta-spec Scenario「图片无法获取时显式报失败」↔ 决策5]:内核契约仍要求一个决策5 已明确不在内核构建的失败信号。**
  `specs/kernel/spec.md:32-35` 仍写「内核以可观察的失败信号告知消费者该图片未送达模型……消费者据此可在不发起模型生成的前提下向用户报错」。但决策5 修订后,图片的下载/大小/解析校验**全部在 gateway 入站、`submit` 前完成**,「失败路径在 gateway 闭合,不进 core」「mapper 不校验」——到达内核的 image part 恒为已校验的 data URL,内核既不会遇到「无法获取/解析」的图片,也无任何机制产出这条「可观察失败信号」。
  不改→下游坏事:delta-spec 是收尾归并依据。这条并入 canonical 内核契约后,verifier 做 Completeness 核对会发现「一条 kernel requirement 无对应实现」(决策5 主动放弃在 core 做),收尾对不上账;reviewer 也会按内核契约去验一个本属 gateway 的行为。
  建议:把该 Scenario 从 **kernel delta 撤掉**(失败契约已正确落在 `specs/gateway/spec.md` 的「异常图片本轮停下、明确告知用户、可重发」,无需在内核重复)。内核侧若要保留一条不变量,改为消费者可观察的弱契约即可,如「内核对无法映射的图片块不致整轮崩溃」——但**不得**再声称内核「告知失败信号」。

- **[WARNING] [决策5 line 129 风险 bullet ↔ 决策5 line 119]:同一决策内自相矛盾,仍引用已弃用的 is_provider_error 机制。**
  line 129 仍写「失败信号经 `is_provider_error` 合成消息传回用户,core 不静默吞掉」,而同一决策的实现指引 line 119 已把此机制判为「不成立」并改为「仅 outbound 展示、不持久化」。
  不改→下游坏事:权威实现指引(line 119)与接口段(line 167)虽已正确,但 worker 扫到风险段的旧措辞可能回头用 `append_message(is_provider_error=...)`,撞上 `manager.py:185-197` 白名单静默丢标记的坑(正是上轮 CRITICAL-2)。把 line 129 改写为与 line 119 一致:「失败在 gateway 入站判定,经 outbound 直接回发用户、不写 kernel 历史,core 全程不接触失败图」。

**Recommendations**(不阻断):

- 这两处都是 CRITICAL-2 修订的「未传播」残留,定位明确、改动极小(撤一条 delta Scenario + 改一行风险措辞)。建议作者一次性全仓搜索 `is_provider_error` 在本 unit 文档内的出现,确认仅保留在「解释为何不用它」的语境,不残留任何「使用它」的措辞。
- 改完即可进 `change-orchestrator`——主干设计本轮已无架构层缺陷。

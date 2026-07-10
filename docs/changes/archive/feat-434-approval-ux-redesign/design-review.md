# Design 评审:feat-434-approval-ux-redesign（第 2 轮）

**结论**:Approved

第 1 轮两条 CRITICAL 作者均已完整修掉，本轮逐条复核无残留、无新引入矛盾；架构进攻四角度走完无存活发现。可进 `change-orchestrator` 实施。

> 第 1 轮报告（2 CRITICAL）见本文件 git 历史。本轮只对照两条 CRITICAL 的闭合 + 复核修订是否引入新问题。

---

## 两条 CRITICAL 闭合核验

| 上轮 CRITICAL | 要求 | 本轮状态 + 证据 |
|---|---|---|
| **C1 决策2 allow 侧「同款通道」不成立 + 降级违反 spec Q7** | ① 现状分析拆开 deny/allow 两侧、点名 `hook_runner` block=False 须改；② 删「降级纯前端」退路、改述为 M1 必做 | ✅ **已闭合**。①现状分析「涉及范围·内核」段（design:23-28）明确「deny 与 allow 两侧传播路径不对称，必须分开看」，逐文件点名 `auto_mode_gate` allow 裸 `{block:False}` 无信号、`runner.py:140-150` block=False 只留 args/allow_unlisted **须改造保留 approval**、`registry` allow 不抛 ToolError、`tool_executor`/`types` allow 须给 ToolResult 新增字段；决策2（design:93-106）改标题为「deny 复用 reason_code 载体，allow 须新建传播链」并列出 allow 五步链（带文件行号）；可复用能力段（design:43）明确 emoji 模板「仅覆盖事件已带 approval 之后的下半程，内核侧产出 approval（尤其 allow）不在此模板内」。②风险段（design:176）改为「allow 链最易漏的一环（**不是降级项**）」，明确「spec Q7 已拍含后端、allow 必标，不存在『不行就退纯前端』的降级」；Milestone 退出标准新增 `[worker]`「**allow 成功**工具 approval 端到端到达前端（不止 deny；覆盖决策2 五步链，含 runner.py block=False 保留 + 成功路径 lift）」 |
| **C2 三份 delta-spec 误用 MODIFIED** | 改为 ADDED（approval 是独立新维度） | ✅ **已闭合**。`specs/{kernel,im,gateway}/spec.md` 三份均已改 `## ADDED Requirements`；现状分析（design:51）同步修正「kernel/spec.md 无对应『终态分类』条；approval 是独立于 reason 的新增维度，故 delta-spec 用 ADDED 而非 MODIFIED」 |

---

## 核实台账（复核修订引入的承重断言；结论附证据）

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 新断言:auto_mode_gate allow 分支返回裸 `{block:False}`、与自动放行在 gate 出口等价 | 对照上轮 Explore 核实 | ✓ 与上轮一致（`auto_mode_gate.py:693/700/707` allow 返回 `{block:False}`；自动放行 `:814/819/828/839/901` 返回 None） |
| 新断言:`runner.py:140-150` block=False 只保留 args/allow_unlisted、丢弃其余 | 对照上轮核实 | ✓ 一致——allow 侧 approval 必须改此分支保留，design 已点名为「最易漏的一环」 |
| 新断言:registry deny 抛 ToolError 带 reason_code=denied、allow 成功路径无 ToolError 载体 | 对照上轮核实 | ✓ 一致（`registry.py:194` deny 才挂 reason_code；allow 成功不抛，故须给 ToolResult 另填） |
| 新断言:ToolResult 须新增 approval、tool_executor 成功路径填充、realtime_stream tool_end 带出 | 对照上轮核实 | ✓ 链路点位与上轮吻合（`tool_executor.py:184-222`、`types.py:72`、`realtime_stream.py:105`） |
| 决策1「对称性仅数据语义、非传播路径」 | 自洽? | ✓ 修订采纳上轮 Recommendation——澄清 approval 字段数据语义对称、deny/allow 传播路径不对称，与决策2 五步链一致 |
| 接口与数据流分两段（内核产出非模板 / 下半程照模板） | 自洽? | ✓ design:139-141 拆分清晰，与决策2、可复用能力段三处口径一致，无矛盾 |
| 三份 delta-spec 是真·平行新增、不顶替既有 reason 徽标条 | 锚 canonical? | ✓ approval 与既有 im:389「工具徽标按中断原因显示终态」是正交两维，ADDED 平行新增，收尾并入不冲突；既有条 Scenario 不被动 |
| 三份 delta-spec THEN 红线 | 有无实现层泄漏 | ✓ 均为「消费者可观察到标识」，无内部函数名/类名/日志串 |
| Milestone 单 M1 + 范围（新增 auto_mode_gate.py / runner.py） | 垂直?范围齐? | ✓ 垂直端到端切片举证仍成立；范围已补内核两文件，与决策2 五步链对齐 |
| Milestone 退出标准两轨 | 可验?覆盖 allow? | ✓ `[reviewer]` 6 条引 spec Scenario；`[worker]` 新增 allow 端到端验证（补上轮缺口），两轨齐、可验 |

---

## 架构进攻（四角度逐个走）

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | approval 内核 gate 产出、沿元信息通道流出；allow 五步链 | ✓ 走完无存活发现。五步链是沿既有数据流（gate→runner→registry/tool_executor→ToolResult→realtime_stream）打通，非新造间接层；产品只 import sdk，无反向依赖 |
| 该不该存在 | 新增 `approval` 字段 / allow 五步链 | ✓ 走完无存活发现。删除测试：复用 reason 会污染 failTag/REASON_BADGE_NAMES 抑制；allow 链每步都是必经载体（无可省略的封装） |
| 深还是浅 | failTag i18n、approval 透传 | ✓ 走完无存活发现。接既有 `t()`、纯数据字段，无浅封装 |
| 治本还是补丁 | 上轮的「降级纯前端」退路 | ✓ 走完无存活发现。该补丁退路本轮已删除，allow 改为正面打通五步链、必做——治本，不再有补丁冒充回退 |

---

## Recommendations（不阻断，作者自行取舍）

- 无。两条 CRITICAL 已闭合，文档可直接进实施。

# Design 评审:feat-434-approval-ux-redesign

**结论**:Issues Found（2 CRITICAL）

逐条核过的承重原子见台账；两条 CRITICAL 均不阻断方案大方向（内核新增 `approval` 字段 + 前端合一），但会让 worker 在最难的 allow 侧走偏、并让收尾归并对不上账，定稿前必须改。

---

## 核实台账（逐条核过的承重原子；结论附证据，非打勾）

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状:ToolCallsPanel 在气泡内、permission_requests 在气泡外（435-453） | 读 MessageBubble JSX | ✓ `message-pane.tsx:436` ToolCallsPanel 在 `.chat-bubble-card` 内、`:442` permission_requests.map 在卡外同层 |
| 现状:permission-card 有 resolved + pending 分支 | 读组件 | ✓ `permission-card.tsx:103` `status==="resolved"` 分支，下方默认 pending 表单 |
| 现状:ToolCallRow 布局 + REASON_LABEL_KEYS | 读组件 | ✓ `tool-calls-panel.tsx:111-138` icon/emoji/name/summary/reason/failTag/duration；`:83-89` REASON_LABEL_KEYS（denied/timed_out/interrupted…→i18n key） |
| 现状:failTag 硬编码 exit/failed 未走 i18n | 读函数 | ✓ `tool-presentation.ts:95-96` `return \`exit ${exit}\`` / `return "failed"`；REASON_BADGE_NAMES `:75-83`、isCallFailed `:65-67` 均如述 |
| 现状:chat-types ToolCall 无 approval 字段 | 读类型 | ✓ `chat-types.ts:59-84` 字段为 id/name/status/input/duration_ms/output/reason/detail/emoji，无 approval |
| 现状:reducer 中 permission_requests 与 tool_calls 两条独立流 | 读 reducer | ✓ `chat-stream-reducer.ts:146-176` tool_call.upserted/completed 改 tool_calls；permission.request/resolved 改 permission_requests |
| 现状:feat-425 emoji 四处透传模板（domain/payload/encode-decode/Gateway） | 逐处读 | ✓ `domain/models.py:209`、`messages.py:94`、`repositories.py:2810-2884` encode/decode、`main.py:3644-3675` Gateway 拼接——approval 可照抄此 IM/Gateway 透传模板 |
| 现状:registry gate block→reason_code="denied"（166-196） | 读 gate | ✓ `registry.py:181` `block` 分支，`:194` details 携 `reason_code="denied"`（注释：自动 block 与用户 Deny 都走 denied） |
| 现状:submit_permission_decision 入口存在、决策回流 gate | 追路径 | ✓ `kernel.py:925-971` 构 PermissionResponse→`broker.resolve`；`auto_mode_gate.py:684` `await request_permission` 取回，`:688` 提 `response.decision` |
| **决策2 前提:auto_mode_gate 能区分「用户 allow」与「自动放行」** | 从 gate 返回值正向追 | **✗ 不成立**：`auto_mode_gate.py:693/700/707` 用户 allow 与各自动放行路径（`:814/819/828/839/901` 返回 None）在 gate 出口都等价于「不 block」；`_handle_ask` 用户 allow 返回 `{"block": False}` 不带任何决策信号。`hook_runner.py:140-150` 在 block=False 时仅保留 args/allow_unlisted、其余返回字段被 `continue` 丢弃 → **CRITICAL-1** |
| 现状:reason_code 链 gate→ToolResult→tool_end | 逐跳追 | ✓ 但**仅 deny 路径**：`tool_executor.py:184-200` 从 ToolError.details 提 reason_code→ToolResult；`realtime_stream.py:105` tool_end 携 reason_code。allow 成功的工具**不抛 ToolError、无此载体** → 支撑 CRITICAL-1 |
| 决策1:approval 新字段不复用 reason | 拍死?有据? | ✓ 拍死有据：reason 现语义=非成功终态徽标，塞 user_allow 会与 REASON_BADGE_NAMES/failTag 抑制纠缠；新字段干净 |
| 决策2:标识源头内核 gate、沿 reason_code 同款透传 | 拍死?前提成立? | ✗ 见上——allow 侧「同款通道」现状不成立，且 design 留的降级退路违反 spec → CRITICAL-1 |
| 决策3:已决改读 tool_call.approval、删气泡外卡 | 覆盖?审计兜底? | ✓ 拍死；bugfix-367「按了多少次同意」由收起态分项计数 + 行内闸门标承载，不丢 |
| 决策4:行内闸门区/结果区分区 + denied 去重 | 自洽?复用? | ✓ 复用 REASON_BADGE_NAMES 抑制；闸门区 deny verdict 读 `approval==="user_deny" \|\| reason==="denied"`（决策1 第87行已给回退式，消歧） |
| 决策5:failTag 接 i18n | 有据? | ✓ 修 spec Q6 既有缺口；failTag 现为纯函数、调用处 ToolCallRow 已有 t()，实现细节下沉 worker 合理 |
| spec Req「技术动作收同一气泡」「待决醒目」「折叠并入」「工具行形态」「行内分区」「失败文案随语言」 | 逐条找落点 | ✓ 分别由决策3/待决卡内移/决策3/决策3+审计兜底/决策4/决策5 覆盖 |
| **澄清 Q7「含后端、allow 成功也标已授权」** | design 有无冲突落点 | ✗ spec Q7 用户拍「含后端」，design 风险段却把 allow 侧标记列为「需 M1 验证、不行就降级纯前端（allow 不标）」——该降级正是 Q7 否决的方案 → CRITICAL-1 |
| 非目标（不改 auto_mode_gate 触发判定/决策粒度/拒绝后行为/详情卡） | design 有无越界 | ✓ 未越界，approval 只读决策结果不改触发逻辑 |
| delta-spec kernel/im/gateway 三份 | 锚 canonical?MODIFIED 用法?THEN 可观察? | ✗ 三份均标 **MODIFIED**，但其 Requirement 标题（「工具执行事件携带终态分类」「工具调用的授权决策随消息持久化与下发」「Gateway 向 IM 中继的工具调用携带授权决策」）在 canonical 中**均不存在**（canonical 最近条目：im:389「工具徽标按中断原因显示终态」、gateway:441「run 进入终态时对在飞 tool_call 按原因收口」、kernel 无终态分类条）。THEN 写法本身合规（「消费者可观察到标识」无实现层泄漏）。但 MODIFIED 锚不到既有标题 → **CRITICAL-2** |
| delta-spec cli no delta | 显式注明? | ✓ design:164 显式「no spec delta」 |
| Milestone 单 M1 | 垂直 vs 横切?举证? | ✓ 垂直端到端切片（approval 须从内核 gate 一路到前端才显示），design:188 举证充分、显式禁横切 |
| M1 退出标准 | 两轨齐?可验? | ✓ `[reviewer]` 6 条引 spec Scenario、`[worker]` 4 条（round-trip 单测/前端分区单测/i18n/全绿），颗粒度恰当非 roadpoint |

---

## 架构进攻（四角度逐个走）

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | approval 标识放内核 gate、沿元信息通道经 sdk→gateway→im→前端 | ✓ 走完无存活发现。approval 是工具执行元信息，与 reason_code/emoji 同层归属正确；产品包只 import agent.sdk、approval 从 core 流出，无反向依赖。决策2 拒绝 Gateway 相关性匹配（无 id 绑定脆弱）是对的 |
| 该不该存在 | 新增 `approval` 字段 vs 复用 `reason` | ✓ 走完无存活发现。删除测试：复用 reason 则 allow 成功行的 reason 会与 failTag/REASON_BADGE_NAMES 抑制纠缠、污染语义；独立字段是必要区分而非多余间接层 |
| 深还是浅 | failTag i18n 化、approval 透传 | ✓ 走完无存活发现。failTag 接既有 `t()` 机制非重造；approval 是纯数据字段非封装层 |
| 治本还是补丁 | design 风险段「allow 半边降级、退回纯前端」退路 | ✗ 这是补丁冒充回退：spec Q7 已拍「含后端、allow 必标」，把它列为「可降级项」是把违反 spec 的临时方案当退路写进文档。长远代价：worker 真去「验证前提」失败后据此降级，交付一个被用户明确否决的 allow-不标版本。并入 CRITICAL-1 |

---

## Issues（按 CRITICAL > WARNING 排序）

- **[CRITICAL] [决策2 / 现状分析 / 风险与回退 / 澄清 Q7]:approval 的 allow 侧「沿 reason_code 同款通道透传」现状不成立，且 design 留的降级退路违反 spec Q7。**
  核实显示「同款通道」只对 **deny 侧**成立——deny 走 `block=True` → `ToolError.details`（可与 `reason_code=denied` 同源挂 `approval=user_deny`）→ tool_executor 提取（`tool_executor.py:184-200`）→ tool_end。**allow 侧**（正是 spec Q7 用户拍板「含后端」专门要求的那半）现状走 `_handle_ask` 返回 `{"block": False}`（`auto_mode_gate.py:693/700/707`），而 `hook_runner.py:140-150` 在 block=False 时只保留 args/allow_unlisted、`continue` 丢弃任何 approval 字段；且 allow 成功的工具不抛 ToolError、没有 reason_code 那样的现成载体。也就是 allow 侧需**从零新建**一条「gate 返回带 approval 信号 → 改 hook_runner 在 block=False 时保留它 → ToolResult 新增 approval → loop 透传 → realtime_stream」链，而非「平行挂、同款随出」。
  **不改→下游坏事**：(1) worker 按现状分析「approval 平行挂 reason_code / 照逐字模板照抄」会严重低估、极可能漏改 `hook_runner` block=False 分支，导致 allow 标识根本传不出，前端「已授权」永不出现；(2) design 风险段把这列为「唯一需 M1 验证的前提，不行就降级纯前端（allow 不标）」——而该降级正是 Q7 用户否决的方案，worker 据此降级即交付违反 spec 的结果。
  **要求**：① 现状分析里把 allow 侧与 deny 侧拆开写清——deny 可照 reason_code/ToolError.details 同源，allow 须新建链并**点名 `hook_runner.py` block=False 分支需改造保留 approval**；② 删除/改写「不行就降级纯前端」退路，spec Q7 已拍「含后端」，allow 必标不是可降级项，应改述为「M1 必做的内核改动」。

- **[CRITICAL] [契约层增量 / specs/{kernel,im,gateway}/spec.md]:三份 delta-spec 误用 MODIFIED，标题锚不到任何既有 canonical Requirement，应改为 ADDED。**
  三份均写 `## MODIFIED Requirements`，但其 Requirement 标题（kernel「工具执行事件携带终态分类」、im「工具调用的授权决策随消息持久化与下发」、gateway「Gateway 向 IM 中继的工具调用携带授权决策」）在对应 canonical（`docs/specs/{kernel,im,gateway}/spec.md`）中均不存在——canonical 现有最接近的是 im:389「工具徽标按中断原因显示终态」、gateway:441「run 进入终态时对在飞 tool_call 按原因收口」，kernel 无「终态分类」条。而 approval 按决策1 是**独立于 reason 的新维度**，本就该是平行新增。
  **不改→下游坏事**：收尾归并时 orchestrator 拿 MODIFIED 去 canonical 找同名标题改，找不到→要么卡住、要么误匹配到既有 reason 徽标 Requirement 并顶替/污染其原 Scenario（denied/超时/中断那几条），canonical 出现同一行为新旧并存或原 Scenario 静默丢失。
  **要求**：三份改 `## ADDED Requirements`（approval 是平行新维度）。若作者本意确是「扩展既有 reason 徽标契约」，则须把 delta 标题**逐字改成被改的既有 canonical 标题**并保留其原 Scenario 再追加——但按决策1 的独立字段定位，ADDED 更正确。

---

## Recommendations（不阻断门禁，作者自行取舍）

- 决策1 的「approval 对称承载 allow 与 deny」叙述可点一句实现差异：deny 侧 `user_deny` 走 ToolError.details（与 reason_code 同源、好挂），allow 侧 `user_allow` 走全新链——「对称」是数据语义对称，传播路径并不对称，免得 worker 误以为两侧实现等价。
- 现状分析第49行「kernel canonical 现有对 tool_call reason 徽标的描述」与代码一致——实测 reason 徽标契约在 im:389，kernel/spec.md 无对应条；若 CRITICAL-2 改为 ADDED 则此句一并修正即可，不必单列。

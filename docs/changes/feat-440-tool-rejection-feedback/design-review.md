# Design 评审: feat-440-tool-rejection-feedback (Round 1)

**结论**: Issues Found

---

**核实台账**（逐条核过的承重原子；结论附证据，不是打勾）:

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| **现状断言** | | |
| 现状:gate _handle_ask 拒时返回 block+reason+approval=user_deny | 追 auto_mode_gate.py:713-718 | ✅ `return {"block": True, "reason": response.reason or "user denied", "approval": "user_deny"}` — 与 design 一致 |
| 现状:registry block 打包 ToolError "tool blocked by hook" + details | 追 registry.py:190-209 | ✅ `ToolError("tool blocked by hook", details={blocked_by_hook:True, reason:..., reason_code:"denied", approval:...})` — 与 design 一致 |
| 现状:tool_executor 非白名单 synthetic error 无 approval/reason_code | 追 tool_executor.py:156-166 | ✅ `ToolResult(error=f"tool '...' is not allowed...", arguments=...)` — 无 approval/reason_code 参数 |
| 现状:tool_executor catch ToolError 提 reason_code+approval 但丢弃 details["reason"] | 追 tool_executor.py:214-238 | ✅ 只提 `details.get("reason_code")` 和 `details.get("approval")`，`error=str(exc)` 仍为 "tool blocked by hook"，`details["reason"]` 未提取 |
| 现状:loop._serialize 原样透传 result.error | 追 loop.py:989-999 | ✅ `if result.error is not None: payload["error"] = result.error` |
| 现状:SubmitPermissionDecisionRequest 仅 message_id+decision | 追 messages.py:414-418 | ✅ `class SubmitPermissionDecisionRequest(BaseModel): message_id: str; decision: str` — 无 reason |
| 现状:gateway_handler push_permission_response frame 无 reason | 追 gateway_handler.py:298-307 | ✅ frame payload = `{kind, message_id, request_id, decision}` — 无 reason |
| 现状:PA main.py:3033 已读 body.get("reason") 并传 kernel | 追 main.py:3030-3039 | ✅ `reason = str(body.get("reason") or "").strip()` → `kernel.submit_permission_decision(reason=reason)` |
| 现状:kernel.submit_permission_decision 接受 reason 并传 broker | 追 kernel.py:996-1042 | ✅ `PermissionResponse(decision=decision, request_id=request_id, reason=reason)` → `broker.resolve()` |
| 现状:broker.PermissionResponse.reason 字段存在但恒空 | 追 broker.py:46-51 | ✅ `reason: str = ""` |
| 现状:permission-card.tsx POST body 无 reason | 追 permission-card.tsx:96 | ✅ `body: JSON.stringify({ message_id: messageId, decision: option.id })` — 无 reason |
| 现状:core 不依赖 platform | 核目录结构 | ✅ tool_executor.py 在 core/agent/，auto_mode_gate.py 在 platform/hooks/ |
| 现状:subagent fork run_origin=BACKGROUND_TASK | 追 context_fork.py:216-223 | ✅ `"run_origin": RunOrigin.BACKGROUND_TASK.value` |
| 现状:_tool_execution_allowlist is not None = subagent | 追 tool_executor.py:54-78 + context_fork.py:243 | ✅ fork 创建 executor 时传 `tool_execution_allowlist=tool_allowlist`；主会话不传（默认 None） |
| 现状:auto-reject 子路径均无 approval | 追 gate 671/686/904/934/937/944-947 | ✅ 所有 auto block return 均无 `"approval"` 键 → registry details 中 approval=None |
| **决策** | | |
| D1:文本统一在 tool_executor | 拍死?歧义?矛盾?spec驱动? | ✅ 拍死（选了单一 helper，拒绝两个替代）；与 D2/D3 无矛盾；spec 4 Req 驱动 |
| D2:文本模块落 core + CC 照搬 + 本地化 | 拍死?歧义?矛盾?spec驱动? | ✅ 拍死；本地化三点具体（newText edit.py:116 验证 ✅，删规则尾句，无 DONT_ASK）；Q1.1 驱动 |
| D3:IM 补两端复用既有 reason 链路 | 拍死?歧义?矛盾?spec驱动? | ✅ 拍死；4 处改动精确；Q2 驱动 |
| **spec 约束** | | |
| Req:主会话用户拒绝（2 Scenario） | design 有落点吗 | ✅ 决策 1 + build_reject_message 表 row 2/3 覆盖 |
| Req:策略自动拦截 | design 有落点吗 | ✅ 决策 1 + build_reject_message 表 row 4 覆盖 |
| Req:subagent 区分 | design 有落点吗 | ✅ 决策 1 + build_reject_message 表 row 1 覆盖 |
| Req:IM 权限卡理由框（2 Scenario） | design 有落点吗 | ✅ 决策 3 + 前端 permission-card.tsx 改动覆盖 |
| 非目标:不改徽标 | design 越界了吗 | ✅ 未越界（相关历史段明确"不改徽标呈现"） |
| 非目标:不改判定逻辑 | design 越界了吗 | ✅ 未越界（"本 unit 不改判定逻辑，只新增/透传 reason"） |
| **delta-spec** | | |
| kernel delta ADDED Req + 4 Scenario | 锚 canonical?THEN 可观察? | ✅ ADDED（新增行为，不改既有）；THEN 均写"投递回模型的该工具结果内容"——消费者可观察；无内部函数名 |
| im delta ADDED Req + 3 Scenario | 锚 canonical?THEN 可观察? | ✅ ADDED（新增 UI 组件）；THEN 均写用户可观察行为；无内部实现细节 |
| gateway: no spec delta | 是否该有? | ✅ "仅透传 reason 字段，无对外行为新增" — 合理 |
| cli: no spec delta | 是否该有? | ✅ "CLI 不经 IM 权限卡；coding_cli 的拒绝文本随 kernel 改进自动受益" — 合理 |
| **Milestone** | | |
| M1 单 milestone | 垂直 vs 横切?举证? | ✅ 垂直切片（端到端语义化拒绝反馈）；举证充分（"内聚特性，~400-500 行，无并行/体量/分阶段触发"）；退出标准两轨齐（5 条 [reviewer] + 3 条 [worker]） |

---

**架构进攻**（四角度逐个走，每条发现带具体长远代价）:

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | reject_messages.py 放 core/agent/；IM 改动放 IM 包 | ✅ 走完无存活发现。reject_messages 由 tool_executor(core) 调用，放 core 正确；IM 改动在 IM 包内，无跨层反向依赖 |
| 该不该存在 | 新增 reject_messages.py 模块 | ✅ 走完无存活发现。删除测试：4 分支选择逻辑 + 5 个常量内联进 tool_executor 会膨胀 catch 块且无法独立单测；单一实现但逻辑非纯平（4 路映射 + 模板组装），接缝有价值 |
| 深还是浅 | build_reject_message 包装模板选择 | ✅ 走完无存活发现。接口（5 个 keyword 参数 → str）比实现（4 路分支 + 模板拼接 + 本地化常量）简单，不是浅封装 |
| 治本还是补丁 | 复用既有 reason 全链路而非造新字段 | ✅ 走完无存活发现。方案正面解决根因（"LLM 拿到的工具结果都是同一句通用字面量"），复用 PermissionResponse.reason 既有字段，无 hardcode/绕过/叠特例 |

---

**Issues**（从台账 ✗ 与架构进攻发现升级而来，按 CRITICAL > WARNING 排序）:

- [WARNING] [决策 1 / 选择逻辑表]: `build_reject_message` 的自动拒行（`approval=None`）写了 `classifier_reject_message(reason)` **或** `auto_reject_message(tool_name)`，但未指定何时用哪个。当前 gate 的所有 auto block 路径共享 `reason_code="denied"` 和 `approval=None`，`build_reject_message` 收到的信号无法区分「分类器 LLM 生成的解释」（如 `"The tool is attempting to modify system files"`）和「系统错误字符串」（如 `"no permission channel (fail-closed)"`、`"gate error: ..."`）。不改 → worker 被迫猜，不同猜法导致不同实现：若一律用 `classifier_reject_message(reason)`，系统错误字符串会被格式化为 `"Permission... Reason: no permission channel (fail-closed)"` 这样对 LLM 无意义的文本；若一律用 `auto_reject_message(tool_name)`，分类器的有用解释被丢弃。建议退回明确策略：① 在 gate 侧新增 `reason_type` 区分信号（如 `"classifier"` vs `"system"`）；② 或在 selection 逻辑里用启发式（如检测 reason 是否含已知系统错误前缀）；③ 或直接拍死用一种函数覆盖所有自动拒路径。

**Recommendations**（不阻断门禁，作者自行取舍）:

- 决策 1 提到"CC 的 `SUBAGENT_REJECT_MESSAGE_WITH_REASON_PREFIX`（带理由版）在本项目是死路径——不实现该变体"。建议在 `reject_messages.py` 顶部注释或 docstring 里显式标注这是有意省略，防止将来有人以为遗漏而补上。
- 架构总览的 mermaid 图 (1) 中 `H` 节点标注为 `reject_text helper`，但实际函数名是 `build_reject_message`。建议统一命名，避免 worker 在代码里搜不到对应函数。

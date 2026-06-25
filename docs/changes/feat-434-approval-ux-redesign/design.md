# feat-434: 审批 UX 与工具调用列表协同重设计 — 技术方案

> 对齐: spec.md v1

> Unit branch: `unit/feat-434` (will be created by orchestrator)

## Changelog

<!-- design 阶段保持空 -->

## 现状分析

### 涉及范围

**前端（合一面板主战场）**
- `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx` — `MessageBubble`：现状工具面板在气泡**内**、`permission_requests.map(PermissionCard)` 在气泡**外**（约 435-453 行）。合一即把审批呈现收进气泡、已决并入工具面板。
- `.../components/tool-calls-panel.tsx` — `ToolCallRow` 行布局（图标/名称/摘要/reason/failTag/duration），`REASON_LABEL_KEYS`。要加「闸门区」、规整「结果区」。
- `.../components/permission-card.tsx` — 删 `request.status==="resolved"` 分支（已决不再走它），pending 保留。
- `.../components/tool-presentation.ts` — `failTag()` 硬编码 `exit ${code}`/`failed`（i18n 缺口）；`REASON_BADGE_NAMES`（denied 去重复用点）；`isCallFailed`。
- `.../chat-types.ts` — `ToolCall` 加 `approval` 字段。
- `src/styles/global.css` `.chat-tool-call-*` / `.chat-permission-*` 段；`src/i18n/zh.json`/`en.json` 加键。

**内核（approval 标识源头）**
- `src/agent/core/tools/registry.py` — gate 经 `_dispatch_intercept("tool_call")` 返回 `{block, reason}`；deny→`reason_code="denied"`（166-196 行）。`auto_mode_gate` hook 知道「这次是用户 allow 还是自动放行」。
- `src/agent/core/agent/tool_executor.py` + `core/types.py` — `ToolResult.reason_code` 的 lift 点（184-222 / types.py:72）；approval 平行挂这。
- `src/agent/platform/hooks/builtins/realtime_stream.py` — tool_end 随 `reason_code` 转发（105 行），approval 同款随出。

**Gateway**：`src/personal_assistant/main.py` ~3600-3664 — 把 `reason_code/emoji/presentation` 透传进 `tool_call` payload；approval 加一条同款透传。

**IM**：`src/IM/domain/models.py` `ToolCall`（184）、`src/IM/api/routes/messages.py` `ToolCallPayload`（78）、`src/IM/infra/repositories.py` `_encode_tool_calls`/`_decode_tool_calls`（~2805/2876）—— 新字段照 **feat-425 emoji** 那套逐字透传。

### 既有约束

- 产品包（`personal_assistant`）只能 import `agent.sdk`；内核 gate 在 `core`，approval 标识必须从内核既有工具元信息通道（`reason_code/emoji` 同款 kernel→gateway→im→前端）流出，Gateway 不得凭空构造。
- IM 不调 `agent`，按**显式字段**持久化 `tool_call`：新字段不进 domain/payload/encode/decode 任一处就会被 `_normalize` 丢掉。
- 前端 reducer 里 `permission_requests` 与 `tool_calls` 是**两条独立流**；已决呈现改为读 `tool_call.approval`，pending 仍读 `permission_requests`。
- COMMENTING_GUIDE / i18n：用户可见文案一律走 `t()`，不硬编码语言。

### 可复用能力

- **feat-425 emoji 字段透传链路** = 本次 `approval` 字段的逐字模板（domain + payload + encode/decode + Gateway forward + 前端 type），照抄即可，不另造。
- `reason_code` / `REASON_LABEL_KEYS` / `REASON_BADGE_NAMES` 机制 = denied 已自动对上，allow 复用同款通道；denied 去重直接用 `REASON_BADGE_NAMES` 抑制逻辑。
- `ToolCallsPanel` / `PermissionCard` / `.chat-tool-call-*` 样式体系 = 合一面板在其上扩展，不重写。
- 原型 `prototype.html`（同目录）= 视觉与交互的对照基准（行内分区、收起态分项计数、待决卡形态）。

### 相关历史

- feat-333（auto_mode_gate 审批 ask 流 + 权限卡）、bugfix-367（权限卡内联 + 审计可见）、bugfix-410/417（tool_call 的 `reason` 徽标：denied/超时/中断）、feat-425（emoji 字段透传，本次模板）、feat-409（presenter detail）。
- 契约层 grounding：`docs/specs/im|gateway|kernel/spec.md` 现有对 tool_call `reason` 徽标的描述与代码一致；approval 是其上的新增维度，无 drift。

## 架构总览

**before → after**：审批呈现从「气泡外独立卡墙」收进「气泡内、并入工具面板」。新增一条 `approval` 标识，沿用 `reason_code` 同款通道贯穿全栈。

```mermaid
graph LR
  subgraph 内核 core
    GATE["registry.py gate<br/>auto_mode_gate hook"]
    GATE -->|"deny: reason_code=denied<br/>allow: approval=user_allow/deny"| TE["tool_executor<br/>ToolResult"]
  end
  TE --> RS["realtime_stream<br/>tool_end 事件"]
  RS --> GW["Gateway main.py<br/>透传进 tool_call payload"]
  GW --> IM["IM ToolCall<br/>domain+payload+encode/decode"]
  IM --> FE["前端 ToolCall.approval"]
  FE --> ROW["合一面板：行内闸门区<br/>已授权/已拒绝"]
```

**前端气泡结构 before/after**：

```
before                                  after（合一）
气泡卡 ┐                                 气泡卡 ┐
  文本 │                                   文本 │
  工具面板（气泡内）                          工具面板（气泡内，已决=行内闸门区）
气泡卡 ┘                                   待决卡（气泡内最下方）
[已决审批卡 ×N]  ← 飘在气泡外的墙          气泡卡 ┘
[待决审批卡]     ← 飘在气泡外
```

## 关键决策

### 决策 1: approval 用新字段，不复用 reason

**新增 `ToolCall.approval: "user_allow" | "user_deny" | null`，闸门区统一读它；`reason` 不动。**

- **理由**：`reason` 现语义是「非成功终态徽标」（denied/超时/中断，红、抑制 failTag）。把成功的 `user_allow` 塞进去会污染语义、与 `REASON_BADGE_NAMES`/failTag 抑制纠缠。新字段干净，且 feat-425 emoji 有逐字模板。
- **对称性**：`approval` 同时承载 allow 与 deny（消除「allow 走新字段、deny 走 reason」的不对称——用户指出的怪点）。`reason="denied"` 保持不动（向后兼容失败行机制）；前端对**历史行**（有 reason 无 approval）回退：`approval==="user_deny" || reason==="denied"` → 闸门区「已拒绝」。
- **拒绝**：复用 `reason` —— 省一字段透传，但语义混淆、维护埋坑。
- **风险**：标识源头在 `auto_mode_gate` hook 须能区分「用户决策 allow」与「自动放行」——见决策 2。

### 决策 2: 标识源头在内核 gate，沿 reason_code 同款通道全栈透传

**`auto_mode_gate` 在用户决策后于 gate 处把 `approval` 写进 tool_call 执行事件，随 `reason_code` 同一条 kernel→gateway→im→前端通道流出。**

- **理由**：approval 是工具执行的元信息，归属与 `reason_code`/`emoji` 同。任何让 Gateway 凭 `permission_requests` 与 `tool_calls` 做事后相关性匹配的方案都脆弱（多条同名 bash 难对上）。
- **拒绝**：Gateway 侧相关性匹配 —— 无 id 绑定、脆弱。
- **风险**：要确认 gate 处 `auto_mode_gate` 的 payload 能透出「本次为用户显式 allow」。自动放行（auto-allow）**不**标 `approval`（保持 null，闸门区不显），只有真正经用户卡决策的才标。

### 决策 3: 已决审批呈现改读 tool_call.approval，删除气泡外已决卡

**`message-pane.tsx` 不再渲染气泡外的已决 `PermissionCard`；`permission-card.tsx` 删 resolved 分支。已决审批 = 工具面板行内闸门区（读 `tool_call.approval`）。pending 仍读 `permission_requests`，且移进气泡内最下方。**

- **理由**：已决审批与工具调用本是同一条流（spec 澄清 Q2），呈现归一到工具行；`permission_requests` 只保留「待决」职责。
- **拒绝**：保留独立已决卡 —— 即现状的「黑框墙」，spec 要消除的。
- **风险**：bugfix-367 的「审计：按了多少次同意」需保住 —— 由收起态「N 次授权·X 允许·Y 拒绝」+ 展开行内闸门标承载，不丢。

### 决策 4: 行内分区（闸门区 / 结果区）+ denied 去重

**行内两区：闸门区（贴名称右侧，读 approval → 已授权/已拒绝）；结果区（行尾，failTag/reason 徽标/duration）。denied 渲到闸门区后，抑制行尾原 denied reason 徽标，避免双印。**

- **理由**：「是否授权」与「执行结果」是两条轴，覆盖「授权后执行失败」边界（spec Req-行内分区）：名称旁「已授权」+ 行尾「exit 1」各占一侧。
- **复用**：`REASON_BADGE_NAMES` 已有抑制机制；denied 从「行尾 reason 徽标」改为「闸门区 verdict」即抑制行尾那条。
- **风险**：超时/中断（非 denied 的 reason）仍留结果区，不进闸门区 —— 它们不是审批结果。

### 决策 5: failTag 接 i18n

**`tool-presentation.ts` 的 `exit ${code}`/`failed` 改走 `t()`（新增 `toolFailExit`={{code}} / `toolFailGeneric`），随界面语言渲染。**

- **理由**：现状 reason 标签走了 i18n、failTag 漏接（spec 澄清 Q6）。修掉这个既有缺口，新文案一律 i18n。
- **风险**：`failTag` 现为纯函数返回字符串、无 `t()` 入参 —— 调用处（`ToolCallRow`）已有 `t`，把成品文案的拼装移到组件内或给 failTag 传 `t`。属实现细节，worker 定。

## 接口与数据流

**数据结构增量**（唯一对外契约变化）：`ToolCall` 全栈加一个可选字段

```
approval?: "user_allow" | "user_deny" | null   // 仅经用户卡决策的工具才有值；自动放行为 null
```

落点（照 feat-425 emoji 逐字模板）：
- 内核：`ToolResult` 携带 → tool_end 事件 `approval`（`realtime_stream`）
- Gateway：`main.py` tool_end 分支把 `approval` 拼进 `tool_call` payload（与 `reason`/`emoji` 并列）
- IM：`domain/models.ToolCall.approval` + `ToolCallPayload.approval` + `_encode/_decode_tool_calls`
- 前端：`chat-types.ToolCall.approval`，`ToolCallRow` 渲染闸门区

**主流程时序（ask → allow → 行内已授权）**：

```mermaid
sequenceDiagram
  participant U as 用户(IM)
  participant FE as 前端
  participant IM as IM
  participant GW as Gateway
  participant K as 内核 gate
  K->>GW: auto_mode_gate ask
  GW->>IM: permission.request
  IM->>FE: 待决卡（气泡内最下方）
  U->>FE: 点「允许」
  FE->>IM: POST /permissions/{rid} decision=allow_once
  IM->>GW: 转发决策
  GW->>K: submit_permission_decision
  K->>K: gate 放行，标 approval=user_allow
  K->>GW: tool_end 事件（带 approval）
  GW->>IM: tool_call_upserted/ completed（approval）
  IM->>FE: tool_call.approval=user_allow
  FE->>FE: 待决卡折叠；工具行闸门区显「已授权」
```

## 契约层增量 (delta-spec)

- kernel: `specs/kernel/spec.md` —— tool 执行事件新增 approval 标识（消费者可观察）
- im: `specs/im/spec.md` —— tool_call 的 REST/WS 序列化携带 approval
- gateway: `specs/gateway/spec.md` —— node 流式增量的 tool_call 携带 approval
- cli: no spec delta（CLI 不在本 unit 范围，内核新增可选字段对其无行为影响）

## 风险与回退

- **历史行兼容**：旧 tool_call 无 `approval` 字段 → 前端读 `undefined`，闸门区不显；denied 历史行回退读 `reason==="denied"`。无迁移、无破坏。
- **自动放行误标**：只有经用户卡决策的才标 `approval`，自动放行保持 null。若 gate 处无法区分用户/自动 allow，则 allow 半边降级（仅 deny 可标）——退回 spec 的「纯前端」边界。**此为唯一需在 M1 实现期验证的前提**，worker 确认 `auto_mode_gate` payload 能透出用户 allow 信号。
- **回滚**：approval 字段全栈可选、向后兼容；前端合一改动集中在 `message-pane`/`tool-calls-panel`/`permission-card`，回退即恢复气泡外渲染。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM | `stop_pidfile .im.pid` | `IM_JWT_SECRET=<unit专属> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" > .im.log 2>&1 & echo $! > .im.pid` | `curl -s 127.0.0.1:$IM_PORT/` 返回前端 |
| Gateway | `stop_pidfile .gateway.pid` | `PYTHONPATH=src python -m personal_assistant.main --config "$WT_CFG" --im-service-url http://127.0.0.1:$IM_PORT --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 出现 bound + agent 已同步 |
| 前端 dev（仅看 UI 时） | `stop_pidfile .vite.pid` | `cd src/IM/frontend && npm run dev -- --port $VITE_PORT --strictPort > .vite.log 2>&1 & echo $! > .vite.pid` | 打开 `:$VITE_PORT` 渲染聊天 |

> 推荐直接 `./scripts/e2e-up.sh` 一键起 IM+Gateway（自动分配端口/隔离 config/auto-bind），免手起。本 unit 改了内核+Gateway+IM+前端，reviewer 走旅程前须整栈重启，避免 stale binary。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-434-M1 | approval-unified-panel | — | A | 内核 `core/tools/registry.py`、`core/agent/tool_executor.py`、`core/types.py`、`platform/hooks/builtins/realtime_stream.py`；Gateway `personal_assistant/main.py`（tool_end 透传）；IM `domain/models.py`、`api/routes/messages.py`、`infra/repositories.py`；前端 `message-pane.tsx`、`tool-calls-panel.tsx`、`permission-card.tsx`、`tool-presentation.ts`、`chat-types.ts`、`styles/global.css`、`i18n/zh|en.json` | `[reviewer]` 工具调用与审批呈现在同一气泡内、气泡外无独立审批卡（覆盖 Req-技术动作收同一气泡）；`[reviewer]` 待决卡醒目可操作、已有已决时新待决与已决同时可见（Req-待决醒目 / Scenario-又来新待决）；`[reviewer]` 允许后行内显「已授权」、拒绝后显「已拒绝」+ 未执行（Req-折叠并入）；`[reviewer]` 收起态显「N 次授权·X 允许·Y 拒绝」、空态无授权后缀（Req-工具行形态）；`[reviewer]` 授权后失败时「已授权」与失败报错各占一侧（Req-行内分区 / 关键边界）；`[reviewer]` 中/英界面失败文案随语言（Req-失败文案随语言）；`[worker]` `approval` 字段贯穿 内核→Gateway→IM→前端，IM REST 历史与 WS 均携带（单测：IM encode/decode round-trip、Gateway 透传）；`[worker]` 前端单测覆盖 ToolCallRow 闸门/结果分区 + denied 去重 + 已决并入；`[worker]` `failTag` 经 i18n，zh/en 各出对应文案；`[worker]` `npm run test` + `pytest -m "not e2e"` 全绿 |

> 单 M1 举证：本 unit 是一条端到端垂直切片——`approval` 标识必须从内核 gate 一路流到前端才能显示「已授权」，无法在不破坏该链路的前提下并行；按 §4.3「后端/前端」横切被禁止。文件数偏多但属同一不可分割链路，单 worker 串行完成。

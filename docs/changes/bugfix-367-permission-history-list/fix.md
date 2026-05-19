# bugfix-367: permission ask 交互三连缺陷（卡片内不显示工具/参数、UI 误显 running、历史丢失 + 卡在前次 resolved）

## Relations

- Related: feat-333（auto-mode classifier / 权限 ask 流首版）

## 原始报告

> http://127.0.0.1:8011/chat/8ba84eee58074bf5b06388c9560c4a2b 好像不太符合预期，我的预期是一轮 llm 工具调用和文字输出放在一个泡中，但是实际上我看 llm proxy 的日志，llm 第一轮就调用了一个 bash，第二轮调用两个，为啥他这里一个泡放了三个工具。你看一下现在的逻辑是什么？

> 哦，我漏考虑了这个情况。如果新的一轮只有工具调用没有文本，确实应该合并到上一个泡泡。我重新说。我的预期是一轮 llm 工具调用和文字输出放在一个泡中，如果没有文本，只有工具调用则合并到上一个泡，不新增泡。直到有文本输出的一轮，新建泡泡。

> 但是现在还是有问题，第一轮他 ask 我了，我同意了，第二轮他又想 ask 我，但是页面还是卡在前一轮 ask 完成，等我刷新后才看到新的请求框

> 那为啥之前这些多个历史的都能看到（附截图：上一会话三轮各自带文字，两个"已允许"卡片独立保留）

> 改列表好点 ... 我得看到我按了多少个同意吧

> 现在很诡异是。这个申请权限的框，看不到它具体要执行什么命令。我要点开上面的工具调用详情。然后他现在正在请求我的 permission 呢。但上面又写着正在运行中，很怪。我自己设想是先弹出这个 permission 的窗口，呃，permission 的窗口里面能够看到它是申请什么工具，然后工具传参是什么。然后等我同意了之后，上面的工具调用才刷新出这个工具 running。因为在我同意之前，他压根没有 run。如果我拒绝的话，它就刷新出是"x"。

> 工具调用还有结果渲染呢，这个你漏了。但是整体思路没问题了

> 不用兼容过去的，当前是开发态。

## 澄清记录

- Q1: 工具-only 轮怎么处理泡边界？
  A(原话): 我的预期是一轮 llm 工具调用和文字输出放在一个泡中，如果没有文本，只有工具调用则合并到上一个泡，不新增泡。直到有文本输出的一轮，新建泡泡。
  Agent 解读: 现有合并行为（content="" 早返回，不拆泡）符合预期，保留。

- Q2: 同一泡里多次 ask，历史保留方式？
  A(原话): 改列表好点 ... 我得看到我按了多少个同意吧。
  Agent 解读: 用户希望每次 ask 在泡里独立保留（一条已允许/已拒绝小条 + 当前 pending 卡），而不是后写覆盖前写。

- Q3: pending 权限框是否需要直接显示要执行什么工具 / 什么参数？
  A(原话): 现在很诡异是。这个申请权限的框，看不到它具体要执行什么命令。我要点开上面的工具调用详情。…我自己设想是先弹出这个 permission 的窗口，permission 的窗口里面能够看到它是申请什么工具，然后工具传参是什么。
  Agent 解读: pending 卡内必须直接展示 `tool_name` + 完整 `tool_input`；用户不该为了看到要授权什么去点开"上面的工具调用详情"。多参工具一视同仁全展示（JSON 化），与 `tool-calls-panel.tsx` 的 INPUT 区口径一致。bash/task/agent 工具的 LLM 入参里有 `description` 字段，应作为人类可读摘要醒目展示。

- Q4: 用户决策完成前，泡内工具调用面板是否应该显示 running？
  A(原话): 然后他现在正在请求我的 permission 呢。但上面又写着正在运行中，很怪。…然后等我同意了之后，上面的工具调用才刷新出这个工具 running。因为在我同意之前，他压根没有 run。如果我拒绝的话，它就刷新出是"x"。
  Agent 解读: 决策前泡内不应出现该工具的调用行；允许后才显示 running → completed；拒绝后直接显示 ✕（denied），且应配 OUTPUT（"permission denied — tool was not executed"）让用户明白没结果不是 bug。

- Q5: 历史数据是否需要兼容？
  A(原话): 不用兼容过去的，当前是开发态。
  Agent 解读: DB schema、协议、前端类型可以做无缝替换式重构，不需要保留旧 dict 形态的读路径兼容；测试若有旧 fixture 直接更新。

## 现象 / 复现

复现会话：`http://127.0.0.1:8011/chat/8ba84eee58074bf5b06388c9560c4a2b`

**触发链路**：一次用户提问 → agent 在 N 轮里反复调工具，其中至少有一轮"无文字、纯工具"且工具触发了 auto_mode_gate ask；后续又有一轮再次触发 ask。

**用户可观察的四个症状**（按严重程度从高到低）：

1. **泡内显示"运行中"，但实际还在等用户授权**。pending 权限卡出现的同时，泡内"X 次工具调用 · 运行中"已经亮起脉冲——agent 根本没开始执行（gate 还 park 在 ask），但 UI 误导用户以为工具已经在跑。
2. **pending 权限卡里看不到要执行什么命令 / 参数**。卡里只显示工具名 + 一句话问题文案，不显示 `tool_input`。用户被迫去点开泡内的"工具调用详情"才看得到要授权的真实内容；而那个详情区根据 § 1 实际是空的（工具还没真的跑），用户无从决策。
3. **第二次 ask 的请求框出不来**。第一轮 ask 用户点了"允许"后，第二轮 agent 又想 ask，但页面一直停在第一次的"✓ 已允许"小条上，按钮组不重新出现；只有**手动刷新页面**才看到新的 pending 请求框。
4. **历史 ask 痕迹丢失**。即使刷新后，也只能看到最新那次 ask 的状态——之前按过的"允许 / 拒绝"在同一个泡里完全找不到，用户无法回看自己在这次 agent 思考过程里授权过多少次、分别授了什么。

对比正常场景（用户提供的另一会话截图）：每轮 LLM 都同时输出文字 + 1 个工具时，每轮各自落在独立泡里，两次 ask 各自留下"已允许 · bash"和"已允许 · write"小条，互不覆盖——这是用户期望的视觉效果。出问题的会话差异在于：中间出现了"无文字、纯工具"的轮次，按既定的"工具-only 合并到上一泡"规则合并到同一泡，从而暴露了"同泡多 ask"这条路径上的所有缺陷。

## 根因

四个独立缺陷，按现象 1~4 一一对应。

**根因 1：kernel 把 observe "tool_call" 的触发位置放错了——在 intercept gate 之外**

`auto_mode_gate.py:818` 与 `realtime_stream.py:99` 都注册在 `tool_call` hook 上，priority 分别是 20 和 1000，看起来应该按序 fire。但深挖一层：

- `auto_mode_gate` 是 **intercept** 类，由 `registry.execute()` 在 `tool_executor._execute_one` → `registry.execute()` → 内部 `_dispatch_intercept("tool_call", ...)`（`registry.py:130`）触发。它会 park 等用户决策。
- `realtime_stream.on_tool_call` 是 **observe** 类，由 `loop.py:302` `await self._dispatch_tool_call_hook(tc, ...)` 触发（这条调用的是 `dispatch_observe_async`，**不是** intercept）。

两条触发路径**完全独立**，priority 排序不跨类生效。`loop.py:283` 一拿到 LLM 返的工具调用就立刻：

```python
executor.add_tool(tc)                     # 后台 task 开始走 registry.execute，gate 在那里 park
await self._dispatch_tool_call_hook(tc)   # 主线立刻 fire observe → realtime_stream → tool_start SSE
```

结果：`tool_start` SSE 在 gate park **之前**就发到前端，前端 reducer 把 `tool_call_upserted(status="running")` 写进 message.tool_calls，工具调用面板亮起"运行中"——而真正的执行还没开始。

为什么这种错能进来：feat-333 实施 gate 时把 gate 挂在了 registry 的 intercept 链上（正确），但 observe 的发射点没有同步迁移；当时不存在"ask 流"，所有 tool 立刻执行，发射时机错位看不出问题。auto_mode_gate 上线后这个错位才暴露。

**根因 2：PermissionCard 不渲染 tool_input**

`src/IM/frontend/src/features/chat/v2/components/permission-card.tsx` pending 分支只渲染 `tool_name` + `question` + 按钮组，**没有显示 `tool_input`**。`global.css` 里其实早就备好了 `.chat-permission-cmd` 这个深色 mono 块样式，但组件没用上。结果用户必须去点"上面的工具调用详情"看参数——而根因 1 又让那里的详情区是空的（工具还没真跑）。两个缺陷叠加直接让用户无法决策。

为什么这种错能进来：feat-333 完成时假设用户能通过"工具调用详情"看到参数，没意识到这是个二跳；mockup 里也没把 input 放进卡内。

**根因 3：PermissionCard 内部状态不响应 prop 变化**

`permission-card.tsx:63` 用 `useState(() => initialState(request))` 初始化卡片内部状态。`useState` 的 initializer 只在首次 mount 跑一次。第一次 ask resolved 后内部 `cardState = { kind: "resolved" }`；当 reducer 把消息上的 `permission_request` 覆盖为新的 pending 对象时，组件 re-render 拿到了新 prop，但内部 state 没有任何同步逻辑，仍渲染为 resolved。刷新页面 → 组件重新挂载 → initializer 重跑 → 看到新的 pending → 显示正常。所以"刷新才看得到"。

为什么这种错能进来：feat-333 设计时只考虑了"同一 message 上一次 ask 的 pending → resolved"状态机，没考虑"同一 message 上前一个 ask 已 resolved、又来一个新 ask"的状态机切换。`useState` 派生 prop 是 React 经典反模式，code review 阶段没识别。

**根因 4：存储与协议层对"同一 message 多次 ask"是覆盖式**

- `src/IM/infra/repositories.py:1157` `update_permission_request` 是 upsert 覆盖：同一 message 的 `permission_request_json` 列只能存一份 dict，第二次 ask 写入时直接覆盖第一次的 resolved 记录。
- `src/IM/application/event_bridge.py:209` `on_permission_request` 调用上面的覆盖方法。
- `src/IM/domain/models.py:233` 与 `src/IM/api/routes/messages.py:104` REST 响应字段是 `permission_request: dict | None`，语义上就只能承载一条。
- 前端 `src/IM/frontend/src/features/chat/v2/chat-types.ts:61` `permission_request?: PermissionRequest | null` 同上；reducer `chat-stream-reducer.ts:106` 的 `permission.request` 处理也是直接覆盖 `permission_request: ev.permission_request`。

为什么这种错能进来：feat-333 立项时"工具-only 轮合并到上一泡"这条规则还没明确（其 spec 假设每个 ask 都挂在不同的 message 上），所以协议设计是 1:1。后来桥接层 `personal_assistant/main.py:1764` 加入"content="" 早返回不拆泡"的合并行为后，1:1 假设就被打破了，但权限协议层没有跟上。

## 修复

> 范围说明：当前为开发态，**不做数据兼容**——DB schema、内核协议、前端类型字段一并替换式重构，旧 dict 形态的存量行 / 旧字段名引用一律不保留读路径。涉及的测试 fixture 同步更新。

### 一、kernel：observe `tool_call` 迁到 intercept gate 通过之后（对应根因 1）

- `src/agent/core/tools/registry.py` `execute()`：在 `_dispatch_intercept("tool_call", ...)`（line 130）拿到结果后：
  - 通过 → `dispatch_observe_async("tool_call", {...})` 发出（payload 与现在 loop.py 等效）→ 继续执行
  - block → 合成 `ToolResult(error="permission denied: <reason>", ...)` → 走正常的 `dispatch_observe_async("tool_result", ...)` 路径（→ `realtime_stream.on_tool_result` → `tool_end(status="failed")` SSE → 前端按现有路径渲染 ✕ 行 + OUTPUT 区，零特殊路径）→ return 不实际执行
- `src/agent/core/agent/loop.py:302` 删除 `await self._dispatch_tool_call_hook(tc, active_hook_ctx, run_id)`；`_dispatch_tool_call_hook` 私有方法如不再被其他调用则一并清除
- 现有 `tool_call` hook 消费者只有 `auto_mode_gate`（intercept）和 `realtime_stream`（observe），无其他模块依赖（已 grep 确认），迁移安全

### 二、IM 持久化协议改 list 语义（对应根因 4，无兼容）

- `src/IM/infra/repositories.py`：
  - 删 `update_permission_request`，改为 `append_permission_request(message_id, permission_data)`：读 list → 按 `request_id` 去重 append；列里**只存 list**，不接受 dict
  - 新增 `update_permission_resolution(message_id, request_id, decision)`：list 内按 `request_id` 定位改 status/decision
  - `_message_from_row`：直接解析为 list，dict 形态视为坏数据
- `src/IM/domain/models.py` `Message.permission_request: dict | None` → `permission_requests: list[dict]`（默认 `[]`）
- `src/IM/api/routes/messages.py` 同步改字段名
- `src/IM/application/event_bridge.py` 两个方法 call 新仓库 API；WS 事件 payload 形状不变（仍是单条），由前端 reducer 负责追加/查找

### 三、前端

#### 类型与状态（对应根因 4）

- `src/IM/frontend/src/features/chat/v2/chat-types.ts`：`permission_request?` → `permission_requests: PermissionRequest[]`
- `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts`：
  - `permission.request`：从覆盖改为按 `request_id` 去重 append
  - `permission.resolved`：按 `request_id` 在 list 中定位、改 status/decision

#### 渲染（对应根因 2 + 3 + 4，对齐 demo.html 三处 § A/§ B/§ C）

- `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`：
  - 由单卡渲染改为 `message.permission_requests.map(req => <PermissionCard key={req.request_id} request={req} ... />)`
- `src/IM/frontend/src/features/chat/v2/components/permission-card.tsx`：
  - § A pending 分支新增 description 行（仅 `tool_input.description` 存在时；bash/task/agent 有此字段）+ `<pre class="chat-permission-cmd">{JSON.stringify(stripDescription(tool_input), null, 2)}</pre>`（复用既有 CSS）
  - 去掉 `useState(() => initialState(request))` 反模式：resolved 分支由 `request.status === "resolved"` 直接派生；只保留 submitting / error 真正的临时态

> § B（tool_call 决策后才显示 running / 拒绝直接 ✕ + denied output）由"一、kernel"自然满足，前端 `tool-calls-panel.tsx` 不需要任何改动。

### 提交粒度

按 M1 单 milestone（lite 路径），建议三个 commit：

- `test(bugfix-367/M1): 红测覆盖 kernel observe 时序 + IM list 存储 + 前端多卡堆叠`
- `fix(bugfix-367/M1): observe tool_call 迁入 registry + permission_requests 列表化 + 卡内 input 渲染`
- `docs(bugfix-367/M1): 回填修复 / 验证`

## 验证

### 自动化

- `tests/agent/unit/test_tool_executor.py`：
  - 用例 A：gate 通过 → observe `tool_call` 在 registry execute 内、对应 `realtime_stream` 看到 `tool_start` SSE 仅一次且在执行真正开始时
  - 用例 B：gate deny → 不发 `tool_start`，但发出 `tool_result(error="permission denied: ...")`，前端 SSE 收到 `tool_end(status="failed")`
- `tests/im_service/unit/test_repositories.py`：append 去重、resolution 按 id 更新、读取永远是 list
- `tests/im_service/unit/test_event_bridge.py`：连续两次 ask + 一次 resolve，list 内两条都留存且状态正确
- `src/IM/frontend/src/features/chat/v2/components/permission-card.test.tsx`：
  - description 行只在有 `tool_input.description` 时出现
  - raw input 区显示完整 `JSON.stringify` 多参
  - 多次新请求时新卡显示 pending（删除 stale-state 反例测试，添加按 key remount 行为测试）
- `chat-stream-reducer.test.ts`：覆盖 → 追加语义切换，按 `request_id` 去重；resolved 不改其它条目
- `message-pane.test.tsx`：同 message 渲染多张卡，顺序与 `permission_requests` 一致

### 手动（修前能复现 / 修后通过）

1. 启动 IM + Gateway + 注册 nano 账号 → 新建 agent
2. 发"删了 hello.py 再 write 进去一次"诱导多轮工具调用且有 ask 的链路
3. 修前确认：pending 卡里看不到命令、上方面板显示"运行中"、第二次 ask 不自动出现、刷新只剩最新一次
4. 修后确认：pending 卡内直接显示命令 + 参数；决策前面板不显示 running；决策后 allow → running → completed，deny → 立即 ✕ 行 + "permission denied — tool was not executed" OUTPUT；同泡多次 ask 历史小条全部保留

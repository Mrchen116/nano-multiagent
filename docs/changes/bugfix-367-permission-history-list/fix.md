# bugfix-367: 同一 agent 泡里多次 permission ask 历史丢失 + 卡在前一次 resolved 状态

## Relations

- Related: feat-333（auto-mode classifier / 权限 ask 流首版）

## 原始报告

> http://127.0.0.1:8011/chat/8ba84eee58074bf5b06388c9560c4a2b 好像不太符合预期，我的预期是一轮 llm 工具调用和文字输出放在一个泡中，但是实际上我看 llm proxy 的日志，llm 第一轮就调用了一个 bash，第二轮调用两个，为啥他这里一个泡放了三个工具。你看一下现在的逻辑是什么？

> 哦，我漏考虑了这个情况。如果新的一轮只有工具调用没有文本，确实应该合并到上一个泡泡。我重新说。我的预期是一轮 llm 工具调用和文字输出放在一个泡中，如果没有文本，只有工具调用则合并到上一个泡，不新增泡。直到有文本输出的一轮，新建泡泡。

> 但是现在还是有问题，第一轮他 ask 我了，我同意了，第二轮他又想 ask 我，但是页面还是卡在前一轮 ask 完成，等我刷新后才看到新的请求框

> 那为啥之前这些多个历史的都能看到（附截图：上一会话三轮各自带文字，两个"已允许"卡片独立保留）

> 改列表好点 ... 我得看到我按了多少个同意吧

## 澄清记录

- Q1: 工具-only 轮怎么处理泡边界？
  A(原话): 我的预期是一轮 llm 工具调用和文字输出放在一个泡中，如果没有文本，只有工具调用则合并到上一个泡，不新增泡。直到有文本输出的一轮，新建泡泡。
  Agent 解读: 现有合并行为（content="" 早返回，不拆泡）符合预期，保留。

- Q2: 同一泡里多次 ask，历史保留方式？
  A(原话): 改列表好点 ... 我得看到我按了多少个同意吧。
  Agent 解读: 用户希望每次 ask 在泡里独立保留（一条已允许/已拒绝小条 + 当前 pending 卡），而不是后写覆盖前写。

## 现象 / 复现

复现会话：`http://127.0.0.1:8011/chat/8ba84eee58074bf5b06388c9560c4a2b`

**触发链路**：一次用户提问 → agent 在 N 轮里反复调工具，其中至少有一轮"无文字、纯工具"且工具触发了 auto_mode_gate ask；后续又有一轮再次触发 ask。

**用户可观察的两个症状**：

1. **第二次 ask 的请求框出不来**。第一轮 ask 用户点了"允许"后，第二轮 agent 又想 ask，但页面一直停在第一次的"✓ 已允许"小条上，按钮组不重新出现；只有**手动刷新页面**才看到新的 pending 请求框。
2. **历史 ask 痕迹丢失**。即使刷新后，也只能看到最新那次 ask 的状态——之前按过的"允许 / 拒绝"在同一个泡里完全找不到，用户无法回看自己在这次 agent 思考过程里授权过多少次、分别授了什么。

对比正常场景（用户提供的另一会话截图）：每轮 LLM 都同时输出文字 + 1 个工具时，每轮各自落在独立泡里，两次 ask 各自留下"已允许 · bash"和"已允许 · write"小条，互不覆盖——这是用户期望的视觉效果。出问题的会话差异在于：中间出现了"无文字、纯工具"的轮次，按既定的"工具-only 合并到上一泡"规则合并到同一泡，从而暴露了"同泡多 ask"这条路径上的两个缺陷。

## 根因

两个独立缺陷叠加：

**根因 A：PermissionCard 内部状态不响应 prop 变化**

`src/IM/frontend/src/features/chat/v2/components/permission-card.tsx:63` 用 `useState(() => initialState(request))` 初始化卡片内部状态。`useState` 的 initializer 只在首次 mount 跑一次。第一次 ask resolved 后内部 `cardState = { kind: "resolved" }`；当 reducer 把消息上的 `permission_request` 覆盖为新的 pending 对象时，组件 re-render 拿到了新 prop，但内部 state 没有任何同步逻辑，仍渲染为 resolved。刷新页面 → 组件重新挂载 → initializer 重跑 → 看到新的 pending → 显示正常。所以"刷新才看得到"。

为什么这种错能进来：feat-333 设计时只考虑了"同一 message 上一次 ask 的 pending → resolved"状态机，没考虑"同一 message 上前一个 ask 已 resolved、又来一个新 ask"的状态机切换。`useState` 派生 prop 是 React 经典反模式，code review 阶段没识别。

**根因 B：存储与协议层对"同一 message 多次 ask"是覆盖式**

- `src/IM/infra/repositories.py:1157` `update_permission_request` 是 upsert 覆盖：同一 message 的 `permission_request_json` 列只能存一份 dict，第二次 ask 写入时直接覆盖第一次的 resolved 记录。
- `src/IM/application/event_bridge.py:209` `on_permission_request` 调用上面的覆盖方法。
- `src/IM/domain/models.py:233` 与 `src/IM/api/routes/messages.py:104` REST 响应字段是 `permission_request: dict | None`，语义上就只能承载一条。
- 前端 `src/IM/frontend/src/features/chat/v2/chat-types.ts:61` `permission_request?: PermissionRequest | null` 同上；reducer `chat-stream-reducer.ts:106` 的 `permission.request` 处理也是直接覆盖 `permission_request: ev.permission_request`。

为什么这种错能进来：feat-333 立项时"工具-only 轮合并到上一泡"这条规则还没明确（其 spec 假设每个 ask 都挂在不同的 message 上），所以协议设计是 1:1。后来桥接层 `personal_assistant/main.py:1764` 加入"content="" 早返回不拆泡"的合并行为后，1:1 假设就被打破了，但权限协议层没有跟上。

## 修复

<!-- worker 回填 -->

## 验证

<!-- worker 回填 -->

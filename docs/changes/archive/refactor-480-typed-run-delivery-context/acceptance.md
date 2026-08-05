# refactor-480 — 验收报告

> 对齐：motivation.md 的用户侧验收标准

> Validation snapshot: `02eb5cca7cadf52e68cd02c27cca51355b5c1bc7 → ff5b2f93e179b0324b1ca100714f8b3620787a13`

> Review round: 1 · mode: full · validated_at: `ff5b2f93e`

## Verdict

**fail**

**Highest Required Action:** `fix-implementation`

隔离真 IM + Gateway 与 freshly built Web IM 中，普通 direct、群聊 @、长回复的 provisional 到单一终态聚合、以及终态后的下一轮回复均可见；但要求调用 bash 的真实用户请求最终在聊天中显示了原始 `<tool_calls>…</tool_calls>` 标记，没有工具事件卡片、工具结果或后续 `TOOL_OK_REF480`。这直接违反本 unit 的“工具与权限事件穿过投递链”不变性，第一轮按严格门槛不能交付。

## User Journeys Exercised

1. **Direct baseline**：在 fresh Web IM 以 e2e 已绑定的 `nano` 测试用户打开 `plato` direct chat，发送 `REF480_DIRECT_20260805`，先看到 provisional agent bubble，随后看到 `DIRECT_OK_REF480` 终态。
2. **Tool delivery**：同一 direct chat 要求 `plato` 用 bash 执行 `printf TOOL_OK_REF480`。用户面没有卡片或结果，只看到完整原始 tool-call markup。
3. **Group / rolling / terminal cleanup**：创建 `REF480 Group`，`@plato` 正常回复 `GROUP_OK_REF480`；随后发送 30 项长回复，先有 provisional bubble，后在同一 Agent 回复位置完成并显示 `ROLL_END_REF480`；再发送 `REF480_CLEANUP_20260805`，得到干净的新一轮 `CLEANUP_OK_REF480`。
4. **External-channel availability check**：在该 Agent 的真实 Web IM `Channels` 页确认显示 “No external channels yet”；本轮隔离栈未提供 design runbook 所述的仓库测试 channel/fixture，未伪造外部通道或以源码/单测替代。

本轮服务接管：先执行 `e2e-down.sh`，使用主仓既有前端依赖在本 worktree fresh build `src/IM/frontend/dist/`，再按 runbook 启动 `e2e-up.sh`。实际 Web IM 首页资产为 `assets/index-e6lX1o-i.js` 与 `assets/index-BXWCVq0P.css`；IM `/openapi.json` 与 worktree IM/Gateway PID 均在旅程前健康。

## Reference Artifacts Reviewed

N/A。motivation/design 未引用前端原型、截图或 must-match 视觉 artifact。

## Issues

### R1-1 — 工具调用在聊天中泄漏为原始标记

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 用户请求 Agent 用 bash 执行 `printf TOOL_OK_REF480` 后，direct chat 最终消息是完整的 `<tool_calls><invoke name="bash">…</invoke></tool_calls>` 标记；没有工具执行卡片、完成结果或请求中的 `TOOL_OK_REF480`。这直接不满足 motivation.md “工具与权限事件穿过投递链”的 THEN，主交互可见结果不可接受。
- **Reproduction:** Web IM → `plato` direct chat → 发送 `REF480_TOOL_20260805: Use the bash tool to run printf TOOL_OK_REF480, then reply with exactly TOOL_OK_REF480.` → 等待终态。
- **Evidence:** 2026-08-05 01:41 Asia/Shanghai 的真实浏览器 DOM snapshot 中，左侧会话摘要与 Agent 气泡均显示 `<｜｜DSML｜｜tool_calls> … printf TOOL_OK_REF480 … </｜｜DSML｜｜tool_calls>`；页面没有 permission/tool card 或 `TOOL_OK_REF480`。

### R1-2 — 外部通道离线回归无法在承诺的 runbook 环境中验收

- **Severity:** major
- **Regression Relation:** unclear
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** design.md Runbook for Reviewer 声明 external shadow 场景可使用仓库测试 channel/fixture；但本 worktree 的真实 Agent Channels 页面显示 “No external channels yet”。因此无法从真实外部入口验证“IM 离线不阻塞外部回复”，也不能把 Web IM 路径冒充为外部通道。
- **Evidence:** 2026-08-05 01:47 Asia/Shanghai 的 `plato` → Channels 页面，仅显示 “No external channels yet” 与 “Add channel”。

## 验收标准覆盖

### Requirement: 消息投递保持 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 普通 owner 对话 | motivation.md §消息投递保持 | Journey 1：真 Web IM direct 发送唯一 nonce 并等待终态 | `DIRECT_OK_REF480` 出现在 `plato` direct bubble，且含 Process/用量/elapsed terminal chrome | pass | 用户消息、provisional 与 final reply 均在同一 direct thread 可见。 |
| Shadow 与 rolling 路径 | motivation.md §消息投递保持 | Journey 3：真 Web IM group @ 提及 + 长 30 项回复 | `GROUP_OK_REF480`；long reply 从空 provisional bubble 聚合为同一位置的 `ROLL_END_REF480` | pass | Scenario 写为 shadow **或** rolling；本轮以 group rolling 条件实际覆盖，且之后下一轮仍可启动。 |
| IM 离线不阻塞外部 channel | motivation.md §消息投递保持 | Journey 4：检查 runbook 要求的真实 external fixture | Agent Channels 页面无任何 external channel，无法由外部用户发入或观察回发 | inconclusive | 必验前置未落实；见 R1-2。没有用 API 200、单测或源码替代。 |

### Requirement: 交互事件保持 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工具与权限事件穿过投递链 | motivation.md §交互事件保持 | Journey 2：真实 direct prompt 明确要求 bash 工具 | 用户面显示原始 `<tool_calls>` 标记，没有工具/权限卡片或终态结果 | fail | R1-1。权限卡片也未出现，无法继续 approve/deny 路径。 |
| 权限等待期间保持运行活性 | motivation.md §交互事件保持 | 通过 Journey 2 尝试到达权限等待 | 未生成可操作的 permission request/card | inconclusive | 不以短时普通回复代替 120s 等待期的 liveness 体验。 |
| IM 离线时 skill-created 仍同步配置 | motivation.md §交互事件保持 | N/A | N/A | not-applicable | THEN 是 Gateway 内部 side effect，非本 reviewer 的用户可观察验收面；应由 design/worker 行为契约与测试保护。 |

### Requirement: 清理和故障行为保持 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 运行结束、失败或取消 | motivation.md §清理和故障行为保持 | Journey 3 完成后立即开启下一轮 | completed 终态 `ROLL_END_REF480` 后，下一轮得到 `CLEANUP_OK_REF480`，无旧文本串入 | inconclusive | 正常 completed 清理可见；失败与取消的真实用户路径因 R1-1 未能形成可控工具/权限等待，未夸大为全终态通过。 |
| Gateway 关闭时排空已接收的投递 | motivation.md §清理和故障行为保持 | 尝试依据 runbook 规划 shutdown-with-detached-delivery | 无法在本轮真栈中建立可验证的 detached tool/permission terminal delivery | inconclusive | 不以进程健康检查或单测替代用户可见的 shutdown drain。 |

## Side Findings

- 在两次 pre-terminal DOM snapshot 中，消息输入框为 disabled；本轮未能建立一个持续可操作的长运行来判断它是否违反现有“运行中仍可插话 /stop”体验，因此没有将其定性为本 unit issue。
- 浏览器自动化宿主记录过与本地产品无关的 Statsig 网络超时；Web IM 本身正常加载、登录、发消息和接收回复，故未计入产品问题。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 是 runtime_delivery 内部表征收口，验收未发现跨包边界变化。
- [x] `docs/specs/gateway/`（长青行为契约层）：无需由 reviewer 直接更新；R1-1 是实现/验收失败，不应以文档追认。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；本 unit 未改变文档体系。

## Recommended Next Step

先派 `fix-implementation` 处理 R1-1，并让可复验的 worktree external channel/fixture 成为 R1-2 的实际前置；修复后本 reviewer 应对工具/权限、外部 IM-offline、失败/取消和 shutdown drain 做定向或完整复验。第一轮没有经验性证据支持 `revise-design`。

---

# Round 2 — 2026-08-05

> Validation snapshot: `3436854f9ef46b88ccd7b4ebbf92c86e4c256ce5`

> Review mode: targeted independent revalidation of tool delivery, ordinary direct delivery, and long-response terminal cleanup

## Round 2 Verdict

**fail**

**Highest Required Action:** `fix-implementation`

R1-1 is **closed**: with the design-specified nonempty temporary allowlist `bash,read`, a real Web IM conversation delivered `R2_TOOL_OK` as a normal final agent reply. The rendered reply contained `Process · 1 tool · 1 thinking` and token metadata, while the fresh browser DOM contained no raw `<tool_calls>` markup. This independently reproduces the corrected fixture precondition and does not indicate a refactor regression.

The overall verdict remains **fail** because the separately required external-channel / IM-offline scenario still has no isolated real fixture. The current design explicitly declares that absence an acceptance blocker and forbids substituting mock, source, unit test, or Web IM traffic for it. It is retained as a delivery-environment blocker, not reclassified as a product regression.

## Round 2 Real Journeys and Evidence

All observations used a freshly built Web IM and fresh IM + Gateway started from this worktree. Browser control logged in as the isolated e2e user, rendered the actual `plato r2 direct` chat, and observed every assertion below in the user-visible DOM. The authenticated public Web IM message endpoint was used only to submit messages after this browser controller's `Send` action failed to mutate the local app; API acceptance alone was never used as pass evidence.

1. **Corrected tool delivery — pass / R1-1 closed.** The temporary test-agent config visibly showed `Tool Allowlist` with `read` and `bash` selected. Prompt `REF480_R2_TOOL_20260805` requested `bash` to execute `printf R2_TOOL_OK`. At 03:18 Asia/Shanghai, the rendered direct chat showed one `R2_TOOL_OK` agent reply, the expandable `Process · 1 tool · 1 thinking` affordance, `2.7k tok · ctx 1%`, and no raw tool-call tag.
2. **Ordinary direct delivery — pass.** `REF480_R2_DIRECT_20260805` received exactly `R2_DIRECT_OK` as a subsequent normal agent reply (03:31 Asia/Shanghai), with its own terminal Process and token chrome; it did not merge with the preceding tool result.
3. **Long-response terminal aggregation and next-run cleanup — pass for the targeted terminal path.** `REF480_R2_ROLL_20260805` rendered a single structured 20-item response ending `R2_ROLL_END` (03:32), then the immediate next request rendered `R2_CLEANUP_OK` as a separate reply. A fresh 50-item request `REF480_R2_ROLLLIVE_20260805` likewise rendered one structured response ending `R2_ROLLLIVE_END` with terminal Process/token chrome (03:37). The browser received completed output before its first 300 ms live DOM sample, so this round does not claim an observed intermediate provisional update; it does establish the user-visible long-response terminal and clean successor path.
4. **External IM-offline path — blocked / inconclusive.** No separately supplied isolated external Feishu/Lark fixture or channel was available. Per the amended reviewer runbook, this cannot be replaced with this Web IM path or a mock.

## Round 2 Issue Disposition

### R1-1 — closed: original tool-markup observation was an empty-allowlist fixture precondition

- **Disposition:** closed
- **Regression Relation:** not a refactor regression
- **Evidence:** Round 2 journey 1’s real browser DOM has the `R2_TOOL_OK` final reply and rendered one-tool Process event, with no `<tool_calls>` text. The only changed test precondition is the explicit `tool_allowlist=["bash","read"]` required by the revised design runbook.
- **Conclusion:** an empty allowlist disables tools; raw model DSML in that state is not evidence that typed run delivery regressed.

### R2-1 — external-channel acceptance fixture remains unavailable

- **Severity:** blocking
- **Regression Relation:** unclear
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** provision the design-required, isolated, replayable real external-channel fixture before delivery. Until then, the required IM-offline / external-reply behavior cannot be verified in a product-faithful journey.
- **Evidence:** no external fixture credentials/channel were supplied to this review; the runbook explicitly marks this as an acceptance blocker and disallows substitutes.

## Round 2 Coverage Update

| Scenario | Round 2 result | Evidence / boundary |
|---|---|---|
| Ordinary owner direct conversation | pass | `R2_DIRECT_OK` is a distinct rendered direct-chat reply after the tool run. |
| Tool event crosses the delivery chain | pass | `R2_TOOL_OK`, `Process · 1 tool · 1 thinking`, terminal token UI, and no raw `<tool_calls>` in browser DOM. |
| Long-response terminal / clean next run | pass (targeted terminal path) | `R2_ROLL_END`, `R2_ROLLLIVE_END`, then separate `R2_CLEANUP_OK`; intermediate provisional state was not observable before completion. |
| Permission wait liveness | inconclusive | No safe real permission-request fixture was provided; no normal reply is used as a substitute. |
| External channel while IM is offline | inconclusive / blocking | Required real external fixture unavailable. |
| Failure/cancel and Gateway shutdown drain | inconclusive | Not re-run without a deterministic, product-faithful fixture. |

## Round 2 Recommended Next Step

Do not reopen R1-1. Provide the isolated real external-channel fixture promised by the reviewer runbook, then re-run the IM-offline external-reply scenario; retain the existing inconclusive boundaries for permission wait, failure/cancel, and shutdown drain until suitable real fixtures exist.

---

# Round 3 — 2026-08-05

> Validation snapshot: `aa97f18c38f96ead4b42fec61386ec1ac46785f2`

> Review mode: independent real external-channel / IM-offline revalidation

## Final Verdict

**pass**

The last open delivery-environment blocker is closed. Round 3 followed the corrected reviewer runbook: it rendered an ignored, isolated `feishu:plato` static test channel from the local test-Bot credentials, then used the already-authorized Lark **user** profile belonging to that same App to converse with the Bot. No credential, Lark/IM identifier, private config, generated runtime file, or nonce value is retained in this report.

R2-1 was an **unexecuted fixture-setup error in Round 2**, not evidence that the fixture was absent and not a refactor/product regression. The real fixture was available locally once the prescribed private static config was rendered and passed to `e2e-up.sh --main-config`.

## Scope and Materials Read

This round re-opened only the required external-channel / IM-offline scenario from `motivation.md`. It used the Round 3 runbook in `design.md`, the external-channel and delivery requirements in `docs/specs/gateway/external-channels.md`, and the isolated-runtime lifecycle contract in `docs/development/worktree-runtime.md`.

## Real User Journeys Exercised

1. **Online external reply.** The isolated IM + Gateway stack started from the private static test-channel config. The same-App authorized Lark user profile sent a unique plain-text nonce to the Bot in its 1:1 conversation. The Bot replied in that same real Lark conversation with the required nonce-derived terminal text.
2. **IM-offline external reply.** After the online reply, only this worktree's IM process was stopped. The IM HTTP endpoint and its dedicated port were both unreachable, while the unchanged worktree Gateway PID remained live. The same Lark user sent a second unique nonce to the same Bot; the Bot again replied in the same 1:1 conversation before IM was restored.

## Passes

- The external Bot received and replied to the online user message through the real Lark conversation.
- With IM demonstrably unavailable, Gateway retained external-channel autonomy and returned the second reply through the same real Lark conversation.
- The offline exercise did not rely on Web IM, a mock, a unit test, source inspection, or a restarted Gateway.
- The process/port checks establish that only IM was stopped; the Gateway that delivered the offline reply was the one that had handled the online reply.

## Issues

None in the Round 3 scope.

## R2-1 Disposition

- **Disposition:** closed as reviewer fixture setup omission
- **Regression Relation:** none
- **Evidence:** both online and IM-offline unique-message/reply journeys completed with the local real Bot fixture required by the corrected runbook.
- **Conclusion:** the former “fixture unavailable” statement resulted from not rendering and supplying the required ignored static config. It must not be carried forward as an implementation defect or external-environment blocker.

## Retest Focus

None for the external-channel / IM-offline path. Future changes that alter Gateway delivery ownership should repeat these two real-Lark journeys using fresh private runtime state.

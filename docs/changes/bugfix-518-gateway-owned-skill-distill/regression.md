# bugfix-518 — 回归验证

> 对齐: [incident.md](incident.md)

> Validation snapshot: `ff27a30b4 → e3d932524`

## Verdict

**fail**

**Highest Required Action:** `fix-implementation`

一条用户可见的必验场景（execution Agent 缺少 distiller 或 `skill_view`）没有可供独立 reviewer 使用的隔离
fixture，因此本轮不能确认它会显示预期的不可执行提示且不创建聊天。其余可观察主路径、跨 Gateway
限制、运行中限制和 source binding 失败路径都在真实双 Gateway 栈中通过。

## User Journeys Exercised

1. **同 Gateway 正常旅程**：用隔离 `nano` 用户登录 Web IM；以普通 direct message 建立完成的 `e2e`
   来源会话，选择它和 `e2e` execution Agent 的 Agent scope，创建 distill chat，发送预填消息并等待普通
   Agent 结果。
2. **选择边界旅程**：在同一双 Gateway 栈中，选择第一个来源后检查第二 Gateway 来源不可选；同时检查
   running 来源不可选。
3. **本机来源不可解析旅程**：选择一个没有 local session binding 的同 Gateway 来源，进入 dialog 并开始
   蒸馏，检查错误留在 dialog 且不创建聊天。
4. **普通浏览回归**：退出选择模式，并检查列表恢复为普通会话浏览外观。

## Reference Artifacts Reviewed

| Reference | Contract checked | Actual evidence | Result |
|---|---|---|---|
| `prototype.html` | 已选来源后的 checkbox、跨 Gateway / running 禁选原因、distill dialog、普通 composer/result 仍是既有聊天旅程 | 2026-08-09, isolated Vite `127.0.0.1:55035`, default desktop 1280×720 browser captures: selection mode and completed normal-chat result | pass — functional/layout relationship agrees; this prototype does not prescribe the production dark-theme tokens. |

Browser captures were reviewed in the isolated acceptance session and deliberately not retained in the repository, per the
worktree runtime rule against committing screenshot caches.

## 验收标准覆盖

### Requirement: 历史会话蒸馏 conversation 选择入口

| Scenario | 期望来源 | 验证方式与证据 | Result | 备注 |
|---|---|---|---|---|
| 选择第一个来源后锁定同一 Gateway | `specs/im/web-chat-ux.md` | 在真实双 Gateway Web IM 中选择 completed `Review source: fast same Gateway` 后，两个第二 Gateway 来源显示 **Different Gateway** 且 checkbox disabled；同节点但 running 的来源显示 **Running** 且 disabled。 | pass | 同屏 screenshot 与 DOM 均确认。 |
| Gateway 返回当前格式 prompt 后预填普通聊天 | `specs/im/web-chat-ux.md` | 点击 Start distillation 后浏览器进入 `Skill distill · e2e` direct chat；composer 原样显示 slash command、`source_jsonl_paths`、`execution_agent_id: e2e`、`target_scope: agent`。点击 Send 后，普通 Agent 气泡报告读取该 session file，并因一轮 ping 不足而不创建 skill。 | pass | 用户可见的普通聊天完成结果证明 returned draft 可沿既有旅程执行；client node hint 的优先级属于非用户可观察实现语义。 |
| execution Agent 不具备 distiller 或 skill_view 时不创建空聊天 | `specs/im/web-chat-ux.md` | 本轮隔离配置只提供具备这两项能力的 execution Agents；runbook 未提供不具备能力的同节点 Agent，reviewer 不改写运行配置或源码来伪造此状态。 | inconclusive | 见 AR-1。 |
| 取得 prompt 失败时不创建空聊天 | `specs/im/web-chat-ux.md` | 选择没有 local session binding 的同 Gateway 来源并开始蒸馏。dialog 留在原处，显示 `source session binding is unavailable`；列表中没有新 `Skill distill` chat，亦未出现普通消息。 | pass | 覆盖“不能为 source 解析本机 path”分支。 |
| 普通 sidebar 浏览不显示蒸馏选择状态 | `specs/im/web-chat-ux.md` | 从选择模式返回到正常 chat；列表恢复为普通 rows，不显示 checkbox、Running 或 Different Gateway 标签。 | pass | 完成普通 distill chat 后再次确认。 |

### Requirement: Gateway 为同节点历史会话生成 distill prompt

| Scenario | 期望来源 | 验证方式与证据 | Result | 备注 |
|---|---|---|---|---|
| 本机 binding 生成可直接预填的 prompt | `specs/gateway/relay-protocol.md` | 上述真实浏览器主旅程显示预填 prompt，后续普通 Agent 结果明确报告读取同一个 session file。 | pass | Gateway 内部不读 transcript / 不启动模型的约束本身不是用户面可观察项。 |
| 任一 source 不能解析时不返回部分 prompt | `specs/gateway/relay-protocol.md` | 同 Gateway 无 binding 来源给出完整、可理解错误，而非半个 composer draft。 | pass | 内部 request_id/node_id 相关性为实现层，未由产品 reviewer 验证。 |
| execution Agent 缺少 distiller 能力时不返回 prompt | `specs/gateway/relay-protocol.md` | 与上方 Web IM capability 场景相同：没有可独立操作的缺能力 fixture。 | inconclusive | 见 AR-1。 |
| 已有 external shadow source 沿用 external binding | `specs/gateway/relay-protocol.md` | not-applicable | not-applicable | 此条是 external shadow binding 的协议/实现场景；本 unit 的用户面验收材料没有外部 channel 旅程。 |

## Issues

### AR-1 — 缺能力 execution Agent 的用户失败态未获独立实证

- **Severity:** major
- **Regression Relation:** unclear
- **Observed / expected:** 规格要求用户选择缺少 `conversation-skill-distiller` 或 `skill_view` 的 execution Agent
  时，在 dialog 看见不可执行原因且没有空聊天。本轮双 Gateway 隔离环境只配置了具备能力的 Agents；没有可在不改写
  配置/源码的前提下建立缺能力 Agent 的受控 fixture，因而无法看到这个用户结果。
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 这是本 unit 明确的必验用户场景。交付前需要提供可由独立 reviewer 正常启动的受控缺能力
  fixture，或以其他不污染实现的产品入口证明该 dialog 状态；当前不能由测试通过替代用户面证据。

No GitHub issue was filed: this is in-unit acceptance evidence, not an out-of-unit defect.

## Side Findings

None. The completed normal chat had no browser console warnings or errors. The ordinary distiller correctly declined to
write a skill for the intentionally trivial one-turn source; that is expected skill behavior, not a distillation failure.

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；IM↔Gateway 的既有职责边界未变。
- [x] `docs/specs/<包>/`（长青行为契约层）：需要在 close-out 将本 unit 的 IM/Gateway delta 合并入 canonical specs；当前 delta 已存在，reviewer 未改写它。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；本 unit 未改变文档体系。

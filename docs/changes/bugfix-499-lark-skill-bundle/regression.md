# bugfix-499 — 回归验证

> 对齐: `incident.md`
>
> Validation snapshot: `9a6d2e5493220c278242d38ca3c8ed1f64226fb1 → a58c487b1940ef4dfe6179ab0fdaf5f04050dcff`
>
> Review round: 1 (full)

## Verdict

**fail** — 本轮没有安全可用的隔离 Feishu fixture，因而不能让真实用户完成任一必验的 Feishu → Gateway → Lark/IM 旅程。没有把空栈 health、mock、单测或现有主/生产实例当成产品验收证据。

**Highest Required Action:** `fix-implementation`，仅表示 unit 在产品门禁尚未关闭前不能交付；所需动作是提供设计 Runbook 指定的隔离 fixture 后重新验收，**不是**基于本轮提出代码归因或要求实现改动。

## 验收前置与服务接管

已按 Runbook 核对本次运行所需的受控入口、隔离要求与清理方式。Runbook 明确要求一个仓外、权限为 `0600` 的 `FEISHU_E2E_MAIN_CONFIG`，以及专用测试 tenant、测试用户、最小权限的 `lark-cli` user identity、可收消息的测试 Bot、当前 chat 和另一目标 chat。

该 fixture 未随本次验收提供，也未发现可安全认定为上述专用 fixture 的路径。为避免误用日常/生产 config、凭据、Lark 资源或持久服务：

- 未启动 IM、Gateway、Vite 或任何空栈；
- 未读取、复制或修改主/生产 config、凭据、聊天或资源；
- 未以 mock、health check、单测、实现阅读或已有服务状态替代真实 Feishu 产品旅程。

因此不存在可用的服务指纹、截图或录屏证据；这是本轮阻塞的原因，而非“未检查”。

## User Journeys Exercised

无。以下计划好的真实旅程全部在启动前被 fixture 门槛阻断：

1. 静态显式 allowlist 的测试 Bot 完成 `fixture ping`，随后在当前 chat 请求只读 Lark 操作并核对用户身份/授权提示。
2. 同一当前 chat 先请求普通回复，再明确指定另一隔离 chat 发送唯一 marker；同时核对当前 chat 的 Gateway 回复与 IM shadow。
3. fresh-IM 托管测试 Bot 完成 `fixture ping` 后重复上述旅程，并在设置页建立受控 Feishu channel。
4. 空 allowlist agent 的 bundle 发现，以及用户明确要求独立 Lark 事件监听。

## 验收标准覆盖

### Requirement: 飞书绑定 agent 可使用完整 Lark 能力

| Scenario | 期望来源 | 计划验证方式 | 证据 | 结果 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 用户从飞书请求 Lark 资源操作 | `incident.md` “用户从飞书请求 Lark 资源操作” | 以隔离测试用户从静态和托管 Bot 的当前 chat 发起只读 Lark 请求，观察 agent 的可发现能力与实际指导 | 无；隔离 tenant、Bot、chat 与 user identity 未提供 | inconclusive | 不能用本地资源目录、测试结果或模拟 channel 证明用户从飞书能完成操作。 |
| Lark CLI 未安装或尚未授权 | `incident.md` “Lark CLI 未安装或尚未授权” | 在受控 fixture 中请求 Lark 操作，观察缺 CLI/缺授权时的用户可见提示且不伪称成功 | 无；不能安全构造/切换真实 fixture 身份 | inconclusive | 不把文档文字或内部测试当成用户提示成立的证据。 |

### Requirement: 飞书对话回复保持 Gateway 所有权

| Scenario | 期望来源 | 计划验证方式 | 证据 | 结果 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 当前飞书对话产生普通助手回复 | `incident.md` “当前飞书对话产生普通助手回复” | 在当前隔离 chat 请求 `gateway-normal-ok`，观察原 chat 回复和同轮 IM shadow | 无；真实当前 chat 与可收消息 Bot 未提供 | inconclusive | 空 IM/Gateway 栈或 API/单测无法证明当前用户实际收到 Gateway 回写。 |
| 用户明确要求操作另一段 Lark 聊天 | `incident.md` “用户明确要求操作另一段 Lark 聊天” | 从当前 chat 指定另一隔离 chat 并发送唯一 marker；观察目标 chat marker、当前 chat 结果说明和 IM shadow | 无；两条隔离 chat 与真实 Lark 身份未提供 | inconclusive | 这是需要真实跨 chat 可见结果的场景，不能以 direct API 或 mock 替代。 |

### Requirement: Lark 监听与身份语义保持全局能力的边界

| Scenario | 期望来源 | 计划验证方式 | 证据 | 结果 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 用户明确要求监听 Lark 事件 | `incident.md` “用户明确要求监听 Lark 事件” | 在隔离 tenant 请求独立监听/自动化，确认普通 Feishu 对话仍由 Gateway 收发 | 无；没有隔离事件来源、测试身份或 Bot | inconclusive | 不能启动可能常驻的 listener 触碰未知账号或用 mock event 作为替代。 |
| 用户请求需要 Lark 身份的操作 | `incident.md` “用户请求需要 Lark 身份的操作” | 在 fixture user identity 下请求读取操作；需要应用 Bot 入/离会时核对其既有 bot 语义 | 无；最小权限 `lark-cli` user identity 与测试会议资源未提供 | inconclusive | 不读取或借用开发机/生产账号的 auth 状态来替代用户旅程。 |

所有必验 Scenario 均为 `inconclusive`，故本轮不能判定产品可交付。

## Issues

### G-1 — 隔离 Feishu 产品验收 fixture 未提供

- **Severity:** blocking
- **Regression Relation:** unclear
- **Recommended Action:** fix-implementation
- **Action Rationale:** design.md 的 `Runbook for Reviewer` 已明确要求仓外隔离 tenant、0600 source config、两个 chat、测试 Bot 与 Lark user identity；本轮缺少这些前置，导致所有 incident Scenario 无法由真实用户面验证。此项不是对实现根因的判断，也不建议在无 fixture 时修改代码；应先提供该受控 fixture，再重新执行完整产品验收。

未创建 GitHub issue：这是本 unit Runbook 规定的验收环境前置缺失，不是观察到的仓外产品缺陷；在没有可复现用户症状时创建产品 issue 会污染队列。

## 复现验证

不可执行。原始问题和目标修复都要求真实 Feishu 入站、Gateway 回写、Lark CLI 身份及跨 chat 可见结果；本轮安全边界不允许把未确认的本机账号或生产聊天拿来复现。

## 回归测试

不可执行真实回归旅程。未将自动化测试、服务健康或实现说明列为通过证据；它们不能替代本 unit 要求的外部用户可见行为。

## 自动化测试增量

本 reviewer 未运行或评价实现侧自动化测试；本角色的判据是上述真实入口。自动化覆盖可由 verifier / code reviewer 另行报告，但不关闭本报告的外部 fixture 产品门禁。

## Reference Artifacts Reviewed

不适用。本 unit 没有前端原型、截图或 must-match reference 契约；其用户面证据要求是 Runbook 所列真实 Feishu journey。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。未观察到需要改变跨包依赖或部署拓扑的用户面证据。
- [x] `docs/specs/gateway/`（长青行为契约层，本 unit 触及的 agent capabilities / external channels area）：需要更新。unit 已含两个 delta；在真实产品门禁通过后，由 orchestrator 将经最终实现校正的 delta 归并进 canonical spec。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。验收中未发现新的通用 Agent 工作约定。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新。本 unit 改变产品能力，不改变文档体系规范。

## Side Findings

无。在未启动产品旅程的前提下，没有把静态材料或未相关服务状态当作 side finding。

---

# Round 2 — 2026-08-04

> Validation snapshot: `a0b4a5a2f`
>
> Review mode: full

## Verdict

**fail** — 已使用专用 tenant、专用测试用户、两条新建私有测试群和受限的
`b499-test` user identity，完整重走 static 与 fresh-IM 托管两条入口。两条入口都
能完成 Bot ping、当前群 Gateway 回复和 IM shadow；但用户一旦请求任何 Lark
操作，助手向当前 Feishu 群暴露原始 DSML tool-call 文本后停止，没有给出可用结果。
显式向另一条测试群发送 marker 也没有发生。因此完整 Lark bundle 对用户仍不可用。

**Highest Required Action:** `out-of-unit` — 还观察到已由 #231 /
`bugfix-497-shadow-mirror-duplicate-reply` 跟踪的 IM shadow duplicate；它不改变本轮
Lark-operation 的直接 `fix-implementation` 结论，但按既有 major out-of-unit 问题的
优先级记录在 Issues。

第一轮的 G-1 fixture 缺失已关闭：本轮只使用了明确提供的、权限为 0600 的测试
fixture；没有访问主/生产配置、聊天或资源。

## 验收前置与服务接管

- 专用测试群：当前群 `oc_9897648ac0f8571d5ea03c75162fd364`，目标群
  `oc_324aa051dcba047417244aca6ddd78b9`；均由测试用户与测试 App Bot 组成。
- `lark-cli --profile b499-test auth status --verify` 成功；该 profile 只具备本轮
  所需的 IM / current-user 最小权限。Gateway 的隔离子进程也固定使用该 profile。
- static run 使用独立 0600 source config；managed run 使用另一份仅有 web relay
  的 0600 source config。两次分别以 fresh IM + Gateway 栈运行，未让同一 Bot
  竞争连接。
- managed run 由 Web IM 的
  `feishu-managed-e2e → Channels → Add channel → Feishu → Save and connect`
  建立。页面显示 **Connected**；同时显示缺少非 @ 群背景所需的两个 scope，但
  明确说明 basic messaging path 可用。本轮所有触发均 @ Bot。

## User Journeys Exercised

1. **Static Feishu entry** — 当前群 @ 测试 Bot 发送 fixture ping、只回复
   `gateway-normal-ok`、只读 Lark 身份请求、跨 chat marker 请求、独立 listener
   边界与启动确认。
2. **Managed Feishu entry** — fresh IM 中从 Settings 建立受控 Feishu channel，随后
   在同一当前测试群重复 fixture ping、普通回复、只读 Lark 身份和跨 chat marker。
3. **Shadow inspection** — 以临时 IM 的 `nano` 测试账户打开 Web IM，并以已认证
   conversations/messages API 核对 external source 与本轮消息。

## 验收标准覆盖

### Requirement: 飞书绑定 agent 可使用完整 Lark 能力

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| 用户从飞书请求 Lark 资源操作 | `incident.md` “用户从飞书请求 Lark 资源操作” | static `b499-static-read-20260804211029` 与 managed `b499-managed-read-20260804212802` 都要求只读检查已授权 user identity。测试 profile 已验证可用，但 Bot 仅回显 raw DSML read/tool-call 内容，未给最终身份或授权结果。 | fail | 用户看见内部 tool-call 标记而非可执行结果或准确前提说明。 |
| Lark CLI 未安装或尚未授权 | `incident.md` “Lark CLI 未安装或尚未授权” | 本轮 CLI 与 user identity 实际可用，故未人为破坏 fixture；两条入口在可用前提下仍未完成只读状态检查。 | fail | 若连可用前提下的状态都不能向用户完成说明，不能把缺失/未授权分支判为可用。 |

### Requirement: 飞书对话回复保持 Gateway 所有权

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| 当前飞书对话产生普通助手回复 | `incident.md` “当前飞书对话产生普通助手回复” | static `b499-static-normal-20260804211258` 与 managed `b499-managed-normal-20260804212613` 在当前群均各只收到一次 `gateway-normal-ok`。两次 fresh IM 均创建 `external_source=feishu` 的影子会话，且含同轮 user / Agent 文本。 | pass | Gateway 仍是当前群唯一外部回复出口；另见 #231 duplicate side issue。 |
| 用户明确要求操作另一段 Lark 聊天 | `incident.md` “用户明确要求操作另一段 Lark 聊天” | static `b499-static-cross-20260804211546` 与 managed `b499-managed-cross-20260804212908` 都明确指定唯一目标群与 marker。当前群只显示 raw DSML skill-read 文本；目标群仍只有建群系统消息，未收到任一 marker。 | fail | 当前群也没有操作成功/失败的正常说明。 |

### Requirement: Lark 监听与身份语义保持全局能力的边界

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| 用户明确要求监听 Lark 事件 | `incident.md` “用户明确要求监听 Lark 事件” | `b499-static-event-20260804211721` 的边界说明正确：仅测试群、普通回复仍由 Gateway、独立且有界监听。用户确认 `b499-static-event-confirm-20260804211838` 后，助手只回显“读取 lark-event / 启动监听”的内部标记，未确认建立监听或完成首个事件。 | fail | 边界文字正确，但用户要求的独立监听未建立。 |
| 用户请求需要 Lark 身份的操作 | `incident.md` “用户请求需要 Lark 身份的操作” | 两条 entry 的只读身份请求均在可用的 `b499-test` user identity 下触发，但均止于 raw DSML。 | fail | 不能确认 agent 默认实际使用 Gateway 已登录的 Lark user identity。 |

## Issues

### G-2 — Lark 操作请求向用户泄露内部 tool-call 文本后停止

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 本 unit 的主价值是让飞书绑定 agent 可发现并执行完整 Lark
  bundle。static 与 managed 两条真实入口都不能完成最小的只读身份检查或指定目标群
  的 marker 发送；用户得到的是内部 DSML 而非结果、错误或下一步。

### G-3 — 已知 external shadow duplicate 仍在本轮真旅程中可见

- **Severity:** major
- **Regression Relation:** unrelated-existing
- **Recommended Action:** out-of-unit
- **Action Rationale:** static 和 managed 的每个 `gateway-normal-ok` 在 Web IM shadow
  中都呈现一条带 Process 的富气泡及一条同文案 plain 副本，而外部当前群仅一条。
  这与已有 #231 / active `bugfix-497-shadow-mirror-duplicate-reply` 的已知用户症状
  相同，属于本 unit 范围之外的 existing shadow-delivery 修复；未新建重复 GitHub
  issue。

## 复现验证

在两次 fresh isolated stack 中均复现 G-2：@ 测试 Bot 请求 `lark-cli` 只读身份或
向明确目标群发送 marker。前者没有最终结果，后者没有 marker；两者都在当前群留下
raw DSML。普通非工具回复在两条入口均正常，表明失败是用户请求 Lark bundle 时才
出现的能力断点，而不是测试 Bot 连通性问题。

## 回归测试

- static fixture ping：通过；测试 Bot 回复
  `b499-static-20260804210948-ack`。
- managed fixture ping：通过；测试 Bot 回复
  `b499-managed-20260804212532-ack`。
- 当前群普通 Gateway 回复与 Feishu shadow：两条入口通过（同时观察到 G-3）。
- 显式另一 chat marker、只读 Lark identity、确认后的 independent listener：失败，
  原因为 G-2。

## 自动化测试增量

本 reviewer 未以自动化测试替代真实用户旅程；实现侧自动化测试由 verifier / code
reviewer 单独报告。上述结论来自真实 Feishu、Web IM 和认证 IM API 的可观察结果。

## Reference Artifacts Reviewed

不适用。本 unit 没有前端原型或 must-match screenshot；本轮已实际使用 Web IM
Settings、Chat 和两条专用 Feishu 群作为用户面真值。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本轮未观察到跨包依赖或部署拓扑变化。
- [x] `docs/specs/gateway/`（agent capabilities / external channels）：unit 的 delta
  仍需在 G-2 修复并通过产品门禁后再由 orchestrator 归并；当前不能以失败实现写入
  canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。本轮问题是产品行为，不是通用工作约定。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。本 unit 不改变文档体系规范。

## Side Findings

- Managed Settings 已向用户显式显示当前 App 缺少非 @ 群背景 / history 权限；本轮
  @ Bot 的 basic messaging path 未被该提示阻断。

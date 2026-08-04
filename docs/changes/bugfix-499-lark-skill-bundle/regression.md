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

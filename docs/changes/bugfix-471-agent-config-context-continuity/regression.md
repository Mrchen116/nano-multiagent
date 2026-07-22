# bugfix-471 — 回归验证

> 对齐: `incident.md`
>
> Round 1 — 2026-07-22

## Verdict

**fail**

**Highest Required Action:** `fix-implementation`

Web IM 的核心直聊旅程已在真实浏览器中证明：同一聊天在运行配置更新后仍理解旧消息、采用新指令，并在首条相应用户消息前显示唯一的持久非消息分界线。该分界线也在 1440、1280 和 375 宽度的真实页面刷新后保持锚定。

但本轮无法从真实产品入口完成本 unit 所要求的外部 Feishu 中断/恢复/唯一 shadow 时间线旅程，也没有完成群聊、活跃回复中切换、工具增加/删除、连续保存、保存失败、older-page prepend 与 fork 的全部用户场景。因此不能把本 unit 判为可交付。

## User Journeys Exercised

1. **Web IM 直聊的配置边界主路径**：登录隔离 IM，打开已有直聊；先发送含唯一标记的消息，再在 Agent 配置页保存影响运行行为的 Custom Instructions，回到同一聊天追问。
2. **持久时间线与响应式回归**：在同一已跨过配置边界的聊天依次以 1440、1280、375 宽度查看并刷新页面。
3. **外部渠道验收前置检查**：在隔离 Gateway 环境中检查真实 Feishu 用户入口可用性；该入口所列会话不属于隔离服务的测试通道，无法将消息安全路由到本轮隔离 Gateway，因此未发送生产渠道探测消息。

## Reference Artifacts Reviewed

| Reference | must-match 契约 | 实际产品证据 | 结论 |
|---|---|---|---|
| `prototype.html` | 固定文案、首条采用新配置的用户消息前、非消息语义 | `acceptance-chat-1440.png`，1440px | pass：固定文案位于追问前，单独呈现为分隔线；没有头像、发送者、气泡、时间、状态或菜单。 |
| `prototype.html` | reload 后锚定稳定 | `acceptance-chat-1280-reload.png`，1280px 刷新后 | pass：分界线仍紧邻相同的追问前。 |
| `prototype.html` | 375px 响应式，低优先级非消息分隔 | `acceptance-chat-375-reload.png`，375px 刷新后 | pass：分界线自然换行，无横向溢出；聊天详情、消息与输入区仍可用。 |
| `prototype.html` | reconnect / older-page prepend | 无真实产品证据 | inconclusive：未完成。 |

## 验收标准覆盖

### Requirement: 既有对话采用新配置时保持上下文连续

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 增加工具后继续刚才的任务 | `incident.md` 112–115 | 未执行工具能力变更旅程。 | inconclusive | 必验场景未完成。 |
| 删除工具后保留既成工具历史 | `incident.md` 117–120 | 未执行已有工具结果后删除工具的旅程。 | inconclusive | 必验场景未完成。 |
| 修改模型、提示词或 skills 后继续既有对话 | `incident.md` 122–125 | 保存 Custom Instructions 后，在同一聊天追问。Agent 回复 `CONFIG-B-471，上一条标记为 CONTEXT-471-ALPHA。`；见 `acceptance-chat-1440.png`。 | pass | 用户可见地同时采用新配置并引用配置前历史。 |
| Gateway 重启后配置边界两侧的历史仍连续 | `incident.md` 127–130 | 未执行 Gateway 重启后的真实聊天追问。 | inconclusive | 必验场景未完成。 |

### Requirement: 配置切换不改变正在进行的整轮回复

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 回复进行中修改配置 | `incident.md` 134–137 | 未在活跃回复期间保存配置。 | inconclusive | 必验场景未完成。 |
| 回复进行中插话 | `incident.md` 139–142 | 未执行活跃回复期间插话。 | inconclusive | 必验场景未完成。 |
| 连续保存多次后再继续聊天 | `incident.md` 144–147 | 未执行连续保存。 | inconclusive | 必验场景未完成。 |

### Requirement: Web IM 用持久分界线说明缓存边界

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 运行配置更新后继续既有聊天 | `incident.md` 151–155；`prototype.html` | 保存运行配置后回到原聊天，首条追问前出现固定文案；1280/375 刷新后仍在相同位置。见三张 `acceptance-chat-*.png`。 | pass | `separator` 独立于用户和 Agent 消息。 |
| 休眠聊天不被批量插入分界线 | `incident.md` 157–160 | 未创建第二个既有聊天作对照。 | inconclusive | 必验场景未完成。 |
| 连续修改多次只显示最终边界 | `incident.md` 162–165 | 未执行连续修改。 | inconclusive | 必验场景未完成。 |
| 纯展示信息更新不提示缓存变化 | `incident.md` 167–169 | 未完成保存展示字段并继续聊天的路径。 | inconclusive | 必验场景未完成。 |
| 配置保存失败不产生错误提示 | `incident.md` 171–174 | 未执行失败保存。 | inconclusive | 必验场景未完成。 |

### Requirement: 各聊天入口保持各自连续且互不串线

| Scenario | 期望来源 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|---|
| 群聊配置更新后保留群上下文 | `incident.md` 178–181 | 未执行真实群聊。 | inconclusive | 必验场景未完成。 |
| 外部渠道既有对话继续使用新配置 | `incident.md` 183–186 | 未提供可指向隔离 Gateway 的 Feishu 测试通道；未以生产 Feishu 会话替代隔离验证。 | inconclusive | 必验场景未完成。 |
| 不同聊天的历史不因配置更新而合并 | `incident.md` 188–191 | 未完成多聊天交叉追问。 | inconclusive | 必验场景未完成。 |

### design.md Prototype / Reference Contract must-match

| must-match 项 | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 结构、位置、固定文案；1440 / 1280 / 375 | 三张 `acceptance-chat-*.png`。 | pass | 位置与文案均匹配。 |
| 非消息语义 | 真实页面 accessibility snapshot 显示为 `separator "Agent 配置已更新"`，而相邻消息各自显示身份与时间；见上述截图。 | pass | 没有消息气泡的附属信息。 |
| reload、reconnect、older-page prepend 的稳定锚定 | reload 见 1280/375 截图；未完成 reconnect 和 older-page prepend。 | inconclusive | 不可由 reload 结果代替。 |

## Issues

### 1. 必验跨渠道与恢复旅程未取得真实产品证据

- **Severity:** blocking
- **Regression Relation:** direct
- **Expected:** 用户能在 Feishu 外部对话中配置更新后继续前文；IM 暂时中断时仍收到回复，恢复后 Web IM 有同一外部对话的唯一 shadow 时间线，且 divider 顺序正确。
- **Actual:** 隔离 IM/Gateway 已启动并可验证 Web IM；但没有提供能切到该隔离 Gateway 的 Feishu 测试通道。可见 Feishu 用户会话均为既有外部会话，不能替代隔离产品入口验收。没有真实产品证据证明外部回复、IM 中断恢复或唯一 shadow 时间线。
- **Reproduction:** 按 `design.md` Runbook 启动隔离 IM/Gateway 后，尝试执行 Feishu 前置探测；缺少接入隔离服务的测试通道，无法安全走后续旅程。
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 这直接阻断 `incident.md` 的外部渠道场景与 `design.md` M2-C4 验收；在真实 Feishu→隔离 Gateway→Web IM 旅程跑通并保留用户可见证据前，不能交付。

### 2. 必验边界旅程没有完成真实用户覆盖

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** 配置更新必须在工具增加/删除、群聊、活跃回复/插话、连续保存、失败保存、重启、多聊天隔离、分页和 fork 等用户操作中保持文档规定的体验。
- **Actual:** 本轮只获得了 Custom Instructions 更新后的同一 Web IM 直聊、刷新和三种宽度的有效用户证据。其余必验场景均未能由真实产品结果关闭。
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 这些是 `incident.md` 明定的必验 Scenario；当前没有用户可观察证据，不能用页面已渲染或自动化结果替代。

## Side Findings

- `Open chat ↗` 会创建一个新的空直聊，而不是回到已选聊天；用户仍可通过左侧已有会话条目回到原聊天。本轮未证明这是本 unit 引入的回归，且不影响配置连续性主路径，因此不作为本 unit issue。

## 自动化测试增量

本报告不以自动化测试替代用户面验收，未运行或评判测试结果。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 改变的是既有跨包运行行为的具体契约，不改变四包职责和依赖方向。
- [x] `docs/specs/<包>/`（长青行为契约层）：需要更新/归并；unit 已提供 kernel、gateway、IM 的 delta-spec，PR 收尾须归并至 canonical specs。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：无需更新。

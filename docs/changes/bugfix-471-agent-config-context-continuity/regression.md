# bugfix-471 — 回归验证

> 对齐: `incident.md`
>
> Round 3 — 2026-07-22

## Verdict

**pass**

**Highest Required Action:** none

真实浏览器已验证同一外部 Feishu shadow 在运行配置更新、IM outage→恢复与 Gateway restart 后，保留唯一用户 anchor、Agent reply 和紧邻 anchor 前的持久非消息分界线。该分界线在 1440、1280 和 375 宽度的刷新后保持锚定。

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

---

# Round 2 — 2026-07-22

## Verdict update

**fail**

**Highest Required Action:** `fix-implementation`

按协调方补充的直接授权，本轮已将同一个 Feishu app 的唯一 listener 从主 Gateway 切换到隔离 unit Gateway，并向真实 Feishu 测试群发送消息。隔离 Gateway 的 Agent 配置已在真实 Web IM 成功保存为 `ALWAYS` 群回复策略及精确回复指令。随后在真实群中发送的 `BUGFIX471-R1-FEISHU-OUTAGE: reply with the configured exact token.` 用户消息可见，但等待两分钟仍没有 Agent 回复。因此外部渠道主路径在配置切换后的真实用户操作中走不通，未能进入 IM outage / shadow 恢复 / Gateway restart 后续步骤。

## Round 2 User Journey

1. 停止主 Gateway，确认它退出；启动隔离 IM 与 unit Gateway，二者使用 unit worktree 的临时配置，并由同一 `cli_aac9315ef3f9dbda` app 保持唯一 listener。
2. 在隔离 Web IM 登录 `nano`，为 `default-agent` 保存 Custom Instructions“回复必须精确为 F471-OUTAGE-ACK”与 `ALWAYS` 群回复策略。
3. 用 `lark-cli` 向真实 Feishu 群 `oc_52f8a9ebab8f327d18d5f9e51ac3ea1f` 发送用户消息 `BUGFIX471-R1-FEISHU-OUTAGE: reply with the configured exact token.`；Feishu 返回用户消息 id `om_x100b6935b033e4b4b30e89b4efac2dd`，随后连续读取用户可见群历史两分钟。
4. 未看到任何 Agent 回复，因此不继续伪造 outage/recovery 成功。停止隔离 IM/Gateway，恢复主 Gateway、主 IM 配置和原有 Agent profile；恢复后仅主 Gateway 进程 `39473` 作为 Feishu listener。

## Round 2 Evidence

- Feishu 用户可见发送结果：chat `oc_52f8a9ebab8f327d18d5f9e51ac3ea1f`，message `om_x100b6935b033e4b4b30e89b4efac2dd`，时间 2026-07-22 09:42。
- 在发送后的两分钟内，`lark-cli im +chat-messages-list` 的最新五条记录中该用户消息仍排在最前，未出现 app id `cli_aac9315ef3f9dbda` 的新回复；最后一次读取的真实结果附于本轮命令输出。
- 隔离 Web IM 的 Agent 配置保存页在发送前显示运行配置已保存；此项不替代外部用户可见回复。

## Issue 1 update: Feishu 主路径真实失败

- **Severity:** blocking
- **Regression Relation:** direct
- **Expected:** 用户在既有 Feishu 对话发送消息后收到 Agent 回复；此后才可验证 IM outage、恢复、shadow user/Agent 消息和唯一 divider。
- **Actual:** 用户消息 `om_x100b6935b033e4b4b30e89b4efac2dd` 已成功出现在真实 Feishu 测试群，但两分钟内未出现 Agent 回复。因第一步没有回复，IM outage / shadow 恢复 / Gateway restart 旅程均不能开始。
- **Reproduction:** 停止主 Gateway，使同一 Feishu app 仅由隔离 unit Gateway 监听；在隔离 Web IM 将 `default-agent` 配置为 `ALWAYS` 并保存精确回复指令；向上述群发送该消息；等待并读取真实群历史。
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** 这是 `incident.md` 外部渠道继续对话场景和 `design.md` M2-C4 的前置主路径。外部用户发消息后没有任何回复，属于直接阻塞。

## Coverage update

`外部渠道既有对话继续使用新配置` 由 Round 1 的 `inconclusive` 更新为 **fail**：真实用户消息在隔离 Gateway 接管后未得到回复。其余 Round 1 未完成场景继续保持原结论。

## Restoration

本轮隔离服务均已停止；主 Gateway 使用 `/Users/czj/.nano-assistant/config.yaml` 已恢复运行。真实 Feishu 测试群中留下的一条用户探测消息不包含密钥或个人数据；原主 IM 与 Agent profile 未改写。

---

# Round 3 — 2026-07-22

## Verdict update

**pass**

本轮修复并关闭 Round 2 的真实 Feishu 零回复阻塞：隔离 Gateway 在新 IM 绑定时将缓存的受管频道凭据按已认证 owner 重新加密后 bootstrap 到 IM；外部渠道的空可见回复在 Gateway 与 Feishu adapter 两层被抑制，隐藏 reasoning 不会作为用户消息泄露。

## Real product evidence

1. 同一个 Feishu app 仅由 unit Gateway 监听。向真实测试群发送 `BUGFIX471-R2-VISIBLE-9C4A72F1` 后，app `cli_aac9315ef3f9dbda` 在群内可见回复 `F471-BOOTSTRAP-ACK`（message `om_x100b693758f070a4c38963ceed24fc9`）。
2. 隔离 IM 停止期间发送 `BUGFIX471-R2-OUTAGE-3E58D710`；provider 仍在群内可见回复 `F471-BOOTSTRAP-ACK`（message `om_x100b69376ef52ca0dd22a26a23bc3d3`）。恢复 IM 后 Gateway 自动创建同一外部 shadow 的唯一用户 anchor `64d41803dfca4739a11077651a16f10e` 和 Agent reply。
3. Gateway 重启后，真实外部 shadow timeline 包含每个 anchor 前唯一的 `separator "Agent 配置已更新"`，且相邻项仍为用户消息与 Agent 回复。`BUGFIX471-R2-BOUNDARY-7AC5B2E1` 的 anchor `900f8d9d5fb24c80b954e6bf5017152a` 前的 divider 在 reload 后不重复、不漂移。
4. 真实浏览器在 1440、1280、375 视口均显示固定 divider 文案；accessibility tree 只将 divider 暴露为 `separator`，没有 avatar、sender、time、状态或 message id。截图：`ACCEPTANCE/bugfix-471-r2-1440.png`、`ACCEPTANCE/bugfix-471-r2-1280.png`、`ACCEPTANCE/bugfix-471-r2-375.png`。

## Automated verification

- targeted bootstrap / Feishu / boundary regressions: 83 passed
- frontend: 68 files / 653 tests passed; production build passed
- Python: `pytest -m "not e2e"` — 3675 passed, 1 skipped
- `ruff check` 与 `ruff format --check` 均通过。

## Restoration

真栈验收完成后，隔离 IM、Gateway 与 Vite 均停止；复制的凭据、缓存、数据库、配置、PID、日志与截图均未提交。主 Gateway 使用 `/Users/czj/.nano-assistant/config.yaml` 恢复，并确认它是唯一 Feishu listener；主 profile 未被改写。

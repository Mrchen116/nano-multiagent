# feat-548 — 验收报告

> 对齐: [spec.md](spec.md) / [design.md](design.md)

> Validation snapshot: `f455c6220 → 298987e90172903436302725092f9856097d423c`
>
> Review round: 1；mode: full；revalidation_mode: full

## Verdict

**pass**

**Highest Required Action: pass**

本轮 7 个必验 Scenario 全部通过，没有 blocking、major 或 minor 产品问题。验收使用隔离账号 `nano`、独立 Playwright session `feat548-reviewer` 和本轮自建会话；没有修改用户已有聊天标题。按 caller 明确要求保留共享演示现场，本轮未重启、清空或重载 `127.0.0.1:59669` 的 IM / Gateway；开始前确认 `openapi.json` 返回 200，真实聊天中 Agent 在线并成功回复。

报告提交时分支已经包含后续提交 `fed0fc8d0`；该提交只同步旧 workspace 测试入口与 canonical 文档，未改变本轮已验产品代码。本报告的产品判据和证据始终固定在 `298987e90172903436302725092f9856097d423c`。

## 用户旅程体验

1. **桌面菜单与原配置入口**（1280×800）：在自建私聊 `3504578206fe44d8a3411ac8fecb6788` 打开顶部省略号菜单，清楚看到 `Rename` 和 `Agent configuration`；后者进入 `qa-inbox-vision-0910` 原 Agent 配置页。菜单位置、两项动作和白色浮层与原型结构一致。
2. **保存、刷新、历史与同 Agent 隔离**（1280×800）：同一 Agent 新建两条私聊 `3504578206fe44d8a3411ac8fecb6788` / `0b240d2b4dba42bba58722c8805d48c9`。目标会话先完成一轮消息 `BASELINE_548R`，再改名为 `feat548-reviewer · 简历修改`；列表、顶部和输入提示立即一致，刷新后新名与既有消息都保留，继续发消息后 Agent 正常回复。另一条私聊仍显示 `Inbox协议自验`。
3. **取消、空白与失败重试**（1280×800、390×844）：输入临时名称后取消，原标题保持；输入纯空白时 `Save` 禁用。对目标会话 PATCH 注入 503 后，弹窗显示 `Could not save. Please try again.`、保留 `失败重试草稿 · reviewer` / `手机失败草稿 · reviewer` 输入，列表和顶部仍是已保存标题；解除注入后直接点击同一 `Save` 即成功。桌面和手机均无溢出或遮挡。
4. **Agent 读取新名、Agent 改名保护与外部同步**：`qa-inbox-vision-0910` 通过真实 `conversations` / `inbox` 工具读取后回复 `会话名称：feat548-reviewer · 简历修改；校验词：海棠548`。另建专用 Agent `feat548-reviewer-agent-0910`，将会话改为 `Agent改名保护 · reviewer` 后再把 Agent 显示名从 `验收 Agent 初始名` 改成 `验收 Agent 改名后`，刷新可见会话标题不变、参与者显示名更新。外部来源测试通过真实 IM `external/find-or-create` 入口创建并复用 `b55c80ab2813493883361dc44bdd10cf`；IM 手动改为 `外部私聊 · reviewer手动名` 后，以新的来源标题再次同步并写入 `EXTERNAL_FOLLOWUP_548R`，返回同一会话 ID，页面刷新后手动标题和后续消息均保留。此项是 IM 入口的外部来源模拟，不声称飞书客户端端到端。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html` 私聊菜单与配置动作 | `design.md` 前端原型表：must-match；私聊顶部省略号菜单，包含重命名和原 Agent 配置入口 | `output/playwright/feat548-reviewer/desktop-menu.png`、`mobile-menu.png`；配置动作实际进入 `/settings/agents/qa-inbox-vision-0910` | 1280×800 desktop；390×844 mobile；菜单展开 | match：入口、动作顺序、浮层位置与紧凑移动布局均对齐；产品沿用现有英文 locale 文案 |
| `prototype.html` 改名、取消、空白、保存失败 | `design.md` 前端原型表：must-match；单字段弹窗、预填、取消/保存、内联失败 | `desktop-renamed.png`、`desktop-blank-disabled.png`、`desktop-save-failure.png`、`mobile-rename-modal.png`、`mobile-blank-disabled.png`、`mobile-save-failure.png`、`mobile-retry-saved.png` | desktop/mobile；成功、取消、空白、503 失败、重试 | match：产品正确预填当前标题，空白禁用、失败保留输入和内联反馈、重试成功；移动弹窗完整可操作 |

说明：独立打开原型时，其演示脚本把输入预填为 `undefined`；spec/design 的目标语义和真实产品都要求预填当前标题，实际产品表现正确，因此不作为产品问题。

## 问题清单

无。

## 验收标准覆盖

### Requirement: 私聊提供会话菜单 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 从菜单访问会话操作 | `spec.md`；`design.md` 决策 1；`prototype.html` must-match | 旅程 1：桌面/手机真实私聊打开菜单；点击 Agent 配置 | `desktop-menu.png`、`mobile-menu.png`；实际路由 `/settings/agents/qa-inbox-vision-0910` | pass | 两端均有 Rename 与 Agent configuration |

### Requirement: 私聊可以按会话修改标题 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 修改已有私聊名称 | `spec.md`；`design.md` 决策 2/4；`prototype.html` must-match | 旅程 2：发送基线消息、保存新名、刷新、继续发消息 | `desktop-renamed.png`、`desktop-agent-new-name.png`；会话 `0b240d2b4dba42bba58722c8805d48c9` | pass | 列表/顶部/输入提示一致；`BASELINE_548R` 保留，后续真实 Agent 回复成功 |
| 外部私聊后续同步保留手动改名 | `spec.md`；`design.md` 决策 3 | 旅程 4：真实 IM external find-or-create 创建，UI 手动改名，再以新来源标题复用并同步后续消息 | `mobile-external-renamed.png`、`mobile-external-followup.png`；同一 ID `b55c80ab2813493883361dc44bdd10cf`；`EXTERNAL_FOLLOWUP_548R` | pass | IM 入口模拟外部来源；未声明飞书客户端端到端 |
| 同一 Agent 的其他会话保持原名 | `spec.md`；`design.md` 风险项 | 旅程 2：同一 Agent 两条新私聊，仅改目标会话 | `desktop-renamed.png`；列表中另一条仍为 `Inbox协议自验` | pass | Agent 显示名在该阶段也保持 `Inbox协议自验` |
| 取消或提交空名称 | `spec.md`；`design.md` 决策 4；`prototype.html` must-match | 旅程 3：桌面取消；桌面/手机输入纯空白 | `desktop-blank-disabled.png`、`mobile-blank-disabled.png`；取消后页面查无临时标题 | pass | 空白时 Save 禁用；取消不生效 |
| 保存失败可重试 | `spec.md`；`design.md` 决策 4；`prototype.html` must-match | 旅程 3：桌面/手机对目标 PATCH 注入 503，观察失败态，解除注入后原输入直接重试 | `desktop-save-failure.png`、`mobile-save-failure.png`、`mobile-retry-saved.png` | pass | 失败反馈清晰；输入保留；未保存名称未提前投影；同一输入可重试成功 |

### Requirement: Agent 使用用户设定的会话名 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 修改后读取会话 | `spec.md`；`design.md` 决策 2 | 旅程 4：真实 Agent 工具读取当前会话；专用 Agent 的自建会话改名后再修改 Agent 显示名并刷新 | `desktop-agent-new-name.png`、`agent-display-renamed-title-preserved.png`；Agent 回复含 `feat548-reviewer · 简历修改` | pass | Agent 得到新标题并正确回复；Agent 显示名更新为 `验收 Agent 改名后` 后，会话标题仍为 `Agent改名保护 · reviewer` |

## Side Findings

- `prototype.html` 的独立演示脚本在打开改名弹窗时显示 `undefined`，而真实产品正确预填当前标题。它不影响产品旅程，也未用于放宽验收判据。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变包职责或依赖方向。
- [x] `docs/specs/<包>/`（长青行为契约层）：已在验收同期的 `fed0fc8d0` 归并到 `docs/specs/im/conversations-messages.md` 与 `docs/specs/gateway/global-agent.md`；该提交晚于固定产品快照，不作为产品验收证据。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；开发与运行约定未变化。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；本 unit 未改变文档体系。

## 验收期间的口径说明

- caller 明确要求保留当前共享演示现场及数据，因此本轮未执行通用 reviewer 流程中的服务重启；只使用隔离账号、独立浏览器 session 和自建测试会话/Agent。
- caller 明确允许从真实 IM 入口模拟外部来源消息；该证据仅支持 IM 外部同步契约，不外推为飞书客户端端到端。

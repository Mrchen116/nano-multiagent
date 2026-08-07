# feat-514 — 验收报告

> 对齐: [spec.md](spec.md) 的验收标准与 [design.md](design.md) 的前端原型契约。

> Validation snapshot: `f54e008b1 → 903199ab5`（派发包中的 implementation-validation snapshot）；本轮真实浏览器运行于 `origin/unit/feat-514` 的 `040b7006f523b32943ca788c6f8684c1015b9804`。

## Verdict

**fail**

**Highest Required Action:** `fix-implementation`

可调模型的创建、保存、reload、同一会话的后续消息，以及固定/无能力/未显式选择的配置呈现均按预期工作；但 E2E 用户选择页面公开的 fixed Kimi 后发送首条消息，得到空的 Agent 气泡，随后会话列表显示 `anthropic: stream ended without terminal event`。这让固定模型的可用聊天路径不能交付。另有 4 条必验 Scenario 及 2 条 must-match 状态没有安全的浏览器前置可生成，故不能以已通过替代。

## 用户旅程体验

测试环境：本 unit worktree 内的 IM + Gateway + Vite（IM `:57056`，Vite `:57321`），使用仓库隔离 E2E owner `nano`；前端通过本轮重新构建的 Vite asset `index-BY98Ndx_.js` 提供。所有 Agent、会话与运行数据均在本 worktree 的 E2E runtime 内。

1. **新建 Agent / 状态切换（桌面）**：默认平台模型时，“Reasoning effort”只说明必须先选模型；选择 `deepseek:deepseek-v4-flash` 后只出现 `High` 和 `Maximum`，且 `High` 为推荐初值；切换到 `kimi:kimi-k3` 后立即换成 “Reasoning is always on and controlled by the model”，没有残留或禁用下拉框；`openai:gpt-5.6-terra` 显示无可配置设置，未伪造控制项。
2. **创建、保存、reload（桌面）**：创建 `reasoning-e2e-514`，保存 DeepSeek `Maximum`；详情页为 v1 且 reload 后仍显示 DeepSeek / Maximum。之后切到 Kimi 保存为 v2，详情页不再显示 reasoning select；再切回 DeepSeek `High` 保存为 v3，随后改为 `Maximum` 保存为 v4。
3. **既有会话后续消息（移动）**：同一已有对话先以 DeepSeek `High` 获得正文 `DeepSeek high works.`；保存 `Maximum` 后用浏览器返回同一会话（历史仍在），下一条获得正文 `Maximum retained the same history.`，页面同时给出“Agent 配置已更新”分隔提示。
4. **固定模型的聊天入口（移动）**：Kimi fixed 状态本身呈现正确；但发送首条消息后，界面只留下没有正文的 Agent 气泡。返回会话列表时，最新会话的可见失败文案为 `anthropic: stream ended without terminal event`。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html` — “模型 → 推理强度”相邻顺序 | must-match：create + detail、1440px/375px、可调模型 | `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-514/src/IM/frontend/.playwright-cli/page-2026-08-07T09-19-48-091Z.png`; `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-514/src/IM/frontend/.playwright-cli/page-2026-08-07T09-08-16-444Z.png` | desktop + mobile; saved DeepSeek Maximum | **match** — 两个原生 select 在同一 Access & Model 卡内相邻；推荐说明在强度控件下方，移动端保持单列。 |
| `prototype.html` — fixed 只读说明 | must-match：create + detail、1440px/375px、fixed 模型 | `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-514/src/IM/frontend/.playwright-cli/page-2026-08-07T09-10-06-781Z.png`；create 页 desktop snapshot `09-04-05-360Z.yml` | desktop + mobile; `kimi:kimi-k3` | **match** — “Reasoning”位置是清晰只读说明及辅助文案，不存在 select。 |
| `prototype.html` — 未选模型反馈 | must-match：create + detail、1440px/375px；platform default | create 页 desktop snapshot `09-01-17-305Z.yml` | desktop; platform default | **pass (desktop)** — 明确提示先选模型且不会孤立保存强度。375px 未独立走到该状态，故 mobile 对照 **inconclusive**。 |
| `prototype.html` — 目录已更新 | must-match：create + detail、1440px/375px；stale capability | 无安全的浏览器状态生成入口 | desktop + mobile; stale capability | **inconclusive** — 需要运维侧缩减 live catalog；reviewer 不修改 config。 |
| `prototype.html` — 正在确认 | must-match：create + detail、1440px/375px；Gateway result unknown | 无安全的浏览器状态生成入口 | desktop + mobile; pending operation | **inconclusive** — 需要人为丢弃 operation result/使 Gateway 不可达；reviewer 不修改服务行为。 |

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 | major | 用户选择页面公开的 `kimi:kimi-k3` fixed 模型后进入聊天并发送首条消息，页面显示无正文的 Agent 气泡；会话列表随后显示 `anthropic: stream ended without terminal event`。 | `fix-implementation` |

### Issue 1 — fixed Kimi Agent 首轮聊天没有可读回复

- **Severity:** major
- **Regression Relation:** suspected-regression
- **Recommended Action:** fix-implementation
- **Action Rationale:** fixed-model UI 已允许用户把 Kimi 保存为该 Agent 的运行模型，但真实聊天入口不能产出可读回复；这发生在本 unit 的固定模型选择后同一用户旅程中，必须先修复或明确、可恢复地呈现失败，才能判定该固定模型路径可交付。Reviewer 未读取源码或追踪内部链路。
- **Reproduction:** 新建/编辑 Agent → 选择 `kimi:kimi-k3` → 保存 → Open chat → 发送 `Reply with exactly: feat514 e2e.` → 等待终态。实际得到空 Agent 气泡；返回 chat list 可见 `anthropic: stream ended without terminal event`。
- **Evidence:** `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-514/src/IM/frontend/.playwright-cli/page-2026-08-07T09-12-35-013Z.png`。

## 验收标准覆盖

### Requirement: 选择模型后呈现与该模型匹配的推理设置 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 选择可调推理强度的模型 | `spec.md`; `design.md` 决策 1、6；`prototype.html` | 旅程 1：create 页选择 DeepSeek | create snapshot `09-03-42-035Z.yml`；desktop/mobile screenshots `09-19-48-091Z.png`、`09-08-16-444Z.png` | pass | 仅见 High / Maximum；High 初始选中。 |
| 未明确选择模型 | `spec.md`; `design.md` 决策 6；`prototype.html` | 旅程 1：create 页保持 platform default | create snapshot `09-01-17-305Z.yml` | pass | 明确提示先选模型；没有独立可提交的强度字段。 |
| 模型目录更新使草稿选项失效 | `spec.md`; `design.md` 决策 5、6；`prototype.html` | 需要 Gateway 运行时缩减 catalog 后保存旧值 | 无安全前置 | inconclusive | Runbook 未提供不改 config/服务行为的生成步骤；不能把未走到的 409/草稿保留写成 pass。 |

### Requirement: 固定思考模型清楚说明限制而不伪造控件 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 选择固定思考模型 | `spec.md`; `design.md` 决策 1、6；`prototype.html` | 旅程 1：create/detail 选择 Kimi | create snapshot `09-04-05-360Z.yml`; mobile screenshot `09-10-06-781Z.png` | pass | 只读“always on”说明和解释；无 select。 |
| 从可调模型切换到固定思考模型 | `spec.md`; `design.md` 决策 4、6 | 旅程 2：已存 DeepSeek Maximum 改 Kimi 并保存 | detail snapshot `09-10-38-659Z.yml`（v2） | pass | 切换时立即移除 select；保存后 profile v2 仍无可配置 strength。 |

### Requirement: 模型与推理设置作为同一份 Agent 配置生效 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新建 Agent 保存模型和推理强度 | `spec.md`; `design.md` 决策 4、6 | 旅程 2：新建 DeepSeek Maximum、保存并 reload | detail snapshots `09-06-05-485Z.yml`（v1）与 `09-06-38-563Z.yml`（reload） | pass | reload 后仍为 DeepSeek / Maximum。DeepSeek High 真实首轮消息也返回正文。 |
| 既有对话中更新模型或推理强度 | `spec.md`; `design.md` 决策 3、6 | 旅程 3：同一 conversation 的 High 首轮 → 保存 Maximum → browser back 回同一 conversation → 下一条 | screenshot `09-17-52-148Z.png` | pass | 历史和第一条回复仍可见；配置边界后新回复返回正文。 |
| 保存失败时保留可理解的编辑状态 | `spec.md`; `design.md` 决策 5、6；`prototype.html` | 需要 Gateway 拒绝或 operation 未确认 | 无安全前置 | inconclusive | 不能通过正常用户控件产生所需 rejection/pending；不得伪造失败。 |

### Requirement: 模型能力由节点配置驱动，而非 Web IM 内置判断 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 部署者为已有模型调整可选强度 | `spec.md`; `design.md` 决策 1、2；生产能力矩阵 | 需要更新隔离 Gateway config 并重启 | 无安全前置 | inconclusive | reviewer 禁止编辑 config；未将当前静态目录误当作“更新后无需前端发布”的证据。 |
| 部署者添加带推理能力的新模型 | `spec.md`; `design.md` 决策 1、2；生产能力矩阵 | 需要第二节点或在隔离 Gateway 注册新模型并重启 | 无安全前置 | inconclusive | 未验证节点间目录隔离，不能给 pass。 |

### Additional caller-directed check: 无能力模型不出现可选控件 — 结论: pass

`openai:gpt-5.6-terra` 显示 “This model does not expose configurable reasoning settings” 与其说明，没有空白、disabled 或可提交的 reasoning select（create snapshot `09-04-43-218Z.yml`）。

## Side Findings

- `e2e-up.sh` 的隔离 owner 登录凭据未在 reviewer runbook 中给出；本轮由 orchestrator 明确授权了仓库隔离账户后才可进入绑定节点。该文档前置缺口不作为本 unit 的产品 defect；orchestrator 已承诺单独补充。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。
- [x] `docs/specs/im/`、`docs/specs/gateway/`、`docs/specs/kernel/`（长青行为契约层）：需要更新。当前 branch 仅有本 unit delta-spec；仍需在收尾按最终行为归并 canonical area 文档。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：无需更新。

本轮未修改上述上层文档；long-lived spec 的归并由 orchestrator 在修复、复验后按最终实现完成。

---

# Round 2 — 2026-08-07

> Revalidation: targeted fast-lane。基线为 `66d31ab16a8338780da25a7a4891645cae60922a`；仅复验 Round 1 Issue 1 在 `c1e0163de` 后的 fixed Kimi 聊天路径，并回归确认 DeepSeek 可选强度。其余 Round 1 的 `inconclusive` 覆盖项按流程继承，未在本轮改写为已通过。

## Verdict

**fail**

**Highest Required Action:** `fix-implementation`

Round 1 的唯一产品失败已关闭：隔离 E2E catalog 中公开的 fixed Kimi 现在为可路由的 `kimiCoding:kimi-for-coding`，新建、保存并打开该 Agent 后，真实首轮聊天得到可读正文 `Kimi route works.`；没有再出现空 Agent 气泡或 `stream ended without terminal event`。同一浏览器会话还确认 DeepSeek 仍只公开 `High` 和 `Maximum`，默认推荐 `High`。

但 Round 1 的 4 条必验 Scenario 及 2 个 must-match 状态仍为 `inconclusive`：目录缩减导致草稿失效、保存失败/确认中、既有模型能力变更、以及新增模型/节点；未提供可由 reviewer 安全触发的隔离运行时前置。本轮的范围不包含这些路径，故 targeted fix 已关闭但整份 acceptance 不能升级为 `pass`。

## Focused user journeys

测试环境：重新启动的 unit worktree 隔离 IM + Gateway + Vite（IM `:51367`，Vite `:51712`），仓库 E2E owner `nano`。只打开一个 headed 浏览器会话，完成后立即关闭；所有 Agent、对话和运行数据都留在该隔离 runtime。

1. **fixed Kimi 创建到真实聊天（desktop）**：新建 `reasoning-e2e-514-r2`，选择 `kimiCoding:kimi-for-coding`。create 与已保存的 detail 页均显示 “Reasoning is always on and controlled by the model” 及解释文本，没有 reasoning select。点击 **Open chat**，发送 `Reply with exactly: Kimi route works.`，Agent 在 4.1 秒后显示正文 `Kimi route works.`，会话列表也显示同一正文。
2. **DeepSeek 选择范围未回归（desktop）**：从同一持久化 Agent 的 Config 页选择 `deepseek:deepseek-v4-flash`；“Reasoning effort”下拉框只有 `High`（已选）和 `Maximum`，且保留 “Recommended for this model: High” 说明。随后使用可见 **Discard** 放弃该仅用于验证的未保存选择。

## Evidence reviewed

| Evidence | Review conclusion |
| --- | --- |
| `evidence/browser.md`，`evidence/create-selectable-1440.png`，`evidence/create-selectable-controls.png` | 持久化 1440px 证据与本轮 DeepSeek 实测一致：只公开 High/Maximum，High 为推荐初值。 |
| `evidence/create-fixed-375.png`，`evidence/create-fixed-375-controls.png` | 持久化 375px 证据显示 Kimi Coding fixed-state 保持一列排版、只读说明且没有 effort selector。 |
| `evidence/fixed-model-detail-desktop.png`，`evidence/fixed-model-chat-desktop.png` | 持久化 desktop 证据显示 fixed Kimi 的保存后详情和成功聊天；本轮用新 E2E runtime 独立复现该聊天成功。 |
| 本轮 create、chat、DeepSeek 截图：`src/IM/frontend/.playwright-cli/page-2026-08-07T11-18-02-937Z.png`、`page-2026-08-07T11-19-45-400Z.png`、`page-2026-08-07T11-20-34-379Z.png` | 独立真实旅程：fixed Kimi 成功产出正文；DeepSeek 的可选项未扩展或倒退。 |

## Coverage updates

| Requirement / Scenario | Round 1 | Round 2 result | Evidence / note |
| --- | --- | --- | --- |
| 固定思考模型清楚说明限制而不伪造控件 / 选择 fixed Kimi | pass | **pass (reconfirmed)** | 新 create 与已保存 detail 的可见 fixed 说明；持久化 375px / desktop evidence。 |
| 模型与推理设置作为同一份 Agent 配置生效 / fixed Kimi 聊天入口 | fail — Issue 1 | **pass** | 新建并保存 `kimiCoding:kimi-for-coding` 后，真实首轮回复 `Kimi route works.`；见本轮 chat screenshot。 |
| 可调推理强度 / 选择 DeepSeek | pass | **pass (reconfirmed)** | 同一 Agent 的 Config 页只显示 High / Maximum，High 已选。 |
| 目录已更新使草稿选项失效；保存失败/确认中；已有模型能力变更；新增模型/节点 | inconclusive | **inconclusive (inherited)** | 本 targeted fast-lane 未改变前置；仍没有 reviewer 可安全执行的隔离运行时路径。 |

## Issue closure

### Issue 1 — fixed Kimi Agent 首轮聊天没有可读回复

- **Round 1 severity:** major
- **Round 2 status:** **closed**
- **Resolution evidence:** E2E 公开的 fixed 模型为已注册的 `kimiCoding:kimi-for-coding`；在全新隔离 stack 中走完保存 → Open chat → 发送首条消息，得到 `Kimi route works.`。没有观察到 Round 1 的空白气泡或 `anthropic: stream ended without terminal event`。

## Remaining required coverage

这不是新的产品 defect；它们是 Round 1 保留的必验浏览器覆盖缺口。要使全量 acceptance 可通过，实施方仍需提供不改 production 配置、且 reviewer 可在隔离 E2E runtime 中执行的前置，覆盖：live catalog 缩减、operation rejection/pending、既有模型 levels 变更和新模型/新节点。

## Review result for orchestration

```text
unit_id: feat-514-model-reasoning-effort
review_round: 2
verdict: fail
highest_required_action: fix-implementation
issues_count: { blocking: 0, major: 0, minor: 0 }
gh_issues_filed: []
report_path: docs/changes/feat-514-model-reasoning-effort/acceptance.md
top_concern: Issue 1 is closed, but inherited required browser coverage remains inconclusive.
needs_re_review: true
```

---

# Round 3 — 2026-08-07

> Revalidation: targeted fast-lane。复核 `2406442af65c0bc436bff801dfe01e62d17eee1d` 对 Round 2 未闭环项的修复：历史 reasoning 值从 fixed / 无声明模型的清除路径，以及 pending 保存是否自行收敛。既有 `inconclusive` 行继续继承，未因代码或 mock 测试改写为产品通过。

## Verdict

**fail**

**Highest Required Action:** `fix-implementation`

实际产品中，正常的历史值清除路径已经可完成：保存 DeepSeek `Maximum` 后，改为无声明的 Mimo 并保存为 v2，再切回 DeepSeek 时只出现推荐 `High`；重新保存 `Maximum` 为 v3、改 fixed Kimi 并保存为 v4 后，再切回 DeepSeek 仍是推荐 `High`。fixed 与无声明状态的详情页都没有遗留的 effort selector，用户能完成保存，不会被旧 `Maximum` 阻挡。

但“已经存在的 fixed / 无声明 profile 带旧值”与“请求已提交但 ACK 丢失”的两个特殊前置，无法仅通过该隔离产品的正常控件安全制造：前者的 API 正确拒绝非法组合，后者在 Gateway 离线前就会把节点标为 offline 并禁用保存。针对两者的本提交前端测试均通过，但它们使用受控响应，不能代替真实用户面验收。因此原先的保存失败/确认中必验 Scenario 仍为 `inconclusive`，全量 verdict 不能升级为 `pass`。

## Focused user journeys

测试环境：更新后的 unit worktree 隔离 IM + Gateway + Vite（IM `:58798`，Vite `:58936`），仓库 E2E owner `nano`。仅使用一个 headed 浏览器会话，完成后立即关闭；未接触生产服务或配置。

1. **无声明模型的可完成清除**：创建 `reasoning-e2e-514-r3`，以 DeepSeek `Maximum` 保存为 v1；改为 `mimo:mimo-v2.5-pro`，页面显示“does not expose configurable reasoning settings”，没有 selector，保存成功为 v2。再选择 DeepSeek，页面选中推荐 `High` 而非旧 `Maximum`。
2. **fixed 模型的可完成清除**：以 DeepSeek `Maximum` 保存 v3；改为 `kimiCoding:kimi-for-coding`，页面显示 “Reasoning is always on and controlled by the model”，没有 selector，保存成功为 v4。再选择 DeepSeek，页面同样回到推荐 `High`。
3. **Gateway 短暂离线的安全边界**：在未提交的 fixed-model 草稿期间停止隔离 Gateway；页面立即将 node 标为 offline、恢复已保存的 v1 DeepSeek 值并禁用保存。Gateway 重启后 node 回到 online。此操作没有产生已提交的 pending operation，故不能用于证明 ACK 丢失后的自动收敛。

## Evidence reviewed

| Evidence | Review conclusion |
| --- | --- |
| `evidence/browser.md` 与四个既有浏览器旅程 artifact | `2406442af` 未改动 `docs/changes/feat-514-model-reasoning-effort/evidence/`；其 selectable desktop、fixed mobile、fixed saved detail、fixed real chat 的内容仍与 `prototype.html` 和 Round 2 结论匹配。 |
| 本轮 no-capability、saved fixed、return-to-DeepSeek 截图：`src/IM/frontend/.playwright-cli/page-2026-08-07T11-58-05-426Z.png`、`page-2026-08-07T12-02-00-887Z.png`、`page-2026-08-07T12-02-34-672Z.yml` | 可观察的两个正常清除流均保存成功；fixed / 无声明均未留下无效 selector，回到 DeepSeek 时出现推荐 High。 |
| `npm test -- --run model-reasoning-field.test.tsx agent-create.test.tsx agent-edit.test.tsx` | **21 passed**。受控 503 `config_apply_pending` 用例在 1 秒后重试并回到已保存详情；fixed stale-value render 用例显示明确的 “Remove unavailable reasoning setting” 操作。此为 caller 要求的代码/测试辅助证据，不能替代下方 pending 的真实产品结论。 |
| `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/im_service/unit/test_agent_config_operations.py tests/unit/personal_assistant/config/test_parse_llm.py` | **21 passed**。 |

## Coverage updates

| Requirement / Scenario | Prior result | Round 3 result | Evidence / note |
| --- | --- | --- | --- |
| 从可调模型切换到固定思考模型 | pass | **pass (reconfirmed)** | DeepSeek Maximum → fixed Kimi 保存 v4；fixed detail 没有 selector，返回 DeepSeek 是 High。 |
| 无能力模型不出现可选控件（caller-directed） | pass | **pass (reconfirmed)** | DeepSeek Maximum → Mimo 保存 v2；无 descriptor 说明且无 selector，返回 DeepSeek 是 High。 |
| 保存失败时保留可理解的编辑状态 | inconclusive | **inconclusive (inherited)** | 受控测试显示 pending 会重试并收敛；真实隔离产品未能安全形成“已提交、等待确认”的状态，离线发生在提交前时保存被禁用。 |
| 目录已更新使草稿选项失效；已有模型能力变更；新增模型/节点 | inconclusive | **inconclusive (inherited)** | 本轮 targeted scope 未新增可由 reviewer 安全执行的 live-catalog 前置。 |

## Issue status

- Round 1 Issue 1（fixed Kimi 首轮聊天无正文）继续保持 **closed**；Round 3 未改变其 chat UI 或 E2E evidence，持久化 `fixed-model-chat-desktop.png` 仍记录可读成功回复。
- 本轮没有发现新的 blocking / major / minor 产品 defect。全量 `fail` 只来自仍未具备真实用户旅程证据的必验覆盖项。

## Review result for orchestration

```text
unit_id: feat-514-model-reasoning-effort
review_round: 3
verdict: fail
highest_required_action: fix-implementation
issues_count: { blocking: 0, major: 0, minor: 0 }
gh_issues_filed: []
report_path: docs/changes/feat-514-model-reasoning-effort/acceptance.md
top_concern: Normal fixed and no-capability clears succeed, but a real submitted-pending operation still lacks an acceptance-safe trigger and user-journey proof.
needs_re_review: true
```

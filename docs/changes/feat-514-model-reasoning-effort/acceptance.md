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

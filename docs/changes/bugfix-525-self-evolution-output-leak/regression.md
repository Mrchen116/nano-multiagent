# bugfix-525 — 回归验证

> 对齐: incident.md

> Validation snapshot: `cd071e649d3fe4fe7a2f392643a49c8f87825898 → 30a701a522f52ef337141806c39fa3848b93358e`

> Review round: 1（full revalidation）

## Verdict

- **Verdict: fail**
- **Highest Required Action: fix-implementation**
- 本轮 5 个必验 Scenario 中，memory 成功路径与普通后台 Agent 结果为 `pass`；no-save / failure、Skill 创建生效、terminal / reconnect 边界三项缺少可独立观察的完整产品证据，按严格验收口径为 `inconclusive`，因此不能放行。

## Reference Artifacts Reviewed

- 无原型、设计稿或截图 must-match 契约。本轮期望来源为 `incident.md` 的 5 个 Scenario、`design.md` 的 `Runbook for Reviewer`、本 unit 三份 delta-spec，以及 current Gateway / IM product specs。

## 验收环境

- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-525`
- branch / validated head: `unit/bugfix-525` / `30a701a522f52ef337141806c39fa3848b93358e`
- isolated node: `wt-unit-bugfix-525-59330`
- isolated IM: `http://127.0.0.1:62088`
- isolated identities: `nano / nano1234`，Agents `e2e`、`e2e-peer`
- services: IM PID `59416`，Gateway PID `59679`；两者 cwd 均为 unit worktree，Gateway 使用 worktree-local `.gateway-config.yaml` 和 `.gateway-workspace/`，未启用 Feishu，未读取用户生产配置。
- stale-binary check: IM 首页可达，首页 SHA-256 为 `2d2ee381df945e070adca2e209625f5e78b47144d39a681555e12026cf8545fa`，前端 bundle 为 `assets/index-C_9quz9B.js`；本 unit 不改客户端，产品后端由上述 worktree cwd 的新进程加载。
- Runbook deviation: `e2e-up.sh` 实际拉起并 auto-bind 真栈，但在 30 秒内未识别 Gateway readiness 文案而返回 `1`，因此未保留 `.e2e-ports.env`。IM OpenAPI、监听端口、Gateway WebSocket / auto-bind、PID 与进程 cwd 均独立核对为健康；详见 Side Findings。

## User Journeys Exercised

1. **J1 — memory review 成功路径**：在 `e2e-peer` 直聊（conversation `ce7a740d8f904296a0c3fbba7f20dee1`，Kernel session `sess_769c077f7a999088`）连续完成 10 个真实 bash 工具轮次，重复表达“recommendation 先给 reproducible-evidence table”的稳定偏好；等待后台 review，再从 Web IM 页面和隔离 workspace 双向核对。
2. **J2 — no-save / failure 边界尝试**：在 `e2e` 直聊（conversation `658b731208cf442c94cfd607d3cd84d4`，Kernel session `sess_4fdec4d58efc90b8`）先由前台 memory 工具保存唯一偏好，再连续完成 9 个无新信息的 bash 轮次，等待后台窗口；检查全部前台回复、raw 文本和通知。
3. **J3 — Skill 创建与边界尝试**：通过 Agent 配置页把 `e2e-peer` 保存为显式 allowlist（`handoff` 为 selected），`/new` 后在 session `sess_36ad8c97d58224f5` 连续执行 10 次相同 incident triage-card 工作流；等待后台窗口，再核对 Web IM 通知、workspace Skill 目录和 Agent 配置页候选/selected 状态。
4. **J4 — 普通后台 Agent 结果**：在 J1 会话中让 Agent 以 `run_in_background=true` 执行 `sleep 2; printf BG-R1-525-ORDINARY`；检查即时主回复与稍后的第二条 Agent 结果气泡，并重新进入 conversation 检查不重复。

## 复现验证

原生产缺陷表现为正常回答后出现独立 Agent 气泡 `Saved: ...`。J1 中每个前台回答都先正常完成；后台 review 随后只在时间线显示一条无头像、无发送者头的轻量 system 行：

```text
· Background self-evolution: memory updated
```

同一页面的完整可见历史中：

- `Saved:`：0 次；
- `Nothing to save.`：0 次；
- review prompt / side-chain 文本：0 次；
- memory-updated structured system notice：1 次；
- 普通后台 sentinel 结果：1 次。

重新进入 conversation 后，上述 memory notice 仍为 1 次，普通后台结果仍为 1 次，没有重放出第二条。隔离 workspace 的 `.nanoassistant/memory/USER.md` 同时出现 session `sess_769c077f7a999088` 对应的持久条目：

```text
User prefers that every recommendation begin with a short reproducible-evidence table ...
```

因此原始 `Saved: ...` 泄漏在成功 memory review 的真实 Web IM 主路径中不可复现，且持久副作用与 structured notice 同时成立。

## 验收标准覆盖

### Requirement: self-evolution 原始过程保持后台私有

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| memory review 在正常回答后完成 | `incident.md` L60-L67；Gateway routing delta “memory review 完成后只显示 structured notice” | J1：真实 Web IM 连续工具轮次 → 等后台 review → 页面历史 + workspace 文件 | 10 条正常 `PEER-R1-525-*` 回答；1 条 `Background self-evolution: memory updated` system 行；raw leak 0；`USER.md` 写入 session `sess_769c077f7a999088` 偏好；刷新后 notice 仍 1 条 | **pass** | 正常回答、持久更新、结构化通知、raw 隔离四项同时可见。 |
| 后台 review 没有可保存内容或执行失败 | `incident.md` L69-L72；Gateway routing delta “无更新或失败的 review 保持私有” | J2：已有前台保存后跑满 9 个无新信息工具轮次并等待；检查页面 | `TOOL-R1-525-1..9` 均正常；`Nothing to save.` /错误栈/raw 回复均未出现；无结构化通知 | **inconclusive** | 页面没有能证明后台 review 确实进入 no-save 或 failure 分支的正向信号；不能把“没看到 raw 文本”替代成该分支已执行。 |

### Requirement: skill 更新在前台 terminal 之后仍可靠生效

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| skill review 创建新 skill | `incident.md` L76-L82；Gateway agent-capabilities delta “fast review 与 slow review 使用同一调和结果” | J3：显式 allowlist + 新 session + 10 次重复 workflow；核对页面通知、workspace 与配置页 | `handoff` 保持 `aria-pressed=true`；10 次 workflow 完成后，无 skills-updated system 行；workspace 只有 `.usage.json` / `.curator_state.json`，无 Skill 目录；配置页 42 个候选中无 triage Skill | **inconclusive** | 确定性真实旅程未让 Skill review 产生新 Skill，故无法验证 raw 隔离、自动加入 explicit allowlist 和后续 session 可用性。前台第 2 轮只把 workflow 写入 memory，不等价于后台 Skill 创建。 |
| terminal 切换或可恢复重连覆盖事件边界 | `incident.md` L84-L90；Gateway agent-capabilities delta “后续前台轮次与 stream 重连不重复调和” | J1/J3：memory notice 与 `/new` 相邻到达并刷新重进；Skill 路径尝试建立显式 allowlist | memory notice 在 `/new` 相邻边界及重新进入后始终 1 条；但没有新 Skill 事件、激活或 reconnect 后可用结果 | **inconclusive** | 只得到 structured memory notice 的单次持久化旁证；Scenario 明确要求 Skill 不漏激活且不重复，不能用 memory notice 替代。 |

### Requirement: 其他后台结果语义保持不变

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 普通后台 Agent 产生用户可见结果 | `incident.md` L94-L97；current `docs/specs/gateway/routing-delivery.md` 后台任务 Requirement | J4：真实 Web IM 启动后台 bash，等待完成，再重新进入 conversation | 主回复 `ORDINARY-STARTED-R1-525`；第二条 Agent 气泡 `Background task ... completed (output: BG-R1-525-ORDINARY).`；刷新重进后仍恰好 1 条 | **pass** | 非 self-evolution 后台文本未被屏蔽，也未重复。 |

## 回归测试

- 正常 Web IM 前台问答：J1/J2/J3 共 30 个以上真实前台回合，除 Side Finding 记录的一次空正文外，后续会话可继续，用户输入与 Agent 回复顺序正常。
- 结构化 self-evolution notice：实时出现、无 Agent 头像/发送者头，重新进入后仍按同一 system 语义显示且不重复。
- 普通后台 Agent route：即时“已启动”语义与稍后的第二条完成结果同时成立。
- Agent 配置：通过真实配置页保存显式 Skill allowlist，重新打开后 `handoff` 仍 selected；未触碰生产 Feishu 或用户 Gateway config。

## Issues

### R1-I1 — no-save / failure 分支缺少可独立确认的产品旅程

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: 必验 Scenario 要求 no-save / failure 时不泄漏且不改变正常回答；当前 Runbook 没有能从真实入口确定进入该分支的受控步骤，页面无正向信号时 reviewer 无法区分“分支执行且保持私有”和“分支根本没执行”。第一轮默认回实现收口确定性验收入口或可观察结果。
- **Expected**: 可从隔离 Web IM / actual relay 确定触发 no-save 或失败的 review，同时看到前台回答保持完成，且没有 raw reply/错误栈。
- **Actual**: J2 前台回复均完成且无 raw 文本，但没有证据证明后台 review 确实进入目标分支。

### R1-I2 — Skill 创建、激活与边界恢复无法在确定性真实入口中闭环

- **Severity**: major
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: 两个必验 Scenario 都要求真实新 Skill、显式 allowlist 生效和 terminal/reconnect 后不漏不重；J3 跑满重复 workflow 后没有创建 Skill，不能用 integration test、Kernel event 或 memory notice 替代用户结果。
- **Expected**: 页面只显示一次 skills-updated system 行；workspace 出现新 Skill；配置页 explicit allowlist 自动含新 name；新 session 可实际使用；terminal/reconnect 后不漏、不重复。
- **Actual**: 无 skills-updated notice、无新 Skill 目录、配置页无新候选，因而激活/后续 session/reconnect 无法验。

## Side Findings

- **Minor / environment**：`e2e-up.sh` 在 IM、Gateway、WebSocket 与 auto-bind 均已成功时仍因 readiness 文案未命中而超时返回 `1`，且不生成 `.e2e-ports.env`。本轮用 PID、cwd、监听端口、OpenAPI 与浏览器真入口交叉确认服务健康后继续；这会增加下一轮复现成本，但未改变上述产品结果。
- **Minor / unrelated-existing**：J3 的 `CASE-R1-525-1` 前台回合显示工具过程但没有正文，后续 9 个回合正常。它不是本 unit 的 raw self-evolution 泄漏，也未阻塞目标路径，未单独立 issue。

## 自动化测试增量

- 本 reviewer 未把 worker 的自动化测试或 progress 结论作为 Scenario `pass` 证据，也未读取实现源码。
- `progress.md` 仅用于了解里程碑声称的覆盖面；本轮 verdict 完全依据上述真实 Web IM、配置页、隔离 workspace 和进程入口观察。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**；本修复不改变顶点依赖或部署拓扑。
- [x] `docs/specs/<包>/`（长青行为契约层，本 unit 触及的 area；通常由 orchestrator §7.1 收尾归并写入）：**需要更新**；本 unit 已提供 Gateway `routing-delivery` / `agent-capabilities` 与 Kernel `runs` delta-spec，canonical 尚待收尾归并。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范，仅当本 unit 改了文档体系本身时）：**无需更新**。

## Recommended Next Step

建议 fix worker 只收口两项验收缺口：为 reviewer 提供不读取源码、能经 isolated Web IM / actual relay 确定触发 no-save/failure 的步骤；提供能确定让 self-evolution 创建 Skill、跨 terminal/reconnect 后在 explicit allowlist 与新 session 中可见且只通知一次的步骤或产品能力。修复后 Round 2 应至少 targeted 复验本轮 3 个 `inconclusive` Scenario；若变更触及事件分类、Gateway lifecycle 或 Runbook 基建，则升级为 full revalidation。

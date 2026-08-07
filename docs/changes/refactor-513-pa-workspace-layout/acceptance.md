# refactor-513 — 验收报告（Round 1）

> 对齐: [motivation.md](motivation.md) 的用户侧验收标准
>
> Validation snapshot: `f54e008b1 → e0e61f779`

## Verdict

**fail**

Highest Required Action: **fix-implementation**

PA 的 Web IM 主路径在用户点开在线 Agent 时直接落入错误页，无法发起对话；CLI 的现有 `/tools` 用户命令也在新 session 上报 runtime error。因此无法确认 PA 的聊天副本、heartbeat/后台任务路径，以及 CLI workspace extension/background task 的用户承诺。

## 用户旅程体验

本轮按 `design.md` 的 Reviewer Runbook 在 unit worktree 重启了隔离 IM + Gateway（随机高位端口、隔离数据库、Gateway config、workspace 和临时 IM 身份），确认节点 online 后开始验证；未触碰生产 home、secret、IM `:8011` 或生产 Gateway。

1. **PA Web IM 主路径（失败）**：浏览器登录隔离 Web IM 后，进入 `Agents`，列表中的 `e2e` 显示 online；点击该 Agent 后页面立即替换为 `Unexpected Application Error!`，无法进入 Agent 详情或直接聊天。此处没有用户可见的 API 错误响应，React Router 默认错误边界直接覆盖页面。
2. **PA 已初始化状态与 heartbeat RPC（部分完成）**：隔离 Gateway 的两个显式 workspace 都创建了 `<workspace>/.nanoassistant/{HEARTBEAT.md,memory,skills}`，未看到 root `HEARTBEAT.md`、root `chat_history/` 或 `.nano/`。真实 IM `GET /im/v1/agents/e2e/heartbeat-md` 返回同一 `HEARTBEAT.md` 内容且 `node_online: true`。但 UI 崩溃阻止了从对话触发 heartbeat、产生聊天副本或后台 bash output。
3. **CLI workspace（失败）**：在新的临时 workspace 中，显式从本 unit 的 `src/` 启动 CLI；`/new` 成功创建 `.nanocode/sessions/<id>.jsonl`，且没有 `.nano/`、`.nanoassistant/`、root `chat_history/` 或 root `HEARTBEAT.md`。随即执行 `/tools`，终端显示 `Error: failed to run /tools.` / `Layer: runtime`，因此用户无法查看 session 的可用工具，也无法完成 workspace extension 的可见性旅程。
4. **SDK 默认/自定义目录（通过）**：两个实际 `agent.sdk` consumer 在临时 workspace 创建 session：未传目录名时只创建 `.nano/sessions/<id>.jsonl`；传入 `.consumer` 时只创建 `.consumer/sessions/<id>.jsonl`。同一 consumer 对 custom session 调 `list_session_tools` 返回 10 个工具，说明这条 public SDK 入口可用。

## Reference Artifacts Reviewed

N/A。design 与验收标准没有要求原型、截图或视觉 must-match 对照；本轮的浏览器截图仅作为 PA 错误页证据。

## 问题清单

### 1. PA 用户点击在线 Agent 后落入错误页，聊天主路径无法开始

- **Severity:** blocking
- **Regression Relation:** unclear
- **Recommended Action:** fix-implementation
- **Action Rationale:** 这直接阻塞本 unit 的 PA 对话、chat history、heartbeat 与后台输出旅程；第一轮不对根因或 design 归责，交由实现修复并复验。
- **Exact user action:** 登录隔离 Web IM（`nano` 测试用户）→ `Agents` → 点击显示 `online` 的 `e2e` Agent。
- **Observed page:** `Unexpected Application Error!` / `Cannot read properties of undefined (reading 'trim')`。
- **Visible browser-console stack:**

  ```text
  Error handled by React Router default ErrorBoundary: TypeError: Cannot read properties of undefined (reading 'trim')
      at J0 (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:52:80837)
      at http://127.0.0.1:63187/assets/index-DhgsaA8v.js:52:110834
      at Object.ug [as useMemo] (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:8:57246)
      at qe.useMemo (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:1:8945)
      at iz (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:52:110807)
      at ed (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:8:48275)
      at vd (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:8:71135)
      at Ig (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:8:81525)
      at yy (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:8:117364)
      at Hw (http://127.0.0.1:63187/assets/index-DhgsaA8v.js:8:116404)
  ```

### 2. CLI 新 session 的 `/tools` 命令报 runtime error

- **Severity:** major
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** `.nanocode` 的初始 session 已建立，但用户无法通过产品现有 `/tools` 查看 session 能力，阻断本 unit 要求的 workspace extension 可见性旅程。
- **Exact terminal result:** `/new` 显示 `Started new session ...`；随后 `/tools` 显示 `Error: failed to run /tools.`、`Layer: runtime`、`Suggestion: check configuration and retry /tools.`。

## 验收标准覆盖

### Requirement: 未指定产品目录的内核用户保持 `.nano` 默认行为 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 消费者未提供 workspace 目录名 | motivation.md | 真实 public `agent.sdk` consumer 在空临时 workspace 创建 session | 仅出现 `.nano/sessions/sess_917080869c46ebad.jsonl` | pass | 同次 custom consumer 仅出现 `.consumer/sessions/...`，未混写。 |

### Requirement: PA 的 workspace 状态收敛到 `.nanoassistant/` — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| PA 在代码仓 workspace 中产生新状态 | motivation.md | 隔离 Gateway + Web IM；登录、选择 online Agent、尝试开始对话 | Agent 点击后错误页；初始 `.nanoassistant/{HEARTBEAT.md,memory,skills}` | fail | 无法完成对话、heartbeat trigger 或 background bash，不能以初始目录替代完整旅程。 |
| PA 继续提供简化聊天副本 | motivation.md | 同一 PA 对话旅程 | Web IM Agent 页错误，未能完成一轮对话 | fail | 因而无法观察 `.nanoassistant/chat_history/` 中 user/assistant 副本。 |
| 人工迁移后的既有 PA heartbeat 继续生效 | motivation.md | 手工部署迁移 + PA heartbeat | 生产迁移未执行；仅审阅 `docs/operations/pa-workspace-layout-migration.md` | inconclusive | 该场景涉及真实既有数据与生产 secret；按 runbook 禁止用生产环境替代隔离验收。 |

### Requirement: PA 的全局数据与默认 workspace 收敛到 `~/.nanoassistant/` — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新建默认 PA Agent | motivation.md | Web IM 创建/进入 Agent；检查其默认 workspace | Agent 详情路由错误；隔离 config 又刻意提供了 `node.workspace_base` override | inconclusive | 无法在不触碰真实 home 的前提下完成默认-home 真实旅程。 |
| 首次部署前人工迁移旧 PA 全局数据和默认 workspaces | motivation.md | 两机生产部署 runbook | 已审阅一次性迁移 prompt，未在生产运行 | inconclusive | 这是明确的 production-only 手工操作。 |
| 默认 workspace 的遗留运行文件随 workspace 保持相对位置 | motivation.md | 完整 default-workspace 手工迁移 | 未执行生产数据迁移 | inconclusive | 不以文档文本代替运行结果。 |
| 人工迁移遇到内容冲突 | motivation.md | 冲突手工迁移 | 未执行生产数据迁移 | inconclusive | 同上。 |
| mini 的 IM JWT 签名密钥随全局根保留 | motivation.md | mini secret preflight、重启 IM 和双 Gateway online | 未触碰生产 secret / IM `:8011` | inconclusive | runbook 已给出 0600、same/different fail-closed 规则，但未拿 production 替代验收。 |
| 用户指定外部 workspace | motivation.md | 隔离 Gateway 使用显式 workspace_root；读取 IM config 与磁盘状态 | IM 返回 worktree 内显式 `.gateway-workspace/e2e`；状态写在其 `.nanoassistant/` | pass | workspace 未被搬到默认 product home。 |

### Requirement: CLI 的 workspace 状态遵循 `.nanocode/` — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| CLI 在 workspace 中运行后台任务或使用 workspace extension | motivation.md | 新临时 workspace 的真实 CLI `/new` → `/tools`，再继续 extension/background journey | `.nanocode/sessions/...` 已创建；`/tools` runtime error | fail | 无法从产品入口确认 extension 可见性或 background output。 |

### Requirement: 旧共享扩展在首次部署时安全分叉 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 人工迁移 PA 的已有共享扩展 workspace | motivation.md | 生产部署手工迁移 | 未执行 production-only migration | inconclusive | runbook 是必要材料，不等于已验证的迁移结果。 |
| 人工迁移 CLI 的已有共享扩展 workspace | motivation.md | 生产部署手工迁移 | 未执行 production-only migration | inconclusive | 同上。 |
| 目标已有同名产品扩展 | motivation.md | 冲突手工迁移 | 未执行 production-only migration | inconclusive | 同上。 |
| 人工迁移后的旧目录发生变化 | motivation.md | 部署后再次启动产品 | PA 主路径和 CLI `/tools` 均阻塞 | inconclusive | 无法完成“只加载产品副本”的用户路径。 |

### Requirement: workspace 安全策略随实际产品目录生效 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 人工迁移已有 workspace 的安全策略 | motivation.md | production-only 手工迁移 | 未执行生产迁移 | inconclusive | 不以 runbook 审阅充当真实迁移验收。 |
| PA 或 CLI 运行 workspace 命令 | motivation.md | 通过 PA/CLI 触发受 policy 约束的命令 | PA 聊天路径及 CLI `/tools` 均阻断 | inconclusive | 无法建立真实 tool command 旅程。 |

### Requirement: 旧运行数据与仓库版本控制不被静默改写 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 外部 workspace 的旧聊天副本和后台输出保持可查看 | motivation.md | 带既有 legacy 文件的外部 workspace 升级旅程 | 本轮未建立可完成的 PA/CLI tool journey | inconclusive | 不从无旧文件的空 workspace 推断保留行为。 |
| workspace 是 Git 仓库 | motivation.md | 在 Git workspace 启动 PA/CLI 后检查版本控制文件 | 本轮未完成可用 PA/CLI 主路径 | inconclusive | 不能用未发生的写入推断 Git 不会被改。 |

### Requirement: 产品运行时只使用终态目录 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 部署后启动 PA 或 CLI | motivation.md | 隔离 PA 初始化与 unit-source CLI 新 session | PA 仅见 `.nanoassistant` 初始状态；CLI 仅见 `.nanocode`，但两个主路径分别被 UI / `/tools` 阻断 | inconclusive | 路径初始写入符合目标，但不能确认完整运行时只使用终态目录。 |

## Side Findings

无。所有本轮发现都阻塞或直接影响本 unit 的用户旅程，因此保留在 unit 内处理；未创建 GitHub issue。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；当前顶层 workspace 图已展示 `.nanoassistant` 下的 sessions、memory、skills、tools、hooks、chat history 与 heartbeat。
- [x] `docs/specs/<包>/`（长青行为契约层，本 unit 触及的 area；通常由 orchestrator §7.1 收尾归并写入）：无需更新；本轮 snapshot 的 kernel / CLI / Gateway / IM canonical spec 已合并该 unit 增量。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；产品仅经 `agent.sdk`、IM 独立的现有架构约束未变。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新；已核对 delta-spec 归并规则，本 unit 未改变该规范本身。

当前的 `README.md`、`docs/operations/`、PA builtin product reference 也已写入 `.nanoassistant` / `.nanocode` 与手工迁移入口；但这些文档更新不能替代上述失败的真实用户旅程。

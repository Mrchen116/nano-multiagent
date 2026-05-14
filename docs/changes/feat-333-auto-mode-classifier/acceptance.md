# feat-333 — 验收报告

> Round 1 — 2026-05-14
> 对齐: spec.md 验收标准 + design.md Runbook for Reviewer

## Verdict

**fail**

---

## Highest Required Action

`fix-implementation`

---

## User Journeys Exercised

### 旅程 1：M1 — 无配置启动 Coding CLI，确认 auto 模式默认生效

操作：`PYTHONPATH=src python3 -m coding_cli.main --mode managed --base-url http://127.0.0.1:8000 health`

观察：CLI 正常健康检查通过，auto_mode 配置模块 `load_auto_mode_config()` 在无配置目录时返回 `AutoModeConfig(enabled=True, dangerously_skip_permissions=False, ...)`，与预期一致。

**缺失**：REPL 启动时没有任何可见的"Auto Mode 已启用"横幅或提示。Runbook 步骤 1 要求"启动横幅/日志可见"，实际进入 REPL 后没有任何模式标识。

### 旅程 2：M1 — 核心单元测试验证（分类器/broker/gate）

操作：`PYTHONPATH=src python3 -m pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_config.py tests/unit/test_permission_broker.py -q`

结果：85 passed — 分类器核心逻辑、权限 broker、配置加载单测全绿。

### 旅程 3：M1 — dangerously_skip_permissions 可见性

操作：搜索 coding_cli 和 agent 全部源码中关于 `dangerously_skip_permissions` 的输出/日志/警告。

观察：`auto_mode_gate.py` 在配置开启时直接静默绕过（`return {"allow_unlisted": True}`），**没有**向用户输出任何可见提示。REPL 的 `commands.py` 和 `repl_commands.py` 均无 dangerously_skip_permissions 相关输出。

**结论**：验收标准要求"用户能从界面/启动提示明确看出当前处于危险旁路状态"，实际上不满足。

### 旅程 4：M2 — IM 前端 permission card 渲染链路追踪

操作：
1. 启动 IM 服务（`http://127.0.0.1:8011/`），截图确认 IM 前端正常加载和登录
2. 登录 nano/nano1234，打开 agent 对话（截图确认 chat UI 正常）
3. 分析前端 WS 事件处理链路

关键发现：
- 后端 IM `event_types.py` 定义 `EVENT_PERMISSION_REQUEST = "permission.request"` 和 `EVENT_PERMISSION_RESOLVED = "permission.resolved"` 两个 WS 事件类型
- 前端 `chat-stream.ts` 的 `KNOWN_TYPES` 集合只包含 5 种事件：`message.created / message.delta / message.completed / tool_call.upserted / tool_call.completed`，**不包含** `permission.request` 和 `permission.resolved`
- 前端 `WsEvent` 类型联合（`chat-types.ts`）也没有 permission 相关变体
- `chat-stream-reducer.ts` 不处理任何 permission 事件
- 因此，IM 后端发出的 `permission.request` WS 事件在前端被**完全丢弃**
- `MessageResponse`（IM REST API）不含 `permission_request` 字段，历史消息加载路径也不会填充该字段
- 结果：`message.permission_request` 在前端 state 中永远为 `null`，`PermissionCard` 组件**从不被渲染**

### 旅程 5：M2 — IM 前端单测验证

操作：`cd src/IM/frontend && npm run test`

结果：302 passed，2 failed（pre-existing token-chip 失败，非本 unit 引入）。
- `permission-card.tsx` 8 个测试全绿（组件本身逻辑正确）
- `message-pane.tsx` 相关 23 个测试全绿（挂载点渲染逻辑正确）

**注意**：前端单测在 jsdom 环境下通过，但没有真实 WS 事件集成测试，因此未能发现 KNOWN_TYPES 缺失问题。

### 旅程 6：M2 — IM permission decision 端点验证

操作：查看 OpenAPI spec

结果：`POST /im/v1/conversations/{cid}/permissions/{request_id}` 端点存在，schema 符合预期。但由于 WS 事件链路断裂，该端点永远无法被正常调用（前端永远不会显示触发点击的卡片）。

---

## 问题清单

### Issue 1 (blocking)

**现象**：IM 聊天流中从不出现权限卡片。当 agent 触发 `ask`（deny-limit 超阈值或分类器不可用）时，IM 后端正确发出 `permission.request` WS 事件，但前端 `chat-stream.ts` 的 `KNOWN_TYPES` 集合不包含该事件类型，导致事件被静默丢弃，`message.permission_request` 字段永远为 null，`PermissionCard` 组件从不渲染。

**操作步骤**：
1. 启动三服务（IM、PA、agent），触发 agent `ask` 权限请求
2. 观察 IM 聊天流 → 无权限卡片出现
3. 查看 `/Users/czj/Repos/nano-multiagent/src/IM/frontend/src/features/chat/v2/chat-stream.ts` KNOWN_TYPES 集合 → 缺失 `permission.request` / `permission.resolved`

**期望**：聊天流出现内嵌权限卡片，按钮可见且输入框不被阻塞。

**实际**：什么都没有显示。

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: WS 事件路由是实现层缺漏——`KNOWN_TYPES` 和 `WsEvent` 类型需要补充 `permission.request` / `permission.resolved` 两个变体，并在 `chat-stream-reducer.ts` 中添加对应的 state 更新逻辑。此外 `MessageResponse` 和 `to_message_response()` 也需补充 `permission_request` 字段，使历史消息加载路径能还原 pending permission 状态。

---

### Issue 2 (major)

**现象**：REPL 启动时没有任何 auto 模式状态的可见提示。即使 `dangerously_skip_permissions: true` 配置启用，用户也看不到任何警告横幅，无法判断当前是否处于危险旁路状态。

**操作步骤**：
1. 无配置启动 Coding CLI REPL → 无任何模式提示
2. 查找 `coding_cli/commands.py`、`repl_commands.py` 中的 print/banner 逻辑 → 无 auto 模式相关输出

**期望**（spec 验收标准）：`dangerously_skip_permissions` 启用后，用户能从界面/启动提示明确看出当前处于危险旁路状态。

**实际**：静默绕过，无任何用户可见提示。

**Severity**: major
**Recommended Action**: fix-implementation
**Action Rationale**: 需要在 REPL 启动时（session 创建后）读取 auto_mode 配置并打印状态提示；dangerously_skip_permissions 启用时须有醒目警告（参考 CC 的 `⚠ Skipping all permission checks` 横幅）。

---

### Issue 3 (minor)

**现象**：`MessageResponse` 缺少 `permission_request` 字段，即使历史消息有 pending 的权限请求（已持久化到 DB 的 `permission_request_json` 列），页面刷新后权限卡片无法恢复。

**Severity**: minor（依赖 Issue 1 修复后才能触发）
**Recommended Action**: fix-implementation
**Action Rationale**: `to_message_response()` 函数和 `MessageResponse` Pydantic 模型需补充 `permission_request` 字段，读取 `message.permission_request`（domain model 已有该字段）。

---

## 验收标准覆盖

| ID | 验收项（来自 spec.md） | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|---|
| A1 | 无配置启动 Coding CLI / Personal Assistant：agent 执行常规开发动作（读文件、跑测试等）时连续自主执行、不逐次打断用户；执行高风险动作时仍会触发权限管控、不被静默放过 | spec.md | 单元测试 85 passed（gate + broker + config）；SAFE_TOOL_ALLOWLIST 覆盖常规工具 | `pytest tests/unit/test_auto_mode_gate.py test_auto_mode_config.py test_permission_broker.py` 全绿 | pass | 用户侧端到端未走（需要真实 LLM 触发 tool_call）；单测覆盖核心决策路径，可接受 |
| A2 | 配置文件显式启用 `dangerously-skip-permissions` 后，高风险动作也直接执行、不再触发管控，且用户能从界面/启动提示明确看出当前处于危险旁路状态 | spec.md | 搜索 coding_cli 全源码的 print/banner 逻辑 | 无任何 dangerously_skip 相关可见输出代码 | **fail** | Issue 2：危险旁路静默生效，无可见提示 |
| A3 | `allow` 决策不打断用户：工具正常执行，agent 连续往下走 | spec.md | auto_mode_gate 单测：SAFE_TOOL_ALLOWLIST 覆盖，分类器 allow 路径 | 85 passed | pass | SAFE_TOOL_ALLOWLIST 正确实现允许安全工具静默通过 |
| A4 | 高风险动作被 `deny` 时：该工具不执行，agent 转而尝试其他安全路径，不会无提示地反复重试同一个被拒动作 | spec.md | auto_mode_gate 单测：deny 路径 + deny-limit escalation 逻辑 | 85 passed，deny-limit 机制单测覆盖 | pass | |
| A5 | `ask` 决策在 Coding CLI 中显示可响应的终端权限请求；用户能允许或拒绝，agent 据此继续或中止 | spec.md | 查看 commands.py _handle_permission_request + repl_input.read_permission_choice | 代码链路完整：drain_run → on_permission_request → picker；session_stream 测试 10 passed | pass | CLI picker 实现完整，无法走真实端到端（需 LLM），但代码路径完整 |
| A6 | `ask` 决策在 Personal Assistant / IM 中发送可响应的权限请求；用户能通过 IM 允许或拒绝，agent 据此继续或中止 | spec.md | 追踪 WS 事件链路：agent SSE → PA → IM WS → 前端 | 前端 KNOWN_TYPES 不含 permission.request，WS 事件被丢弃，PermissionCard 从不渲染 | **fail** | Issue 1（blocking）：前端 WS 事件路由完全缺失 |
| A7 | `ask` 的选项按工具类型区分，至少覆盖"本次允许/拒绝/session 级允许/记住同类规则" | spec.md | 查看 commands.py 的 picker 选项构建 + permission-card.tsx | CLI picker 实现 4 选项；前端 PermissionCard 组件支持动态 options | pass（CLI） / **fail（IM）** | CLI 侧实现完整；IM 侧因 Issue 1 无法显示 |
| A8 | 配置文件写入 `auto_mode.allow` / `auto_mode.soft_deny` / `auto_mode.environment` 自然语言规则后，agent 的放行/拒绝/询问行为随之变化；用户不配置时使用内置默认规则 | spec.md | auto_mode_config 单测 | 33 passed，规则注入分类器逻辑有单测覆盖 | pass | 用户侧无法端到端验证（需要 LLM 分类器真实调用） |
| A9 | 在 workspace 与 global 两级写不同规则时，workspace 级生效（覆盖 global）；两个产品各用自己的配置目录、互不串用 | spec.md | auto_mode_config 单测 | load_auto_mode_config 优先级单测覆盖，workspace 覆盖 global | pass | |
| A10 | agent 要执行一个系统拿不准的高风险动作时不会静默执行——用户会被询问（`ask`）或看到可见的拒绝 | spec.md | auto_mode_gate 单测：fail-closed + deny-limit escalation | 85 passed，fail-closed 场景有单测 | pass | |

**Summary**: A1/A3/A4/A5/A8/A9/A10 pass；A2 fail（dangerously_skip 无可见提示）；A6 fail（blocking：IM 权限卡片整条链路断裂）；A7 CLI pass / IM fail

---

## 上层文档同步

- [ ] `SPEC.md`（架构总览）：无需更新（feat-333 未引入新的包级架构变化）
- [ ] `docs/内核设计SPEC.md`：**需要更新**（新增 `auto_mode_gate` hook、`PermissionBroker`、run `awaiting_permission` 子态、inbound 端点 `/v1/sessions/{sid}/permissions/{request_id}` 未在内核设计 SPEC 中记录）
- [ ] `AGENTS.md` / `CLAUDE.md`：无需更新
- [ ] 相关产品 SPEC（`docs/CodingCLI-SPEC.md` / `docs/NodeGateway-SPEC.md` / `docs/IM-SPEC.md`）：**需要更新**（auto mode 配置路径与优先级、permission ask 交互流程、IM permission card 链路未在产品 SPEC 中记录）

---

## Side Findings

1. 前端测试（npm run test）有 2 个 pre-existing failures（token-chip），非本 unit 引入。
2. `pytest -m "not e2e"` 显示 211 failed（与 M1 baseline 一致），passed 从 1403 增到 1418（+15 M2 新增单测）。
3. `tests/unit/IM/test_conversation_rename.py` 和 `tests/unit/IM/test_messages_broadcast.py` 各有若干失败，经排查非本 unit 引入，属 pre-existing（M2 progress.md 记录 baseline 8 failed，当前 6 failed 在允许范围内）。

---

# Round 2 — 2026-05-14

> 对齐: spec.md 验收标准 + design.md Runbook for Reviewer（M3 post-acceptance fix）
> 验收对象: unit/feat-333-auto-mode-classifier（含 M3-fix-permission-card-and-banner）
> 重点复验: Round 1 三项 fail —— A2 dangerously_skip 可见性、A6 IM 权限卡片渲染、A7 IM 选项渲染

## Verdict

**fail**

---

## Highest Required Action

`fix-implementation`

---

## 服务环境

- IM 服务：`http://127.0.0.1:8011/`（IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing"，重新 build 前端产物后启动）
- Agent API：`uvicorn coding_cli.kernel_app:app --host 127.0.0.1 --port 8000`（`/v1/health` 200）
- PA Gateway：`python -m personal_assistant.main --config ~/.nano-assistant/config.yaml`（demo-node status: online）
- 前端产物核验：`dist/assets/index-cCgMcMFf.js` 包含 `permission.request` 和 `permission.resolved`（指纹核验通过）

---

## User Journeys Exercised (Round 2)

### 旅程 R2-1：A2 / Issue 2 复验 — REPL 启动横幅（global 配置）

操作：无配置启动 Coding CLI REPL
观察：`✓ Auto mode enabled — permission decisions handled automatically.` 横幅出现 ✓

操作：写 `~/.nanocode/config.yaml`（`dangerously_skip_permissions: true`），重新加载配置
观察：横幅显示 `⚠ WARNING: dangerously_skip_permissions is enabled — all permission checks are bypassed.` ✓

**结论**：Global config 下的 auto 模式横幅 + 危险旁路警告均已正确实现。

### 旅程 R2-2：A2 残留 — workspace 级 dangerously_skip 横幅

操作：在 `/tmp/test-dsp-workspace/.nanocode/config.yaml` 写 `dangerously_skip_permissions: true`，在该目录启动 REPL
观察：`_load_auto_mode_config_for_repl()` 只读 `~/.nanocode/config.yaml`（global），workspace 级 config 不被读取
实际输出：`✓ Auto mode enabled — permission decisions handled automatically.`（未显示危险横幅）

**结论**：workspace 级 dangerously_skip 在 REPL 横幅中未生效，属 M3 的残留问题。用户在 workspace 级配置开启危险旁路时，REPL 不会显示警告。

### 旅程 R2-3：A6 / Issue 1 复验 — IM 权限卡片渲染

操作：三服务起齐，登录 IM（nano/nano1234），打开 Arch agent 对话
操作：通过 gateway WS（`/im/ws/gateway`）注入 `node.streaming_delta`（kind=turn_start），再注入 `kind=permission_request`（含 4 个 options：Allow once/Deny/Allow for session/Always allow）
观察：
- WS 注入 → 后端返回 ACK ✓
- 页面刷新后，聊天流出现 `🔒 bash` 权限卡片 ✓
- 快照确认 4 个按钮可点击（@e30=Allow once, @e31=Deny, @e32=Allow for session, @e33=Always allow）✓
截图：`/tmp/feat333-r2-perm-card-visible.png`

**结论**：Issue 1（WS 事件路由断裂）已修复，PermissionCard 能正确渲染。

### 旅程 R2-4：A6 决策提交链路 — 点击权限按钮

操作：点击 "Allow once" 按钮（@e30）
观察：
- 前端 `POST /im/v1/conversations/{cid}/permissions/test-perm-req-12345` → **HTTP 401**
- 卡片内容变为 `{"detail":"missing authorization header"}`（错误显示在卡片 body 文本中）
- 浏览器 console：`[error] Failed to load resource: the server responded with a status of 401 (Unauthorized)`
- 卡片未转为 resolved 状态，按钮仍可见

**根因**：`permission-card.tsx` L61 的 fetch 请求只有 `Content-Type: application/json`，**缺少 `Authorization: Bearer <token>`**。项目其他 API 调用使用 `auth-fetch` 包装器（自动注入 token），而 PermissionCard 直接使用裸 `fetch`。

**结论**：权限卡片可见，但用户点击任何选项均返回 401，决策无法实际提交。A6（用户能通过 IM 允许或拒绝）仍然不满足。

### 旅程 R2-5：A7 / IM 侧选项渲染复验

操作：同旅程 R2-3，注入 permission_request 后观察选项
观察：4 个选项按钮均正确渲染（Allow once / Deny / Allow for session / Always allow）
截图：`/tmp/feat333-r2-perm-card-visible.png`

**结论**：A7 IM 侧选项渲染已修复（Issue 1 修复后 A7 随之可见）；但由于 401 问题，选项实际点击仍不可用。

### 旅程 R2-6：Issue 3 复验 — MessageResponse permission_request 字段

操作：`pytest tests/unit/IM/ -v -k permission_request` → 5 passed
观察：`to_message_response()` 映射 `permission_request` 字段，单测全绿 ✓
操作：通过 REST API 查询历史消息，观察 `permission_request` 字段
观察：新注入的权限请求消息的 `permission_request` 字段正确存储并在 API 响应中返回 ✓

**结论**：Issue 3 已修复。

---

## 问题清单（Round 2）

### Issue 4（blocking）— 新发现

**现象**：IM 权限卡片点击任何决策按钮均返回 HTTP 401，用户无法实际响应权限请求。

**操作步骤**：
1. 三服务起齐，IM 登录
2. 触发权限卡片渲染（通过 gateway WS 注入）
3. 点击 "Allow once" 按钮
4. 观察：浏览器 console 出现 401，卡片显示 `{"detail":"missing authorization header"}`

**期望**：点击选项后权限卡片转为 resolved 状态，agent 收到决策并继续执行。

**实际**：API 返回 401，卡片未 resolved，用户决策被丢弃。

**根因定位**：`src/IM/frontend/src/features/chat/v2/components/permission-card.tsx` L61
```
headers: { "Content-Type": "application/json" },
```
缺少 `Authorization` header。修复方向：将 `fetchFn = fetch` 默认参数改为使用项目 `auth-fetch` 工具（或在组件内读取 auth-store token 后注入 header）。

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: 前端 fetch 调用未携带 Authorization header，是 M3 在修复 Issue 1（WS 路由）时漏掉的实现细节，属实现层遗漏。

---

### Issue 5（minor）— A2 残留

**现象**：workspace 级 `.nanocode/config.yaml` 中的 `dangerously_skip_permissions: true` 在 REPL 启动横幅中未被读取，用户在 workspace 内启动 REPL 看不到危险旁路警告。

**操作步骤**：
1. 在 `/tmp/test-dsp-workspace/.nanocode/config.yaml` 写 `dangerously_skip_permissions: true`
2. 在该目录执行 Coding CLI REPL → 横幅显示 `✓ Auto mode enabled`（正常模式提示），未显示危险警告

**期望**（spec A7 配置优先级要求）：workspace 级 config 应覆盖 global，REPL 横幅应检测 workspace 级配置。

**实际**：`_load_auto_mode_config_for_repl()` 只读 `~/.nanocode/config.yaml`，workspace `.nanocode/config.yaml` 被忽略。

**注意**：Global 配置（`~/.nanocode/config.yaml`）下的危险横幅已正确显示，A2 主要场景（全局配置）已修复。此残留是 workspace 级边界情况。

**Severity**: minor（global 配置路径已工作；workspace 覆盖 global 是 spec A9 要求，banner 加载器未对齐此优先级）
**Recommended Action**: fix-implementation
**Action Rationale**: `_load_auto_mode_config_for_repl()` 需要同 `load_auto_mode_config()` 对齐，先读 workspace `.nanocode/config.yaml`（当前 cwd），再回落 global。

---

## Round 2 验收标准覆盖（继承 Round 1 + 更新 fail 项）

| ID | 验收项（来自 spec.md） | R1 结果 | R2 结果 | 证据 | 备注 |
|---|---|---|---|---|---|
| A1 | 无配置启动：常规工具连续执行，高风险工具触发管控 | pass | pass（继承）| auto_mode_gate 单测 85 passed | |
| A2 | dangerously_skip_permissions 启用后危险旁路可见 | **fail** | **pass（global）/ fail（workspace）** | global config: 危险横幅 ✓；workspace config: 横幅未读取 Issue 5 | Global 路径修复，workspace 残留 minor 问题 |
| A3 | allow 决策不打断用户 | pass | pass（继承）| 单测覆盖 | |
| A4 | deny 时工具不执行，agent 转安全路径 | pass | pass（浏览器实测）| rm -rf 被拒，agent 提示安全替代方案 | 端到端真实验证 |
| A5 | Coding CLI ask 可响应终端权限请求 | pass | pass（继承）| CLI picker 单测覆盖 | |
| A6 | IM 中 ask 可响应；用户能允许或拒绝 | **fail** | **fail** | 权限卡片渲染 ✓，但点击 → 401（Issue 4 blocking）| M3 修复 WS 路由但遗漏 auth header |
| A7 | ask 选项按工具类型区分，4 选项均覆盖 | fail（IM）| pass（渲染）/ fail（提交）| 4 个按钮 @e30-@e33 正确渲染 | 卡片可见，选项存在，但 auth 失败导致无法完成 |
| A8 | 自然语言规则配置后行为变化 | pass | pass（继承）| 单测 33 passed | |
| A9 | workspace 覆盖 global，两产品隔离 | pass | pass（agent core）/ 注意（banner）| auto_mode_config 单测；banner 加载器未对齐 workspace 覆盖 | banner 是 minor issue，agent 决策逻辑优先级正确 |
| A10 | 高风险动作不静默执行 | pass | pass（浏览器实测）| rm -rf 被 deny，agent 提示用户 | |

**R2 Summary**: A1/A3/A4/A5/A8/A9/A10 pass；A2 global pass / workspace fail(minor)；A6 fail(blocking Issue 4：权限决策提交 401)；A7 渲染 pass / 提交 fail（依赖 Issue 4 修复）

---

## 上层文档同步（Round 2）

- [x] `SPEC.md`（架构总览）：无需更新
- [x] `docs/内核设计SPEC.md`：仍需更新（同 Round 1；M3 未触及此类文档）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] 相关产品 SPEC（`docs/CodingCLI-SPEC.md` / `docs/NodeGateway-SPEC.md` / `docs/IM-SPEC.md`）：仍需更新（同 Round 1）

---

## Side Findings（Round 2）

1. 前端单测：305 passed，2 failed（pre-existing token-chip，同 Round 1）。
2. permission-card.test.tsx 8 passed，chat-stream-reducer.test.ts 11 passed（含 permission.request/resolved reducer case）。
3. IM 权限端点 `POST .../permissions/{request_id}`（有 token 时）返回 `{"status":"forwarded"}`，后端链路正常。前端 auth 问题是唯一阻塞点。
4. 注入 permission_request 后，卡片出现在聊天流中但选项按钮紧贴（`Allow onceDenyAllow for sessionAlways allow`），没有视觉间距；功能层面 4 个按钮是独立 `button` 元素可点击，属 polish 级 UI 问题，不影响功能验收判定。

# feat-383 — 验收报告

> Round 1 — 2026-05-28
> 对齐: spec.md 验收标准（5 Requirement / 11 Scenario）

## Verdict

**fail**

## Highest Required Action

**fix-implementation**

## 概要

后端全链路（Agent Kernel HTTP → PA client → Gateway WS → IM HTTP）所有路径验证通过，占位符、真实工具描述、真实 workspace 路径行为均正确。但前端因 TypeScript 构建失败，worktree 无 `dist/` 产物，IM 服务 fallback 到主仓旧版 dist，导致浏览器中用户实际使用的是旧版前端。旧版前端向 `/prompt-preview` 发送的请求缺少 `skill_ids` 字段，且在初始加载时 `tool_ids: []`（需用户手动点击才能触发，且依然缺 `skill_ids`）。R1 和 R5（Tool 切换/Skill 勾选的预览实时刷新）在真实浏览器端均不能开箱验收。

## 环境说明

- IM: `http://127.0.0.1:60949`，Kernel API: `http://127.0.0.1:60950`
- Gateway 已 patch `kernel.base_url → http://127.0.0.1:60950`（e2e-up.sh 不自动 patch，reviewer 手动补充）
- 前端 TS 构建失败（见 Issue-1），IM 服务 fallback 到主仓旧版 dist (`index-w28ra6Bm.js`)
- 指纹核验：主仓旧版 dist 中不含 `skill_ids`、`agent_id_hint` 等本 unit 关键 marker → stale-binary 确认

## 用户旅程体验

### 旅程 A — agent-detail 预览：工具 + 时间 + 工作目录（覆盖 R1 S1、R2 S1/S2/S3、R3 S1、R4 S1）

**API 层验证**（IM HTTP 全链路）：

```
POST /im/v1/agents/default-agent/prompt-preview
{"tool_ids":["read"],"skill_ids":[],"features":{},"custom_prompt":"","scenario":"direct"}
→ ## Available Tools
  - read: Read the contents of a file. Supports text files and images (jpg, png, gif, webp)...（真实描述，未截断）
  Current date and time: <运行时注入：当前时间>
  Current working directory: /Users/czj/nano-assistant/workspace/default-agent
```

确认：工具真实描述 ✓，datetime 占位符 ✓，cwd 真实路径 ✓

**无工具时：**
```
{"tool_ids":[],...} → ## Available Tools\n(none)
```
确认：空工具列表显示 `(none)` ✓

**未注册工具静默跳过：**
```
{"tool_ids":["fake_tool_xyz","read"],...} → 只显示 read 的真实描述，fake_tool_xyz 不出现
```
确认：静默跳过 ✓

**浏览器层（旧版 dist 服务）：**
Arch agent（UI 中可见 Tool Allowlist: read/write/edit/bash），打开预览后：
- 初始请求 body: `{"features":{...},"custom_prompt":"","tool_ids":[],...}`（缺 skill_ids）
- 预览内容：`## Available Tools\n(none)` — **不反映 UI 的 tool_allowlist**
- 需用户手动点击工具 pill 后 `tool_ids` 才更新，但仍无 `skill_ids`

### 旅程 B — agent-create 预览：workspace 路径（覆盖 R3 S2/S3）

**API 层验证**：
```
POST /im/v1/nodes/wt-unit-feat-383-54538/prompt-preview
无 agent_id_hint → Current working directory: <运行时注入：workspace 路径>  ✓
有 agent_id_hint=test-new-agent → Current working directory: /Users/czj/nano-assistant/workspace/test-new-agent  ✓
```

**浏览器层**：无法验证（前端未构建，agent-create 页的 agent_id_hint 字段缺失于旧版前端）

### 旅程 C — Custom Instructions 修改（覆盖 R1 S3）

**API 层验证**：
```
{"custom_prompt":"My special instructions: always be concise.",...}
→ 预览中包含 "My special instructions: always be concise."  ✓
```

**浏览器层**：Custom Instructions 是 Behavior 区的旧有字段，旧版前端也会传递——浏览器截图确认这条在旧版也工作正常。

### 旅程 D — Skills 勾选（覆盖 R5 S1/S2/S3）

**API 层验证**：
```
{"tool_ids":[],"skill_ids":["gstack-browse"],...,"workspace_root":"/Users/czj/nano-assistant/workspace/default-agent"}
→ workspace 内无对应 skill 文件（静默跳过），Skills 段不出现  ✓（S3 语义）
{"skill_ids":[],...} → Skills 段不出现  ✓（S2）
```
S1（有 skill 文件的 agent 勾选技能后显示真实描述）因缺乏含 skill 文件的 workspace 无法在 API 层直接验证；浏览器层因 stale-binary 无法验证 skill_ids 透传。

## 问题清单

### Issue-1 [Blocking]

**现象**：`src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx` 中 5 处测试夹具缺少 `permission_requests` 字段，导致 TypeScript composite build（`tsc -b`）失败，`npm run build` 报错退出。Worktree 无 `dist/` 产物，IM 服务 fallback 主仓旧版前端。

**用户影响**：浏览器中预览不反映 UI 的工具勾选（缺 `tool_ids` 初始化）和技能勾选（缺 `skill_ids` 字段），R1 S1/S2 和 R5 S1 的"勾选→预览实时刷新"在真实用户入口完全失效。

**归属分析**：`message-pane.test.tsx` 最后修改于 `bugfix-367/M1/R3` commit（`permission_requests` 列表化），与 feat-383 变更无关，但在主仓 `main` 也复现（说明是既有 pre-existing 问题）。feat-383 worker 没有发现/修复此构建问题，没有在 progress.md 中记录；AGENTS.md 要求 "前端产物不提交，需要时执行 `npm run build`"，而构建失败等同于产物缺失。

**Severity**: blocking  
**Recommended Action**: fix-implementation  
**Action Rationale**: 前端 TypeScript 构建错误阻断 dist 产物生成，导致本 unit 前端变更无法触达用户。该构建错误（message-pane.test.tsx 缺 permission_requests 字段）虽由 bugfix-367 引入，但 feat-383 worker 必须确保 `npm run build` 在交付时全绿，否则用户无法使用新版前端功能。

---

### Issue-2 [Major]

**现象**：e2e-up.sh 启动 Gateway 后，Gateway 连接的 kernel 地址仍是默认 `http://127.0.0.1:8000`（主仓默认端口），不是 worktree kernel 的 ephemeral 端口。design.md Runbook for Reviewer 提示需要 patch `.gateway-config.yaml` 的 `kernel.base_url`，但 `e2e-up.sh` 脚本未自动完成此 patch。Reviewer 需手动 patch 才能使全链路 IM→Gateway→Kernel 工作。

**用户影响**：worktree e2e 环境开箱不可用，任何依赖 IM→Gateway→Kernel 全链路的验收操作（promptpreview, agent chat 等）都会静默访问主仓 kernel（若有）或失败。

**Severity**: major（仅影响 reviewer/CI 验收流程，不影响生产用户，但阻碍 e2e 验收）  
**Recommended Action**: fix-implementation  
**Action Rationale**: e2e-up.sh 应自动 patch kernel.base_url 到 worktree kernel port，而非在 design.md runbook 中要求手动操作。

---

### Issue-3 [Minor]

**现象**：Vite dev server（`vite.config.ts`）的 proxy 目标固定为 `http://127.0.0.1:8021`，worktree 无法通过 Vite dev server 登录 worktree IM（60949 端口），前端 dev 工作流在 worktree 场景下需要手动改 vite.config.ts。

**Severity**: minor（reviewer 可绕过，直接访问 IM 服务端口）  
**Recommended Action**: fix-implementation

## 验收标准覆盖

### Requirement: 预览忠实反映用户在 UI 上的当前配置 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户切换 Tool Allowlist 勾选 | spec.md §验收标准 R1 S1 | 旅程 A：API 层 IM HTTP 全链路 tool_ids 切换测试；浏览器层 network intercept | API 层：传 `["read"]` → 预览含真实描述 ✓；传 `[]` → `(none)` ✓。浏览器层：初始加载预览 body 含 `tool_ids:[]`，缺 `skill_ids`，Arch 的 tool_allowlist 不反映到预览（stale-binary） | **fail** | 旧版 dist fallback 导致初始预览不含工具信息；用户需手动点击 pill 才触发；skill_ids 字段始终缺失 |
| 用户切换 Skill 勾选 | spec.md §验收标准 R1 S2 | 旅程 D：API 层 skill_ids 透传测试 | API 层：skill_ids 透传到 kernel 已验证；浏览器层 request body 无 skill_ids（stale-binary） | **fail** | stale-binary 导致 skill_ids 无法从浏览器传出 |
| 用户修改 Custom Instructions | spec.md §验收标准 R1 S3 | 旅程 C：API 层 custom_prompt 修改测试；浏览器中 Custom Instructions 是旧有字段 | API 层确认透传正确；浏览器旧版前端也支持 custom_prompt | **pass** | 此字段是旧有功能，新旧版均支持 |

### Requirement: 工具列表显示真实描述，不截断 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已勾选的工具在预览中显示真实说明文本 | spec.md §验收标准 R2 S1 | 旅程 A：API 层传 `tool_ids:["read"]`，检查描述内容和长度 | `- read: Read the contents of a file. Supports text files and images (jpg, png, gif, webp)...`（完整 180+ 字符，未截断）✓ | **pass** | 后端逻辑正确；浏览器用户实际体验因 stale-binary 无法自动验收，但底层 API 已正确 |
| 用户未勾选任何工具 | spec.md §验收标准 R2 S2 | 旅程 A：传 `tool_ids:[]` | `## Available Tools\n(none)` ✓ | **pass** | |
| 配置中存在内核未注册的工具 id | spec.md §验收标准 R2 S3 | 旅程 A：传 `tool_ids:["fake_tool_xyz","read"]` | 预览只显示 read 描述，fake_tool_xyz 不出现 ✓ | **pass** | |

### Requirement: 工作目录显示真实 workspace 路径或明确占位 — 组内结论：pass（API 层）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 已存在 agent 的预览显示真实路径 | spec.md §验收标准 R3 S1 | 旅程 A：IM HTTP `/agents/default-agent/prompt-preview` | `Current working directory: /Users/czj/nano-assistant/workspace/default-agent` ✓；浏览器也确认 `/Users/czj/nano-assistant/workspace/Arch` ✓ | **pass** | 后端+浏览器均验证通过（cwd 是后端注入的） |
| agent-create 页已填 Agent ID | spec.md §验收标准 R3 S2 | 旅程 B：`/nodes/{id}/prompt-preview` with `agent_id_hint=test-new-agent` | `Current working directory: /Users/czj/nano-assistant/workspace/test-new-agent` ✓ | **pass** | API 层验证；浏览器层无法验证（stale-binary 的 agent-create 页缺少 agent_id_hint 字段） |
| agent-create 页未填 Agent ID | spec.md §验收标准 R3 S3 | 旅程 B：`/nodes/{id}/prompt-preview` without agent_id_hint | `Current working directory: <运行时注入：workspace 路径>` ✓ | **pass** | |

### Requirement: 运行时才注入的字段以占位符明确呈现 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 时间字段在预览中显示占位 | spec.md §验收标准 R4 S1 | 旅程 A：多次 API 调用；浏览器 text_content 检查 | API 层：`Current date and time: <运行时注入：当前时间>` ✓；浏览器页面 text_content 含 `运行时注入：当前时间` ✓ | **pass** | 后端改动，不依赖前端字段 |

### Requirement: Skills 段反映当前勾选的技能集合 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 勾选了若干技能 | spec.md §验收标准 R5 S1 | 旅程 D：测试环境 workspace 内无 skill 文件，无法验证有 skill 时的渲染 | 无可用 skill 文件的 workspace；浏览器无法透传 skill_ids | **inconclusive** | 需要含 skill 文件的 workspace 才能完整验证；浏览器 skill_ids 无法传递 |
| 未勾选任何技能 | spec.md §验收标准 R5 S2 | 旅程 D：API 层 `skill_ids:[]` | Skills 段不出现 ✓ | **pass** | |
| 配置中存在 workspace 下解析不到的 skill id | spec.md §验收标准 R5 S3 | 旅程 D：API 层传 `skill_ids:["gstack-browse"]`，workspace 无此文件 | 该 id 不出现在预览中（静默跳过）✓ | **pass** | |

## 上层文档同步

- [ ] `SPEC.md`（架构总览）：无需更新（本 unit 为预览保真度改进，架构不变）
- [ ] `docs/内核设计SPEC.md`（agent 内核）：无需更新（`/v1/prompt-preview` 签名扩展已在 design.md 记录）
- [ ] `AGENTS.md` / `CLAUDE.md`：无需更新
- [ ] `docs/NodeGateway-SPEC.md`、`docs/IM-SPEC.md`：无需更新（协议扩展属于实现细节，不改用户可见接口语义）

## Side Findings

- 前端 TypeScript 构建失败（`message-pane.test.tsx` 缺 `permission_requests` 字段）在主仓 `main` 也复现，根因是 `bugfix-367` 引入 `permission_requests` 字段后未同步更新测试夹具。为 out-of-scope 遗留 bug，但阻断了本 unit 的前端构建，因此在 Issue-1 中列为 blocking fix-implementation。

---

_reviewer: r1-reviewer_
_service env: IM=60949, Kernel=60950, Gateway patched kernel.base_url_

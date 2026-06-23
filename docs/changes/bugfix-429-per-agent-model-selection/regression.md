# bugfix-429 — 回归验证

> 对齐: incident.md v1
> Round: 1 — 2026-06-24

## Verdict

**fail**

## Highest Required Action

`fix-implementation`

---

## 覆盖表

### Requirement: agent 配置选定的模型真实生效

#### Scenario: 选定非默认模型后对话用该模型

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态/验收标准 |
| GIVEN | 全局默认 kimiCoding:K2.6；default-agent.default_model 设为 codex_oauth:gpt-5.5 |
| WHEN | 与 default-agent 对话（全新会话） |
| THEN | LLM 请求 model==codex_oauth:gpt-5.5 |
| 验证方式 | LLM proxy 日志 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-06-24_07-37-20_762_sess_32182571ea21ba62/2026-06-24_07-37-20_762-req-anthropic_messages.json` |
| 证据 | `"model": "codex_oauth:gpt-5.5"` ✅；agent 回复「Hi」 |
| 结果 | **pass** |
| 备注 | default-agent 是配置文件预存 agent |

#### Scenario: 跨 provider 类型都能生效

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态/验收标准 |
| WHEN | gpt-probe agent（动态新建）设模型 volcanoArk:doubao-seed-2-0-code-preview-260215，对话 |
| THEN | LLM 请求 model==volcanoArk:doubao |
| 验证方式 | LLM proxy 日志 `2026-06-24_07-41-54_588_sess_3a98ccb64475db02` |
| 证据 | 日志显示 `"model": "kimiCoding:K2.6"` — 期望 doubao，实际仍是全局默认 kimi |
| 结果 | **fail** |
| 备注 | gpt-probe 是动态新建 agent；IM 和 gateway config 均正确存 doubao，但内核发请求用 kimi。同 agent 改为 gpt-5.5 后再测（新建对话），仍是 kimi（session `07-44-27`）。问题出在动态新建 agent 的 model 路由链路。 |

---

### Requirement: 改模型后旧会话也用新模型

#### Scenario: 回到历史会话继续聊

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态/验收标准 |
| GIVEN | default-agent 用 gpt-5.5 聊过一条（历史会话 5e86cb26） |
| WHEN | 改 default-agent 模型为 kimiCoding:K2.6，在同一旧会话继续发消息 |
| THEN | 新消息由新模型 kimi 产生 |
| 验证方式 | LLM proxy 日志 `2026-06-24_07-38-15_283_sess_f879ca4bc0b208fd` |
| 证据 | `"model": "kimiCoding:K2.6"` ✅；agent 回复「Bye」 |
| 结果 | **pass** |
| 备注 | 旧会话在模型改变后确实使用新模型，不被旧会话固化 |

---

### Requirement: 没选模型时有默认兜底

#### Scenario: agent 未设模型

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态/验收标准 |
| GIVEN | Arch agent default_model=null |
| WHEN | 与 Arch 对话 |
| THEN | 用全局默认 kimiCoding:K2.6 正常回复 |
| 验证方式 | LLM proxy 日志 `2026-06-24_07-38-57_859_sess_661d587acd1345cc` |
| 证据 | `"model": "kimiCoding:K2.6"` ✅；Arch 回复「Hi」 |
| 结果 | **pass** |

---

### Requirement: IM 模型选择展示 provider/格式

#### Scenario: 模型下拉标注各模型的格式

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态/验收标准 |
| WHEN | 用户打开 agent 配置页的模型下拉 |
| THEN | 每个可选模型旁展示 provider/格式（例：codex_oauth:gpt-5.5 标 anthropic） |
| 验证方式 | (1) capabilities API 返回；(2) 前端 JS bundle 代码逻辑 |
| 证据 | (1) `GET /im/v1/nodes/wt-bugfix-429/capabilities` 返回 `"models": [{"name":"codex_oauth:gpt-5.5","provider":"anthropic"},...]` ✅；(2) JS bundle `index-uegp7GRH.js` 中含 `G.provider?" · ${G.provider}":""` 和 `me.provider?" · ${me.provider}":""` 两处渲染逻辑 ✅ |
| 结果 | **pass**（数据层 + 渲染逻辑均已就绪；因 headless 环境未能截取真实浏览器下拉截图，以 API + bundle 证据代替） |
| 备注 | 注：无法通过浏览器直接截图验证实际 UI 渲染，以 capabilities API 响应和编译产物中的渲染代码作为等价证据 |

---

### Requirement: 模型选择持久化

#### Scenario: 重启后保留所选模型

| 项 | 内容 |
|---|---|
| 期望来源 | incident.md §目标状态/验收标准 |
| GIVEN | 动态新建 gpt-probe agent，选模型 codex_oauth:gpt-5.5；gateway 重启 |
| WHEN | Gateway 重启后查询 agents |
| THEN | gpt-probe 仍在，default_model 仍是 codex_oauth:gpt-5.5 |
| 验证方式 | 重启后 `GET /im/v1/agents` + 读 gateway config |
| 证据 | 重启后 IM 返回 `gpt-probe → codex_oauth:gpt-5.5` ✅；gateway config 同步写入 ✅ |
| 结果 | **pass** |
| 备注 | 持久化链路（链路B）已修复：动态新建 agent 和其 default_model 均写入 gateway config，重启后保留 |

---

### Requirement: 切换边界行为可预期

#### Scenario: 改模型时该 agent 正有回复在进行

| 项 | 内容 |
|---|---|
| 结果 | **not-applicable** |
| 备注 | 并发场景需要精确计时控制，无法在 headless 脚本环境安全重现；incident.md 设计说明「进行中的 run 用原模型跑完」是内核续跑复用 RunRecord.model 的结果，属实现层行为，不适合作为 reviewer 用户面旅程验证 |

#### Scenario: 所选模型上游不可达

| 项 | 内容 |
|---|---|
| 结果 | **not-applicable** |
| 备注 | incident.md 明确写「本单元不新增特殊错误 UI / 重试策略，复用内核既有 LLM 错误呈现」，属非目标，不在验收范围 |

---

## Issues

### Issue 1: 动态新建 agent 的 model 路由不生效

- **Severity**: major
- **Regression Relation**: direct（直接违反「跨 provider 类型都能生效」Scenario）
- **Recommended Action**: fix-implementation
- **Action Rationale**: 用户在 IM 上动态新建的 agent（gpt-probe）设模型后，对话的 LLM 请求仍使用全局默认 kimi，而非所选 doubao 或 gpt-5.5。预存配置 agent（default-agent）的模型路由正常生效，说明动态新建 agent 的 model 注入链路存在缺口。持久化（链路B）已修复（重启后值保留），但 Gateway 读取并注入内核的链路对动态 agent 不生效。
- **用户观察**：
  - 操作：IM 创建 gpt-probe，模型设 doubao → 发消息 → LLM proxy 日志 `model=kimiCoding:K2.6`
  - 操作：gpt-probe 改模型为 codex_oauth:gpt-5.5 → 全新对话发消息 → LLM proxy 日志仍 `model=kimiCoding:K2.6`
  - LLM proxy 证据：`2026-06-24_07-41-54_588_sess_3a98ccb64475db02` 和 `2026-06-24_07-44-27_522_sess_bccd7a52e89d10e6` 均为 kimi
  - 对比：`default-agent`（预存 agent）设 gpt-5.5 → `2026-06-24_07-37-20_762_sess_32182571ea21ba62` model=gpt-5.5 ✅

---

## 旅程记录

### Journey 1: 主路径——default-agent 选 gpt-5.5 → 对话 → 验证 LLM 请求

- PATCH default-agent config `default_model=codex_oauth:gpt-5.5` → 200，profile_version=2
- 创建含 user + default-agent 的对话
- 发消息 → agent 回复「Hi」
- LLM proxy 新 session `07-37-20_762`：`model=codex_oauth:gpt-5.5` ✅
- **覆盖 Scenario**: 选定非默认模型后对话用该模型

### Journey 2: 旧会话继续聊用新模型

- 改 default-agent 模型为 kimiCoding:K2.6
- 在同一旧会话（有 gpt-5.5 历史）再发消息
- LLM proxy 新 session `07-38-15_283`：`model=kimiCoding:K2.6` ✅
- **覆盖 Scenario**: 回到历史会话继续聊

### Journey 3: 无模型 agent 的默认兜底

- Arch（default_model=null）创建对话发消息 → agent 回复「Hi」
- LLM proxy 新 session `07-38-57_859`：`model=kimiCoding:K2.6` ✅
- **覆盖 Scenario**: agent 未设模型

### Journey 4: 动态新建 agent 的模型路由（跨 provider）

- 动态新建 gpt-probe，设 doubao；对话发消息
- LLM proxy `07-41-54_588`：`model=kimiCoding:K2.6` ❌（期望 doubao）
- 改 gpt-probe 模型为 gpt-5.5；全新对话
- LLM proxy `07-44-27_522`：`model=kimiCoding:K2.6` ❌（期望 gpt-5.5）
- **覆盖 Scenario**: 跨 provider 类型都能生效（fail）

### Journey 5: 持久化——重启后保留模型

- 动态新建 gpt-probe，选 gpt-5.5 → gateway config 写入 gpt-probe=gpt-5.5 ✅
- 重启 gateway → IM 和 config 均保留 gpt-probe.default_model=codex_oauth:gpt-5.5 ✅
- **覆盖 Scenario**: 重启后保留所选模型

### Journey 6: capabilities API + 前端 provider 展示

- `GET /im/v1/nodes/wt-bugfix-429/capabilities` → models 含 `provider` 字段 ✅
- JS bundle 含 provider suffix 渲染逻辑 ✅
- **覆盖 Scenario**: 模型下拉标注各模型的格式

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**（本 unit 不改架构层级关系）
- [x] `docs/specs/kernel/spec.md`（内核契约层）：**需要更新** — design.md delta-spec 列出 submit 新增必填 model、reconfigure_llm 退役、按 provider 路由等增量，应在 PR 阶段由 orchestrator 收尾归并
- [x] `docs/specs/im/spec.md`（IM 契约层）：**需要更新** — capabilities.models 携带 provider 字段是本 unit 新行为
- [x] `docs/specs/gateway/spec.md`（Gateway 契约层）：**需要更新** — 每 run 按 agent 当前 default_model 路由、重启保留等新行为
- [x] `docs/specs/cli/spec.md`（CLI 契约层）：**无需更新**（/model 对用户可观察行为不变）
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**
- [x] `docs/SPEC_GUIDE.md`：**无需更新**

---

## Side Findings

- **IM JWT secret 未固定**：本次测试用随机 secret 启动 IM，token 跨重启会失效（不影响本 unit 验收，但如需多次验收需重新登录）。属已知配置注意项，不立 issue。
- **capabilities API 中 `codex_oauth:gpt-5.5` 的 provider 显示为 `anthropic`**：主 config 将 gpt-5.5 注册在 `anthropic` provider 下（工作绕过），而非 AGENTS.md 示例中的 `openai_compat`。这是环境配置问题，不影响本 unit 修复的可验证性，但意味着「跨 provider 类型」的真实验证（anthropic vs openai_compat）在当前 config 下无法实现——两类模型都在 anthropic provider 下。

---

## 环境说明

- IM: unit worktree 代码，隔离端口 55928，JWT secret reviewer-bugfix429-secret
- Gateway: unit worktree 代码，PID 3243，--foreground --auto-bind
- 前端产物: unit worktree 重建，index-uegp7GRH.js（build 于验收期间）
- LLM proxy: 127.0.0.1:4000（用户主实例，验收期间正常运行）

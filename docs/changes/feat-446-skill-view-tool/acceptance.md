# feat-446 — 验收报告

> Round 1 — 2026-07-03
> 对齐: `docs/changes/feat-446-skill-view-tool/spec.md`

## Verdict

fail

Highest Required Action: fix-implementation

Issues count: blocking 2, major 2, minor 0

## User Journeys Exercised

1. 真栈启动与登录: 按 `design.md` Runbook 使用 `./scripts/e2e-down.sh` + `./scripts/e2e-up.sh` 启动隔离 IM/Gateway，登录 `nano/nano1234`，确认 Gateway 节点在线。
2. Agent 配置与 Skills 入口: 从 Web IM 进入 Agents -> `default-agent` 详情页，检查 tool allowlist、内置 distiller skill 可见性、Skills 使用统计入口。
3. `skill_view` 主路径与失败路径: 在真实 IM 对话中让 agent 调用 `skill_view(name="change-spec-author")` 和 `skill_view(name="nonexistent-skill")`，展开 Process 工具调用卡。
4. `/skill:` 触发路径: 在同一真实对话中发送 `/skill:change-spec-author`，观察是否出现新的 `skill_view` 工具行并通过 usage API 核对计数。
5. F2 历史会话蒸馏入口: 在左侧 conversation 列表对两条会话执行右键，观察是否出现"生成 skill"菜单/多选模式。

Evidence:
- `/tmp/feat446-acceptance-agent-detail.png` — Agent detail 中 `skill_view` 默认选中，但无 `Config / Skills` 或统计面板入口；同页 `Workspace Root` 显示为 `.../.gateway-workspace/luban`。
- `/tmp/feat446-acceptance-skill-view-cards.png` — `skill_view` 成功/失败工具卡展开态。
- `/tmp/feat446-acceptance-f2-no-context-menu.png` — conversation 右键后未出现生成 skill 入口。
- Usage API after the first `skill_view`: `use_count=1`, `session_refs[0].session_id=sess_952f9d14836a99b8`, `trend_buckets[-1]=1`.
- Usage API after `/skill:change-spec-author`: `use_count` 仍为 `1`，且 IM 中该轮只有 thinking process，没有新的 tool row。

## Issues

### I1 — Skills 使用统计面板入口缺失

- Severity: blocking
- Regression Relation: direct
- Recommended Action: fix-implementation
- Action Rationale: 本 unit 明确要求 IM Agent Skills 页可见 skill 使用统计、archived 过滤、热力图、健康度视图、空态/离线态；真实 Web IM 的 Agent detail 只有配置表单和 Access/Model，没有可点击的 `Skills` 面板入口。
- User impact: 用户无法在产品里查看 use_count、状态、趋势、archived 记录、agent 热力图或自进化健康度。

### I2 — 历史会话蒸馏入口不可达

- Severity: blocking
- Regression Relation: direct
- Recommended Action: fix-implementation
- Action Rationale: spec 要求用户右键 conversation 进入"生成 skill"多选模式；真实 conversation 列表右键两条会话均无菜单、checkbox 或"蒸馏为 skill"入口。
- User impact: 用户无法从历史会话发起 F2 蒸馏，后续执行 agent 选择、scope 选择、跳转预填都无法发生。

### I3 — `/skill:` 触发没有产生新的 `skill_view` 工具调用/统计

- Severity: major
- Regression Relation: direct
- Recommended Action: fix-implementation
- Action Rationale: spec 要求 `/skill:<name>` 和 agent 主动调用走同一条 `skill_view` 路径并记录统计；真实对话中 `/skill:change-spec-author` 后无 `skill_view` tool row，usage API 的 `use_count` 仍为 1。
- User impact: 用户显式 slash skill 的使用不会被审计和统计，compaction/自进化统计也不能可信覆盖这条常见入口。

### I4 — default-agent 详情/统计落到 luban workspace

- Severity: major
- Regression Relation: unclear
- Recommended Action: fix-implementation
- Action Rationale: 在 `default-agent` 详情页，header 显示 default-agent，但 `Workspace Root` 显示 `.../.gateway-workspace/luban`；真实 `skill_view` 后 `.usage.json` 也出现在 `.gateway-workspace/luban/.nanoassistant/skills/.usage.json`。这会直接污染 per-agent 使用统计和 F2 agent 级写入判断。
- User impact: 用户查看 default-agent 时看到/使用的是另一个 agent 的 workspace，无法信任 agent 维度统计。

## 验收标准覆盖

### Requirement: skill_view 作为独立只读工具可用 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| agent 调用 skill_view 读取 skill 内容 | spec.md | 真实 IM 对话请求 agent 调用 `skill_view(name="change-spec-author")` | 工具卡显示 `success=true`, `name`, `location`, `content_preview`, `content` | pass |  |
| agent 调用不存在的 skill | spec.md | 同一真实 IM 对话请求 `skill_view(name="nonexistent-skill")` | 工具卡显示 `success=false`, `message=Skill 'nonexistent-skill' not found` | pass |  |
| 同名 skill 按既有优先级读取 | spec.md | 未构造两个同名可见 skill | 未验证 | inconclusive | 需要可控产品态构造同名 PA/agent skill 后复验。 |

### Requirement: IM 工具调用面板展示 skill_view 审计信息 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| skill_view 成功调用的折叠态可审计 | spec.md | 展开 Process 前后观察工具行 | `skill_view` 行显示 `查看 skill：change-spec-author` | pass |  |
| skill_view 成功调用的展开态展示内容 | spec.md | 展开成功工具行 | 显示 name/location/content_preview/content | pass | 未看到单独"展开全文"按钮，但全文字段已在展开态可见。 |
| skill_view 调用失败时展示失败态 | spec.md | 展开失败工具行 | 红色/失败行显示 `failed` | pass |  |
| skill_view 失败原因可见 | spec.md | 展开失败工具行 | 展示 `Skill 'nonexistent-skill' not found` | pass | 用户可判断是 skill 名称或可见性问题。 |

### Requirement: skill_manage 不再包含 view action — 组内结论: not-applicable

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| skill_manage 的 action 枚举不含 view | spec.md | N/A | N/A | not-applicable | 工具 input_schema 属实现层/协议面，不是 reviewer 用户面验收范围。 |

### Requirement: 使用统计追踪 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| agent 主动调用 skill_view 记录使用统计 | spec.md | 真实 `skill_view` 后通过公开 usage API 辅助核对 | `change-spec-author.use_count=1`, `last_used_at=2026-07-03T01:08:31Z` | pass | 用户可见 UI 缺失，API 仅作辅助。 |
| 用户通过 /skill: 斜杠命令触发时也记录使用统计 | spec.md | 真实 IM 发送 `/skill:change-spec-author` | 无新增 tool row；usage API `use_count` 仍为 1 | fail | I3。 |
| skill_view 失败调用不记录使用统计 | spec.md | 真实不存在 skill 调用后核对 usage API | usage 中仅有 `change-spec-author`，无 `nonexistent-skill` | pass |  |
| 重放同一次 skill_view 不重复计数 | spec.md | N/A | N/A | not-applicable | 事件重放/恢复重试是实现层条件，不是用户可直接触发的产品旅程。 |

### Requirement: 压缩存活（compaction survival） — 组内结论: not-applicable

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 压缩后已读 skill 内容保留 | spec.md | N/A | N/A | not-applicable | 压缩后上下文注入内容是内部上下文，不是直接用户可观察结果。 |
| 压缩存活对同一 skill 去重 | spec.md | N/A | N/A | not-applicable | 同上，应由实现验证/contract 覆盖。 |

### Requirement: Curator 自动生命周期管理 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 30 天未用的 skill 标记为 stale | spec.md | 用户面应在统计面板看到 stale | Skills 面板入口缺失 | fail | I1 阻塞用户面验收。 |
| 90 天未用的 skill 归档 | spec.md | 用户面应在 archived 过滤看到 archived | Skills 面板入口缺失 | fail | I1。 |
| stale skill 被重新读取后复活 | spec.md | 用户面应能读取 stale 并看到 active | Skills 面板入口缺失 | fail | I1。 |
| stale skill 仍可被用户发现和使用 | spec.md | `/skill:`候选/统计面板状态 | Skills 面板入口缺失，未构造 stale skill | inconclusive |  |
| archived skill 退出日常使用路径但可审计 | spec.md | `/skill:`候选 + archived 过滤视图 | Skills 面板入口缺失 | fail | I1。 |
| 手工或未知来源 skill 不被 Curator 归档 | spec.md | 候选 + 统计状态 | 未构造 90 天手工 skill；Skills 面板入口缺失 | inconclusive |  |
| Curator 归档失败时不隐藏 skill | spec.md | 归档失败原因应在面板可见 | Skills 面板入口缺失 | fail | I1。 |

### Requirement: skill_view 记录 session 引用 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| skill_view 调用记录 session_id 和 timestamp | spec.md | 真实 `skill_view` 后公开 usage API 辅助核对 | `session_refs[0].session_id=sess_952f9d14836a99b8`, `timestamp=2026-07-03T01:08:31Z` | pass | 用户面 UI 缺失；API 证明数据存在。 |

### Requirement: 从历史 session 蒸馏 skill（F2） — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户从 IM 历史 conversation 入口发起蒸馏 | spec.md / prototype-f2.html | 左侧 conversation 右键 | 无菜单、checkbox、多选模式 | fail | I2。 |
| 默认会话列表不显示运行态标签 | spec.md | 正常浏览 conversation 列表 | 行只显示标题/时间/摘要/unread，无"已结束/运行中" | pass |  |
| 用户选择可蒸馏 conversation 后选择写入范围并跳转 | spec.md / prototype-f2.html | 右键入口后继续流程 | 入口不可达 | fail | I2。 |
| 用户通过弹窗指定生成级别后提交蒸馏 | spec.md | 入口不可达 | 入口不可达 | fail | I2。 |
| source JSONL 路径不可用时不部分生成 | spec.md | 入口不可达 | 入口不可达 | inconclusive | 需要入口修复后复验。 |
| 用户选 conversation + 意图生成 skill | spec.md | 入口不可达 | 入口不可达 | fail | I2。 |
| agent 写入 skill 后在普通对话里展示结果 | spec.md | 入口不可达 | 入口不可达 | fail | I2。 |
| 本期不新增专门预览确认 UI | spec.md | 入口不可达 | 未看到预览确认 UI，但主入口也不可达 | inconclusive | 无法证明完整流程中不会出现。 |
| 蒸馏 skill 是一个普通 SKILL.md | spec.md | Agent detail Skills allowlist 可见 `conversation-skill-distiller` | `conversation-skill-distiller` 出现在 agent skill allowlist | pass | Scenario 原文偏实现层；这里仅以用户可见内置 skill 存在作辅助。 |
| 执行 agent 未启用蒸馏 skill | spec.md | 入口不可达 | 入口不可达 | fail | I2。 |

### Requirement: Per-skill Batch 优化触发 — 组内结论: not-applicable

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 达到阈值后触发 batch 分析 | spec.md | N/A | N/A | not-applicable | 后台任务触发/LLM side-chain 属实现层，非用户可直接观察。 |
| batch 分析只 patch 不创建 | spec.md | N/A | N/A | not-applicable | 同上。 |
| batch 分析要求 ≥2 session 的证据 | spec.md | N/A | N/A | not-applicable | 同上。 |
| 手工 skill 达到阈值也不自动 patch | spec.md | N/A | N/A | not-applicable | 同上。 |
| 同一 skill 不并发启动多个 batch | spec.md | N/A | N/A | not-applicable | 同上。 |
| batch 有效证据不足时不 patch | spec.md | N/A | N/A | not-applicable | 同上。 |

### Requirement: 系统提示词引导模型使用 skill_view 而非 read — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| formatter 引导用 skill_view 加载 skill | spec.md | 真实对话请求 agent 不用 read，观察工具行 | agent 使用 `skill_view` 工具读取存在 skill | pass | 仅证明真实主路径可引导到 `skill_view`。 |

### Requirement: 使用统计面板（IM 前端，初版） — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Skill 列表视图 | spec.md / prototype.html | Agent detail 查找 Skills 面板 | 无统计面板入口 | fail | I1。 |
| 使用统计面板空态 | spec.md / prototype.html | Agent detail 查找 Skills 面板 | 无统计面板入口 | fail | I1。 |
| 使用统计面板加载失败 | spec.md / prototype.html | Agent detail 查找 Skills 面板 | 无统计面板入口 | fail | I1。 |
| Agent 维度视图 | spec.md / prototype.html | Agent detail 查找 Skills 面板 | 无统计面板入口 | fail | I1。 |
| 自进化健康度视图 | spec.md / prototype.html | Agent detail 查找 Skills 面板 | 无统计面板入口 | fail | I1。 |

### Requirement: 所有引用点正确迁移 — 组内结论: mixed

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| background review 白名单包含 skill_view | spec.md | N/A | N/A | not-applicable | 后台白名单是实现层，不用用户旅程判定。 |
| 产品层工具列表包含 skill_view | spec.md | Agent detail Tool Allowlist | `skill_view` 按钮可见且 pressed | pass | PA 用户面通过；coding_cli 未作为本轮用户旅程覆盖。 |
| PA agent 默认启用但可取消 skill_view | spec.md | Agent detail Tool Allowlist | `skill_view` 默认 pressed | pass | 取消并保存未执行，避免改变持久配置；默认启用已验证。 |
| 已有显式工具白名单不被自动扩宽 | spec.md | N/A | N/A | not-applicable | 需要构造持久化显式白名单，属于配置状态/实现边界，非本轮产品旅程。 |

## Side Findings

- `./scripts/e2e-up.sh` 在普通非持久 shell 中返回 ready 后，IM/Gateway 子进程会随命令结束退出；在保持 shell 会话打开后服务正常。这是 reviewer 运行环境与脚本后台进程模型的交互问题，未作为本 unit 产品 issue 计数。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。此 unit 行为增量主要落在包级契约。
- [x] `docs/specs/<包>/spec.md`（长青行为契约层，本 unit 触及 kernel/im/gateway）：需要由 orchestrator 收尾归并，尤其是 `skill_view`、usage dashboard、F2 distill、Curator/F4 的 current 行为。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。

## Recommended Action

继续走 fix-implementation。第一轮禁止 `revise-design`；本轮发现的问题都是用户面承诺未达成或数据错位，未触发 design 三道闸。

---

# Round 2 — 2026-07-03

> 对齐: `docs/changes/feat-446-skill-view-tool/spec.md`
> validated_head: `58160ca0bac194081c0ca1198d8c5a6ebe0b25f6`

## Verdict

fail

Highest Required Action: fix-implementation

Issues count: blocking 2, major 1, minor 0

## User Journeys Exercised

1. 真栈启动与登录: 先 `npm run build` 重建 Web IM dist，再用 `./scripts/e2e-down.sh` + `./scripts/e2e-up.sh` 启动隔离 IM/Gateway。因本地非持久 shell 会让 e2e 子进程退出，本轮把 e2e-up 放在长驻 shell 中运行。登录 `nano/nano1234`，确认 Gateway 节点 online。
2. Agent detail 与 Skills dashboard: 从 Web IM `Agents -> default-agent` 进入真实详情页，检查 `Config / Skills` 入口、`View skill statistics` 按钮、工具 allowlist、workspace root、Skills 空态和 skill_view 后刷新。
3. `skill_view` 工具卡回归: 在真实 default-agent 对话中要求 agent 调用 `skill_view(name="change-spec-author")` 和 `skill_view(name="nonexistent-skill")`，展开 Process 工具调用卡。
4. `/skill:` 触发路径: 在同一真实对话中发送 `/skill:change-spec-author\nPlease load this skill...`，观察是否出现新的 `skill_view` 工具行，并核对使用统计是否增加。
5. F2 历史会话蒸馏入口: 在左侧 conversation 列表验证顶部 `Generate skill` 入口、conversation 右键菜单 `Distill to skill`、多选模式、无 transcript 行的禁选/提示和后续按钮行为。

Evidence:
- `/tmp/feat446-r2-acceptance/default-agent-skills-empty.png` — Agent detail 的 `Skills` tab 可达，空态显示 `No skill usage yet`。
- `/tmp/feat446-r2-acceptance/skill-view-tool-cards.png` — `skill_view` 成功/失败工具卡；成功行显示 `skill_view`、`查看 skill：change-spec-author`、location、content；失败行标红并显示 `Skill 'nonexistent-skill' not found`。
- `/tmp/feat446-r2-acceptance/default-agent-skills-still-empty-after-tool.png` — 成功 `skill_view` 后刷新 default-agent Skills tab 仍显示空态。
- `/tmp/feat446-r2-acceptance/default-agent-usage-after-slash.json` — `/im/v1/agents/default-agent/skills/usage` 在成功 `skill_view` 和 `/skill:` 后仍返回 `skills: []`。
- `/tmp/feat446-r2-acceptance/slash-no-skill-view-row.png` — `/skill:change-spec-author` 轮次只有 `Process · 1 thinking`，没有 `skill_view` tool row。
- `/tmp/feat446-r2-acceptance/f2-context-menu.png` — conversation 右键菜单出现 `Distill to skill`。
- `/tmp/feat446-r2-acceptance/f2-multiselect-no-transcript.png` — 右键进入多选模式后，真实 conversation 行显示 `No transcript` 且 checkbox disabled，但该行被 checked。
- `/tmp/feat446-r2-acceptance/f2-no-transcript-after-distill-click.png` — 点击 `Distill to skill` 后没有弹窗、跳转、预填或错误说明。
- Console/network: browser console 0 errors / 0 warnings；dashboard usage API 请求均为 HTTP 200，但 default-agent payload 为空。

## Issues

### R2-I1 — default-agent Skills dashboard 不显示真实 skill_view 使用记录

- Severity: blocking
- Regression Relation: direct
- Recommended Action: fix-implementation
- Action Rationale: 本 unit 要让用户在 IM Skills dashboard 看到 skill 的 use_count、最近使用时间和趋势。真实 default-agent 对话中 `skill_view(name="change-spec-author")` 成功并展示了工具卡，但 `Agents -> default-agent -> Skills` 仍显示 `No skill usage yet`，`GET /im/v1/agents/default-agent/skills/usage` 也返回 `skills: []`。当前可见效果是用户刚看了 skill，却在该 agent 的统计面板中看不到任何记录。
- User impact: 用户无法用 dashboard 审计 default-agent 实际查看过哪些 skill，也无法信任 agent 维度热力图、健康度或 Curator/F4 的使用统计入口。

### R2-I2 — `/skill:<name>` 仍没有产生 visible `skill_view` tool row 或统计增量

- Severity: major
- Regression Relation: direct
- Recommended Action: fix-implementation
- Action Rationale: Round 1 的 `/skill:` 问题仍可复现。发送 `/skill:change-spec-author\nPlease load this skill...` 后，assistant 回复 skill 已加载，但该轮只有 `Process · 1 thinking`，没有 `skill_view` 工具行；全局 `.usage.json` 中 `change-spec-author.use_count` 仍为 1，default-agent dashboard API 仍为空。
- User impact: 用户显式使用 `/skill:` 的常见入口没有可审计工具行，也不会稳定进入使用统计，破坏本需求“统一走 skill_view”的核心承诺。

### R2-I3 — F2 蒸馏入口可达但真实 conversation 无 transcript，流程不能继续

- Severity: blocking
- Regression Relation: direct
- Recommended Action: fix-implementation
- Action Rationale: 右键菜单和顶部按钮已可进入多选模式，但真实 default-agent conversation 行显示 `No transcript`、checkbox disabled；右键进入时该 disabled 行还被 checked，`Distill to skill` 按钮可点，点击后没有弹窗、跳转、预填或错误说明。用户仍无法从真实历史 conversation 走到 scope 选择和 `/skill:conversation-skill-distiller` 预填。
- User impact: F2 从历史 session 蒸馏 skill 的主路径仍不可用。入口不再消失，但用户选不了可用 transcript，也得不到可恢复的下一步。

## 验收标准覆盖

### Requirement: skill_view 作为独立只读工具可用 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| agent 调用 skill_view 读取 skill 内容 | spec.md | 真实 IM default-agent 对话请求 `skill_view(name="change-spec-author")` | 工具卡显示 `success` 行、name、location、content 预览 | pass |  |
| agent 调用不存在的 skill | spec.md | 同一真实对话请求 `skill_view(name="nonexistent-skill")` | 失败行显示 `Skill 'nonexistent-skill' not found` | pass |  |
| 同名 skill 按既有优先级读取 | spec.md | 未构造两个同名可见 skill | 未验证 | inconclusive | 需要可控产品态构造同名 PA/agent skill 后复验。 |

### Requirement: IM 工具调用面板展示 skill_view 审计信息 — 组内结论: pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| skill_view 成功调用的折叠态可审计 | spec.md | 展开 Process 前后观察工具行 | `skill_view` 行显示 `查看 skill：change-spec-author` | pass | 无回归。 |
| skill_view 成功调用的展开态展示内容 | spec.md | 展开成功工具行 | 显示 name/location/content 预览，并有 `expand all` 长内容入口 | pass |  |
| skill_view 调用失败时展示失败态 | spec.md | 展开失败工具行 | 失败行红色/failed，工具名仍为 `skill_view` | pass |  |
| skill_view 失败原因可见 | spec.md | 展开失败工具行 | 展示 `Skill 'nonexistent-skill' not found` | pass | 用户能判断是名称/可见性问题。 |

### Requirement: 使用统计追踪 — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| agent 主动调用 skill_view 记录使用统计 | spec.md | 真实 `skill_view` 后刷新 Agent Skills dashboard + usage API | default-agent dashboard/API 仍为空；可见统计未更新 | fail | R2-I1。 |
| 用户通过 /skill: 斜杠命令触发时也记录使用统计 | spec.md | 真实 IM 发送 `/skill:change-spec-author` | 无新增 `skill_view` tool row；use_count 未增加 | fail | R2-I2。 |
| skill_view 失败调用不记录使用统计 | spec.md | 成功 + 失败双调用后核对可见统计和 sidecar | 未出现 `nonexistent-skill` 统计 | pass |  |
| 重放同一次 skill_view 不重复计数 | spec.md | N/A | N/A | not-applicable | 事件重放/恢复重试是实现层条件，非 reviewer 用户旅程。 |

### Requirement: 从历史 session 蒸馏 skill（F2） — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户从 IM 历史 conversation 入口发起蒸馏 | spec.md / prototype-f2.html | 左侧 conversation 右键 + 顶部 Generate skill | 右键菜单出现 `Distill to skill`，顶部按钮进入多选 | pass | Round 1 入口不可达已修复。 |
| 默认会话列表不显示运行态标签 | spec.md | 正常浏览 conversation 列表 | 默认行显示标题/时间/摘要/unread，无运行态标签 | pass |  |
| 用户选择可蒸馏 conversation 后选择写入范围并跳转 | spec.md / prototype-f2.html | 右键入口后继续流程 | 真实 conversation 均显示 `No transcript`，无法进入弹窗/跳转/预填 | fail | R2-I3。 |
| 用户通过弹窗指定生成级别后提交蒸馏 | spec.md | 右键入口后继续流程 | 未出现 scope 弹窗 | fail | R2-I3。 |
| source JSONL 路径不可用时不部分生成 | spec.md | `No transcript` 行被右键预选后点击 Distill | 无跳转/发送/生成，也无错误说明 | pass | 没有部分生成，但交互无反馈，归 R2-I3。 |
| 用户选 conversation + 意图生成 skill | spec.md | 入口后继续流程 | 无法选择 transcript-backed conversation | fail | R2-I3。 |
| agent 写入 skill 后在普通对话里展示结果 | spec.md | 入口后继续流程 | 无法进入发送/写入阶段 | fail | R2-I3。 |
| 本期不新增专门预览确认 UI | spec.md | F2 入口流程观察 | 未出现 SKILL.md 草稿预览卡或确认写入状态机 | pass | 主流程仍未完成。 |
| 蒸馏 skill 是一个普通 SKILL.md | spec.md | Agent detail skills allowlist | `conversation-skill-distiller` 可见 | pass |  |
| 执行 agent 未启用蒸馏 skill | spec.md | 未构造禁用蒸馏 skill agent | 未验证 | inconclusive | 需要可选 transcript-backed row 后复验。 |

### Requirement: 使用统计面板（IM 前端，初版） — 组内结论: fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Skill 列表视图 | spec.md / prototype.html | Agent detail -> Skills，真实 skill_view 后刷新 | 入口可达，但仍显示空态，无 `change-spec-author` row | fail | R2-I1。 |
| 使用统计面板空态 | spec.md / prototype.html | 启动后首次打开 Skills | 显示 `No skill usage yet` | pass | 空态本身清晰。 |
| 使用统计面板加载失败 | spec.md / prototype.html | 未强制断开 Gateway | 未验证 | inconclusive | 本轮未破坏真 Gateway 验证环境。 |
| Agent 维度视图 | spec.md / prototype.html | 需要非空统计数据 | dashboard 仍为空，无法进入有效热力图验证 | fail | R2-I1。 |
| 自进化健康度视图 | spec.md / prototype.html | 需要非空统计数据 | dashboard 仍为空，无法有效验证 | fail | R2-I1。 |

### Requirement: 所有引用点正确迁移 — 组内结论: mixed

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 产品层工具列表包含 skill_view | spec.md | Agent detail Tool Allowlist | `skill_view` 默认 pressed | pass |  |
| PA agent 默认启用但可取消 skill_view | spec.md | Agent detail Tool Allowlist | default-agent 无显式改动时 `skill_view` 默认启用 | pass | 未保存改动，避免污染配置。 |
| 已有显式工具白名单不被自动扩宽 | spec.md | N/A | N/A | not-applicable | 需要构造持久化显式白名单，非本轮用户旅程。 |
| background review 白名单包含 skill_view | spec.md | N/A | N/A | not-applicable | 后台白名单属实现层。 |

### Requirement: default-agent 详情/统计不串到 luban workspace — 组内结论: mixed

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| default-agent detail 显示自己的 workspace | Round 1 I4 / AGENTS worktree isolation | Agent detail Config 页面 | Workspace Root 为 `.gateway-workspace/default-agent` | pass | Round 1 UI 串 workspace 已修复。 |
| default-agent skill usage 在 default-agent dashboard 可见 | Round 1 I4 + spec dashboard | default-agent 成功 `skill_view` 后刷新 Skills | default-agent usage API 仍为空 | fail | R2-I1；本轮现象不是显示 luban root，而是 deployment-root使用记录未进入 agent dashboard。 |

## Side Findings

- `./scripts/e2e-up.sh` 在普通非持久 shell 中仍会返回 ready 后丢失 IM/Gateway 子进程；本轮使用长驻 shell 保持服务。此项延续 Round 1 side finding，未计入本 unit 产品 issue。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。
- [x] `docs/specs/<包>/spec.md`（长青行为契约层，本 unit 触及 kernel/im/gateway）：需要由 orchestrator 收尾归并，但当前 fail 不建议先归并为 current。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`：无需更新。

## Recommended Action

继续走 fix-implementation。Round 2 已修复部分 reachability（Agent Skills tab、F2 右键菜单、default-agent workspace root），但三条用户主路径仍失败：dashboard 看不到真实 `skill_view` 使用、`/skill:` 不产生 tool row/统计、F2 不能从真实 conversation 继续到 scope 选择和预填。

# feat-474 — 验收报告

> 对齐: spec.md v1 的验收标准；design.md「Runbook for Reviewer」

# Round 1 — 2026-07-23

## Verdict

pass

## 验收方式

真实入口：`PYTHONPATH=src python3 -m coding_cli.main --model kimiCoding:K2.6 --provider anthropic --llm-base-url http://127.0.0.1:4000 --text '...'`，模型为本地代理 `kimiCoding:K2.6`，真实 Kernel + 真实文件系统，工作目录 `/tmp/feat474-review/workdir`（unit worktree 内 `git status --porcelain` 全程干净，无副作用）。design.md Runbook 明确"无新常驻服务，仅验内核/CLI 时可不启 IM"，故未额外起 IM/Gateway。

## User Journeys Exercised

1. **默认最少参数派发**（覆盖：最少参数新建 / 旧仪式字段不再被要求 / 默认 general-purpose 能改代码）—— 不传 `subagent_type`、不传 `load_skills`/`category`/`timeout_seconds`，只给 description+prompt，派子 agent 写文件；主 agent 用 `read` 独立复核内容。
2. **Explore / Plan 只读边界 + 未知类型/错误大小写失败**（覆盖：Explore 只读 / Plan 只读 / 未知类型失败 / 错误大小写失败）—— 分别派 `Explore` 尝试写文件、`Plan` 只做规划、显式传 `oracle`、显式传 `explore`（小写），逐一用独立 `ls` 或字面错误信息核对。
3. **类型可发现性**（覆盖：主 agent 能知道有哪些类型可选）—— 不给任何提示，直接问主 agent"你的 agent 工具支持哪些 subagent_type"，验证它仅凭工具自身说明就能完整列出。
4. **前台超时自动转后台 + 运行中插话**（覆盖：前台过久自动转后台且不可调超时 / 运行中仍可插话）—— 派默认类型子 agent 跑 `sleep 150`，全程观察到 120s 整点转后台；再对旅程 2 中已完成的 `Explore` 子 agent 用其 `agent_id` 续聊，确认消息进入同一子 agent 而非新建，且展示类型正确显示为 `Explore`（未被误标 `general-purpose`）。

## Reference Artifacts Reviewed

N/A —— design.md 无「## 前端原型」段，spec.md/design.md 未引用任何原型、设计稿或 reference screenshot；本 unit 不改前端。

## 问题清单

（无发现问题。）

## Highest Required Action

pass

## 验收标准覆盖

### Requirement: agent 调用更轻，去掉赘余传参 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 最少参数即可新建子 agent | spec.md L79-81 | 旅程1：只传 description+prompt，不传 skill/category/超时 | `tool_start.arguments` 只含 `description`/`prompt`；`tool_end` 显示 `status:completed`，`subagent_type:"general-purpose"`；文件 `default_ok.txt` 内容经主 agent `read` 与 reviewer 独立 `cat` 双重核对一致 | pass | |
| 旧仪式字段不再被要求 | spec.md L83-85 | 旅程1/2/3/4 全部 6 次真实调用均未传 `load_skills`/`category`/`timeout_seconds` 且均成功；另追加探测：显式要求主 agent 硬塞未声明字段 `load_skills`，主 agent 自陈"schema 之外字段会被拒绝"并拒绝违规调用 | 6 段 `tool_start.arguments` 记录（journeyA/B/C/D/E/Plan/Timeout/TypesKnown .log）；`journeyF.log` 显示模型对违规请求的自我认知 | pass | 严格意义上"传入即失败"这一子命题因真实 LLM 工具调用天然遵循 schema、无法从用户旅程侧直接触发违规调用去观察拒绝响应，但"不必再提供"这条 THEN 的字面验收标准已被 6 次真实调用完整满足；该 schema 边界（`additionalProperties:false`）另有 delta spec `tools-hooks.md` Scenario 明确记载 |

### Requirement: 三种真类型能力可区分 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 默认 general-purpose 能改代码类工作 | spec.md L89-91 | 旅程1 | 见上；子 agent 真实创建并写入文件，主 agent 独立读回内容一致 | pass | |
| Explore 只读探索 | spec.md L93-95 | 旅程2：派 `Explore` 子 agent 尝试写 `explore_should_fail.txt` | 子 agent 自陈"以只读模式运行，没有文件写入/编辑工具"；reviewer 独立 `ls` 确认该文件确实不存在 | pass | |
| Plan 只读出方案 | spec.md L96-100 | 旅程2：派 `Plan` 子 agent 为"新增 hello.py"制定计划 | 子 agent 返回结构化实现步骤+关键文件+核心代码建议（未创建任何文件）；reviewer 独立 `ls` 确认 `hello.py` 不存在 | pass | |
| 主 agent 能知道有哪些类型可选 | spec.md L101-103 | 旅程3：无提示直接问"支持哪些 subagent_type" | 主 agent 仅凭工具自身说明完整答出 `general-purpose`(含默认)/`Explore`/`Plan` 及各自用途，未被 reviewer 提示 | pass | |

### Requirement: 未知类型失败可理解 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 未知类型名 | spec.md L108-111 | 旅程2：显式传 `subagent_type=oracle` | `tool_end.status:"failed"`，`error:"Agent type 'oracle' not found. Available agents: general-purpose, Explore, Plan"` | pass | |
| 错误大小写 | spec.md L112-114 | 旅程2：显式传 `subagent_type=explore`（小写） | `tool_end.status:"failed"`，`error:"Agent type 'explore' not found. Available agents: general-purpose, Explore, Plan"`，与未知类型同一表现 | pass | |

### Requirement: 后台超时与插话行为保持产品语义 — 组内结论:pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 前台过久仍自动转后台，且不可调超时参数 | spec.md L120-124 | 旅程4：默认类型子 agent 前台跑 `sleep 150` | `tool_end.duration_ms:120006`（整 120 秒转出），`status:"async_launched"`，附 `agent_id`+`output_file`；全程 `tool_start.arguments` 无 `timeout_seconds` 字段可传 | pass | |
| 运行中仍可向子 agent 插话 | spec.md L125-128 | 旅程4：持旅程2中 `Explore` 子 agent 的 `agent_id=a0a3a44279a70b8a9` 发续聊 | 续聊结果原样返回 `still-explore`（即该子 agent 本体的回复，不是另起的无关子 agent）；`tool_end.presentation.detail.subagent_type` 正确显示 `"Explore"`（未误标 `general-purpose`，对应 M1 progress.md「Fix 1」修复项） | pass | |

## Side Findings

- REPL `/tools` 命令在若干次尝试中对已存在会话返回"Tools for session \<unknown\> (0): (no tools)"，与本 unit 无关（本 unit 未改 REPL `/tools` 展示逻辑），且未阻塞任何验收路径（真实 `agent` 工具调用全程正常）。不确定是既有已知行为还是环境特例，记录但不立 issue（minor，未影响本 unit 可接受性）。
- `--text` 一次性模式下，旅程4 的后台子任务在主进程退出时打印 `background_task_notify_delivery_failed | error='registry is shutting down...'`——这是 `--text` 单次调用架构的预期行为（进程退出前未等到后台完成通知），非本 unit 引入的回归，与 feat-337 既有语义一致。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新 —— 本 unit 未改包边界/依赖方向。
- [x] `docs/specs/kernel/`（长青行为契约层：`tools-hooks.md`/`background-tasks.md`/`skills.md`/`prompts.md`）：**已由 orchestrator §7.0 归并** —— canonical 已反映 feat-474（去掉 load_skills/category/timeout_seconds；真类型 general-purpose/Explore/Plan；未知类型 Available agents）。delta 仍保留于本归档目录 `specs/kernel/` 供对照。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新 —— 未涉及命令面/依赖方向约定变化。
- [x] `docs/SPEC_GUIDE.md`：无需更新 —— 未改文档体系本身。

需要更新的项：无（canonical 已归并）。

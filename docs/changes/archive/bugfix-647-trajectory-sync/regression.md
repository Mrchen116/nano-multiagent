# bugfix-647 — 独立产品回归

> 对齐：incident.md；mode=full；revalidation_mode=full。
> Validation snapshot：`236a4698c7a8a2d03efa00c35049914d2422771d → a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7`。

## Round 1 — 2026-10-23 隔离真实产品旅程（进行中）

### 入口与环境

- reviewer 独立读取 incident/design、IM agent-work 与 conversations-messages、Gateway global-agent、worktree-runtime 和共同体验标准。只检查客户端 API 契约，未读受审实现定位根因。
- checkout `/Users/czj/.codex/worktrees/trajectory-sync/nano-multiagent`，branch `codex/bugfix-647-trajectory-sync`，实核 HEAD 等于 validated_at。caller 提供同源码构建证明；Node PID 71296 的可执行路径及参数指向本 worktree 的 `apps/node/lib/cli.js` 与 `.gateway-config.yaml`，DSH PID 71391；IM PID 71043，端口 49160，健康接口 200。Node 24.22.1。
- 测试身份 nano（`u_i2cggc2i`），隔离 node `wt-nano-multiagent-70898`，Global Agent `e2e-global`，新建私聊 `c_izjqj90l`。所有写入均在此私聊及其内部子执行，未访问生产或外部通信。
- 使用 Web 实际 API：auth/login、conversations、messages、agents/e2e-global/work 与 work/sessions/{id}/turns。设计明确无客户端改动且允许此入口；不宣称 Web/iOS 视觉或 viewport 验收。
- 临时原始证据 `/tmp/nano647-review/`；包含纯测试消息和 Work JSON，不纳入 Git。令牌单独保存在本机 auth.json，不引用或提交。

### 首次旅程与已观察证据

15:06:21Z 发送真实请求，要求内部子 Agent 计算、期间主 Agent 查询任务图并报告；15:06:41Z 追加标题更正。根 session `4064e3f6-11fa-41ab-bc89-85e34a0e64ef`；子 session `7a1b4cbc-51a5-4052-90a6-8858b74ef4ee`。

| 场景来源 | 实际结果与证据 | 判定 |
|---|---|---|
| M1 reviewer：新子工作及过程 | Work 从空 other_executions 更新为子 session，真实父级为根 session；委派工具完成与子执行终态分开。子轮次随后 completed，elapsed_ms=22336，model_id=deepseek:deepseek-v4-flash；工具参数、失败内容保留。证据 `work-mid.json`、子 session 的快照 | pass（失败工具的完整呈现）；成功结果待后续补验 |
| incident：当前查询/发送；global-agent 多项独立推进 | 子工作期间 task_graph list 两次均成功，duration_ms=34/31，返回 total=0；开始消息实际存在私聊消息列表，非仅工具 sent。 | pass（新工作；不据此推断数百冷历史性能） |
| incident 保留发送前重验；global-agent 私聊新补充 | 根 seq56 send_message 返回 held_for_revalidation，未发出；seq63 inbox read 读取更正消息 `22b3dd8102c74e3eab08e5c5f7bdcdb4`，seq72 新发送才成功；聊天列表无被拦草稿，最终标题确为“确认版647”。证据 `main-*.json`、`round1-messages.json`。 | pass |
| agent-work 真实结束状态 | 根轮次 completed，elapsed_ms=55522，finished_at=15:07:17.102Z；最终聊天明确说明执行受阻而非虚构工具成功。证据 `round1-terminal-work.json`。 | pass |

### 环境阻碍与分层边界

- bash 被自动审批 fail-closed 拒绝：`classifier_unavailable` / `UNSUPPORTED_REASONING_EFFORT`，审批模型 deepseek-v4-flash 不支持固定 low。已交 caller 调整本隔离审批模型，不关闭审批；成功工具旅程须调整后补验。
- 孙调用真实返回 `subagent depth 2 exceeds maxDepth 1`。caller 核实为既有默认能力限制，禁止为本回归扩大委派深度；孙执行、新增/续写/重启及失败游标的低层覆盖由独立 native 测试/持久实验承担，不将此产品旅程冒充孙执行成功。产品 M1 退出标准仍须独立观察新子执行成功工具结果。
- 冷历史读取、解压次数与首次扫描成本不由本次新会话壁钟证明；独立原生实验报告承担性能结论。

### Round 1 补充 — 环境恢复后的最终验证

caller 将仅本隔离 `.gateway-config.yaml` 的 `llm.tool_approval_model` 指向支持现有 low 的 `codexOAuth:gpt-6-luna`，保持独立审批策略；15:08:21Z 原数据重启 ready，新 Node PID 76123。reviewer 再次核实进程使用本 worktree 路径；无受审源码变更。初次环境阻碍已解决，不作为实现缺陷。

| 场景来源 | 实际结果与证据 | 判定 |
|---|---|---|
| incident 新增/续写与重启；agent-work 刷新回看 | Gateway 重启后根 session 不变，第一轮 completed；旧子 session 的 completed 与 14 条 items 仍可读取，参数/错误/父级保持。`postrestart-work.json`、`postrestart-child.json`。 | pass |
| M1 reviewer 新子工作与最终工具结果 | 15:10:44Z 新消息触发子 session `1afa4b5c-5ae5-4adb-af2a-ba2158d22e6a`。中途读取真实 running，Python 工具 seq126 已 completed，stdout `385`、exitCode=0；sleep 工具 seq135 当时 running，之后 completed、exitCode=0。最终子轮次 completed，elapsed_ms=30909，model_id=deepseek:deepseek-v4-flash；根第二轮 completed/45555ms、main_execution=idle。`final-work.json`、`final-child.json`。 | pass |
| incident 当前查询/发送；global-agent 独立推进 | 新子执行仍运行时，两次 task_graph list 均成功（47/25ms）；私聊实际收到进展消息。15:11:18Z 第二次报告时子执行仍处于 sleep 阶段。没有以委派启动工具完成伪称子任务完成。`main-*.json`、`final-messages.json`。 | pass |
| 显式完成交付 | 15:11:28Z 私聊消息 `e38b27e1d04f4ddb867926869d0a9323` 标题“实测版647”，实际报告 Python 输出385；可与子 Work 工具结果对照。 | pass |
| incident 已有子会话续写；agent-work 不丢展示上下文 | 追加消息 `bc777909177f4a41b1eec196f0b7c568` 要求复用同一子会话；最终 other_executions 仍为2，原子session新增 turn2 completed/6810ms，bash 输出55、exitCode0；turn1的385、sleep结果、耗时与模型均仍保留。私聊 `87fb43ab23fe4350b8cd7be7f1d73b74` 内容“续写647：55”。`continued-work.json`、`continued-child.json`、`continued-messages.json`。 | pass |

### 最终 Verdict

**pass（本次分配的独立产品回归范围）**。M1 reviewer 必验的新子工作、最终工具结果、正常查询/发送及真实新消息发送前重验均独立观察通过；重启回看和同子会话续写也通过。用户能经真实 Work 接口辨认根/子归属、运行与完成，检查成功和失败的实际工具细节，并在原私聊收到显式交付。未发现 blocking/major/minor 实现问题，highest_required_action=pass，needs_re_review=false。

此结论不扩大为冷历史性能、孙级执行成功或人为注入持久化失败验证：这些按 design/M1 分层分配给独立原生测试与实验，需由 caller 合并其证据。原生默认 maxDepth=1 的产品孙执行不适用本隔离配置，并未伪报 pass；无客户端视觉变更，Web/iOS 视觉验收 not-applicable，viewport 未操作。无本轮必须匹配的前端原型。

### 自动化增量与上层文档

本 reviewer 未修改或重新运行源码测试；通过真实产品入口独立取证。自动化测试增量、冷历史对照与失败恢复证据由独立验证报告承担，本报告不重复其成功叙述。

- [x] `SPEC.md`：无需更新；本次不改变跨包架构或公开用户行为。
- [x] `docs/specs/`：无需更新；保留现有 Work、Inbox、发送前重验与持续工作契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

### 完成与清理

仅新增本 regression.md，按 caller 指令不提交。未启动额外长期进程，原隔离栈由 caller 统一 e2e-down；本机临时测试凭据在取证结束后删除。未改生产、源码、测试、受控配置或设计；未向外部创建 issue（gh_issues_filed=0）。

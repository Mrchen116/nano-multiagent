# refactor-581 — 独立产品验收

当前交付结论见 **Round 10**：用户明确暂缓物理 iPhone 部分后，本次授权范围 **pass，30 pass / 3 authorized-deferred**；不代表33项全部实机通过。Round 1–9保留原始发现及当时判定。

## Round 1 — 2026-10-10

Validation snapshot: `4915c44cb7f7b829414a19087877ad9b73d69ea1 → e89179da8956577b288ee374fe791c2ce82d5047`。模式 full；来源为 motivation.md S01—S33 与 design.md Runbook，未读取实现定位问题，未使用 worker 成功叙述替代验收。

**Verdict: fail。Highest Required Action: fix-implementation。** 本轮发现 3 个 major 产品问题；必验覆盖仍有 inconclusive。未执行不等于实现失败，但不能据此通过 Full 门禁。report_commit: none（caller 明确要求不提交）。

### 环境及版本边界

- 独立隔离栈 `.dsh-runtime/final-review`，Web/IM `http://127.0.0.1:59784`，测试 owner `u_m77krl29`，node `wt-final-review-31430`。未触碰生产与主 checkout。
- Node PID 31502、受管 DSH PID 31522；`node apps/node/lib/cli.js status --config .dsh-runtime/final-review/.gateway-config.yaml` 返回 `RUNNING ... ready=true`；lsof cwd 为当前受审 worktree；`/health` 为 ok。Node 运行冻结版本，真实模型 `deepseek:deepseek-v4-flash`，本地代理。
- Root 在本轮进行 usage 修正并于 03:22 后重建共享 frontend dist。最初已加载的浏览器及 NaN/配置截图有明确时间；03:25 navigate 后的审批 UI 属于旧 Node + 修订前端的混合构建，仅作为审批行为证据，不冒充完整冻结版本 UI 通过。
- caller 仍持有栈用于修正后重启/复验；本 reviewer 未执行销毁，避免丢失 Workflow 失败现场。最终清理由 caller 或后续 round 负责。

### 用户旅程及证据

原始公开 API 时间线保存在 `output/acceptance-final-round1-evidence.json`，包含本轮各聊天的消息、工具、审批及结果；没有登录 token。

1. 文件读取、停止、续聊、分支：`c_lhu7i3pw` 真实 read 返回隐藏文件 token `SENT9D08B171`；Web 展示 Process · 1 tool。长 bash 运行后 `/stop` 确认「已停止当前操作」，20 秒观察未出现完成哨兵。之后普通聊天正常。分支 `c_tlkcilec` 保留 `CODE8ACD162B`，排除分支点之后的 `LATER6AA884`，真实追问答对暗号，原聊天不受分支追问污染。`/compact 保留两个暗号和读过的文件 token` 返回「已压缩 13 项较早上下文」，后续消息 `d5a20a8386f74f32b7703fbacaeaf441` 正确答 `CODE8ACD162B`。
2. Global 多聊天：`c_jiozgwns` 委派真实后台 child，`c_g7gqu9aw` 发送 `AMEND8753771B` 更正，同一 child 收到跟进。公开 Work 中 read committed、child identity、followup 和实际 dispatch 断言通过。原聊天最终唯一消息 `f6db526e59a14807a398dcc45ae0a7ac` 包含 total 63420/count 60，更正群无机器人消息，没有把草稿/工具/思考混入正式交付。
3. Cron：`c_tjakbwf5` 发起 20 秒一次性任务。审核模型发生 `Anthropic stream ended without a stop reason`，产品转人工审批，故原无审批 helper 等待 90 秒超时不是调度失败。批准 request `b2e8d5ac-669d-4105-96ba-5bd30b328268` 后出现 REGISTERED；到期消息 `74a0d05765554c99b8436ab461997a2c` 在同聊天输出 `CRON091B20D0`；随后追问 `1477f9cdd9fd47edb9bc5109ed4316e4` 正确引用该 token。
4. Web 审批：Workflow 主轮的 bash 等待触发审核不可用回退，真实 Web 显示申请卡，点击 Allow once 后 request `0792e64e-0f38-478d-ba63-ff42b871432d` resolved，工具实际输出 `waited`，持久 `approval=user_allow`。此证据是主轮审批，不充当 Workflow child、拒绝和取消迟答全覆盖。
5. Workflow：第一次按旧 current spec 大写 `Workflow` 配置无法发现工具，不计实现失败。按 unit native 名称 lowercase `workflow` 重新启用后，run `4d13702c-d2e2-4f8e-9eba-6215b74a22aa` 启动。两次 read 报 lossless JSON 错误；公开 `/workflows` 可查询到两 child 均 failed/value null/outputTokens 0，整个 run 382ms 完成，result.ok=false，无第三 child、无最终和。已停止主轮反复等待读取。
6. 飞书 retained 数据直接核阅：`.dsh-runtime/native-feishu-fixed/acceptance.json` 有 native-center confirmed 平台消息 `om_x100b63a78cb370a0c3e45027c7477c0`、IM completed token、pending_frames=0。另核阅 `feishu-output-image-evidence.json`（真实平台 img_key 卡）、`feishu-approval-evidence.json`（allow_once 卡及 FEISHU_APPROVAL_OK confirmed）、`feishu-offline-evidence.json`（补交付且 pending=0）。这些较早媒体/审批/离线证据来自旧中心阶段，仅保留其未变 Node channel 切片；不是本轮独立重跑全部飞书场景。

### Reference Artifacts Reviewed

Design 明确沿用现有客户端，不要求新增原型。N/A（无 must-match 原型契约）。真实截图：`output/playwright/final-acceptance-chat.png`、`final-acceptance-empty-capabilities.png`、`final-acceptance-approval-pending.png`。Playwright snapshot：`.playwright-cli/page-2026-10-09T19-22-50-970Z.yml`、`page-2026-10-09T19-23-44-121Z.yml`。截图/浏览器缓存保持本地，不作为产品源码提交。

### 问题清单

| ID | Severity / Relation | 期望与实际、复现 | Recommended Action / Rationale |
|---|---|---|---|
| F1 | major / suspected-regression | 登录 nano → Agents → E2E Agent。期望可选择工具/模型/skills/五项 Features；实际 Tool Allowlist 为 —，五项 Features 缺失。公开 GET `/im/v1/agents/e2e/capabilities` 返回 models/skills/tools/commands/features 全为空。 | fix-implementation；阻塞 S07/S25/S33 用户配置入口。 |
| F2 | major / suspected-regression | 普通/工具回复的 Web 用量显示 `ctx NaN%`，例如 `c_lhu7i3pw` 文件读取回复。 | fix-implementation；用量与上下文状态不可信，root 正在修正但本轮未验证新版本。 |
| F3 | major / suspected-regression | 上述 Workflow 并行真实子任务求乘积，再委派求和。两 child 立即 failed，未得结果；workflow read 返回 `tool "workflow" returned invalid output: value is not lossless JSON`。/workflows 显示 result.ok=false、outputTokens 0。 | fix-implementation；S10 主路径失败，阻塞后续控制/恢复验收。原因由实施方定位，不由 reviewer 推断。 |

环境/范围缺口：已安装签名 iPhone build 但用户设备未解锁，未取得物理 UI 操作证据；本栈只有一个节点，未完成两节点/公司资格矩阵。未运行项不转换为 N/A。

### 验收标准覆盖

所有期望来源均为 motivation.md 对应 Scenario；验证方式均从既有真实产品入口检查目标不变性。完整场景中仅通过部分分支时保留 inconclusive，备注指出已通过切片。

| Requirement | Scenario | 实际证据与未覆盖范围 | 结果 |
|---|---|---|---|
| R1 | S01 文本/图片/三端 | Web 文本、工具及审批已观察，飞书 retained；iPhone 未解锁，Web 图片未执行。 | inconclusive |
| R1 | S02 两节点/隔离 | 单节点两个 fixture Agent；双节点/公司资格矩阵未执行。 | inconclusive |
| R2 | S03 Global 并行聊天 | 旅程2：同主 session/同 child 更正、单次正式交付、群无草稿。 | pass |
| R2 | S04 更正边界 | Global 更正切片通过；single_thread 正文/同群工具/后台结果边界未完整覆盖。 | inconclusive |
| R3 | S05 通用工作 | read/bash 与 Global child 读写通过；搜索/网页/专项工具未执行。 | inconclusive |
| R3 | S32 原生工具/升级 | 原生 read/bash/subagent/send_message 使用通过；截断续读、升级以及全部 Skill 引用未验。 | inconclusive |
| R3 | S06 两层工具 | 未配置两 workspace 同名 plugin 及冷恢复旅程。 | inconclusive |
| R3 | S07 选择/显式空 | F1：用户界面无候选，无法完成选择。 | fail |
| R3 | S33 Feature 启停 | F1：五项 Feature 配置入口缺失，启停/重启资产旅程不能通过。 | fail |
| R4 | S08 委派/后台 | 旅程2真实后台 child、同 child followup、正确最终归因交付。 | pass |
| R4 | S09 停止 | 长 bash 停止及20秒无迟到完成、可续聊通过；等待模型/审批迟答矩阵未验。 | inconclusive |
| R5 | S10 JS 并行流水线 | F3，两 child 失败，未能走到第三子任务和最终结果。 | fail |
| R5 | S11 保存/命名/嵌套 | 被 F3 阻塞，未执行完整旅程。 | inconclusive |
| R5 | S12 暂停/继续/重启 | 被 F3 阻塞，未执行完整旅程。 | inconclusive |
| R5 | S13 前缀复用 | 被 F3 阻塞，未执行完整旅程。 | inconclusive |
| R5 | S14 共享预算 | F3 的零用量失败不能证明预算机制。 | inconclusive |
| R6 | S15 默认 Auto | 真实工具自动审核及失败人工回退已出现；独立模型/来源语义矩阵未完整验。 | inconclusive |
| R6 | S16 规则切换 | 本轮未调整规则及重启，不能以同名配置推定通过。 | inconclusive |
| R6 | S17 三端/child 审批 | 旅程4主轮 Web Allow once 通过；飞书 retained；iPhone/child/拒绝/取消迟答未完成。 | inconclusive |
| R6 | S18 Global 短确认 | 真人短回复/系统通知区别未验。 | inconclusive |
| R7 | S19 记忆维护 | 未执行自动维护及受控记忆编辑旅程。 | inconclusive |
| R7 | S20 Skill 维护 | 未执行阈值维护/后台生成后启用旅程。 | inconclusive |
| R8 | S21 原主会话到期 | 旅程3：真实到期原聊天发出 token，后续追问仍理解。 | pass |
| R8 | S22 过期补发 | 尚未制造停止期间过期与恢复。 | inconclusive |
| R8 | S23 多任务/历史 | 单次任务通过，周期/手动运行/开关/执行历史矩阵未验。 | inconclusive |
| R9 | S24 Heartbeat | 未执行忙碌/活跃时段/静默/可行动矩阵。 | inconclusive |
| R10 | S25 配置/备用 | F1 阻塞模型候选 UI；配置API修改工具可下一轮使用，备用/粘性/公开输出边界未完整验。 | fail |
| R10 | S26 新历史 | 分支暗号及 focus compact 后继续聊天通过；重启/历史生成Skill/幂等查询未覆盖。 | inconclusive |
| R10 | S27 开发切换 | 本次新会话运行正常；完整非聊天资产接入/切换演练未由 reviewer 执行。 | inconclusive |
| R11 | S28 任务图/发送 | Global 实际唯一发送通过；任务图保存/冲突/访问资格/未知发送未验。 | inconclusive |
| R11 | S29 断线/重启 | 飞书旧阶段离线补交付 retained；最终树接收/审批/发送故障矩阵未独立验。 | inconclusive |
| R12 | S30 运维 | 实际 status/PID/cwd/health 通过；登录自启/停止恢复未完成。 | inconclusive |
| R12 | S31 终态入口 | 真 TS IM+Node+DSH 可聊，但 operations/gateway.md 仍给旧 Python 入口；文档归并和全部三端待完成。 | inconclusive |

### 上层文档同步

- [x] SPEC.md：需要最终终态归并，由 caller 完成。
- [x] docs/specs/gateway 与 im：需要最终 delta 归并；旧 current `Workflow` 名称不可当作新 native tool ID，Cron UI 仍写 without conversation context，待纠正。
- [x] AGENTS.md / CLAUDE.md：需要与退役依赖和实际入口对齐。
- [x] docs/specs/CONTRIBUTING.md：本次不改变文档体系，无需更新。
- [x] docs/operations/gateway.md 等操作入口：仍有旧 Python 命令，需要 caller 更新并核对可运行性。

needs_re_review: true。下一轮须继承本轮 fail/inconclusive，并只在有真实新增证据后关闭；不得用已安装 iPhone 或模拟器代替物理验收。

## Round 2 — 2026-10-10，修正复验及扩展旅程

Validation snapshot: 后端 `bbbaee580c10ff71d279ddb81583de1150abd83e`，用量 UI 修正 `3014fe8cd`；后续 Cron 修正须另列定点复验，不能把后来 HEAD 当成本轮全部旅程的运行版本。仍为 full 模式，来源为 motivation.md S01—S33。只读取公开产品入口、现有运行手册和原始 retained 输出，没有读取实现定位问题。

**Verdict: fail。Highest Required Action: fix-implementation / complete-acceptance。** F1/F2/F3 已关闭；新增 F4 major（Cron 列表字段和删除入口），等待冻结修正版实测。必验范围仍有 inconclusive，尤其物理 iPhone；这些不代表已证实实现失败，也不能作为通过证据。report_commit: none（caller 要求不提交）。

### 版本、环境与证据边界

沿用 Round 1 的专用测试 owner、IM/Web 和持久数据，未重新 bootstrap。通过公开 Node CLI 两次停止/启动测试节点，Node PID 从旧 31502 更新至 41582；运行配置仍为 `.dsh-runtime/final-review/.gateway-config.yaml`。旧 `.gateway.pid` 文件不是本轮运行事实，使用 CLI status/PID 就绪与真实请求确认。栈按 caller 要求保留供复验，最终清理由 caller 负责。

本轮公开消息时间线保存在 worktree 本地 `output/acceptance-final-round2-evidence.json`；Round 1 原始 JSON 已移动到 `output/acceptance-final-round1-evidence.json`，上轮相对链接仅是搬移前位置。截图、JSON、运行数据库均为本地证据，不提交。较早旧中心的 retained 证据仅证明未变 Node/DSH 层切片，不能冒充最终 TypeScript IM 的全链路复验。

### 已关闭问题

- **F1 closed**：公开 capabilities 实际返回 6 models、27 tools、43 skills、5 features；Web 配置候选及 Features 恢复。专用 `review-empty` 显式 tools=[]/skills=[] 的聊天真实无法 read；随后实际点击 Web 的 read 并 Save Agent，同一聊天下一轮 read 成功返回隐藏 token `SENT9D08B171`。证据 `output/round2-empty-agent-config.txt`、`round2-empty-agent-selected.txt`。
- **F2 closed**：重载修正前端后，新消息显示 `ctx 1%`；旧缺计数消息显示缺省符号，展开用量没有 NaN 或异常。证据 `output/round2-usage-fixed-snapshot.txt`、`round2-usage-expanded.txt`。
- **F3 closed**：使用中性工作指令和模型支持的继承推理设置，Workflow `c538e616-cd98-4631-9346-39b040be8032` 的两个真实并行 child 返回 CEDAR581/MAPLE581，第三 child 取得前序结果并组合；read 返回结构化结果，最终消息 `0424c6…` 完成三个子任务。没有将错误 low 推理配置的失败算成引擎行为，也没有以主模型自报完成替代 child timeline。

### 本轮新增真实旅程

1. **Web 图片及新历史**：从 Web 粘贴红左蓝右图片并实际 Send，回复 `0623b489…` 正确识别两侧颜色，继续追问答右侧蓝色。Round 1 compact/fork 原聊天在冷启动后仍答对 CODE8ACD162B（`544717…`）。图片截图和快照在 `output/round2-image-paste-snapshot.txt` 及 `output/playwright/`。
2. **Workflow 保存、嵌套、控制和恢复**：上述 run 保存个人命名 `acceptance-join`，带参数命名运行 `35440823…` 完成；嵌套 run `8d0e3085…` 完成三个实际 child。相同脚本显式 resume run `4c6e6d33…` 为 129ms、outputTokens=0，冷启动后再恢复也复用。控制 run `86711613-eaa0-40ab-81aa-c663692d8f41` 在第一个 sleep child 运行时 pause，只见第一任务；restart 1 结束旧 attempt、保持 queued，无第二派发；resume 后第一任务两个 attempts、第二任务一个 attempt，最终 SECOND_DONE。证据取自 `/workflows` 公开快照与真实消息。
3. **共享预算**：同一父轮 `+2k` 创建两个 Workflow `89bd8824…` 和 `aabbdad9…`，两者同 budgetId、target=2000、shared consumed=3560、remaining=0；各两个实际 child 完成，第三 logical call 因预算耗尽而没有 attempt。已有在途任务可超出阈值，耗尽后未新派发；不能把 agentsStarted 的 3 当作三个实际执行。未设置预算的此前旅程成功，重放 outputTokens=0。
4. **工具归属和选择**：全局与 workspace A 同名插件 `acceptance_scope` 分别返回 GLOBAL_BOX_581/LOCAL_BOX_581；A 的两个聊天均 local，B 为 global，冷启动后再调用仍分别正确（`8ee71226…`、`0c82721…`）。插件是本轮隔离测试资产，没有修改受审源码。显式空集合、Web 下一轮启用 read 已在 F1 复验。
5. **Feature、记忆及 Skill**：`review-features` 建立 USER.md 记忆“薄荷纸船”和 revision 2、todo 的任务图后，关闭 memory/task_graph/skill 及显式 tools=[]/skills=[]；请求改为“红色桥梁”和完成任务时零实际调用，文件/图均不变。重新启用后 graph 仍 revision 2/todo；真实 skill_manage 申请 `3def40…` 获人工允许，创建 acceptance-paper 并调和显式 skills=[] 为该 skill，随后 skill 调用加载 PAPER_SKILL_581，冷启动后仍可用。单独关闭 memory 时，message `bd8ff217…` memory 返回 UNKNOWN_TOOL、task_graph get 成功，文件没有 PURPLE_OFF_581。模型在能力关闭轮输出过 DSML 样式文本，但没有执行或副作用，记录为模型输出质量现象，不伪报为禁用绕过。
6. **更正、Heartbeat 与 Cron 冷恢复**：普通群 `c_oo0q4nf4` 在 bash sleep 期间接收 NEW_PAPER_581 更正，最终只交付新值 `0a0b6c…`，旧 bubble 无过时正文。Heartbeat 的空文件在两次 5s 周期观察中静默；加入行动内容后 `773988…` 交付 HEARTBEAT_PAPER581；关闭后再观察 11s 无新增。另一次性 Cron COLD_DUE_581 在 Node 停止期间到期，恢复后同一原聊天 `bd146…` 交付一次：scheduledAt 19:42:21.860、deliveredAt 19:42:53.049 UTC。没有另建任务聊天。
7. **原始 retained 证据复核**：最终树双节点 `.dsh-runtime/two-node-evidence.json` 的两个节点实际读出各自文件 sentinel；另一 active owner 对两聊天、媒体、审批返回 404、可见 agents=[]，suspended 为 401。native-feishu-fixed 最新 JSON 的真实平台 confirmed、IM completed、pending_frames=0。`knowledge-live.json` 前台结束后的 memory/skills system notices、实际已启用配置和 usage auto=1 证明后台产物调和；不证明所有阈值/归档。`cancel-approval-evidence.json` 的 pending request 经 stop 后 decision=cancelled、工具 failed，迟到 allow 返回原 cancelled，未执行 printf；该材料属于旧中心阶段的 Native 层 retained 切片。

### 新增问题

| ID | Severity / Relation | 期望、实际与证据 | Action |
|---|---|---|---|
| F4 | major / suspected-regression | Web `/settings/agents/cronBot287b3f` 应显示两条已存在任务并能针对正确任务删除。实际两行无标题，Delete URL 使用 undefined；公开 `/im/v1/agents/cronBot287b3f/cron/jobs` 却返回真实 title/prompt/id。证据 `output/round2-cron-ui.txt`、`round2-cron-requests.txt`、`round2-cron-response.txt`、`output/playwright/round2-cron-undefined.png`。 | fix-implementation；caller 已接收。旧文档 `/cron-jobs` 的 404 不作为此问题依据。 |

### S01—S33 累积覆盖

pass 仅表示该行完整用户结果已有足够证据；有成功切片但明确缺少场景分支者继续 inconclusive。本表继承上轮证据，不覆盖原始失败记录。

| Scenario | 实际证据 / 尚缺范围 | 结果 |
|---|---|---|
| S01 | Web 文本、图片及追问，飞书真实平台 retained；物理 iPhone 仍锁定，未完成三端同旅程。 | inconclusive |
| S02 | 本轮直接核阅最终树双节点原始权限/文件/聊天/审批证据。 | pass |
| S03 | Round 1 多聊天同 child、更正和正式发送归因。 | pass |
| S04 | 新增普通群正文边界，继承 Global 边界；同群显式发送工具及后台结果的更正边界仍未全验。 | inconclusive |
| S05 | read/bash/写文件、原生插件真实完成；搜索/网页/专项完整可用性未实测。 | inconclusive |
| S32 | 原生调用成功；大文件截断续读、版本升级、全部旧 Skill 引用未作产品旅程。 | inconclusive |
| S06 | A 两聊天 local/B global，冷启动后保持；Agent 自建/共享工具未单独完成。 | inconclusive |
| S07 | 显式空、UI 选择下一轮生效、关闭期间无副作用及生成 Skill 调和真实通过；社区来源矩阵未完整验。 | inconclusive |
| S33 | memory/task/skill 独立关闭重开与资产保留，Heartbeat 关闭有效；全部五项关闭后冷恢复/在途收口矩阵仍缺。 | inconclusive |
| S08 | Round 1 真实 child 跟进及后台交付，Round 2 多 child 归因。 | pass |
| S09 | 真实长工具停止、续聊及旧中心审批取消迟答 retained；等待模型和迟到 child 新请求隔离未完整验。 | inconclusive |
| S10 | 真实并行两 child 后第三 child 流水线，非 Workflow 普通对话仍可用。 | pass |
| S11 | 个人保存/命名/参数/一层嵌套通过；项目同名优先级未验。 | inconclusive |
| S12 | pause 阻止新派发；restart 指定 attempt；resume 仅替换该任务且第二任务只执行一次。 | pass |
| S13 | 完全相同前缀零 token 复用、冷启动恢复通过；修改中间调用及其后不复用尚未实测。 | inconclusive |
| S14 | 同父轮两个 Workflow 共享预算耗尽阻止新 attempt；重放零输出用量，未设置预算正常完成。 | pass |
| S15 | 默认审核真实调用/独立模型及故障回人工 retained；所有来源授权语义未完整验。 | inconclusive |
| S16 | Nano/DSH 规则真实写入 retained；最终中心来源/未决请求/无人值守全矩阵缺。 | inconclusive |
| S17 | Web 主轮允许、飞书卡允许、取消迟答 retained；iPhone、Workflow child 拒绝与原消息归属未完整验。 | inconclusive |
| S18 | Global 真人短确认后实际文件落盘 retained；系统事件不能同意及阈值分流缺。 | inconclusive |
| S19 | 真实 memory 控制读写、关闭无副作用，自动维护后 system notice 原始材料。 | pass |
| S20 | 实际生成、人工批准、配置调和、后续 Skill 使用和冷恢复；阈值触发/review/归档缺。 | inconclusive |
| S21 | 到期原聊天交付、继续追问引用。 | pass |
| S22 | 停机期间到期、原数据启动后一次补发。 | pass |
| S23 | 多条已存任务存在但 F4 UI 查询/删除失败；周期错过、手动、历史状态仍待。 | fail |
| S24 | 空内容静默、行动交付、关闭停止真实通过；忙碌及活跃时段外未验。 | inconclusive |
| S25 | 工具/模型候选 UI 恢复、配置下一轮真实生效；备用链/粘性/公开输出边界未实测。 | inconclusive |
| S26 | compact 重点、分支、冷启动连续性；retained distill 仅生成 prompt/export，未证明实际新 Skill；幂等查询缺。 | inconclusive |
| S27 | 原始 Air/Mini 迁移报告保留源资产及新会话映射；仍有 pending 映射阻塞正式激活，不等于部署。 | inconclusive |
| S28 | task graph 保存后未执行、Global 明确发送成功；冲突/unknown/断线重放矩阵缺。 | inconclusive |
| S29 | 冷启动持久数据及离线补交付 retained；接收/执行/审批/外发 unknown 全阶段未覆盖。 | inconclusive |
| S30 | CLI status/stop/start 管理进程与实际恢复两次通过；真实登录自启未验。 | inconclusive |
| S31 | TS IM+Node+DSH 实际运行；最终文档归并与物理三端完整验收仍由 caller 收口。 | inconclusive |

needs_re_review: true。F4 修复后可单独关闭，但不能自动关闭其余 inconclusive 或以安装 iPhone build 代替物理设备行为。

## Round 3 — 2026-10-10，F4 targeted 复验

Validation snapshot: `7690ae4ae64e2844b018ebd6c64d0c0317d49aaa`。caller 确认本次只改 Node 后端且构建完成；reviewer 用原配置、原数据库执行 `restart`，公开 status 为 `RUNNING pid=44374 ready=true DSH=44383`。IM/前端未改，不作无关重启。

**F4 closed。总体 Verdict 仍为 fail，Highest Required Action: complete-acceptance。** 当前已发现的 F1—F4 四个 major 实现问题均经对应真实旅程修正复验；不代表 33 个必验场景全部通过。Round 2 的 inconclusive 继续有效，S23 从 fail 更新为 inconclusive（UI 查询/删除已通过，周期补最近一次、手动运行与真实执行历史尚未完整验）。report_commit: none。

实际 Web `http://127.0.0.1:59784/settings/agents/cronBot287b3f` 显示两条任务的真实标题、指令与 native schedule；点击 `Delete 一次性提醒（20 秒后）` 后该行移除、30 秒任务保留。重新加载后删除项数量=0、保留项数量=1，证明不是仅本地 UI 移除。第一次自动化使用过窄的按钮名字未匹配；改用真实 accessibility name 后执行成功，不作为产品故障。响应 body 采集发生浏览器协议读取错误，因此不声称取得该 DELETE response body；实际持久删除由刷新后结果证明。

原始证据：`output/round3-cron-fixed.txt`、`output/round3-cron-after-delete.txt`、`output/round3-cron-reload.txt`。测试节点保持运行供 caller 后续使用/清理。

另有 **minor F5 文案**：Cron 区域仍显示 `Scheduled tasks that run without conversation context.`，与已经实测的原主对话上下文语义不一致；不阻塞 F4 的功能关闭，建议随文档/客户端措辞归并修正。没有把此旧文案当作 Cron 实际上下文丢失。

needs_re_review: true；剩余必验范围见 Round 2 累积覆盖表，尤其物理 iPhone 和各标明未执行的条件分支。

## Round 4 — 继续补验真实条件分支（2026-10-10）

validated_at: `7690ae4ae64e2844b018ebd6c64d0c0317d49aaa` 的既有 final-review 构建；此轮 caller 正并行修正文档/入口，未把未重启的新代码当作已验。Node 原数据停机恢复后 PID 48065。以下为追加事实，不覆盖前轮失败记录。

- **S11 / S13 pass**：同名个人定义原为 MAPLE581，实际 `/workflows eebef43d-e5de-482a-8055-4719f42e4dfc save project acceptance-join` 保存 BIRCH581；调用 `/acceptance-join {"round":4}` 的 run `2c89228c-16a2-40cd-9c59-9fe227589a32` 实际输出 `CEDAR581,BIRCH581`，确认项目同名优先。中间调用修改恢复 run `eebef43d-e5de-482a-8055-4719f42e4dfc` 的第一调用 `replayed=true, attempts=[], outputTokens=0`；第二和第三各有新 attempt，输出 BIRCH581 和组合结果。公开工具详情而非仅模型叙述见 `output/round4-c_p815ybqw.json`。
- **S05 / S32 补足读取与网页实际切片**：1,159,906 字节、10,000 行文件首次无范围 read 返回 capped 与 offset=442 续读提示；实际 offset=9995/limit=10 返回真实末行 `FINAL_SECRET_9C64E581`。第一次模型猜错绝对路径得 not-found，改相对路径正确解析到本 Agent workspace；没有隐藏失败。原始详情 `output/round4-c_pv6oitsl.json`。另直接核阅 `.dsh-runtime/web-live.json` 的真实 `web_fetch` HTTP200 与 `web_search` Sources/IANA 原始结果；保留其 native 层来源，不冒称为本轮重新请求外网。未来上游版本升级不是本次锁定依赖的额外实际升级门禁。
- **S24 pass**：Web 开启 Heartbeat、5s cadence、active_hours 09:00–10:00，而当时 UTC19:59，原有可行动 HEARTBEAT 文件未引发新消息。真实 bash sleep25 运行期间从 Web 清除时窗，仍无心跳插入；普通回复 `BUSY_DONE_581` 完成后才在20:00:36出现 HEARTBEAT_PAPER581，之后按5s节律继续。已恢复 Heartbeat关闭、空工具配置。证据 `output/round4-heartbeat-outside-save.txt`、`output/round4-heartbeat-busy.json`、`output/round4-heartbeat-final.json`；继承前轮空内容静默与行动内容交付。
- **S23 底层路径补验**：周期任务首到期19:57:00，Node停机跨过19:57和19:58，原数据恢复后只出现最近19:58的一条补投（deliveredAt19:58:19.791），没有19:57回填；后续正常19:59/20:00/20:01各一次。真实 schedule_update 改标题和每3600秒成功，schedule_run 立即 accepted/pending；首次 history 仅 pending/not_yet_delivered，主轮结束后原对话输出 PERIODIC_PAPER_581；再次 history 同一 acceptedSeq173，consumedSeq188、pending=false、terminal completed、delivery confirmed。所以未将收件等同于实际完成。原始 `output/round4-c_tjakbwf5.json`、`output/round4-periodic-jobs.txt`。试图传原生工具不存在的 enabled=false 参数失败，不据此判产品故障；随后按真实参数面修改成功。
- **S25 聊天主路径证据核阅**：`.dsh-runtime/final-fallback-final/evidence.json` 含真实 TS IM+Node 请求，unavailable-primary HTTP401 后公开失败提示及备用切换说明，实际备用模型输出；同聊下一问与冷重启第三问故障provider请求累计仍1；partial-primary先公开正文后报错，未拼接备用答案。此证据证明聊天备用/粘性/重启/已公开输出边界，不能独自证明 Heartbeat/Cron 备用路径。

### 本轮新增可复现入口问题

**F6 major / S23：Web 无法选择当前 Cron 工具。** 同一在线节点公开 `GET /im/v1/nodes/wt-final-review-31430/capabilities` 返回28项工具，`schedule_*` 候选为空；真实 Web Tool Allowlist 同样无这些按钮。缺 `schedule_create`、`schedule_list`、`schedule_update`、`schedule_run`、`schedule_history`。通过公开 Agent config 的 `tool_allowlist` 手动加入原生名称后工具实际可用，并完成上述真实操作，说明问题不只是模型未调用或显式名单未选。原始 `output/round4-capabilities.txt`；修复后的真实 Web 选择仍待复验。旧 `schedule_cancel` 不在有效工具面，不要求为兼容补回。

**F7 major / S26：Generate skill preflight 仍要求旧 skill_view。** 从新系统真实 Workflow 历史执行 Web Generate skill → 选 conversation → execution Agent e2e → Start distillation，提示 `Enable skill_view for the execution agent before starting.`。该 Agent 已有原生 skill/read/skill_manage 能力，公开候选只有 skill、没有 skill_view，用户无法通过正常配置满足旧检查。未创建新执行聊天、未发送蒸馏任务。caller 正修复，现场保留待复验；原生历史导出 prompt 成功的旧证据仍不能证明实际新 Skill 已生成。

本轮暂不发布最终通过结论；F6/F7 修复复验、实际历史→Skill，以及 caller 所领未决分支继续进行。report_commit: none。

## Round 5 — F6/F7 修复及余下实际旅程（2026-10-10）

validated_at: `34164e5e241b55bd674ffa0d7aedef4e83e2eb1f`；caller 构建的前端 `index-SPRHUw_W.js`，原数据 Node 重启 PID53712。report_commit: none。

- **F5 minor closed**：真实刷新后的 Cron 文案为 `Scheduled tasks that return to their original conversation and retain its context.`，与已经验过的主对话语义一致。
- **F6 major closed**：在线 capabilities 和 Web Tool Allowlist 现在同时显示六个 `schedule_create/list/update/delete/run/history`；真实从未选状态选中 schedule_delete → Save Agent → 当前聊天原生调用返回 `{deleted:true}` → schedule_list=[]。页面刷新后周期任务消失，旧的已到期一次性任务仍保留。见 `output/round5-capabilities.txt`、`output/round5-cron-selected.txt`、`output/round5-c_tjakbwf5.json`。新增周期验收任务已删除，不会留下未来唤醒。
- **S23 关闭/重开补验**：公开配置关闭 cron 后，在原聊天请求 manual run 没有真实 tool_call 或副作用；模型输出了无效 DSML 文本（质量问题，不能当作执行）。重开后 schedule_history 仍恰为原4条 timed+1条 manual，同一 manual acceptedSeq173、consumedSeq188，无新增执行，已存任务保持。最终真实删除完成。已验成功/仅入队状态区分；故障终态分支由 caller 补证中。
- **F7 major closed / S26 实际历史→Skill 补齐**：从 Web Generate skill 选择 `direct-review-wf2` 的新历史、执行者 e2e、agent scope，成功生成执行聊天 `c_u5msjorr` 及精确导出路径。真实发送预填 prompt 后，Agent 读取源导出、提炼方法，用 skill_manage 创建 `acceptance-workflow-evidence`，随后原生 skill 再加载并返回完整 instructions；不是只生成 prompt 或空文件。记录 `output/round4-distill-sent.txt`、`output/round4-c_u5msjorr.json`。第一次自动化按变动列表序号误选了 heartbeat 来源，生成了一个未发送空聊天；随后使用语义名称选择正确 Workflow 来源，不把自动化选错报成产品问题。压缩重点/正确分支/冷恢复继承前轮；稳定入站重放的压缩幂等仍待 caller 原始证据。
- **S06 pass**：在既有全局/局部覆盖、A两会话/B隔离和冷启动旅程之外，Agent 真实 write 创建标准 Cordis 模块、保留旧条目追加隔离 owner `plugins.json`；重启后启用新工具，创建者 e2e 与 workspace B 均实际调用 `created_paper_581` 返回 CREATED_SHARED_PAPER_581。见 `output/round4-c_lhu7i3pw.json`、`output/round5-c_lhu7i3pw.json`、`output/round5-c_dj50n39l.json`。一项无必要的环境变量枚举被人工拒绝，改用 pwd/已知路径继续；未暴露环境凭据。最后冗余纠正消息排队后又请求 pwd，已在创建完成后 /stop，不冒称它是工具创建失败。
- **S07 / S33 的代表性旅程充分**：继承显式空工具/Skill、仅选择read后下一轮可执行、memory关闭时task/skill仍可用、资产保留与重新启用、Heartbeat关闭无后续触发、本轮Cron关闭后无执行且重开记录不重复；多次原数据冷启动后配置与资产仍保留。不额外要求对每一个社区Skill重复同一白名单算法，或对五个Feature作无穷排列组合。已开始且成功写入的资产未被宣称撤销。
- **S09 / S17 Web 子审批补证核阅**：`.dsh-runtime/final-workflow-approval-evidence.json` 的真实 child审批均归原启动消息，deny目标不存在、allow_once目标内容真实写入；另一待决调用 /stop 后决议 cancelled，迟到 allow 返回 cancelled，后续 AFTER_CANCEL_581 正常。允许之后模型额外提出的一次bash申请不是已发生工具重放；它未执行而用于取消测试。物理iPhone审批依然未证明。
- **S20 后台机制补证核阅**：`.dsh-runtime/final-knowledge-evidence.json` 明示19次/100天为隔离fixture前置，真实第20次原生skill调用后计数20、uses_since_last_B=0；实际维护child/review completed，旧Skill真实迁入.archive并保留内容。没有声称等待了100天。新Skill生成/自动配置调和/后续使用继承前轮；统计公开投影见下方F8，不把后台事实抹掉。
- **S28 冲突/幂等补证核阅**：`.dsh-runtime/final-graph-evidence.json` 中真实 task_graph 同参数同request_key重试返回完全相同receipt，stale revision新key返回version_conflict，最终get revision2且仅2个todo节点；没有执行计划。首次模型漏change_note得invalid_arguments，补齐后才开始上述验证，不伪报首次调用成功。
- **S30 pass**：结合本轮与前轮实际 status/stop/start、DSH readiness，以及 `.dsh-runtime/lifecycle-acceptance/evidence.json` 的 launchd PID97098→崩溃替换97302、手动停止、显式关闭自启记录。IM不可用仍显示真实运行态；最终TS栈保留日志也显示多次真实重启。motivation不要求额外物理睡眠/网络排列作为本场景门禁。

### F8 major — 在线 Skill 使用统计静默返回空

S20维护/归档在实际持久记录中发生，但在线 `GET /im/v1/agents/e2e/skills/usage` 对刚真实创建并加载的 acceptance-workflow-evidence 返回200、node_online=true、skills=[]和全0。caller的另一个真实第20次/归档fixture在 `.dsh-runtime/final-knowledge-evidence.json` 也出现同样公开空结果。current `docs/specs/im/agents-nodes.md` 明确要求返回name/source/state/use_count等所有使用数据，因此不是离线降级或仅陈旧fixture。原始 `output/round5-skill-usage.txt`。caller已确认并修复中，待原数据IM重启后的公开查询/页面复验。

总体仍 fail（F8和未决必验范围，物理iPhone仍inconclusive），但本轮关闭F6/F7，不把已经完成的功能继续标成未做。caller继续负责故障/unknown及剩余来源边界；最终矩阵将以累积实际证据收口。

## Round 6 — 公开统计修复及补证核阅（2026-10-10）

validated_at: `0ddf25b8b42a7e2062a6cdc950f8411380cdef48`；只按原参数/原数据库重启隔离 IM，PID55483；Node53712保持。report_commit: none。

**F8 major closed。** 在线 e2e Skill Usage API 现在返回 acceptance-workflow-evidence 的 use_count=1、last_used_at、对应真实session_refs，以及distiller的2次使用。真实点击 Web `View skill statistics` 后显示2条Skill和次数1/2，不再空白。证据 `output/round6-skill-usage.txt`、`output/round6-skill-usage-ui-loaded.txt`。入口最初错误用link定位而超时，改用真实button后正常进入，不计产品故障。历史蒸馏经用户明确skill_manage生成的产物当前source=F1/手动创建，caller解释为此次明确用户触发写入分类，记非阻塞观察，不扩大重大门禁。

caller的 `.dsh-runtime/final-knowledge-evidence.json` 保留了原空 `public_usage_before_fix` 并追加 `public_usage_after_fix`：threshold-check active及实际使用22次、aged-check archived，health created2/active1/used1，与持久记录一致。初始第20次触发后的计数20与维护child后续再用两次形成22有明确时间与调用记录，不相互矛盾。因此S20的维护/归档/启用及公开统计完整闭环通过。

**S28 / S29 ACK未知发送补证成立。** 独立核阅 `.dsh-runtime/final-unknown-send-evidence.json`：受控WebSocket代理在真实IM已经提交消息后丢弃实际agent.message ACK并断开，Node publication持久state=unknown；Work真实显示send_message disconnected而不伪装成功，经过连接重建与冷重启后socket publication仍只有一次，公开消息只有 `716949f9a4d6460dacb2eacfbd66157a` 的 ACK_LOST_ONLY_ONCE_581 一条。结合既有成功发送、审批取消和离线完成补交付、原数据冷恢复证据，覆盖要求的可辨认状态与不盲重放副作用，不额外要求每种断开时点与所有客户端作笛卡尔组合。

**S26 压缩幂等补证成立。** `.dsh-runtime/final-compact-idempotency-evidence.json` 显示真实公开Idempotency-Key重发在冷启动后返回同一inputID `e6fd72b15a5c4ff68e7eb8cbba2b80be`，公开历史仅一个压缩控制确认；未出现第二次压缩请求/回复。最初证据中的after_restart_recall误指19:35旧消息，已明确提醒caller修引用，不以该字段证明20:15之后的新回忆。压缩重点、冷恢复连续性及正确fork已有本reviewer前轮独立证据，实际历史→Skill也已完成；不因这处辅助引用错误抹掉真实幂等结果。

**S04后台结果 / S32原生后台读取补验通过。** 群里原生bash run_in_background=true启动30秒工作得到bash-2，用户在完成前更正；真实job_output(wait=true)读到BG_OLD_PAPER_581，但最终面向群成员正文只发BG_NEW_PAPER_581，工具原始结果与最后用户更正被正确区分。见 `output/round6-group-background.json`。同群显式发送工具分支另有待厘清入口：当前single_thread的send_message只暴露DSH子Agent参数agent_id/message，向本群调用返回subagent unavailable；两次都没有外发。该探针更正到达首次调用之后，不冒称完成了发言边界测试；caller正判断正确公开入口，见 `output/round6-group-tool.json`。

**F9 major / S04（caller已确认实现遗漏）**：同群发送探针中single_thread只有DSH内部send_message(agent_id,message)，产品外发target/text分支仅global有，导致用户无法通过工具向当前群发送。不是补一个猜测工具名；caller将复用现有双用途入口并保留原生子Agent分支，同时在同群实际发送边界复核已接收更正。修复前S04继续fail，其普通正文/global正式发送/后台结果的通过证据均保留。

Round 6 补证更新：S23 **pass**。已独立核阅 `.dsh-runtime/final-cron-failure-evidence.json`：真实模型注册30秒提醒后切换到受控HTTP401 provider，实际到期失败；切回可用模型调用原生schedule_history，记录receipt confirmed/accepted true但terminal.kind=error、code=AUTH、delivery=failed。与本reviewer已验manual pending和正常completed形成三种真实状态，未混淆收件与执行。

S26 **pass**。caller已修正上述压缩证据的新追问引用：问题 `0667dd76d3c049289db557d7807bb03b` 在20:15:46发出，新的回复 `9ea8cfced943498184d1db44d6d48e07` 20:15:46.577无工具返回正确原始暗号；结合本reviewer新历史实际蒸馏、分支与其他压缩证据，完整用户结果通过。旧错误引用保留在本报告的发现过程，不再作为当前证据。

F8视觉复核：`output/playwright/round6-skill-usage-fixed.png` 为1280×720真实Web截图，Skill列表两行、使用次数1/2和趋势条均正常显示，非仅接口返回。

## Round 7 — 同群发送首次修复仍未闭环（2026-10-10）

validated_at: `0ca89aee67474d5014f92b04ebf24ace1307bd61`；原数据Node重启PID59882，IM55483保持。

**F9仍open / S04 fail。** 现在single_thread已能看到并调用send_message(target,text)，但真实target=current在下游返回 `Error: scope_not_allowed`。初始消息20:25:41启动35秒bash，20:25:44收到更正，明确早于旧稿的发送边界。旧稿tool因审核服务故障转人工后得到allow_once，仍未通过下游scope；随后最新token再次调用同工具也同样scope_not_allowed。两者都未实际外发，不能把“旧稿没发出”单独算更正机制通过。原始 `output/round7-group-correction-admission.json`、`output/round7-group-final.json`，caller继续修正同一F9链路。

**S15 / S16 / S18机制补证核阅**：`.dsh-runtime/final-approval-policy-evidence.json` 明确使用真实RuntimeClient和受控审核模型fixture，含9个session原始events、14次review请求、5次人工请求和实际effect集合。实际观察前两次classifier_block不执行，第三次转人工批准后才执行；独立review-model参与判定；无有效判定分别走交互人工、global return_to_agent、system unattended；reject/cancel/timeout均无对应effect，DSH规则下的敏感动作被拒绝。结合既有真实模型的Nano/DSH规则写入、global真人短确认、Web/飞书审批旅程，说明产品机制按边界工作，不把受控模型的固定判定伪称自然模型全语义评测。

`.dsh-runtime/final-approval-source-evidence.json` 是实际ApprovalSources产出的受控native-shaped消息transcript：真正human为human-instruction；同一child的父任务/父消息为direct-parent-instruction；其他Agent冒称owner approved仍为fact并附不得洗白权限的说明；人工拒绝为constraint；live Inbox单独保留，read工具中的注入文本不进入授权正文。没有声称每种quoted/cron/background输入都各自跑过独立自然模型审查矩阵；该确定性来源边界与实际RuntimeClient效果、真实审批链联合构成本场景证据。

## Round 8 — 同群发送与更正闭环（2026-10-10）

validated_at: `38d6e5206bae3af38daca384c9e7d40303fe08ae`；原数据IM重启PID61501，Node59882保持。此快照用于F9复验，后续备用修复应另列快照。

**F9 major closed / S04 pass。** 同一群真实新请求在20:29:10开始25秒bash，更正20:29:12已接收。到工具发送边界，旧稿 `TOOL_OLD_ROUND8_581` 的 send_message(target=current) 返回 `held_for_revalidation`；后续最新稿 `TOOL_NEW_ROUND8_581` 返回sent及message_id `b4b96861d11f48049a94ac302759aecd`，群中实际只有这条新稿正文，旧稿没有公开发送。初始bash因独立审核服务故障转人工后allow_once，明确是测试者对该具体调用的批准，不冒称自动审核成功。原始 `output/round8-group-admission.json`、`output/round8-group-final.json`。结合先前普通正文、后台结果和global正式发送的真实更正旅程，S04要求的四个发言边界已覆盖。

至此F1–F9均经对应真实产品旅程修正并复验关闭。此前各轮失败保留为审计过程，不是当前仍open的问题。最终累计矩阵在主动模型备用补证完成后追加；原生iPhone仍无法操作，不能以Web或模拟器通过代替。

### Round 8 累计场景状态（主动备用补证前）

此表替代Round 2的旧累计状态；判定依据是上文逐轮实际观察与注明来源的原始材料，不是测试计划或单元测试数量。

| 场景 | 当前结果 | 累计实际依据与边界 |
|---|---|---|
| S01 普通聊天及图片追问 | inconclusive | Web实际图片发送/左右颜色追问、飞书真实平台交付通过；物理iPhone锁定，未执行。 |
| S02 两节点及身份隔离 | pass | 两个真实Node独立workspace暗号；异权消息/媒体/审批404、停用身份401。 |
| S03 Global多聊天并行 | pass | 多来源持续Inbox、同一子任务追加更正、正式群发送可追溯且草稿不外发。 |
| S04 更正与发言边界 | pass | 普通正文、后台结果、Global正式发送及Round 8同群工具held_for_revalidation→最新稿实际交付。 |
| S05 既有工作能力 | pass | 实际读写/bash/专项工具；网页检索与读取原始结果已核阅，未增加替代付费服务。 |
| S06 两层工具归属 | pass | A两会话局部覆盖/B共享、冷启动保持；Agent实际创建共享工具后两Agent调用成功。 |
| S07 工具及Skill禁用 | pass | 显式空集合无执行；真实Web选择read后生效；生成Skill纳入有效选择，无来源绕过。 |
| S08 委派与后台完成 | pass | 实际多子Agent、追加要求、后台job_output读取，身份和结果来源明确。 |
| S09 停止工作 | pass | 长工具停止后无迟到正文；Workflow待审批取消、迟到allow不执行，后续正常聊天。 |
| S10 JS并行流水线 | pass | 两个实际子Agent并行后第三个组合真实结果；普通聊天无强制Workflow。 |
| S11 保存命名及嵌套 | pass | 保存个人与项目定义、带参调用、一层嵌套；同名项目BIRCH实际覆盖个人MAPLE。 |
| S12 暂停继续及指定重启 | pass | 暂停阻止新派发；选中任务旧attempt终止、新attempt完成后继续第二任务。 |
| S13 前缀复用 | pass | 同脚本0token重放、冷恢复；修改中间调用仅前缀重用，变化处及后续真实重跑。 |
| S14 共享预算 | pass | 同轮两Workflow共同预算耗尽后无新attempt，已有并发消耗可超阈；重放0、不设置时无限制。 |
| S15 默认Nano审核 | pass | 真实模型写入与独立审核记录，受控RuntimeClient副作用验证及来源转录边界联合；不称自然模型全语义评测。 |
| S16 切换DSH规则 | pass | 实际切换后的审核记录及RuntimeClient拒绝/人工/无人值守分流，原请求决议归属保留。 |
| S17 三端人工与Workflow审批 | inconclusive | Web/飞书批准拒绝、子审批原消息归属及取消迟答通过；物理iPhone未执行。 |
| S18 短确认及自动输入 | pass | Global真人短确认实际执行；受控来源和RuntimeClient验证系统输入非同意、阈值及无判定分流。 |
| S19 记忆维护 | pass | 实际受控读写、关闭无副作用、后续使用及后台成功更新通知。 |
| S20 Skill维护启用 | pass | 真实第20次触发、维护child、老资产归档、生成调和/后续可用；公开API及真实Web统计一致。 |
| S21 原对话定时执行 | pass | 实际到期回创建对话并可继续引用上下文，无独立任务会话。 |
| S22 停机到期补发 | pass | 原数据停机跨到期后恢复，原对话只补一次。 |
| S23 Cron管理及历史 | pass | 真实多条查询/修改/删除、开关、manual、跨两周期只补最近；历史真实区分pending/completed/error。 |
| S24 Heartbeat策略 | pass | 空文件静默、活跃时段外跳过、长工具忙碌时不打断，完成后行动内容交付，关闭停止。 |
| S25 配置与备用 | inconclusive | 配置下一轮、聊天备用/粘性/冷恢复及公开partial不拼接通过；Heartbeat/Cron完整备用证据由caller补充。 |
| S26 新历史连续性 | pass | 实际重点压缩、冷恢复/幂等input、正确消息前分支；Web新历史导出后真实生成并加载Skill。 |
| S27 开发态切换 | pass | 新会话接入保留workspace/记忆/Skill/工具/非聊天配置，迁移报告及实际扩展工具证明；不承诺旧聊天兼容或生产已激活。 |
| S28 图与发送事实 | pass | 图保存不执行、同key幂等/旧revision冲突；授权边界及实际发送成功、失败、unknown明确。 |
| S29 断线和恢复 | pass | 离线结果补交付、待决取消/冷恢复；实际ACK丢失持久unknown，重连和冷重启均不重发已提交消息。 |
| S30 运维入口 | pass | 多次真实CLI status/stop/start及就绪；launchd启动/崩溃替换/停止/关闭自启原始证据。 |
| S31 终态入口 | inconclusive | 实际TS IM+Node+DSH与Web/飞书入口，旧CLI退役；三客户端条件仍缺物理iPhone。 |
| S32 原生工具与升级边界 | pass | 原生命名/参数、大文件截断续读、原生后台结果；锁定未修改DSH公开接口，不把未来上游升级额外当成本次实机门禁。 |
| S33 Feature独立启停 | pass | memory/task/skill独立、Heartbeat/Cron关闭与重开、资产保留及冷启动；不虚称逆转已完成写入。 |

当前累计29 pass、4 inconclusive。最高必要动作仍为complete-acceptance；F1–F9无open实现问题。S25补证完成可更新为30 pass，剩余三个场景均由同一个物理iPhone访问条件阻塞。

## Round 9 — 主动备用补证与最终判定（2026-10-10）

**S25 pass。** reviewer独立读取 `.dsh-runtime/final-heartbeat-fallback-evidence.json` 的原始请求、配置和公开消息：新Heartbeat会话没有前置human消息，主模型HTTP401后公开失败提示、切换说明和真实备用模型 `deepseek:deepseek-v4-flash` 的 `HB_BACKUP_581` completed均在同一owner聊天，primary请求恰1次。不是借用最后一条普通用户输入来重新运行。`.dsh-runtime/final-proactive-fallback-before-hb-fix.json` 仅取其cron_registration/cron_messages/cron_conversation切片：真实schedule_create注册后30秒到期，401→切换说明→CRON_BACKUP_581 completed归原对话。该旧文件另外两次故障请求来自后续旧Heartbeat探针，不能把文件整体passed或累计请求数当成Cron的结果；Heartbeat通过依据是独立的新文件。与此前聊天备用、粘性、冷恢复和真实partial禁止拼接的证据合并，S25要求闭环。

**最终累计：30 pass，3 inconclusive，无open产品缺陷；Verdict: fail；Highest Required Action: complete-acceptance；needs_re_review: true。** S01、S17、S31三个inconclusive来自同一个未完成条件：尚未执行物理原生iPhone的聊天/图片追问/审批及三客户端终态确认。caller本轮实时调用iPhone Mirroring入口返回 **宿主Mac locked / manual unlock needed**；这是宿主Mac锁屏导致设备操作入口不可用，不能表述为已经观察到iPhone自身锁屏。所有前文简称“iPhone锁定”均应按本段精确事实理解。

最终矩阵沿用Round 8表，唯一状态变更为S25从inconclusive→pass。三项缺失不是实现故障，也不能由Web、飞书、构建或模拟器通过代替。未作生产部署验收、未宣称迁移源pending资产已经正式激活；S27通过仅指约定开发态新会话与非聊天资产接入。

report_commit: none。reviewer只追加本acceptance.md；原始运行材料位于未提交output/和.dsh-runtime/。隔离final-review栈依caller要求保留供统一清理，本reviewer创建的周期任务已删除、Heartbeat已关闭。caller另有并行实现/文档修改未由reviewer覆盖或提交。

最终实现冻结：`88d49182b0cccfc2937bdc0a337dfe436f76be9d`。caller报告该冻结build/typecheck及全后端50文件119测试通过；此自动检查结果不是reviewer重新运行的证据。Round 9主动Heartbeat实际证据来自caller修复后的隔离peer节点，Cron来自注明的先前真实切片；本reviewer的final-review其他旅程保持各轮已注明快照，没有虚称把全部场景在最终HEAD重跑一次。

清理更新：caller最终要求停止本reviewer隔离栈。先核对Node59882启动时间2026-10-10 04:25:00及绝对final-review配置、IM61501启动时间04:29:01及精确worktree/59784命令，然后使用公开CLI stop停止Node，向核对过的IM发送SIGTERM。后验三个PID（Node59882、其DSH59886、IM61501）均不存在，CLI显示NOT RUNNING，59784无监听。数据库、截图及证据保留；未清理caller其他peer/飞书/proxy服务。


## Round 10 — 用户明确暂缓物理iPhone，按调整后范围收口（2026-10-10）

- validated_at: `c10650095a9619b0e36129f20646ea1d51673744`（本轮文档与授权范围核对）。
- executed_at: 真实产品执行沿用Round 1–9各自注明的运行快照；最终实现冻结为 `88d49182b0cccfc2937bdc0a337dfe436f76be9d`。本轮没有启动服务或重跑旅程。
- effective_at: `c10650095a9619b0e36129f20646ea1d51673744`。已核对从最终实现冻结至该HEAD仅文档/指引归并和决定记录变化，无产品源码变化，因此已验行为证据继续适用；不冒称在文档HEAD重新运行全部场景。
- report_commit: none（由caller统一收口，本reviewer不提交）。

用户原文：“除了iphone上，其他的场景都验收了吗，iphone可以暂时跳过，他和web端用的一套接口吧？”该明确决定已记录在motivation的本次交付范围及pending-decisions中。本轮只调整物理原生iPhone操作的验收范围，不把未执行事实改成通过，不撤销前述环境记录，也不授权生产部署。

**Verdict: pass（用户明确调整后的本次交付范围）；Highest Required Action: none；needs_re_review: false（本次范围）。累计30 pass / 3 authorized-deferred；open产品缺陷0。** F1–F9均已真实复验关闭。Round 9原总体fail对应调整之前的完整必验范围；本轮用户决定使物理iPhone部分不再阻塞本次交付，其他30项通过证据与状态均不变。

| 场景 | 本次状态 | 已有通过证据及延期边界 |
|---|---|---|
| S01 普通聊天及图片追问 | authorized-deferred | Web/飞书与共享接口证据保持；仅物理原生iPhone聊天、图片理解及追问交互暂缓。 |
| S17 人工确认及Workflow审批 | authorized-deferred | Web/飞书、Workflow子审批归原启动消息、拒绝/取消迟答不执行保持通过；仅物理iPhone审批UI暂缓。 |
| S31 CLI退役及终态服务 | authorized-deferred | TS终态服务、个人助手/IM管理入口、Web/飞书及旧CLI退役证据保持；仅第三客户端的物理iPhone终态操作确认暂缓。 |

其余S02–S30及S32/S33除上述两项外，沿用Round 8累计表与Round 9的S25更新，合计30项pass。authorized-deferred是用户授权延期，既不是pass，也不是实现fail；因此本报告不写“33 pass”。后续仍需补齐上述物理原生iPhone切片，届时追加真实设备证据。iPhone和Web共用IM HTTP/WebSocket后端契约，只能说明共享后端已有覆盖，不能证明Swift原生展示、图片交互或审批操作已经实机验证；iOS自动构建/测试门禁不在此次延期范围。

本轮未重新启动或修改隔离栈，Round 9已核对的清理结果保留。仅更新acceptance.md，不修改canonical文档、不提交、不创建PR；本次范围可交付，生产部署仍未授权。

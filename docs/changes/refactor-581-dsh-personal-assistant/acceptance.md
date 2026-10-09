# refactor-581 — 独立产品验收

## Round 1 — 2026-10-10

Validation snapshot: `4915c44cb7f7b829414a19087877ad9b73d69ea1 → e89179da8956577b288ee374fe791c2ce82d5047`。模式 full；来源为 motivation.md S01—S33 与 design.md Runbook，未读取实现定位问题，未使用 worker 成功叙述替代验收。

**Verdict: fail。Highest Required Action: fix-implementation。** 本轮发现 3 个 major 产品问题；必验覆盖仍有 inconclusive。未执行不等于实现失败，但不能据此通过 Full 门禁。report_commit: none（caller 明确要求不提交）。

### 环境及版本边界

- 独立隔离栈 `.dsh-runtime/final-review`，Web/IM `http://127.0.0.1:59784`，测试 owner `u_m77krl29`，node `wt-final-review-31430`。未触碰生产与主 checkout。
- Node PID 31502、受管 DSH PID 31522；`node apps/node/lib/cli.js status --config .dsh-runtime/final-review/.gateway-config.yaml` 返回 `RUNNING ... ready=true`；lsof cwd 为当前受审 worktree；`/health` 为 ok。Node 运行冻结版本，真实模型 `deepseek:deepseek-v4-flash`，本地代理。
- Root 在本轮进行 usage 修正并于 03:22 后重建共享 frontend dist。最初已加载的浏览器及 NaN/配置截图有明确时间；03:25 navigate 后的审批 UI 属于旧 Node + 修订前端的混合构建，仅作为审批行为证据，不冒充完整冻结版本 UI 通过。
- caller 仍持有栈用于修正后重启/复验；本 reviewer 未执行销毁，避免丢失 Workflow 失败现场。最终清理由 caller 或后续 round 负责。

### 用户旅程及证据

原始公开 API 时间线保存在 [acceptance-final-round1-evidence.json](acceptance-final-round1-evidence.json)，包含本轮各聊天的消息、工具、审批及结果；没有登录 token。

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

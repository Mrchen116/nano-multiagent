# Design Review: feat-552

> 状态说明（2026-09-12）：Round 1–3 属于旧方案。用户随后确认了新的 CC 复刻与 Nano 适配原则，design.md 及 delta 已重写，并授权独立 subagent 审查到可实施；新稿从 Round 4 起审查，旧结论不能作为新稿通过依据。

## Round 1

### Metadata

- reviewer: `/root/feat552_design_reviewer`
- review_mode: `full`
- mode_reason: 首轮独立完整审查；逐项核现状、决策、spec、delta 和 milestone，并进行四角度架构进攻。
- started_at: `2026-09-11T01:26:59+08:00`
- completed_at: `2026-09-11T01:32:32+08:00`
- duration: `5m 33s`
- inputs: 本 unit `spec.md` v1、`design.md`、5 份 delta-spec、3 份 evidence JSON、evidence README、两个 milestone 骨架。
- code_baseline: `origin/main=71734873805199d011f777791e8add7b14b80e60`；先读 `b35ed739e` 的 feat-546 worktree，主 checkout 同步后直接读 canonical。审查过程中 main 合并提交变为 `4d38a6f493eff194763997acb86345b2afb93baf`；受审 unit 未改动。未把旧 checkout 缺少全局文件视为缺实现。
- scope: 设计审查；源码只读，没有运行 Nano 验收、实施、启动服务、提交或部署。既有 dirty/untracked 内容未改。

### Verdict

Issues Found — 2 CRITICAL / 0 WARNING。

总体架构可以保留：共享 gate、应用拥有来源事实、全局拒绝回主 Agent、复用消息与工作记录的路线成立。阻断点集中在新设计与现行 SDK/delta 契约没有闭合，修正后复审；本结论不授权实施，也不替代用户醒来后的 review。

### Coverage

完整核对：现状表 10 项、补充现状/约束/复用/历史 7 项；D1–D8 全部决策（含 D1 的每类适配）；spec 6 段用户场景、R1–R6 的 17 个 Scenario、澄清与非目标；delta 的每个 Requirement 和关联修改；M1/M2。上游参数另查原始 proxy 文件哈希及官方配置/权限说明。下列路径除显式写 evidence 外均相对仓库根；行号为本轮实际读取位置。

### 核实台账：现状与生产路径

| 原子 | 实际核实动作和证据 | 判断 |
|---|---|---|
| A1 gate 是真实统一审批链 | 从 `src/coding_cli/product.py:244`、`src/personal_assistant/product.py:475` 的 build_kernel 正向追至 `src/agent/sdk/kernel.py:834` build_hook_registry、`src/agent/platform/hooks/loader.py:116` builtin root，再到 gate `setup`/intercept (`auto_mode_gate.py:831`)；不是测试专用实现 | 成立 |
| A2 旧策略、两阶段、原话投影 | gate 的旧 BASE_PROMPT、阶段常量及 classifier 调用；`src/personal_assistant/tools/inbox.py:241` 解析工具 JSON 并把 user/external 写成用户消息；conversations 继承后因 self.name 检查不作此投影 | 成立；D3 正面改变来源契约 |
| A3 配置覆盖 | `src/agent/platform/config/auto_mode.py:76–83` workspace update global；`:47–56` 无 hard_deny/total，`:122–124` 规则列表解析 | 成立 |
| A4 Broker 计数与 ask | `src/agent/platform/permissions/broker.py:234–289` key=(run_id,tool_name)；gate `:986–1013` 超限跳过 classifier，`:798–815` 人工允许重置/allow_session | 成立 |
| A5 工具检查和 Bash 能力 | gate `:879–909` 先调用工具检查；`:936–942` 当前宽许可可先返回；`bash_policy.py:71–78` 含四种 git 宽前缀，`:214–225` workspace 替换阻断列表，`:338` prefix 匹配 | 成立；D2/D7 修的是现存路径 |
| A6 core 传递及结果 | `src/agent/core/agent/loop.py:550–559` 将完整 history 放入 HookContext；`core/tools/registry.py:279–280` denied；`core/agent/tool_executor.py:236–279` 转换失败来源与终态；HookContext `:145–159` 为 core 类型 | 成立 |
| A7 child 路径 | `src/agent/platform/tools/builtins/agent.py:670–701` 父工具集合减子类型 deny、继承 skills、记录 parent_session_id；`background_tasks/runtime_runner.py:195–208` 真实 auxiliary TurnRequest，`:234–238` follow-up 使用 user role | 成立；D8 必须同时覆盖新派发和 follow-up |
| A8 Inbox/query 数据源 | `src/personal_assistant/tools/conversations.py:7–20` 沿同一工具传输查询但不改消费；`gateway/global_inbox.py:1188–1246` 以 session/call/digest 核 SDK proof 并提交读取收据 | 成立；新增 query 证据是设计目标而非已存在能力 |
| A9 全局 journal/wake 装配 | `gateway/composition.py:285,338` 实例化 store/service；`global_work.py:216–240` journal 接受 SDK committed event 并确认 Inbox；`global_run_coordinator.py:216–238,380–385` 使用 global_main 和 HUMAN | 成立，不能按 HUMAN 推断交互 UI |
| A10 send_message/cron | `tools/send_message.py:199–210` 走内部 dispatch；`gateway/internal_dispatch.py:398–427` 外部投递完成后记录 dispatch_confirmed；`:235,351,386` 存在 held_for_revalidation；`tools/cron.py:351–370` 只读检查及动作投影 | 成立；新描述/确认字段留在既有发送链合适 |
| A11 实际 Cron 误拒 | 读取 `sess_492f06fa9eea990f` 的 `20-22-00_444`、`20-22-01_709` 两份 request，均含“请创建一个一次性 cron 任务”；第二份 non-stream response 确实以 untrusted inbox / unauthorized persistence 拒绝 | 成立；未声称新机制通过 |
| A12 包边界 | 根 AGENTS；`docs/specs/kernel/sdk-boundary.md:14–45` 还包含精确导出/所有权豁免约束，不能只检查 import 方向 | D3 类型导出的契约缺口见 R1-C2 |
| A13 current drift | `docs/specs/kernel/runs.md:139–151` 广义“内核不内置权限策略”与上述 builtin 装配不同；design 已主动标记 | 成立，runs MODIFIED 方向正确 |
| A14 可复用设施 | 模型 caller/HookContext、tool result committed、Inbox receipts、dispatch_confirmed、parent_session_id 都在上述生产链；未发现另一个必须替代的平行审批实现 | 成立 |
| A15 历史角色 | spec Relations 与 feat-539 原草稿仅作为来源；feat-546 能力由本轮真实源码复核；安全检查与子工具交集亦实查 | 不以历史状态代替 current |
| A16 上游资产 | 解析三个 JSON；defaults 实数 17/69/1/21；两份原始 classifier request SHA-256 与 stages manifest 完全一致，参数分别 2112+stop 与 10240 无 stop，两者无 thinking 字段 | 成立；只证明捕获参数/内容，不证明 Nano 成功率 |
| A17 隔离与 runbook | `scripts/e2e-up.sh:115,181,336,370–375` 支持 main-config、独立 workspace、PID 和 IM_URL；设计明确只停自己进程并复用数据重启 | 足以交付后续 reviewer；本轮不执行 |

### 核实台账：决策

| 原子 | 四问与证据 | 判断 |
|---|---|---|
| D1 完整策略适配 | 版本化策略/运行时资产已拍死；11 类适配逐行对 spec R1/R3/R6：授权与 outcome、编码/PA、恢复来源、已投递提议、内置调度、协作、记忆/指令、中文请求、host containment、CC 专属工具、模型资格均有采用或不采用结论。上游参数/默认资产已实查 | 覆盖充分，无需再建 PolicyEngine |
| D2 顺序与快路径 | 对应 R1 用户限制、R6 边界；自检先于宽许可和保守 Bash 识别直接针对 A5；ask 与普通 classifier block 已分开，无新 shell AST/沙箱承诺 | 决策明确、自洽 |
| D3 来源 | 对应 R3 全部反例/R4 恢复；A8/A10 提供原件和投递证据。系统核身份，模型核授权范围；同聊天/同请求者/明确 reply_to/部分批准均有规则 | 架构成立；既有投影契约迁移缺失见 R1-C1；类型边界见 R1-C2 |
| D4 无 pending 状态机 | 对应 R2/R4；A9 证明全局 run 是 HUMAN。return_to_agent 来自应用绑定，新消息走已有 wake，无自动重放 | 决策明确；不增加全局调度器 |
| D5 来源与计数 | R5 全覆盖。根 session 3/20、成功重置连续、有效 block 累计、no-verdict 不算拒绝、interactive 才人工恢复已定义；全局不建暂停锁避免确认后绕过 classifier | 无决策间冲突；现有 allow_once 等入口复用合理 |
| D6 模型/预算 | R1/R3/R5 驱动；捕获参数已核。固定双阶段快照、模型不静默降级、成组预算与不足返回 no-verdict、无第二 client | 边界可实施；Nano 实模效果仍待实施验收 |
| D7 配置 | R6 配置迁移驱动；global root 已存在，workspace 覆盖为显式改变，默认空数组保留旧义，$defaults/重复错误已拍死；Bash 放宽旁路同时治理 | 未扩出组织管理；delta 场景保留见 R1-C1 |
| D8 子任务和消息 | R6/R3 驱动；A7/A10 证明真实落点。委派不冒充人类，子任务继承根策略；不做第三次 LLM 完成审查有逐动作检查依据；外发/cron 都按动作而非整工具豁免 | 合理，无需额外多态/审核服务 |

上游旁证独立打开了 [Auto 配置](https://code.claude.com/docs/en/auto-mode-config) 与 [权限模式](https://code.claude.com/docs/en/permission-modes)：前者说明项目 autoMode 配置不被读取、自然语言规则与 permissions.deny/ask 是不同层，并支持 `$defaults`。这些旁证不等于逐分支复刻或运行验证。

### 核实台账：spec 约束

| 原子（spec 原要求） | design 落点/可验出口 | 判断 |
|---|---|---|
| 用户场景 1“日常工作不再反复确认” | D1/D2/D7；T1/T2 | 覆盖 |
| 用户场景 2“全局主 Agent 自己沟通” | D3/D4/D8；T3/T4 | 覆盖 |
| 用户场景 3“等待期间继续工作” | D4；T3/T4 | 覆盖 |
| 用户场景 4“确认跨运行仍有效” | D3/D4；T5 | 覆盖 |
| 用户场景 5“用户能分辨为什么没做” | D5/D6；T6 | 覆盖 |
| 用户场景 6“共用机制统一迁移” | D1/D7/D8；M1/M2，风险回退段 | 覆盖 |
| R1 日常本地开发：“正常操作自动完成” | D1 PA/CLI 适配、D2 Bash、T1 | 覆盖 |
| R1 一次 Nano 定时：“不因 Inbox 来源…拒绝” | D1/D3/D8、T2 | 覆盖 |
| R1 限制：“确认前不要推送或删除” | D2/D3、T3/T4 | 覆盖 |
| R2 替代/确认/停止：“不弹授权窗” | D4/D5，return_to_agent | 覆盖 |
| R2 问题可理解：“做什么、影响哪个对象” | D4 主模型指导、T3 | 覆盖 |
| R3 简短同意：“其他条件未变化…不再…拒绝” | D3 单一投递提议关联、T3 | 覆盖 |
| R3 无回答/拒绝/无关回答：“待确认操作不执行” | D3/D4、T4 | 覆盖 |
| R3 引用/Agent 转述：“不被当作…真实同意” | D3/D8、T4/T7 | 覆盖 |
| R3 部分同意：“只继续明确获准的部分” | D3 多选与语义范围、T4 | 覆盖 |
| R4 其他聊天：“可处理新请求” | D4 不 park、T3 | 覆盖 |
| R4 空闲收到回复：“无需…重新提交整项任务” | D4 wake/查回、T3/T5 | 覆盖 |
| R4 重启/压缩：“缺失时先查回或澄清” | D3 查询证据、D4 原件恢复、T5 | 覆盖 |
| R5 审批失败：“没有得出结论” | D5 no-verdict/D6，T6 | 覆盖 |
| R5 多次拒绝：“不能…直接放行” | D5 全局诊断计数但不暂停/放行 | 覆盖 |
| R5 其他入口：“继续使用原有入口” | D5 interactive、T1/T6 | 覆盖 |
| R6 主/子任务：“不会…扩大可用权限” | D8、T7 | 覆盖 |
| R6 沟通/迁移：“正常沟通仍可进行…明确说明” | D7/D8、T7/升级清单 | 覆盖 |
| Q1 撤回卡片；后续方向三种处理 | D4；未把撤回项当成批准 | 不冲突 |
| 确认上下文前提与 Q2“对的” | D3/D4；等待只冻结依赖动作 | 不冲突 |
| Q3“统一更新所有 Auto 入口” | M1/M2，非全局仍 interactive | 不缩水 |
| 最新 CC proxy 取证、独立设计后等用户 review | evidence 与交付边界，未实施 | 遵守 |
| 非目标：无新卡片/确认产品/组织平台，不复刻专属云工具/资格/沙箱 | D1/D4/D7/D8 明确不采用；只有 existing facilities | 未越界 |

### 核实台账：delta-spec

| 条目 | canonical 对照及核实 | 判断 |
|---|---|---|
| runs MODIFIED「工具使用权限经注入…裁决」 | 精确锚 `runs.md:139`，正文澄清 core/platform；明确保留旧 allow/deny 与 interrupt 两场景；无等待为 SDK 消费者可见 | 合格 |
| runs ADDED「Auto 统一判断…」 | 明确 deny/真实来源是新保证；但 D3 替换的旧投影 Scenario 仍在 `runs.md:181–190` | 新条目本身清楚，迁移冲突 R1-C1 |
| runs ADDED「分类器未给出有效结论…」 | 对应 D5/D6，未执行/source 是消费者可见 | 合格 |
| runs ADDED「子任务继承…」 | 两个 Scenario 覆盖委派和伪造，同现有工具/skills 交集契约并行增强 | 合格 |
| runs「关联修改」指定模型失败 | 锚现有 Requirement 标题，明确去掉可能 allow fallback；但未形成完整 MODIFIED 及保留其他三个 Scenario | R1-C1 |
| sdk-boundary MODIFIED「装配与会话…」 | global root 两个 Scenario 精确锚定；当前标题下 10 个 Scenario，delta 仅改写两个且未保留其余八个。新增 core re-export 又没有修改已有 ownership Requirement | R1-C1/R1-C2 |
| tools-hooks ADDED「未执行结果…来源」 | 与 `tools-hooks.md:106` 用户 approval 维度独立；既有拒绝文本 `:145–165` 仍成立，可并行增加结构化来源 | 合格 |
| tools-hooks ADDED「transcript…不把执行成功当授权」 | 是 SDK 自动决策消费者可观察的语义约束，不是内部调用断言 | 合格 |
| gateway ADDED「全局自动拒绝…」 | 对照 global-agent 当前连续工作/工具链与 external-channels 原生卡片条件“产生工具权限审批”；新全局路径不创建该请求，故无需重写单聊天卡片行为 | 合格 |
| gateway ADDED「真实用户消息…」 | 来源/同意/反例三个 Scenario 与 R1/R3 对齐；现有 Inbox 消费与访问范围保留 | 合格 |
| gateway ADDED「等待确认…」 | 三个 Scenario 覆盖独立工作、恢复、故障；与现有多事项推进一致 | 合格 |
| cli ADDED「Auto 减少…」 | 本地工作/有效拒绝阈值/故障均为终端可见；不修改原 REPL 交互形态 | 合格 |
| cli ADDED「权限配置升级…」 | 启动诊断/默认可用为终端行为，与 D7 对齐 | 合格 |
| IM no spec delta | 不改 IM HTTP、前端消息类型和群复核；权限不创建来自 Kernel 路由，已有普通消息协议足够 | 合理 |

### 核实台账：milestone 与整体闭合

| 原子 | 核实 | 判断 |
|---|---|---|
| M1 shared-auto-migration | 覆盖共享策略至 CLI/单聊天端到端行为，[reviewer] R1/R5/R6 与 [worker] 矩阵均有；不是纯后端/类型层 | 垂直切片成立 |
| M2 global-chat-confirmation | 全局拒绝→普通消息→其他任务→确认再审/恢复为独立价值，[reviewer] 与 [worker] 两轨齐 | 垂直切片成立 |
| 拆分证据/交集 | 已给 20 文件 900–1300 行 + 12 文件 600–900 行估算，显式超窗口；有共享 SDK 但串行 A→B，不要求并行无交集 | 不据未知实际 LOC 再索要实施计划 |
| 骨架 | 两目录只有 .gitkeep，符合设计期要求 | 合格 |
| 人类 review 层 | 总览一句话、三项可见变化、依赖图、每个 D 的结论清晰，grounding 下沉现状 | 可直接评方向 |
| 数据闭合 | context request→应用核验→同份 S1/S2→结果来源→tool outcome→主 Agent→已有发送/历史；无只有接口无人调用的孤点 | 主链闭合 |
| 风险与回退 | 原件不足/no-verdict/配置迁移/模型误拒均有应对；版本回退不做静默运行双路 | 合格 |
| 运行验收 | runbook 有启动/健康/停止/保留数据重启/真 PTY；T1–T7、基线对照、核心各 3 独立 session 全过与无 KPI 夸大 | 足够设计阶段使用 |

### 架构进攻

1. **归属**：逐一攻击策略 module、来源 provider、core DTO、Broker 根计数、Gateway query/dispatch 事实。策略属于 platform；消息事实属于 Gateway；根 session 计数属于已有 Broker；回调依赖注入不构成 platform import PA。唯一未闭合的是新增 core DTO re-export 与既有 SDK-owned/豁免契约（R1-C2），不要求把类型搬进 SDK 导致 core 反向 import。
2. **该不该存在**：删除测试：policy module 删除会把 126k 策略和 gate 控制重新混在一起；来源 provider 删除会迫使内核相信工具 JSON 或 import 产品数据源；query/dispatch 事实删除会丢失恢复/可见性证明。三者都集中真实复杂度。pending 数据库、独立 scheduler、第二 LLM client、完成后第三次分类器均未新增，没有假想多态维护税。
3. **深还是浅**：独立搜索已核实既有 HookContext/model caller、GlobalInbox receipts/work_events、dispatch_confirmed、parent_session_id。设计复用它们，只把产品核验结果压缩成有限事实接口；没有把完整 Gateway/数据库/HTTP 细节泄漏给 gate。配置和来源版本化有现实用途，未发现纯搬代码的浅 wrapper。
4. **治本还是补丁**：不仅换 prompt，而是同时修不可信 Inbox 身份、确认上下文、宽白名单、自检优先级、配置覆盖、子任务与 no-verdict。Bash 采用有限可证明读形态，不声称完整 AST/沙箱；遇到不确定转 classifier，与本次目标相符。没有发现必须额外扩展安全平台才能成立的问题。

### Issues

- **[R1-C1][CRITICAL] delta-spec 未完整迁移旧审批上下文契约，并遗漏被替换 Requirement 的原 Scenario。** 定位：`specs/kernel/runs.md` 的 ADDED 来源条目/末尾“关联修改”，以及 `specs/kernel/sdk-boundary.md:7–27`。D3 明确停止用 `to_auto_classifier_result` 认证人类来源，但 current `docs/specs/kernel/runs.md:181–190` 仍承诺“消费者消息接收工具显式声明结果审批投影”即可提供该上下文。仅添加 provider 条目会让 canonical 留下两套相反的准入条件。另 SDK 的「装配与会话分两层」目前还有应用零前置、三类应用同构、工具目录共享、稳定方法集、三项模型配置和 Workflow child 覆盖八个原 Scenario，delta 没保留；模型失败条目也只是散文关联修改。不改会让 worker/归并者自行选择保留旧认证入口、删除无关契约或临场重写 delta。请按既有精确标题写完整 MODIFIED（或明确逐 Scenario patch 并逐项保留未改项），将结果投影降为动作/内容描述与新来源 provider 的关系写清；不能只靠 ADDED 覆盖旧规则。

- **[R1-C2][CRITICAL] 新增 core 类型直接 re-export 没有对齐 SDK 所有权边界。** 定位：design「SDK 小接口与内部结果」`ApprovalContextRequest` / `ApprovalConversationEvent` 的 core 类型 SDK re-export，以及 SDK delta `:9`。current `docs/specs/kernel/sdk-boundary.md:14–45` 规定默认 SDK-owned，并把允许 core/platform re-export 的豁免名单逐字钉死；`tests/contract/test_agent_sdk_surface_guard.py:1–26,36–84` 同时守卫名字和所有权。现设计只改“装配与会话”，没有明确新增类型属于受审豁免，也没给 public 类型完整名单（ApprovalContext 的所属/导出应同样拍死）。不改会让 worker 为过 contract 擅自扩豁免、增加 SDK wrapper，或把 core 类型搬到 SDK 造成反向依赖。请保留当前合理分层，显式拍死每个公开类型的 owner/re-export 清单，并给 SDK 边界的对应 MODIFIED delta 和守卫更新范围；无需为此新增一套运行时抽象。

### Recommendations

- [R1-R1] 修正上述两个契约交接问题后，由同一 reviewer 复核实际 delta；不用重开来源系统、再调研一遍 CC 或提前实施来证明设计。
- [R1-R2] 用户 review 时保留“设计审查结论”和“Nano 真模型验收尚未发生”的边界。3 次核心闭环是实施门槛，不是现有通过率证据。


## Author Resolutions — Round 1

- R1-C1：接受。runs delta 按原 Requirement 精确 patch 两个来源 Scenario，并保留四个动作描述 Scenario；模型选择保留三项并精确替换失败项。SDK 装配声明逐 Scenario patch，列全八项不变契约。
- R1-C2：接受。三个公开 DTO 均明确归 core/hooks/approval_context.py，SDK 根 re-export；精确表面与 ownership 豁免仅增加这三个名字，并钉死 owner 路径。SDK delta 保留六项原 Scenario，精确修改豁免项；M1 明列两项 contract 守卫。
- 作者同时修正：非空旧 workspace auto_mode 必须报迁移配置错误并阻止 Auto 动作，避免静默忽略旧 deny 而放宽；CLI 没有独立配置根参数，runbook 改为只读核对用户配置并用 SDK 临时根验配置矩阵；既有未提交研究资料改为文本定位，避免交付依赖未跟踪文件。
- 未实施产品代码，未声称 Nano 真模型验收通过；请按实际修改复审。

## Round 2

### Metadata

- reviewer: `/root/feat552_design_reviewer`
- review_mode: `delta`
- mode_reason: R1 两项修订基本为契约闭合，但 D7 由“忽略旧 workspace 配置”改为“迁移前阻止 Auto 动作”，有有界行为变化，故不是 closure。复核来源/SDK 旧问题、配置上下游与 runbook；未改变需求范围、核心分层或 milestone 拆分。
- started_at: `2026-09-11T01:35:30+08:00`
- completed_at: `2026-09-11T01:37:00+08:00`
- duration: `1m 30s`
- inputs: R1 与 Author Resolutions；当前 design、runs/SDK/CLI delta、evidence README；current canonical 契约、SDK surface guard 与 CLI 工厂。
- execution_boundary: 仅追加本报告，未改受审文件或源码，未实施、运行 Nano 验收或启动服务。

### Verdict

Approved — 0 CRITICAL / 0 WARNING。

R1 两项阻断均关闭。设计可作为后续实施输入，仍须等待用户醒来后的 review；本轮通过不授权开始实施或部署。

### Coverage

- 本轮重查：D3 来源投影契约迁移；D7 workspace 配置错误及 SDK/CLI 的采用规则；三个公开 DTO 的 owner/re-export 与守卫；模型失败 delta；CLI runbook 与研究链接。
- retained_from: Round 1 — A1–A11、A13–A17 的生产链/证据，D1/D2/D4/D5/D6/D8 的主体决策，R1–R6 场景覆盖、未改 delta、M1/M2 和全局恢复/发送路线均未发生语义变化。D3 没更换来源架构，只补精确契约；D7 改变的是升级前错误路径，正常已迁移配置的裁决语义未变。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 精确 patch 原来源 Scenario，保留动作描述/模型/SDK 其他场景 | `specs/kernel/runs.md:18–41` 明确保留四项动作描述 Scenario，逐名替换两项来源 Scenario；模型选择保留三项，仅替换失败项。与 current `docs/specs/kernel/runs.md:154–218` 对照，旧“工具声明即提供来源”不再并存。SDK delta `:9` 逐名保留八项未改场景，与 current `sdk-boundary.md:71–115` 一一对应 | closed |
| R1-C2 | 三个 DTO owner/根包导出/精确豁免与 M1 守卫拍死 | design `:210–217` 明确三个类型统一属于 `agent.core.hooks.approval_context`，根 SDK re-export，不加 wrapper/公开别名；SDK delta `:31–40` 精确修改 ownership Requirement 并保留六项原 Scenario。独立核 `tests/contract/test_agent_sdk_surface_guard.py:38,132–163`，EXPECTED_SURFACE 与 _OWNERSHIP_EXEMPT 确为当前守卫落点 | closed |

### 本轮重查证据及影响链

| changed atom | 核实动作/证据 | 结论 |
|---|---|---|
| D7 非空旧 workspace auto_mode 阻止动作 | design `:185,189` 与 SDK delta `:15–21` 一致：先报迁移错误，不执行，显式迁移并清除旧项后恢复；无旧项/空映射可用默认。current `src/agent/platform/config/auto_mode.py:76–83` 原来确实允许 workspace 覆盖，故忽略旧 deny 可能放宽，新增错误路径有真实动机 | 符合 spec R6“不静默扩大权限”，没有引入兼容双策略 |
| 配置错误与 no-verdict/交互 | D7 是政策尚未可用的迁移错误，不是 D5 的普通 classifier block；D7 明确不执行，未授权人工卡片替代迁移。D5 的模型故障低风险可继续、全局不 park 仍适用于有效配置下的模型故障，不能据此绕过迁移错误 | 无交互/计数语义冲突；默认用户不被新增错误阻断 |
| 配置父子/全局影响 | D8 根会话有效策略继承不变，D7 只在旧配置存在时阻止动作；M1 覆盖 config/SDK，M2 在完成迁移后验证全局闭环。显式迁移先于部署仍在风险段 | 无需新 milestone 或额外运行时抽象 |
| 模型失败/来源失败 | runs delta `:31,40–41` 保留确定性只读快路径，no-verdict 不计普通拒绝、不用 unattended allow；与 D5/D6 和 SDK provider 的角色一致 | 无新的隐式放行 |
| CLI 验收资源 | `src/coding_cli/product.py:244–255` 固定 `~/.nanocode`；独立搜索 CLI 参数未见 global config root 参数，`commands.py:226` 有所用 llm-base-url。只读确认当前用户 config.yaml 不存在；design `:313` 明确验收前复查、不能覆盖 HOME/用户配置，用 SDK 临时 root 跑配置矩阵，PTY 保留真实入口行为验证 | 修正了 R1 runbook 中未充分核实的独立配置根假设；没有降低真实交互验收要求 |
| evidence 链接 | evidence README `:9` 将未提交旧研究包改为文本来源说明；本 unit 策略/stages/defaults 的本地交付链接仍在，捕获输入未改 | 不以未跟踪资料作为交付依赖 |

### 受影响的架构进攻

- **归属**：三个共享 DTO 留 core，产品经 SDK 取得；精确豁免成为显式契约，既不把 core 指向 SDK，也不为通过所有权测试再造 DTO wrapper。R1-C2 的长期维护风险已消除。
- **该不该存在 / 治本**：D7 的迁移错误沿现有配置加载和未执行结果返回；删除这条检查就会忽略原 workspace deny 而使用较宽默认，有具体行为风险。它不增加配置迁移服务或运行时双 classifier，是合理的升级边界。
- **深浅**：来源 provider 接口未扩张；补 delta 后旧工具投影只承担内容描述，应用核原件的职责没有重复落在第二处。其余架构进攻结论继承 R1。

### Issues

无。

### Recommendations

- [R2-R1] 归并 CLI delta 时，可把“CLI 启动采用新的 Auto 机制”精确为首次 Auto 决策时显示迁移错误，与 D7 的明确时点统一；SDK delta 已完整规定阻止行为，不需要新增交互或架构。
- [R2-R2] 保持当前交付阶段：将设计和独立审查留给用户 review，Nano 真模型旅程、实现、配置迁移执行与部署仍未发生。

## Author Resolutions — Round 2

- 已逐项核查本轮 delta 证据、R1-C1/C2 closure 和继承范围；接受 Approved，当前无实质问题。
- R2-R1：作为归并措辞建议保留。CLI Scenario 的 WHEN 表达采用新机制，未承诺在启动时预扫描所有 session；实际报错时点已由 D7 与 SDK delta 明确为首次 Auto 决策。按该明确契约实施即可，无需变更已审产物或扩展启动流程。
- R2-R2：接受。交付限设计和取证，留待用户 review；本轮后未修改受审设计、spec、delta 或证据。

## Round 3

### Metadata

- reviewer: `/root/feat552_design_reviewer`
- review_mode: `delta`
- mode_reason: 用户 review 要求撤回新增委派审批；变化限于 agent 新派发/follow-up 的准入，子任务实际工具审批、来源继承及 SDK 接口不变。已独立检查实际 diff 和相关上下游，无需扩大为 full。
- started_at: `2026-09-11T17:39:54+08:00`
- completed_at: `2026-09-11T17:41:00+08:00`
- duration: `1m 06s`
- inputs: 当前 design D2/D8、现状表、T7，kernel runs delta，spec R6，R1/R2 审查；相关生产源码。
- execution_boundary: 只追加本报告；未修改受审文件，包括 design 第 41 行用户已有空格。未实施代码、运行产品验收或启动服务。

### Verdict

Approved — 0 CRITICAL / 0 WARNING。

撤回委派分类器后，文档之间一致，仍满足子任务实际动作遵循统一 Auto 的要求。

### Coverage

- 本轮重查：agent 免审与 child 实际工具审批的关系；D2/D8/现状表/runs delta/T7 一致性；委派来源及策略/工具/skills 继承；M1 范围。
- retained_from: Round 2（完整 inventory 见 Round 1）— 共享策略、配置迁移、来源 provider/DTO、计数、全局普通确认、发送和恢复链没有变化；R1-C1/C2 的闭环仍有效。

### 历史结论校正

| 历史项 | 本轮核实 | 状态 |
|---|---|---|
| R1-C1 / R1-C2 | 本次不撤销来源契约迁移或 DTO owner/导出边界；runs 只改委派 Scenario | 保持 closed |
| R1 决策台账 D8「委派先审」与架构进攻中的委派审批认可，R2 对该部分的继承 | 原认可未举出“agent 免审导致 child 实际动作免审”的证据。用户纠正成立：新建/继续 child 与 child 工具执行是不同边界。旧审查中认可新增委派分类器必要性的结论由本轮取代；不回写历史 | corrected |
| R1 spec R6 覆盖与 M1/M2 切片 | R6 要求主/子任务的操作受统一机制约束，没有要求委派本身增加一次 LLM 审批；M1 仍负责继承与实际动作检查 | 继续成立 |

### 本轮核实台账

| changed atom | 实际证据 | 判断 |
|---|---|---|
| 当前 agent 免审不等于 child 动作免审 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:187–198` 的安全表含 agent；`platform/background_tasks/runtime_runner.py:190–208` 打开 child session 并提交真实 auxiliary TurnRequest；实际工具由 `core/agent/tool_executor.py:192` 调用 registry.execute，仍经过工具权限链 | 保留委派免审有现行实现依据，不能从工具名字免审推导整个子任务免审 |
| D2/D8 与现状 | design `:46,123,191–195` 一致保留新派发和 follow-up 免审，并明确不新增委派动作投影/启动前 classifier；send_message 的动作审批仍单独保留 | 一致，无残留要求把 agent 移出安全表 |
| 来源与能力继承 | design `:195` 仍要求有效 Auto 配置、模型、交互和已验证用户事实继承；agent_delegation 不冒充人工。当前 `platform/tools/builtins/agent.py:670–701` 已做父工具集合减子类型 deny、skills 继承与 parent_session_id | 没有把取消委派分类器扩成放宽实际动作或伪造授权 |
| runs delta / spec R6 | delta `:63–69` 明确新派发/follow-up 免审，实际动作仍经权限链，伪造同意仍不赋权；spec `:183–185` 要求同范围主/子操作统一受约束 | 对齐用户纠正及首文档要求 |
| T7 和 M1 | design `:323` 同时检查不新增委派 classifier 请求与 child 实际需审核动作仍审批，越权判据落到实际动作；M1 `:266` 仍需 agent/RuntimeRunner 以完成继承，无需为删一个分类步骤拆新 milestone | 验收覆盖正确，没有要求阻断合法派发 |
| 残留文本扫描 | 在 unit Markdown（排除历史 review）检索“先审后/审委派/委派分类器/委派动作投影/agent 移除”，只剩明确不新增的目标语义 | 未发现与修订矛盾的活跃契约 |

### 受影响的架构进攻

- **该不该存在**：对委派 classifier 做删除测试，子任务每个实际工具动作的 gate 仍在，工具/skills 交集和来源限制仍在。没有证据证明额外一次审批必需；保留它会增加 LLM 延迟与误拒，并重复判断尚未发生的动作。此次删除降低复杂度，符合本仓避免过度设计要求。
- **归属/治本**：约束继续落在实际副作用动作处；来源继承解决真实用户授权与委派文本的区分，而不是靠审一次委派文本代替整个 child 的后续权限检查。
- **深浅**：没有新增接口或 wrapper；删除委派投影后，既有 child 执行链继续承担执行检查，职责更集中。

### Issues

无。

### Recommendations

- [R3-R1] 后续按修订后的 T7 验证“派发免审、实际动作受审”两个边界；不要重新以 agent 安全表项本身作为新增委派审批的理由。

## Round 4

### Metadata

- reviewer: `/root/feat552_design_reviewer`
- review_mode: `full`
- mode_reason: 用户重新确定核心上下文、配置、Bash、计数和恢复边界；旧 inventory 不能直接继承。重新读取当前完整设计/spec/delta、全部 evidence 文件及相关源码。
- started_at: `2026-09-12T01:09:16+08:00`
- completed_at: `2026-09-12T01:35:48+08:00`
- duration: `26m 32s`（包含对话中断）
- baseline: `main d5f3183ba`；输入对照 `/tmp/feat552-round4-input-hashes.json`。只读保留其他 dirty 文件，包括 auto_mode.py 的空白修改。
- scope: 只追加审查报告。未实施、提交、推送或启动 Nano；运行了已有 CC 函数回放脚本，未调用模型。用户后续已授权设计完成后按 change-orchestrator-simple 实施；冻结输入的旧阶段说明不作为本轮问题。

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING。

主体方案可保留。唯一阻断为全局 Heartbeat 的真实会话归属同时落入两个相反分流规则；明确该入口优先级即可，不需要新增权限框架。

### Coverage 与历史结论

本轮重新核对现状表全部 10 项、D1–D8、spec 六段场景与 R1–R6 全部 17 个 Scenario、最新澄清/非目标、5 份 delta 全部 Requirement、两项 milestone 与四角度架构进攻。

R1/R2 的 provider/DTO/配置迁移结论已被用户新决定取代，不再当作实施要求。R3“agent 派发免审，child 实际动作受审”仍成立，但本轮重新核实；不继承旧 root 共享计数或恢复授权认证。R1-C1 关于 delta 精确锚定/保留旧场景的原则已用于本稿，R1-C2 因公开 DTO 撤出而不再适用。

### 现状与事实核对台账

路径相对仓库根；CC 偏移只针对 evidence 指定固定哈希。

| 原子 | 本轮核实动作与证据 | 结论 |
|---|---|---|
| gate 真生产入口 | CLI product.py:244、PA product.py:475 → SDK kernel.py:834 build_hook_registry → platform/hooks/loader.py builtin → auto_mode_gate.setup；旧安全表 :187 含 agent/send_message | 同一真实链，无平行死实现 |
| 历史来源缺口 | core/agent/runtime.py:482–486 仅 hook run_origin，:667 新消息 metadata 主要 submission/run；prompting.py:110–140 重建 LLMMessage；llm/interfaces.py:20–40 无消息 origin/host 字段 | D3 接线有真实动机 |
| Broker | platform/permissions/broker.py:234–289 按 run/tool；gate:986 预查阈值；现有 pending/cancel/allowlist 保留 | 当前断言成立 |
| Bash | bash.py:217–269 单次 check_command_policy；bash_policy.py:71–78 四个宽 Git 前缀、:214–225 overrides 替换 | 应在该链实现等价语法/参数规则 |
| 配置/SDK | auto_mode.py:76–83 workspace update global；SDK kernel.py:746 配置根；CLI product.py:255 / PA product.py:493 显式 global root | 保留覆盖不需 SDK delta |
| Inbox/query | tools/inbox.py:241–285 当前成功结果 JSON 投影，筛 user/external；conversations.py 继承但 self.name 阻止用户投影 | D3 必须改混合来源和物化，不能只改 prompt |
| send_message | tools/send_message.py:199–210 既有 dispatch；gateway/internal_dispatch.py:398–427 外部发送后记录 confirmed，另有 held 状态 | 保留真实 outcome 可行，无需新投递认证 |
| global | global_run_coordinator.py:216–238 创建 global_main、HUMAN 的系统 wake；入站 :491–515 保存 sender 信息 | 必须区分调度 origin 和消息 origin |
| Cron/Heartbeat | cron_execution_service.py:516 CRON；heartbeat_scheduler.py:452–460 resolve_global 返回主会话，:559–566 仍 origin=heartbeat；heartbeat_runner.py:395 同样用于重试 | Cron 隔离成立，Heartbeat 分流交集见 C1 |
| child | agent.py:670–701 工具集合减 deny、skills/parent 继承；runtime_runner.py:190–208 真 auxiliary，:234–238 follow-up USER；tool_executor.py:192 仍 registry.execute | 派发免审不免 child 动作 |
| current 契约 | 重新读 kernel runs/sdk-boundary/tools-hooks、gateway global-agent/heartbeat-cron、CLI；runs:139 广义“内核不内置权限策略”确与 platform 装配不同 | drift 已在 delta 处理 |
| 固定 CC 资产 | 实读二进制 SHA-256=a681f300…2558；defaults 17/69/1/21；核对 policy 的 Path A/B、host live/restored、调度/协作例外与 stages 参数 | 不把文档说明当成灰度开启证据 |
| context 实验 | 7 份 classifier request 原件哈希全部匹配 experiments JSON；重跑原 yTr VM 脚本 6 项通过；脚本依赖替身限 human ASCII，不能证明真实开启分支或模型正确性 | 证据边界清楚 |
| CC host/计数 | 独立读固定二进制 166126000 附近 Wjn：message+call+正文、10000 上限；165599392 Sfe/Jlt/WV/Zlt：3/20；165633383 local tracking、总阈值清零/提示 | D3/D6 的这些前提成立 |
| 附件与骨架 | JSON 全部可解析，context-replay 源码已读；两个 M 只有 .gitkeep；既有原 Cron 误拒原件在前轮已定位，本轮设计未宣称新机制通过 | 不需预填实施记录 |

### 决策台账

| 决策原子 | 逐项检查及依据 | 结论 |
|---|---|---|
| D1 原文与七类适配 | coding→assistant、Path/outcome/host 原文、六个实际 cron action、协作、真实目录、宿主事实、短 Inbox 说明均拍死；与原 policy 和实际 cron.py:351–370 对照 | 无隐含新权限引擎；R1/R3/R6 驱动 |
| D2 优先级 | 自检一次、deny 先于宽 allow，agent 保留/send_message 移除；当前生产链可承载 | 明确 |
| D2 Bash 五项 | 原始字符串、tree-sitter Bash、全命令/flags/参数表、复合合成、sandbox 条件与显式 overrides 均明确；算法/表落内部模块 | 架构可实施，完整固定源映射和差分 fixture 为退出条件，不能拿辅助旧源码冒充固定版本 |
| D3 原生输入 | 真人后 pending assistant、末尾 2000 UTF-16、非真人清 pending、当前旁白不入；role 不决定 origin；旧 unstamped 明确沿 CC | 与函数证据一致 |
| D3 host | 投影完成时物化、匹配调用；内存 id+正文登记，live/restored 生命周期、头 2000 和 partial 已定义 | 无需原件认证服务；普通历史重建不能当重启 |
| D3 多聊天 | 历史发送 target/text/outcome + Inbox sender 原文，模型判断；不造 reply_to/固定问答实体 | 用户明确选择；正反例验收承担模型行为证明 |
| D4 自动来源 | scheduled/system/同轮三模板，cron 任务与新同意分开；global wake/child 各保留来源 | 原模板固定包可提取，未把字面 user 当真人 |
| D5 压缩恢复 | 当前窗口、原生 user 与 restored host 区分；查询背景可辅助重新问，不恢复旧授权 | 最新 spec R4 已同步接受 |
| D6 计数 | 实际 session_id、3/20、child 独立、allow 清连续、总阈值清双计数，无永久锁、跨 run 保留 | CC 前提已核，内部接口足够 |
| D6 分流 | global session metadata 与原 unattended 的交集真实存在；表和文字未裁定 global heartbeat | C1 |
| D7 配置/模型 | 原根/覆盖/空数组、扩展键与 $defaults，2112/10240、同快照、模型不降级、无额外裁剪、prompt-too-long source | 最新用户约束内，不恢复旧强制迁移 |
| D8 child | agent 免审、父已读只读快照、agent 来源、普通 child prose 分支关闭、host 恢复降权、不做完成第三审 | 与实际 child 执行边界一致 |
| 接线表 | Message→LLMMessage→runtime/loop/prompting、tool seam、projector、metadata route、Broker、结果、child 均有调用方/生命周期；core 不 import platform/PA | 数据主链闭合 |

### spec 约束台账

| 原子 | 设计/验收对应 | 结论 |
|---|---|---|
| 场景1日常不反复确认 | D1/D2/D7，T1/T2/T9 | 覆盖 |
| 场景2主Agent沟通 | D3/D6，T3/T4 | 覆盖 |
| 场景3等待继续 | D6，T3 | 覆盖 |
| 场景4跨运行 | D5、最新 R4 澄清，T5 | 以新用户决定解释旧场景文字 |
| 场景5区分原因 | D6/T6 | Heartbeat 交集待 C1 |
| 场景6统一迁移 | D7/D8，T8/T10 | 最新确认是不搬配置 |
| R1本地开发；一次Cron；限制仍生效 | D1/D2/D3，T1/T2/T4 | 三项覆盖 |
| R2三种处理；问题可理解 | D6，T3 | 两项覆盖 |
| R3简短同意；无答/否决/无关；引用/转述；部分/多选 | D3，T3/T4 | 四项覆盖，不要求确定性匹配 |
| R4另一聊天；空闲回复；重启压缩 | D5/D6，T3/T5 | 三项覆盖 |
| R5服务失败 | D6/T6，spec 明确保留原 unattended allow | C1 |
| R5多次拒绝；其他入口 | D6，T7 | 两项覆盖 |
| R6主/子任务；沟通/原配置 | D2/D7/D8，T8/T10 | 两项覆盖 |
| 原澄清卡片撤回、Q2、Q3 | 普通聊天、独立推进、共用机制且入口不同 | 无回退旧卡片 |
| 最新=1、原文适配、Inbox工具、scheduled来源 | D1/D3/D4 | 覆盖 |
| 最新移除认证/DTO/裁剪/配置迁移、child独立计数、完整Bash | 撤出表、D2/D5–D8 | 全部落实 |
| 非目标/授权 | 无新卡片/UI/组织服务/OS沙箱；后续实施授权另由主任务执行 | 未越界 |

### delta 与 milestone 台账

| 每个 Requirement / M | 核实 | 判断 |
|---|---|---|
| runs MODIFIED callback | 原标题精确、两个旧 Scenario 保留 | 合格 |
| runs MODIFIED 动作描述 | 四项保留，两项 host 投影替换 | 合格 |
| runs MODIFIED 指定模型 | 三项保留、失败项保持既有 fallback 并区分 source | 合格 |
| runs ADDED 来源语义 | 真人prose、非真人、恢复三个 Scenario | 对齐 D3–D5 |
| runs ADDED 计数分流 | 主/child与阈值/故障 | Heartbeat交集继承C1 |
| runs ADDED child约束 | 派发免审/真实来源 | 合格 |
| tools-hooks ADDED deny优先 | 消费者观察不被宽许可盖过 | 合格 |
| tools-hooks ADDED Bash | 参数/复合两个 Scenario | 合格 |
| tools-hooks ADDED 工具来源说明 | 物化/稳定历史，SDK工具消费者视角 | 合格 |
| tools-hooks ADDED 结果来源 | 未执行/outcome | 合格 |
| gateway global 三个 ADDED | 未获准处理、Inbox多来源、等待恢复，8个 Scenario逐项与D3/D5/D6核对 | 除C1外一致 |
| gateway heartbeat-cron ADDED | scheduled、system、任务内动作；明确原fallback不变 | 与D6有C1冲突 |
| CLI ADDED | 常规、多轮、阈值、故障、原配置五项可见行为 | 合格 |
| SDK/IM no delta | 无公开参数/DTO、根不变，IM协议/UI不变 | 合理 |
| M1 | CLI/单聊天端到端+完整Bash、计数/模型；大规模实现/资产与M2串行 | 垂直切片成立 |
| M2 | 全局聊天确认/独立任务/调度来源/恢复为端到端出口 | 垂直切片成立 |
| 拆分/退出 | 20–25与12–16文件规模、共享处串行；T表明确worker确定性与reviewer真旅程 | 两轨可执行，无需另拆层 |
| runbook/风险 | 隔离e2e、PID确认、保留数据重启、CLI真实根、T1–T10、核心各3次；模型/截断风险承认且不扩框架 | 足够进入实施后验证 |

### 架构进攻

1. **归属**：policy/Bash/Broker留platform，core只传来源和记录，产品注入固定工具说明及会话元数据，不新增反向import。session级route却与run级无人值守重叠，是C1的职责判定缺口。
2. **该不该存在**：删除provider/DTO/确定性问答服务后现有工具投影仍完成职责；host内存登记解决真实live/restored差异，不是另建认证数据库；Bash语法适配器承载明确用户要求，没有假想多态。
3. **深浅**：复用model caller、工具检查、SessionDirectory、消息metadata和发送outcome；Bash入口统一组合语法/表，不让执行器再查。无第二LLM client或独立审批状态机。
4. **治本**：来源通路覆盖submit/steer/recovery/compact，避免只改初始prompt；完整Bash替代宽前缀。保留配置fallback是用户决策，不能借审查恢复一刀切deny。C1只需明确既有入口交集的结果，不需增加新框架。

### Issues

- **[R4-C1][CRITICAL] D6 未裁定全局 Heartbeat 同时命中全局 session 路由和无人值守来源时的行为。** design:191–200 令全局会话及child返回Agent，同时承诺原无人值守fallback不变，并只解释“Cron/heartbeat的独立session”。实际 `heartbeat_scheduler.py:452–460` 对global返回全局主session，:559–566仍提交origin=heartbeat；`heartbeat_runner.py:395–401` 重试亦如此。故设置session级return_to_agent后，该真实Heartbeat会同时满足两列。采用全局优先会使显式unattended_fallback=allow的原Heartbeat变为不执行，违背spec R5和heartbeat-cron delta“原fallback不变”；采用原origin优先又必须明确普通global child与BACKGROUND_TASK的例外。请明确按实际run入口的优先级，至少列出global Inbox wake、global Heartbeat、single-thread Heartbeat、独立Cron及global普通child，并把global Heartbeat的allow/deny fallback纳入T6。不改会让两个worker实现出不同裁决，不是未实施的假想边界。

### Recommendations

- [R4-R1] evidence/README“对本设计有用的事实”第2项仍说恢复时重新验证原记录，第1项仍说assistant待对齐；已被当前D3/D5和最新用户确认取代。可标为历史结论，防止实施者把它们当目标；当前design的优先级已明确，不单独阻断。
- [R4-R2] M表可直接标注[reviewer]/[worker]并引用T项，方便轻量编排；现有T表已足以区分，不必增加大规模审查流程。

### Author Resolutions

- **R4-C1 — accepted.** 作者复核 `heartbeat_scheduler.py:452–460` 的 global binder 路径及 `:559–566` 的 HEARTBEAT 提交，另查 `session_binder.py:271–309` 和 Heartbeat `ensure_agent_runtime` 刷新；确实不能仅凭 session 标签选路由。按用户已确认的“原无人值守 fallback 保持”规定入口优先级：继承全局交互的普通 child → Heartbeat/Cron 自动入口 → global 主会话设置 → 其他原路由。global Heartbeat 保留显式 allow/deny fallback；global wake 与普通 child 返回主 Agent。D6 增加入入口表和重试归属，D8 明确 child 继承 session 选择而非父本轮 Heartbeat 例外；共享 PA runtime 装配负责设置标签，覆盖 binder/coordinator/Heartbeat 刷新。spec R5、kernel/global/heartbeat delta 和 T6 同步，T6 包含真实 global Heartbeat 不可达审批模型的 allow/deny 临时文件动作验证。这是消除已确认规则的交集歧义，不新增权限框架或配置开关。
- **R4-R1 — accepted.** evidence README 两处旧目标已改成用户确认的 `=1` 和 CC live/restored 边界；spec 场景4/6同步为当前恢复/配置原则，避免实施者读旧场景产生相反理解。
- **R4-R2 — accepted.** M1/M2 退出标准直接标注 `[reviewer]` / `[worker]` 并引用 T 项；没有新增门禁、milestone 或过程台账。
- **后续授权同步。** spec/design 阶段声明更新为用户已授权通过设计审查后使用 change-orchestrator-simple 实施、精简重复流程；尚未修改产品代码、创建实施分支或启动服务。


## Round 5

### Metadata

- reviewer: `/root/feat552_design_reviewer`
- review_mode: `delta`
- mode_reason: R4 的完整台账仍有效；本轮语义变化可封闭为 D6 实际入口优先级、D8 继承对象及其装配/验收覆盖。另有恢复/配置旧文字清理、两轨标签和实施阶段授权更新，没有更换核心架构、上下文协议、配置体系或 milestone 拆分。
- started_at: `2026-09-12T01:40:49+08:00`
- completed_at: `2026-09-12T01:42:50+08:00`
- duration: `2m 1s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

与 Round 4 冻结 manifest 比较，变更恰为 design、spec、kernel/runs、gateway/global-agent、gateway/heartbeat-cron、evidence/README 六个文件。逐项重查 D6/D8、交互 metadata 接线、R5 及受影响 Scenario、三份 delta、T6、M1/M2 退出标签及旧文字清理。落盘前确认 17 个输入文件哈希均未变化。`git diff --check -- docs/changes/feat-552-global-auto-approval` 通过。

retained_from: Round 4 — D1–D5/D7 的策略、上下文/恢复语义、固定 CC 源证据、模型与配置方案没有改变；tools-hooks/CLI delta、实验原件及 milestone 骨架哈希相同。其完整台账和未受影响的架构检查继续有效，不重复运行 CC 探针、重抄台账或冒充实施验收。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R4-C1 | accepted；用实际入口优先级解开全局 session 与无人值守运行交集 | design:200–213 明定普通 global child → Heartbeat/Cron → global 主 session → 其他，列全局 wake、两类 Heartbeat、Cron、child 及其他入口；model retry 保留归属。D8:233 明确继承 session 交互而非父本轮 Heartbeat 例外。spec R5:171/174、三份 delta 和 T6 同步 | closed |
| R4-R1 | accepted；删除仍像目标的旧恢复认证/待对齐描述 | evidence README 的事实1明确用户选择 =1，事实2明确 live/restored、不恢复认证；spec 场景4/6:103/105 与 D5/D7 一致 | closed |
| R4-R2 | accepted；直接增加两轨标签和 T 引用 | design:295–296 的 M1/M2 均有 reviewer/worker 出口，并引用既有 T；无新增 milestone/过程门禁 | closed |

### 本轮重查证据与影响链

| changed atom | 独立核实动作与证据 | 判断 |
|---|---|---|
| 实际入口优先级 | `heartbeat_scheduler.py:452–460` 确认 global 复用主 session，:559–566 提交 heartbeat；`global_run_coordinator.py:216–238` 则以 global 场景和 HUMAN 提交 wake；`cron_execution_service.py:516` 提交 CRON。design:204–211 对各入口有唯一结果 | R4 的真实交集已消歧，显式 unattended allow 不被 global 标签意外取消 |
| 重试和 runtime 装配 | binder:289–305 创建时传 global 场景；coordinator:217–222 与 heartbeat_scheduler:512–526 均经 ensure_agent_runtime 刷新。`kernel_client.py:172–194` 将场景交给 `session_composition.py:52–100` 共用 runtime 投影；`heartbeat_runner.py:385–401` 重试保留 HEARTBEAT 及 global 场景。design:200/251 要求共享装配覆盖这些路径 | 有真实共用落点；不能只在 Inbox wake 上打标签。此处评审的是明确的改动契约，当前代码尚未实现该新标签 |
| child 识别及继承 | `agent.py:670–701` 取得父 session、构造 kind=subagent 并传 parent_session_id；`background_tasks/runtime_runner.py:183–205` 默认 BACKGROUND_TASK，:234–238 follow-up 用 USER。design:202/210/233 用既有身份和继承设置识别普通 global child | 不从枚举猜真人或权限方式；父 Heartbeat 的临时 fallback 不污染 child。既有子任务身份可承载，不需新权限状态机 |
| 既有 fallback 与硬限制 | gate:849–856 当前根据 run origin/workflow_unattended 分流，:944–976 有工具 allow/deny/ask 处理。design:195–198/202 保留各入口原处理，明确 deny 与必须人工安全检查先处理 | 新优先级不将 classifier fallback 扩大成工具硬限制豁免；其他入口仍沿原路由 |
| 受影响 spec/delta | 全读三份改动 delta，核对 R5:169–179；kernel 模型故障、计数分流，global 连续拒绝，heartbeat 新 Scenario 均表达同一入口区分；runs 原 MODIFIED 标题和保留 Scenario 未删 | 消费者可观察结果一致，现有 canonical runs:218 的显式审批/unattended fallback 未被无意抹去 |
| 验收与交付 | T6 明列 global/single Heartbeat、Cron allow/deny 及 global wake/child 对照；表后另要求真实 global Heartbeat 不可达审批模型 + 临时文件动作各一次，区分协议异常 fixture 和真实入口。M2 引 T6，M1/M2 串行范围保持 | 能抓住原冲突，不仅测试孤立路由函数；设计通过后可按已授权 simple 实施，部署仍另行授权 |

### 受影响的架构进攻

1. **归属**：产品提供交互选择，runtime 保留实际 run 来源，platform gate 统一判定；主会话标签不冒充本轮入口，child 继承不复制父临时调度状态。D6/D8 组合没有新增反向 import 或产品权限逻辑下沉 core。
2. **该不该存在**：复用既有 session/scenario、child 身份和共用 runtime 装配即可；没有新增路由服务、公开 DTO 或配置开关。把各入口判断散写在 Gateway 每个调用点会造成刷新遗漏，当前共用装配要求能避免该具体维护代价。
3. **深浅**：统一 gate 收敛入口交集规则，沿现有 binder/coordinator/Heartbeat 接线；无需为本次消歧另造包装层。其他未变抽象继承 Round 4。
4. **治本**：明确 run 与 session 两层事实的优先级，并用真实 global Heartbeat 验证，直接解决 R4 的生产入口冲突；没有把症状用一刀切 deny 或仅改测试桩掩盖。

### Issues

无。Round 4 唯一 CRITICAL 已闭合，本轮未发现会使实施者实质走偏的新问题。

### Recommendations

无新增建议。可进入用户已授权的 change-orchestrator-simple 实施；本轮结论只表示设计可实施，不表示新机制已经运行验证。

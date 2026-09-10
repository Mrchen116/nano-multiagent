# Design Review: feat-552

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

# refactor-581：个人助手迁移到DSH — 技术方案

> 对齐：[motivation.md](motivation.md) Q1—Q24、R1—R12 / S01—S33。Q22—Q24要求DSH源码零改动与独立Feature插件生命周期，已纳入修订并通过独立Round 3（0 CRITICAL / 0 WARNING）。见[独立审查记录](design-review.md)；未实施、未部署。
>
> 本文是实施入口：维护最终决策、契约增量、里程碑与验收接管方式。[终态架构](target-architecture.md)是本设计的职责/接口详述，[Workflow设计](workflow-control-design.md)是其控制子系统详述，[迁移计划](migration-plan.md)维护数据/发布操作顺序，[能力地图](capability-plugin-map.md)维护固定源码依据；这些文件一并冻结和审查，不存在另一套候选实现。

## Changelog

- 2026-10-09：需求Q1—Q21收口，建立12项Requirement、32个Scenario、5个实施阶段与5份delta-spec；独立Gate 2经R1修订后R2 Approved。

## 现状分析

### 涉及范围

| 当前范围 | 当前职责 | 迁移目标 |
|---|---|---|
| `src/agent/` | 自研loop、模型/工具、session、子Agent、Workflow | DSH公共包承担通用执行；Nano仅保留已确认缺失的policy/Workflow/knowledge扩展 |
| `src/personal_assistant/` | 节点、渠道、Inbox、身份、配置、主动策略、交付 | TypeScript节点产品；业务模块与DSH插件明确分开 |
| `src/IM/` | 独立中心API/WS、身份、聊天、配置、任务图、客户端 | 独立TypeScript IM后端；保留现有React Web与Swift iOS |
| `src/coding_cli/` | 自研Coding CLI | 终态退役；个人助手及IM运维入口继续可用 |
| `scripts/`、运行配置、测试及current文档 | 隔离启动、运维、契约和行为保护 | 启动/构建/测试默认指向新路径；终态不再依赖旧Kernel运行 |

源码基线为Nano `4915c44c`、DSH `5badb150`；当前写作checkout是保留已有dirty状态的`main@76fe1d7e`。实施必须从包含已核查最新Nano基线的隔离unit checkout开始，不能把当前旧checkout的缺失iOS文件误判为无需迁移。能力与本机扩展资产的已知/未知边界见能力地图§8.5。

### 既有约束

IM中心不执行Agent loop；产品身份、访问资格、共享任务图、配置operation和交付真源不下放给模型。当前`agent.sdk`依赖红线在旧路径仍运行期间继续有效；终态由新的依赖契约替换，而非绕过旧契约偷偷import内部。禁止修改全局Git配置、覆盖用户dirty工作、提交本机数据/凭据；运行隔离按仓库worktree规范。

### 可复用能力

- **直接用DSH**：session/loop、原生工具与名称、Skills加载、MCP、provider/同模型retry、subagents/jobs、compaction、approval、schedule。依赖锁定和升级使用标准包/profile；不复制源码或维护旧工具名/schema兼容层。
- **改接现有产品能力**：中心API/WS、Inbox及摄取、身份、配置同步、任务图、渠道/发送/回执、三个客户端。换语言不重设计其业务规则。
- **补齐明确缺失**：Workflow四项控制/保存嵌套、知识自动维护、Auto产品政策、跨模型fallback、手动压缩focus/幂等、现有搜索后端/网页提取与专项工具。5个Feature插件单元见终态架构§5.4；基础接入/策略服务另外装配，npm包数量不等于Feature数量。
- **不用**：旧Coding CLI、旧Agent loop、旧Python Workflow解释器、旧聊天转换器、独立Cron会话派发、过期一次性跳过策略、DSH Web作为Nano客户端替身。

### 相关历史

- Workflow既有契约及控制来源在[Workflow设计](workflow-control-design.md)中追溯；保留用户确认的语义而非旧执行器。
- `feat-532`记忆循环及`feat-539`Auto相关工作均可能含未完成设计；本次以固定基线的current行为和已注册能力为准，不把未落地研究目标混入迁移范围。
- 最新原生iOS与移动Web修复已包括在Nano基线；其客户端回归面保留。旧聊天兼容已由Q18排除，不能从以往迁移习惯重新加回。

## 架构总览

采用“独立IM中心 → 节点产品服务 → 每节点owner一个DSH受管子进程”。节点继续拥有业务；DSH拥有执行；插件连接两者。图、包边界、数据owner及真实旅程见[终态架构§3—11](target-architecture.md#3-从用户旅程推导职责)。

终态代码边界固定为`apps/im-server`、`apps/node`、保留的Web/Swift客户端，以及`packages/{product-contracts,personal-assistant,channels,dsh-integration}`。包目录不等于都要独立发布；普通产品模块不使用Cordis/DSH类型，所有上游依赖集中在integration runtime一侧。

Nano自有主插件按11种装配单元组织：4种基础接入/策略、global模式、Workflow常规工具及5种Feature。唯一完整职责清单见[终态架构§5.6](target-architecture.md#56-nano自有插件完整清单)；DSH原生依赖、社区安装项及每Agent实例数量另计。

## 关键决策

1. **节点/IM服务端采用TypeScript，IM仍独立部署。** Q5/Q9允许按终态合理安排。拒绝将整个Gateway插件化；不让IM后端重写阻塞第一条DSH纵向链，但它是本unit的终态范围，不能以过渡Python服务宣布迁移完成。
2. **一个owner节点一个受管DSH子进程，唯一stdio协议写入方。** 这是生命周期隔离，不是同OS用户下的不可信租户沙箱。不开每session进程池，不新增分布式选主。
3. **所有顶层会话统一经原生SessionController创建/恢复。** 稳定命名Nano preset承载可重建的配置与插件；先恢复可信绑定和preset，再挂原生schedule。临时setup闭包不会自动持久化，具体调用链见[终态架构§7.1](target-architecture.md#71-为什么不直接套官方-sdk)。
4. **可以替代的工具使用原生名字、schema和实现。** 迁移Skill引用；功能配置仍做真名单，产品专属发送/Inbox/任务图保留独立入口。DSH内部`send_message`不能顶替Nano对外发送。
5. **定时任务回原主对话，过期一次性恢复后补发。** 完整复用原生schedule owner，不保留第二套安排/timer。Heartbeat任务选择、忙时/静默等缺失策略留在产品服务。
6. **Auto只运行一个consumer，规则可选Nano/DSH。** 默认Nano；两套规则共用独立审核模型、真实来源和产品分流。规则选择是节点配置，按既有审核配置的重启边界生效，不新增前端表单或第二条分类链。
7. **Workflow四项控制和知识自动维护是必须迁移的能力。** 自有Workflow provider复用公开PTC/subagent，不重写Agent loop；知识策略复用文件/Skill/child/jobs服务。不因上游缺失改成手工维护。
8. **开发态从新会话开始。** 不转换旧模型历史、旧fork或旧蒸馏格式；非聊天资产接入、新系统持久化/恢复及新历史功能保留。原数据不因写作或实施准备被删除。
9. **DSH源码零改动。** 使用锁定且未修改的上游依赖，不维护fork/patch、不monkeypatch或私有导入；schedule用每数字人原生服务的公开生命周期，fallback在同一产品运行内衔接多个原生turn，详见终态架构§10。
10. **5个Feature可独立启停。** Task Graphs、Memory Curation、Skill Creation、Cron、Heartbeat各有独立插件scope/disposer，共享稳定接入与运行结果底座。关闭撤销后续能力而保留持久数据，在途工作按current收口；详见终态架构§5.4。

## 接口与数据流

权威接口与恢复语义在终态架构§6—10；不将设计伪代码宣称为已存在的SDK。

| 边界 | 本次必须落实 | 验证点 |
|---|---|---|
| 节点 → runtime | 版本/能力握手，ensureSession、submit/lookup、observe、cancel、approval answer、release/shutdown | durable ACK基于真实flush；同input重复不二次接受，回执丢失可查；审批/取消不能被长请求堵住 |
| runtime → 产品回调 | 工具实际身份、取消信号、来源、调用/发送操作ID | 不接受模型伪造owner；发送未知能补查，不能靠重试重发 |
| 事件 → Work/客户端 | session seq、输入/轮次/工具/子任务/Workflow归属，持久补读和临时增量分开 | 缓存token口径归一；后台结果真实持久后才报告可恢复；不把turn结束等同交付成功 |
| 配置 → scope | 有效revision、模型/推理/context window、工具/Skill选择、global/workspace两层、历史fork快照 | 默认发现与显式空集合不同；新建/恢复/child同源装配；运行中配置不被半套热换 |
| schedule → 主对话 | 原生task.sessionId、原生schedule来源、产品触发/执行归因 | 冷恢复仍装配正确preset；回原对话、补发一次性；原生收件历史与模型执行历史分开 |
| Workflow → 子Agent | logical call/attempt、派发gate、终态结果前缀、共享turn预算 | 公开run对象不冒充logical identity；暂停/重启/重放/预算与真实child生命周期一致 |

主会话命名preset是执行装配入口，节点仍持有配置权威。私有workspace工具不因包安装进入全局；同workspace的多会话/恢复/child按持久声明装配。scope不能作为业务授权替代品。

客户端布局与交互沿用现有产品；本次不新增页面、表单或导航，因此不生成静态前端原型。工具名称和schema来自原生元数据，现有通用工具展示消费它；实际Web/iOS/飞书验收必须验证更新后的数据在现有界面可用。如果实施发现需要新增客户端交互，按真实增量补设计/原型并复审，不在实施中自由重做UI。

## 契约层增量 (delta-spec)

| 领域 | Delta目标 | 变化 |
|---|---|---|
| 定时任务 | [gateway/heartbeat-cron](specs/gateway/heartbeat-cron.md) | 原主会话投递、过期补发、系统来源及手动运行/历史保证 |
| 能力与权限 | [gateway/agent-capabilities](specs/gateway/agent-capabilities.md) | 原生工具/两层扩展、可选Auto规则；既有审核模型/真名单等保留 |
| Workflow | [gateway/workflows](specs/gateway/workflows.md) | JavaScript及已确认控制/前缀/预算/命名嵌套成为产品层契约；运行真源替换旧SDK表述 |
| 新历史 | [gateway/relay-protocol](specs/gateway/relay-protocol.md) | 新DSH历史的分支/蒸馏，排除旧历史兼容 |
| 运行生命周期 | [gateway/service-lifecycle](specs/gateway/service-lifecycle.md) | 产品节点及受管执行运行时的就绪/停止边界 |
| 回复用量 | [im/response-metrics](specs/im/response-metrics.md) | 按能力映射 L3 保留未知计数，缺失计数不补零，使用 `—` 或省略未知详情；修复阶段显式记录客户端缺失值语义 |
| 聊天路由与运行存活 | [gateway/routing-delivery](specs/gateway/routing-delivery.md) | DSH 会话术语与统一 liveness 判据，审批等待依赖实际心跳；不保留旧永久豁免 |
| Agent Cron 管理 API | [im/agents-nodes](specs/im/agents-nodes.md) | 纠正既有文档路径为客户端实际使用的 `/cron/jobs`；保持任务列表与删除行为 |
| IM、Web、iOS其他产品协议 | no spec delta | 保留既有HTTP/WS与业务行为；实现不能擅自改变schema或UI交互 |
| 旧Kernel/CLI与顶层依赖 | 退役计划见下文 | 不再发布旧库/CLI；`SPEC.md`/AGENTS依赖约束在最终退役提交更新，旧kernel/cli current文档整体移入历史并更新领域入口 |

旧Kernel能力中仍属产品的部分已投影到R3—R7/R10及上述gateway delta；不把旧`agent.sdk`契约改写成新DSH内部API。迁移期间旧路径仍受原契约保护，只有所有consumer迁走才能删它。新current依赖契约验证IM/产品不import DSH、integration仅使用公开包入口。

## 风险与回退

主要风险是输入持久确认、scope冷恢复、模型/权限来源、后台结果持久交付和新版插件差异。每项有明确owner与里程碑退出证据，不以“薄适配”预判维护量。

[迁移计划§4、§7](migration-plan.md#4-数据与资产范围)定义账号/凭据、workspace、配置和实际外发等资产边界及切换顺序。先停收/排空、备份、接入新绑定，再启动唯一新消费者。未产生新写入可以恢复检查点；已有新消息/外发时先保留增量并对账，不恢复旧快照掩盖变化。生产部署另按具体发布授权，不在设计阶段执行。

## Runbook for Reviewer

本节是实施完成后接管契约；命令入口现有，但在本次规划时仍启动旧实现。**M1/M5必须更新其受管进程和构建目标，验收先核实际cwd/版本/PID，不能拿旧栈成功当新栈通过。**

| 服务 | 停止命令 | 启动/构建命令 | 健康检查 |
|---|---|---|---|
| 隔离IM + 节点 + DSH受管子进程 | `./scripts/e2e-down.sh` | `pnpm install --frozen-lockfile`；`pnpm build`；`./scripts/e2e-up.sh` | 读取脚本生成的`.e2e-ports.env`，请求实际IM `/health`；产品节点状态及runtime版本/握手均就绪；PID/cwd与受审checkout对应 |
| 同栈专用飞书测试profile | `./scripts/e2e-down.sh` | `./scripts/e2e-up.sh --feishu` | 同上并核专用bot已连接；用现有`e2e-feishu-probe.py`路径及真实平台完成输入/卡片/回执验收 |

pnpm脚本名`build`是本unit需要建立的根工作区入口；依赖版本按DSH baseline `pnpm@11.7.0`、Node `^22.19.0 || >=24`锁定。单测/契约采用`pnpm test`，产品整栈仍由上述隔离脚本启动；具体测试文件和筛选参数由实施产物提供，不能在尚无测试时声称已执行。

**Review驱动方式**：全程端到端真栈。API身份、配置、故障可用客户端同一HTTP/WS入口驱动；消息/工具/审批/Work及原生名称在Web和Swift iOS真实界面观察；飞书用真实平台专用bot和审批回调。不同机制的确定性测试可用stub provider制造失败，但每种模式至少完成一条真实LLM链。iOS模拟器和镜像不能代替真机证据。

**验收前置及2026-10-09定向核查**：

| 资源 | 来源/当前查证 | 实施验收时的可用性检查 |
|---|---|---|
| 本地工具链 | Node `v25.8.2`、pnpm `11.5.2`已存在；目标依赖需切到锁定pnpm版本，不改全局Git或其他项目 | checkout内安装锁定版本并构建；记录版本，禁止把本机旧依赖缓存当lock一致 |
| 本地模型代理 | 既有隔离配置`config/e2e/gateway.yaml`和本机已用Anthropic协议代理；不在文档复制凭据 | 从隔离配置走一次真实请求，核模型/代理路径与LLM日志；不擅自改直连或付费provider |
| 飞书 | `~/.config/nano-multiagent/feishu-e2e.env`存在；仓库已有专用profile/单监听锁 | 接管时检查专用bot凭据和平台scope、可收输入/卡片回调；不得复用/踢下生产监听器。文件存在不等于本轮完成平台验收 |
| Web | 现有浏览器与隔离IM地址 | 真浏览器核文本/图片、工具展示、审批、断线恢复；测试账号由隔离fixture创建 |
| iOS真机 | `/Applications/Xcode.app`存在；命令级`DEVELOPER_DIR`核实一台已配对iPhone、Developer Mode已启用；当前tunnel不可用 | 接管时连接/解锁该设备并确认可达；按既有工程签名安装受审build再验前后台/图片/审批。不在本轮宣称真机验收已通过 |
| 双节点发布 | 既有个人舰队与[生产操作规范](../../operations/prod-fleet.md) | 发布前核目标revision、owner/node绑定、Mini-only IM、实际进程cwd/PID与HTTPS/WSS；生产授权后执行 |

以上资源归属和取得路径已明确；若接管时必需平台/设备不可用，验收标记未执行并恢复资源后继续，不能降格为源码或单测验收。不得在当前写作文档的dirty主仓启动测试服务。

## Milestones

拆分依据是**分阶段可运行验证与独立发布边界**：先证明一条真实DSH链，再扩大产品模式，随后完成上游没有的能力，最后替换中心与退役旧路径。不是按数据层/API/UI/测试横切；每段包含它的实际用户路径、配置、测试和运维接线。默认顺序执行，不为了并行预建多worktree。

| ID | 标题 | 依赖 | 并行组 | 文件范围（目标路径） | 退出标准 |
|---|---|---|---|---|---|
| M1 | DSH驱动的完整单聊 | 无 | 顺序 | `apps/node/`、`packages/dsh-integration/`基础协议/preset、PA单聊及`e2e-up/down` | **[reviewer]** S01单聊文本/图片、S09停止、S17一次人工审批、S29 runtime重启链可走通；**[worker]** 真实DSH profile和版本可识别；input/flush/lookup、scope冷恢复、独立审批/取消回调故障点契约通过；启动脚本实际使用新node/DSH，不能用旧Kernel替身 |
| M2 | 完整个人助手与多渠道 | M1 | 顺序 | `packages/personal-assistant/`、`channels/`、产品contracts、Web/iOS协议接线 | **[reviewer]** S01—S04、S17—S18、S21—S24、S28—S30、S33相关项：global/single_thread、飞书、身份、主会话schedule/补发、Heartbeat、任务图和实际发送；**[worker]** source/owner/配置operation、群复核、去重/回执及schedule冷恢复结果归因通过；schedule入队flush与receipt提交间故障及trigger/message对应可解释；按Agent原生Schedule服务卸载/重挂与独立存储、跨重启开关及Feature启停通过；两种模式和隔离节点不串扰，产品安排无双写 |
| M3 | 原生能力、配置与知识维护 | M2 | 顺序 | integration `knowledge/policy`、模型/工具/Skill装配、配置/资产接入、新历史接线 | **[reviewer]** S05—S08、S15—S16、S19—S20、S25—S27、S32—S33相关项：全局/workspace工具、真名单、模型/Auto切换、自动维护与新历史；**[worker]** default/empty过滤、两层shadow/恢复、真实用量归一、fallback原生turn间衔接、idle/maintenance准入、输入去重、模型/prompt/effort/窗口、原生overflow、retry优先及成功后粘性、focus幂等、现有专项工具/搜索后端验证；原生名字无兼容副本，非聊天资产不丢失 |
| M4 | 完整JavaScript Workflow | M3 | 顺序 | integration `workflow/`、命名catalog、控制/预算/结果持久、产品后台投递 | **[reviewer]** S10—S14及S17的Workflow后台审批/完成：并行/流水线、保存嵌套、暂停重启、前缀恢复和预算；**[worker]** 按Workflow设计验证logical call/attempt、并发/完成序、跨重启终态前缀、实际usage、真实child清理；结果先持久再可交付，退出旧Python运行依赖 |
| M5 | TypeScript中心与旧路径退役 | M4 | 顺序 | `apps/im-server/`、协议/数据库适配、发布/开发入口、移除旧`agent/coding_cli`与旧服务运行路径、文档/CI | **[reviewer]** S01—S33在最终树适用场景成立，S31仅保留PA/IM入口；Web/iOS/飞书及多节点从同一目标协议工作；**[worker]** IM认证/API/WS/SQLite/媒体/配置契约、最终依赖边界、DSH依赖无源码补丁/安装重写/私有导入、5项Feature卸载与重启、隔离切换与回滚演练通过；旧Kernel/CLI不可达，旧current文档归档，新current/delta对齐；全量选定门禁和CI在最终树执行或有有效retained依据 |

M1—M4允许过渡期继续使用现有Python IM，但不改变M5全TypeScript后端终态。每段的`[reviewer]`是产品结果要求，不意味着每段单独重复所有正式门禁；正式reviewer/verifier/code review按最终集成树和实际变更范围执行，已有有效证据可复用。

生产部署不混入编码milestone的完成声明：M5产出可审查版本及演练证据后，经具体部署授权按迁移计划切换并核真实平台/设备/节点。迁移计划本身的完成不代表这些实施或部署结果已发生。

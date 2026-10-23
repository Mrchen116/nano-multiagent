# bugfix-646: Global Task 续跑、等待与反馈闭环 — 技术方案

> 对齐: incident.md

## Changelog

- 实施真实模型验收发现Nano/Codex 工具审批均硬编码 low，与默认 DeepSeek high/max 能力不匹配。采用既有 disclosure 审核的能力选择：支持 low 则用 low，否则原模型 default/首个声明档位；不改模型、来源证据、规则或 verdict。增加同模型请求参数回归保护。

## 现状分析

### 涉及范围

- integration `task-execution.ts` 通过原生 idle、pre-step、followup 合并自动输入；snapshot 来自 PA，模型仍由原生 DSH 执行。
- PA `task-execution.ts` 解析 current responsibility 与 Schedule evidence；IM `task-graphs.ts` 在异步预检和同步提交阶段确认 waiting。后者是等待时间约束的权威边界。
- integration `features/task-graphs.ts` 注册工具与提示；返回 `{ok,result}`，apply 的 result 当前只有图摘要、client_refs 与 changed_ids，不含节点和固定聊天；本次增加提交时的最小反馈投影。`global-mode.ts` 已规定非空私有收尾和 send_message 显式交付，shared interactive-ui 提示/Skill 与其冲突。生成源为 `scripts/generate-interactive-ui.ts` 的 Skill 前言和 `src/IM/frontend/src/features/chat/interactive/catalog.tsx` 的 composition guide；修改源并重生成资产。这是模型文案源，无客户端交互变化。
- `global-agent.ts` 既有 publication prepared/sending/confirmed/held/unknown 与 request_key/receipt 处理继续复用。

### 既有约束

仅使用 DSH 公开 exports，不修改 DSH、不添第二执行循环；Task 业务状态只由真实业务操作改变。审批保持现有独立审查，无 blanket allow、无重放授权。配置映射属 feat-645。保留 main 其他任务的暂存文件，实施使用隔离 worktree。无客户端改动，不生成原型。

### 可复用能力

- 用：native `exec.deferContext` 在成功工具结果后注入收尾提醒；native inbox 合并、取消、flush、pre-step 最后一步保护；Task receipt、Schedule ownership 与真实下一触发时间；publication 状态确认。
- 改：已有 interrupted 屏障与拒绝记录的清除条件，区分错误来源、可确定的 Task 范围与未知会话范围；不添加持久调度系统。
- 不用：DSH goal pause 的业务 phase 修改、仅人类恢复、blocked 后禁止所有后续工具；这些不适合多 Task Global。

### 相关历史

feat-635 的设计已要求复用 DSH Goal 思路、waiting 用原生安排。现有提示把设计中的无预算约束直接写给模型，并泛化了 SingleThread 的 NO_REPLY。参考 DSH checkout `5badb15009ae1756c3afe0ae0cef1faafc290ccc` 的 goal-round-driver `prompt.ts` 与 tool-goal `wrapup.ts`：沿用检查当前事实、推进验证、成功状态变更后收尾，以及失败 disarm 而不伪造 phase 的原则。参考不是本仓自动生效契约。

## 架构总览

PA 仍产生完整责任快照 → integration 在原生边界注入任务引导 → 模型读取事实、推进/验证或建立 Schedule → IM 校验并提交 waiting → tool 的成功结果注入任务所属聊天收尾提醒 → Global send_message 实际交付。等待到期由原生 Schedule 进入同一会话，不新增 timer。

## 关键决策

1. **续跑提示以行为为核心，Global 不使用 NO_REPLY。** 保留全部 doing/waiting 的稳定标识、标题、聊天、入口、等待原因与复查信息，详情按需读取。要求当前工作区、工具结果与持久状态优先于旧叙述；推进、验证；完成需证据。移除模型提示中的预算宣言，代码仍不设 Task 回合上限。SingleThread 静默 sentinel 只在该模式原有交付场景使用；shared Skill 明确模式分支。

2. **等待前先重估阻塞，复查期限由任务决定但不超过一小时。** 先检查替代途径、可独立完成部分；涉及他人前置先确认请求已送达；创建有效 future Schedule 再写 waiting。到期重读状态、核实外部变化，并重新判断原阻塞是否仍必要；可做则 doing，否则续期。generic Schedule 仍可长期安排。IM 对新增/变更 waiting 校验 `0 < next_check_at - now <= 3600000`，同步提交再次检查；错误使用明确 `task_wait_schedule_too_late`，不改原图。无需迁移历史安排。

3. **成功 waiting 才注入反馈提醒，目标取服务端固定 conversation_id。** IM 在成功 apply 事务内为 changed node 的 waiting/in_review/done 生成 `result.feedback`（见接口段），随 mutation receipt 一起保存；integration 仅消费 `{ok:true,result.feedback}` 才 deferContext，不依赖额外 get 成功，也不从最近消息、human owner 或参数 target 推测目标。包含图/node、实际 wait 与 next_check_at，要求已完成、阻塞、尝试、所需协作者和检查时刻；相同内容已有 confirmed delivery 不重发。继续其他责任；保留原生最终工具结果后的步骤。in_review/done 也提醒把结果交付到固定聊天。无新增自动发言旁路，发送继续审批与复核。

4. **运行状态与业务状态分离；新输入可处理不等于自动重试获准。** 参数、版本冲突、`{ok:false}` 业务校验返回模型修复，不能一律 disarm。flush/snapshot/agent 错误复用 interrupted 停止无意义自动重复，业务状态不变。配置修复、Task 数据源恢复的变更提示或一次真实成功的新输入轮次可重新评估运行错误。拒绝记录不因 ordinary input、heartbeat、同名不同动作成功清空；记录精确动作与拒绝时责任，而非只记 tool name。成功执行同一动作或相关责任有实质变化才解除对应阻挡，所有执行仍经过独立审批。

5. **以真实可知范围限制自动重复，不伪造动作归属。** Task 工具操作能以 graph/node 定位时（包括 dependency from/to），只抑制受影响节点的无变化自动重试，其余 doing 可继续；delete 可覆盖未在快照展开的后代，按当前图责任批次抑制；普通工具无法可靠定位 Task 时采用会话当前责任批次屏障，允许新输入、当前轮合法替代/收尾和新增独立责任，不能猜测某个 Task。用于判断恢复的责任投影排除整图 revision（另一节点更新不算旧任务恢复），包括节点身份、status、wait、resume_request、title 和节点自己的 updated_at。IM 的节点 updated_at 随该节点实际修改更新，不沿用整图 updated_at；PA 保留这个已有字段，因此正文改变能触发重新评估，同图其他节点更新不能清掉旧屏障。恢复只是重新评估，不能视为审批授权。被抑制节点仍出现在责任提示中，明确不得重复原拒绝动作；它不等于 waiting、完成或授权。运行错误属于共享 session 时阻断该 session 的自动调度，不能宣称其他同 session 模型任务可独立运行。

6. **失败保留可核实状态与原有幂等机制。** Schedule 成功但 waiting apply 失败：读取真实状态、相同 request_key 重试未知写入，不盲建第二 Schedule；只清理本轮确定无引用且自己创建的安排。waiting 成功但 send 失败/未知：保留 waiting 与定时复查，按 publication 当前状态决定修复/重试，不能倒回 doing 以制造消息重发。Schedule 到期与安排失效 watcher 竞态继续通过 native inbox/pre-step 重读合并。明确停止/关闭永远优先。

审批误判的处理边界：本次保留拒绝和来源证据，不增加 task_graph 白名单、不降低共享资源规则。真实拒绝返回模型说明并寻找合法路径；不可执行时停止无效重试并交付阻塞。原始人类授权、Agent 派发、Task 控制、Schedule 唤醒分别保留来源，不把 task snapshot 提升成人类授权。分类器规则调整需要独立证据，不纳入本次。

## 真实验收发现的交付与停止接线补充

- SingleThread 共用的 conversation query 不应执行仅支持 Global 的 `agent.session.ensure`。只在 Global 注册工作主会话；SingleThread 查询仍由 IM 校验节点、Agent 与聊天成员权限，不新增豁免。
- `/stop` 目前暂停持久 Task 并保留原生 inbox，却没有将真人停止事实写入模型/审批证据；旧排队答复因晚处理而被误认为恢复。复用已有 `session.submit(mode=inject)`：在 pause receipt 确认之后、解除 stop fence 之前，以稳定 input ID 注入并 flush `task-human-control` 来源的停止通知，携带宿主已核实的操作者、原消息 ID/时间、作用范围与暂停数量。明确停止前已排队输入即使晚处理也不能恢复 paused Task，只有停止后新的明确真人恢复才可。暂停成功但通知失败则仍维持已有 stop pending/fence，重试同 receipt 与同 input ID；不新增调度器、状态表或删除无关排队消息。来源说明承认此受信控制事实，不把普通 system 文本提升为授权。仅 inject+flush 不等于模型已见：fence 期间若原生 pre-step 已领取普通输入与控制通知，reject 恢复时必须保留 task-human-control 的 next-step 语义（其余普通输入仍为 next-turn），确保解 fence 后首个模型步已同时看到停止事实；以原生队列竞态测试覆盖，不凭 accepted 标记推断可见。
- SingleThread 已确认通过 send_message 向本轮绑定聊天发送文字结果后，模型结尾的 NO_REPLY 应与已交付卡片一样被抑制，不能公开泄露哨兵或重复结果。使用实际 confirmed publication 的目标与 turn 关联；其他聊天、unknown/failed 发送和已有可见审批不能因此吞掉本聊天正文。Global 仍不使用 NO_REPLY。正常 SingleThread final prose 仍可直接交付。真实第二轮还确认 Task 分配/完成通知会产生独立原生轮次，不能跨轮复用旧送达标记：仅当该轮全部输入均为 IM 宿主 system 类型且现有 system_notice.kind=task_graph 时，沿既有自动轮次静默路径处理 NO_REPLY（无可见审批时），仍处理任务且允许有意义正文交付。RelayInput 仅声明当前线上已有的可选 system_notice.kind 字段，不新增线协议；真人或其他系统通知不因此获得该静默待遇。

## 接口与数据流

- `TaskResponsibility` 最小投影增加节点 `updated_at`，源为 IM 现有 list/execution 返回的该节点时间，PA 不再裁掉此字段；无需数据库迁移或正文加载。driver 私有状态保存拒绝 action key 与受影响责任投影（排除 graph revision），提示附受抑制任务标识。snapshot 仍完整，不隐藏责任或改写 status。分别覆盖同节点 description 修改与同图其他节点修改。
- `task_graph apply` 成功 result 增加可选 `feedback: {conversation_id, tasks: [{node_id,title,status,wait?,result?}]}`，只包含本次 changed_ids 中 waiting/in_review/done 节点，wait 为校验后实际持久值。IM 在事务中完成 wait 规范化后、保存 receipt 前生成；conversation_id 取持久图。反馈以同一 result.graph_id/revision 标明“该次提交时的事实”，不自称之后仍是最新状态。PA 沿现有包装透传，integration 只读 `ok === true` 且反馈非空才调用 deferContext。无需追加取证 get，因此读源故障不把已提交写入改判失败。若写入结果 unknown，根本不注入成功提醒，按原 request_key 核实；重放 receipt 返回相同投影，提示核对已确认交付而非再次发送。模型收到更晚状态变更时先重读，不依据旧提交事实重开工作。get/create 或无反馈字段不注入；测试覆盖子节点、跨聊天、失败/未知、重放与更晚状态。
- 在 IM `prepareWaits` 与 `execute` 的既有有效性检查中增加 one-hour cap。返回结构仍为标准 TaskGraphError；普通 schedule API 不改。
- 续跑/等待引导统一解释 Schedule 唤醒的重新评估义务，避免独立维护两套相反规则；shared interactive-ui 提示与生成 Skill 同步改写模式区分。

## 契约层增量 (delta-spec)

- Gateway Task: `specs/gateway/task-graphs.md` → `docs/specs/gateway/task-graphs.md`。
- Gateway Global: `specs/gateway/global-agent.md` → `docs/specs/gateway/global-agent.md`。
- 审核模型参数兼容性：`specs/gateway/agent-capabilities.md` → `docs/specs/gateway/agent-capabilities.md`，只记录同模型推理能力选择，不涉及 feat-645 的功能/工具开关。

## 风险与回退

模型仍可能不遵从行为提示，必须真实模型场景验收，不能靠精确文案断言放行。generic 动作归属无法可靠识别时采用会话批次抑制，保留新输入与当前轮处理能力。无新增存储迁移，回退代码不会损坏已存在 task/schedule/publication；不得回滚生产数据。本次不部署生产。

## Runbook for Reviewer

**Review 驱动方式**：端到端真栈；无客户端代码变化，使用 Web 客户端实际调用的认证、聊天消息、Task/Agent API 驱动，并读取同一聊天历史与任务结果；模型必须使用仓库 E2E 已配置的真实 provider，不用 fixture 冒充模型验收。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 本 unit 隔离 IM + Node/DSH | `./scripts/e2e-down.sh --wt "$WT_ROOT"` | `PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-up.sh --wt "$WT_ROOT" --main-config "$WT_ROOT/output/task-review.yaml"` | `.e2e-ports.env` 的 IM_URL 的认证 `/im/v1/agents`、Node online、真实聊天可响应 |

**验收前置**：caller 在 worktree output 生成仓库 E2E config 临时副本，为 e2e-global/e2e-peer 启用 task_graph、Cron 及对应工具（显式配齐以隔离 feat-645），保留独立 node identity/data/workspace/home；使用默认专用 nano/nano1234 测试用户。真实 provider 从仓库 catalog 的本地代理接入，先发隔离聊天确认可用；不可用如实报告 blocker。本地 workspace 临时文件模拟缺失后出现的外部条件；短 Schedule 由实际模型自行创建，超一小时边界由 Task API 使用真实 native Schedule 另测。模型仅操作隔离数据和临时文件，不外发到生产聊天。

必验旅程：同图两个任务、不同聊天最新输入；一个检查临时缺失文件后建立短 waiting 并反馈原聊天，另一个独立工作实际完成；外部创建文件但不发消息，Schedule 到期恢复并交付；提前答复恢复；仍缺失时重评估并续期不重复刷屏；实际 API 拒绝超时 waiting；Task 控制停止后旧 Schedule 不重开；普通参数错误可以修复。不可控模型/审批/持久化异常由 native driver 永久测试提供故障注入证据，产品 reviewer 检查真实链路的可观察停止/恢复与失败诚实性，不能只用 mock 代替正常旅程。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-continuation | Task 责任、等待与交付闭环 | 无 | 串行 | integration driver/task feature/interactive guidance，PA 快照字段与现有交付接线，IM waiting 校验及提交反馈投影，product-contracts 责任字段、提示生成源与产物，所属测试及 specs | [reviewer] incident 全部 Scenario 通过真实旅程及必要故障证据验证，原聊天等待/结果可见、独立工作完成、期限生效、无重复刷屏、停止有效；[worker] 有意义红测后窄测试绿，native 拒绝/普通输入/错误恢复和最终交付步骤保护、IM 首次/续期边界与原子性验证，完整构建/typecheck/CI、独立 code review/verifier、记录版本与隔离进程清理 |

## 用户复核续修：停止不唤醒与变更同步审计（2026-10-24）

本节替换上文“解除 stop fence 后主动处理旧输入”的实施语义，其余设计与 M1 范围保持。用户已明确批准延迟消费停止提醒，不新增 milestone。

- 删除 TaskExecutionDriver.block(false) 因 inbox 非空主动 followup 的逻辑。PA stop 仍先 block/cancel/drain/pause，inject 已核实控制通知并 flush 成功后解 block；解 block 只是允许以后有效触发，不自身触发模型。原生被拒绝步骤的恢复仍保持 task-human-control 为 next-step。停止确认由宿主发送，无需模型。
- 保留停止处理中被挡住的普通输入与 Schedule。它们没有丢失，但不能仅因队列非空立即执行；停止完成后新消息/Schedule/真实责任变化带来的正常唤醒会一并消费。停止不是永久禁用 Agent，暂停 Task 的恢复仍需明确恢复事实。
- poke 的正常 idle 调度仍让位原生待处理输入；对 changed(..., reconsider=true) 的真实责任重新评估，允许在队列含停止通知时读取当前责任。仅当仍有 runnable 且通过现有 cancelled/denial 判断才 followup，防止明确页面恢复被 inject 阻塞；纯暂停/删除的 quiescent 与无变化 cancelled 责任不唤醒。
- agent/pre-step 冷恢复时，即使 state.shown 不存在且最新责任为空，普通新输入也附当前完整责任快照；已知旧责任变化继续发送 delta。原生历史不是最新任务事实；不恢复所有已结束任务的详情推送。
- 群解散直接写任务 JSON 的路径，在事务提交后向这些图的负责人复用 TaskGraphService.notifyChange，不生成新的聊天 Task 通知。原有普通 API/Agent/PA 提交后通知、改派前后负责人并集与 reconnect 重新读取继续复用。
- 审计记录入口、提交后通知、负责人范围、运行中下一步与空闲后续读取证据。不把仅存在通知回调当作模型已见：native 请求内容与真实产品运行状态分别验收。

验证：rewrite-merge 现有原生 stop fence 测试，检查解除后零模型调用、停止通知持久恢复、后续新输入首步可见；单独覆盖页面恢复与冷恢复空责任。IM 在现有 task-execution 测试保护修改/改派/删除及群解散的提交后通知。产品复验 stop 完成后 idle/请求计数不增长，后续普通问题正常、旧答复不恢复、页面恢复可继续；Task 外部修改在运行中下一步可见。Global 非空内部收尾、SingleThread 静默、既有 waiting 一小时和交付契约保持有效。

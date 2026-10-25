# Code Review — feat-659 Agent Context Engineering

## Snapshot 与结论

- reviewer: `/root/final_review`；未参与受审实现。同一独立 reviewer 按派发兼任 verifier，分别保留报告。
- review_mode: `full`；2026-10-25。
- executed_base / effective_base: `b4ea8f908691d6a309ceb787d4d37d36ec7dfc69`。
- validated_at / effective_through: `572d336a5b721c221a844bf20e7841d785295a89`。
- 范围：上述完整 diff 的 19 个文件（300 additions / 1 deletion），以及 spec、design（含唯一 M1）、design-review、user-request。执行时 HEAD 与固定版本相同；无产品源码、测试、依赖、协议或权限行为改动。
- 方法：实际使用 change-code-review、agent-context-review 的两模式；追读受影响消费链及 current specs，直接复核指定本机请求/结果，复用仍适用测试。仅写审查报告，不修改受审对象、不新增角色/Gate、不启动服务。

**PASS：受审 diff 无存活 finding，0 CRITICAL / 0 WARNING。**

```json
[]
```

此结论是固定版本的独立代码审查；不表示远端 CI 已通过。新增的 validation.md 是主作者在审查期间提供的本地运行记录，不算作冻结实现的代码增量。

## 发现机制与实现审查

先从 AGENTS → development/README → 唯一通用规范追踪发现入口，再核七角色的调用、报告归属、证据要求及例外，最后将规范的声明与真实消费链对照。`agent-context-engineering.md:7-98` 覆盖八类 Surface、完整生命周期与组合关系，按实际影响触发；五组原则明确宿主派生身份、来源/权限、未知结果及更新/恢复。Skill 的 description 包含适用任务和不触发范围，正文 28 行将两模式及 finding 字段保留在程序层，细则回链规范和观测操作。没有复制 current 产品契约、强制全 Surface checklist 或另建 Snapshot。

七个 change-* SKILL.md 的新增规则与 design 模板、workflow:86-92 一致：design-author 在原设计/milestone 对齐，原 design-reviewer 执行 Mode A，worker 与两个编排路径检查实际交付，原 code reviewer 执行 Mode B，verifier 核一致性并复用。Full/lite/快速开发与直接小修的原职责和门禁不变。特别检查默认 simple 直接实施路径已覆盖，未只覆盖条件派发的 worker。

`llm-integration.md:30-88` 将 preview、适配前 llm/stream、代理入口、转换后 provider payload 和行为分开；其结构检查命令不输出正文，观测路径可由本轮实际日志验证。两份 README、AGENTS、coding-guidelines、documentation-system、testing 均指向同一权威。全文 diff 未包含原始请求、私人对话、配置或运行产物。

## Mode A 实际试用：假设设计输入

本节是按派发执行的新 Skill **Design Review 方法演练**，用于检验新程序能否识别实施前的接口设计缺陷；沿用本报告，不重开 Gate 2。它不是当前 nano 产品 bug，也不进入上面的存活代码 finding 数组。

输入：拟设计 `transfer_task(owner_id, task_id)`；`owner_id` 必填，真实 owner 仅在宿主会话对象，无发现接口；正常任务说明只给 `task_id`。

| 字段 | 独立输出 |
|---|---|
| 位置 | 本节假设设计的 `transfer_task.parameters.owner_id`；规则依据 `agent-context-engineering.md:21` |
| Surface | Tool Definition / 参数来源及可信身份边界 |
| expected | Agent 凭正常任务和可获得信息转交指定 task，宿主保证当前 owner 真实归属 |
| observed | Schema 强制模型提供 owner_id，却既未提供该值，也无可查询通路 |
| failure_scenario | 合法任务只有 task_id；模型无法可靠构造合法调用，只能停下询问或猜 ID。类型合法与执行成功不证明该输入可可靠取得 |
| impact | 拟议任务无法自主完成；若执行层信任所填 owner，还可能选错作用域，但未给执行层设计，不能确认越权 |
| recommendation | 从可信会话派生 owner 并从模型必填参数移除；若需选择目标 owner，另提供有权限的发现/消歧入口，不能让当前 owner 身份靠猜测 |
| severity / status | WARNING / CONFIRMED：确认的是给定前提下的信息通路缺失；不是已观测模型误填或已发生越权 |
| evidence / limit | 派发的完整假设输入；没有真实实现或模型运行。修订后应核最终 schema 和宿主绑定，再用只含 task_id 的正常任务验证 |

非触发输入：仅调整 Web 工具卡片 padding/color，无模型投影、字段、语义或生命周期变化，**不需要完整 Context Review**，仍走适用的普通前端审查。依据是已限定的实际影响，不是 frontend 文件名；若共享 renderer/序列化同时改变才重新判断。该输入未制造无关 CSS 修改。

## Mode B 实际试用：独立复核 A/B/C

本 unit 改变的是开发 Agent 的规范/Skill 消费路径，因此触发本方法。A/B/C 是方法试运行，并非本 unit 新增的产品功能。先核真实拥有者与 current specs，再读取以下本机原件的相关字段；没有仅以链接存在、UI 卡片或文件名作证。

证据基线为 `93d1c3b01a8e3b39dbff84546482761b4d1e8a5d`，与固定 HEAD 的产品源码相同。环境为隔离 daily 真 IM/Node/锁定 DSH，模型 `codexOAuth:gpt-6.1-sol/high`。主 session `d48f723e-95be-4a9b-8533-2f0fcb4ec69d`；代理 session 目录前缀 `2026-10-25_20-13-25_748`。逐一核对 10 份入口请求及 `logs/raw/openai_codex/` 同时间戳 upstream payload：system 与 `input[0].content` 相同，所有 tool_result 与对应 function_call_output 的 ID/正文一致。不能只搜索 upstream instructions。

### A — 工具定义、sent 与 unknown

- 代码：`packages/dsh-integration/src/global-mode.ts:27-43` 的描述区分 public target/text 与内部 agent_id/message acceptance，`output.render` 序列化真实结果；`packages/personal-assistant/src/global-agent.ts:565-610` 区分 held、真实 sent、unknown 和查询核实。模型无需填 owner。
- `20-13-58_020` 和 `20-14-31_355` 请求中的上一 send 结果是 sent。独立与仓外 enabled/disabled-messages.json 对账，同 message_id/正文真实存在；enabled/disabled-work.json 的相应 turn completed，后续没有重复公开 send。因此本例支持 sent 内容交付、后续模型正确收尾及 IM 产品事实三层结论，不泛指任意工具成功等于任务完成。
- 补充 session `ac659-task-outcome-20261025`，目录前缀 `2026-10-25_20-18-59_387`：直接核 `native-unknown/result.json` 的事件 17/22/25，以及 `20-19-29_904` / `20-19-38_559` 的入口和 upstream。第一次结果为 write_outcome_unknown，第二次 confirmed；两次 apply 的全部参数（包括 request_key）相同，模型只在确认后报告保存及 revision 2。`features/task-graphs.ts:25-43` 的真实 output.render 与确认后 feedback 条件、task-feedback 测试支持其接线。
- unknown 的宿主 product.call 是**受控夹具**，模型与 DSH 是真实运行；不是真网络故障，不证明 IM 写入幂等、真实故障恢复或公开消息送达。真实 held、内部 acceptance、拒绝/权限分支仅有代码与已运行 fixture 支持；本轮没有这些分支的真实模型验收。

### B — Inbox 来源和交付时点

- 代码：PA `global-agent.ts:212` 的 wake 不含正文且不是授权；`inbox.ts:248-268` 投影发送者/时间/正文，`:322` 在精确持久内容匹配后消费；integration `global-mode.ts:44-62` admission/prepare；`policy/sources.ts:8` 明确来源/历史不升级授权，`tool-references.ts:71-77` 使用宿主 Agent 作用域解析引用。
- 首请求的 wake 以 user role 传输，但正文明确不是 permission，system 也解释来源；本轮任务正文未提前出现。`20-13-29_240` 才见 check 的来源/未读数，`20-13-34_868` 才见 read 的真人 ID/type/name/time/正文；随后 skill → conversation info → send，回复 target 来自同一 Inbox 结果。
- Work 的 `payload.work_facts[type=inbox_read_committed]` 保留同输入 message_id/complete_message（enabled seq 12、disabled seq 33），不是把 UI 预览当持久摄取。证明这两次单真人直聊的顺序和来源保真；多用户混合来源、PA observer、群聊授权与忙碌插话的真实模型行为未重演。inbox/global-agent/knowledge 等 fixture 只补确定性边界，不升级为攻击或权限验收。

### C — Prompt / Skill / 配置

- 代码：`agent-config.ts:113-123` 按当前 Feature 过滤稳定 section/context；`capabilities.ts:133-156` 同时过滤 Skill list/get；`features/intelligent-ui.ts:6-16` 是相关指导拥有者。current agent-capabilities 的 Feature 与工具独立契约允许指导关闭而已选工具保留。
- 前 6 次 system 为 10014 字符，Feature 指导一次；第一次动态目录仅两项元数据，没有试点正文。真实 skill 调用后 `20-13-41_183` 才出现正文/资源根，随后生成正确合计 54 并交付。
- 后 4 次 system 为 7489 字符，Feature 指导零次；新空目录明确替换旧目录，禁止用旧目录名。未新增 skill 调用/正文，普通加法结果 9。两阶段工具列表相同的 9 项符合独立选择；旧 skill_content 作为历史保留不是再次注入。
- 支持本任务中的发现→加载→消费与关闭更新；用户显式命名了试点 Skill，不能据此声称未命名任务的自动发现率或所有 Skill/开关组合可靠。没有真实测试关闭后的显式非法加载；已运行 capabilities/native-human-source fixture 提供该接线边界。

### 范围限制与停止条件

Memory、History/Compaction 仅复用 knowledge、agent-context-default、Inbox restart 等已有测试及相关代码；**没有真实压缩/换窗、跨窗长期等待状态或真实 Memory 注入行为试点**。这不构成本次方法规范的缺实现，不能据此宣称相关产品行为已验收。具体证据摘要见 [context-pilots](M1-context-engineering/evidence/context-pilots.md)，私有原件仍在仓外。未发现需要新增观测能力的实际盲区。

复核范围已覆盖需求与 design-review R1-R1 建议的两模式及非触发例。没有在当前 diff 发现可举证的设计冲突、接口退化或隐私入库问题；停止审查，不为数量追加假想 finding。复用测试及交付待办见 [verification](verification.md)。

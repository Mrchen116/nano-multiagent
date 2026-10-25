# Context Review 方法试运行

## Baseline、环境与证据边界

2026-10-25，`unit/feat-659@93d1c3b01a8e3b39dbff84546482761b4d1e8a5d`；运行时代码与设计调查基线一致，本 unit 仅改开发文档/Skill。Node 24.22.1、pnpm 11.7.0、锁定 DSH 0.2.1-alpha.1 / dsh-agent-context 0.3.0-rc.5。本机默认 Node 25 不满足 engines，显式使用临时 npm Node 24 工具链。

使用 `scripts/e2e-up.sh --profile daily --wt <unit worktree>` 创建隔离真 IM/Node/DSH、owner、workspace 与身份。调用与 Web 相同的 IM API（复用 `tests/e2e/critical_paths/_im_client.py`），未使用生产身份/聊天。目标 `daily-engineering`，模型 `codexOAuth:gpt-6.1-sol/high`，保留日常 Codex 审核设置。请求消费是真模型，不是预录响应。

场景增量：在 E 独立 workspace 添加合成 `context-pilot` Skill，元数据说明订单核对用途，正文规则为每笔减 2、给原始/折扣合计与笔数，并含规则标记 `AC659_RULE_V1`。第一轮显式启用该 Skill 与 nano-interactive-ui、intelligent_ui；关闭其余自动 Feature，工具选择仅保留通信与 Skill（原生基础工具仍按产品固定能力存在）。不修改受版本控制的运行配置。

第一次用户任务只给目标、订单金额 10/20/30 和 Skill 名，不给工具调用、计算结果或隐藏身份。第二次空闲后关闭 intelligent_ui、清空 Skill allowlist，询问普通加法 4+5。两轮均要求只回最终文字，无需确认/过程消息。两轮模型都实际读 Inbox 再向来源聊天交付，分别为原始 60/折扣 54/3 笔和 9。

本机原件：`/Users/czj/.codex/reports/nano-context-engineering-20261025/` 中 pilot-summary、enabled/disabled-work/messages；原始模型请求在代理日志。只提交本文的小型脱敏结论，原件含运行数据不入 Git。临时驱动脚本不作为永久回归。

- 主 session：`d48f723e-95be-4a9b-8533-2f0fcb4ec69d`。
- 代理目录后缀：`2026-10-25_20-13-25_748_<session>`。
- 入口请求：该目录 `*-req-anthropic_messages.json`；共 10 次主模型请求。
- 转换后 provider payload：`logs/raw/openai_codex/<同时间戳>-upstream-req-anthropic_messages.json`。
- 入口的 system 映射到 Responses payload 的 `input[0]` system 消息；`instructions` 另有简短协议指令。已逐轮核对，不能仅搜索 instructions 判定指导丢失。
- 公共回复在 IM 历史与同 ID 的 tool result 中对账，两个 Work turn 均 completed。

## A — Tool Definitions / Tool Results

触发依据：send_message 的定义、序列化结果与后续决策共同决定 Global Agent 是否正确结束交付。审查位置为 integration `global-mode.ts::apply`、PA `global-agent.ts::send/confirmPublication` 与当前路由契约。

**实际模型输入与行为：** 第一轮 `20-13-58_020` 请求包含 send_message 的实际 Schema 和上一调用的结果 `{status:sent,target:<本次来源聊天>,message_id:<真实消息ID>}`；上游同时间戳 payload 中对应 function_call_output 保留此结果。此前调用的 target 来自 Inbox 返回，结果正文来自已加载 Skill，模型没有被要求填写宿主 owner。IM 历史中确有相同消息，模型随后仅私有收尾，没有重复公开发送；第二轮 `20-14-31_355` 同样对账。

**静态与确定性运行补充：** Schema 描述区分 target/text 的 public delivery 与 agent_id/message 的 native acceptance；Global Prompt 区分 held 与 sent，PA held 分支明确未发送及读取新消息后以新调用重审。`global-agent.test.ts` 的同聊天更正/hold、冷启动不确定投递查状态而不重发案例，以及 `communication-native.test.ts`、`task-feedback.test.ts` 全部纳入本轮已通过的窄回归。task-feedback 用受控 unknown 结果与同 key 重试验证未确认时不注入成功反馈，确认后按 Feature 只注入一次；这些是 fixture 行为，不是真模型拒绝/未知分支验收。

结论：本次真实 sent 路径没有发现 Context 缺陷，有交付内容、行为与产品事实三层证据。不能据此宣称真实模型在 held、内部 acceptance、传输失败或 unknown 下均正确；这些状态的本轮证据层级如上，工具成功也不泛指整个用户目标完成。

## B — Runtime Injection / IM

触发依据：同一个 Global 主会话先接收 system wake，随后自行获取真人消息；若丢失来源或把 wake 当授权，会改变任务处理。审查位置为 PA `global-agent.ts::wakeInput/call`、`inbox.ts::read/commitRead`、`tool-references.ts`，integration `global-mode.ts` 与 `policy/sources.ts`。

**实际模型输入与行为：** 首请求 `20-13-25_748` 只有 Inbox 唤醒文本及运行快照/Skill 目录，没有订单任务正文；唤醒明确不是 user permission。源消息通过原生 user role 传输，但 system 来源指导明确禁止将 wake/Agent/引用等提升为真人授权。下一请求 `20-13-29_240` 的 check 结果只有来源名/target/未读数；`20-13-34_868` 才包含 read 后的真实发送者 type=user、稳定 ID、名字、UTC 时间与正文。顺序为 wake → check → read → 加载 Skill → 查询会话 → send。后续 read 的正文与输入消息 ID 一致，Work 留有 inbox_read_committed 事实；模型回复目标来自同一条来源链。

**静态与确定性运行补充：** 来源规则同时供主模型与审批；`knowledge.test.ts` 的 live human Inbox Skill 案例包含 Agent/system 来源不触发及裁剪后不重复，`inbox.test.ts` 覆盖部分读取/图片缺失不消费与重启，`global-agent.test.ts` 覆盖 busy 期间新通知、PA 观察来源与恢复。不是根据 role=user 或字段存在单独判断授权。

结论：本次单真人直聊来源/注入时序没有发现缺陷。混合真人/Agent、PA observer、群聊授权与忙碌插话的真实模型行为未在这两轮重演，相关本轮支持来自静态与已运行 fixture；不将这些扩大为真实多用户攻击或权限验收。

## C — System Prompt / Skill / 配置交互

触发依据：开关影响最终稳定指令、动态目录、正文加载与历史保留，单看 config 保存成功不够。审查位置为 `agent-config.ts`、`capabilities.ts`、`features/intelligent-ui.ts` 与 DSH 原生 Skill 组装。

**实际模型输入与行为：** 启用时 6 次请求的 system 长度为 10014 字符，Feature 指导开头 `Choose the response form` 仅出现一次，身份及 Inbox 来源规则各出现一次。第一请求动态目录列出两个选中 Skill，未加载试点规则正文；模型实际调用 skill(name=context-pilot)，`20-13-41_183` 请求才出现带资源根与规则的 skill_content；随后算出 54。

关闭后下一新回复从 `20-14-11_188` 起共 4 次请求，system 长度 7489，Feature 指导为 0 次，身份/来源规则各仍 1 次。动态消息明确新空目录替换此前所有目录、不可使用旧目录名字。上游 input 中的 system 同样变化；第二轮没有新 skill 调用或新 skill_content，回答 9。已有第一轮正文仍作为历史存在，这符合连续会话，不误报成新注入残留。

实际工具列表两轮均为 9 个：conversations/get_context_remaining/history/inbox/new_context/notes/send_message/skill/subagent。工具显式选择与 Feature/Skill 选择分开：关闭指导并未擅自删除仍选中的 skill 或公共通信能力。send_message 描述仍有“when Feature enabled”的条件句，不是无条件继续开启。

结论：本次相关指导没有重复或关闭后再次注入，Skill 发现/实际加载/消费与配置一致。没有把 UI preview 当最终输入，也没有要求删除旧历史。此单任务不能证明所有 Skill 的自动触发质量；禁用后的显式调用拒绝另由已运行 native-human-source/capabilities fixture 支持。

## 不触发反例

只修改 Web 工具卡片的 CSS 间距/字体，且 `tool-presentation.ts` 的展示与 `output.render` 模型链路均无变化：无 LLM 输入或生命周期影响，按普通前端审查，不做完整 Context Review。若同一变更改共享序列化或 renderer 供模型使用，则重新判断影响；不因目录是 frontend 就豁免。该反例是方法演练，不为证明跳过而实际制造无关 CSS diff。

## Memory / History 的补充范围

本次复用了 agent-context-default、knowledge、Inbox restart 等窄测试，确认默认 context 工具、Feature/Skill 与来源恢复相关确定性机制。没有主动触发真实模型的换窗/压缩，也没有实测长期等待事项恢复；不将上述测试升级为该行为通过。规范覆盖这些 Surface，未来相关 diff 仍需按真实启用的 engine 补证。

## 方法效果与发现范围

上述三例由主实施者按新 Skill 的 Implementation 方法进行自检，不冒充独立门禁；最终由现有独立静态 reviewer 用同一 Skill 复核，并在原门禁报告记录 Design 模式与非触发输入的试运行。没有在本 unit 修改产品代码；本次已确认的开发方法缺口是原联调文档未区分代理入口与转换后 provider 请求，已在 llm-integration 就地修正，未另建观测平台。

## A 的真实模型 unknown 恢复补充

为验证失败语义消费，复用 task-feedback 的 product.call seam，启动独立 RuntimeClient、真实锁定 DSH 与真实 `codexOAuth:gpt-6.1-sol`，工具定义/序列化不改。仅启用 task_graph（task Feature 关闭，避免自动任务推进）；工具权限跳过仅用于无外部副作用的独立夹具，不能当生产审批验证。

合成用户提供其已知的 graph、revision、child 与核对结果 54，要求记录完成并说明是否确认；没有提供 request_key、操作 JSON、重试要求或预期回复。product.call 第一次 apply 返回现有 fixture 的 `ok:false / write_outcome_unknown` 和相同请求身份核实提示，第二次返回 `ok:true / revision:2 / changed_ids:[child]`。服务端是夹具，模型响应不是夹具。

结果：模型实际执行两次 apply，request_key 与所有参数逐项相同；收到确认后才输出已保存、child 完成及 revision 2。没有把第一次未知当成成功。已核入口与上游请求：session `ac659-task-outcome-20261025`，目录前缀 `2026-10-25_20-18-59_387`；`20-19-29_904` 是未知结果后的请求，`20-19-38_559` 包含第二次确认；两份上游 payload 均保留相应结果。本机 `native-unknown/result.json` 保留原生事件和调用。

本证据确认该模型在这一受控 unknown → confirmed 路径的参数/状态消费；不能证明 IM 写入幂等、真实网络故障恢复或消息送达。既有 task-feedback 窄回归承担其受控接线，不增加一次性永久测试。

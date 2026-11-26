# feat-797 外部 Worker 权限审批设计

## 现状与决定

Global/PA 的 delegate_worker 启动独立子进程，根 turn 可先于 Worker 结束。DSH 公开 approval.request 只允许开放的根 turn，其自动审批和阶段审计仍服务原生调用。外部审批复用 integration 的 pending 请求、独立 approval.answer RPC、超时和完成通知；直接从绑定的 Worker 进入宿主，避免伪造 DSH turn 或 tool/call。

## 协议与生命周期

LocalWorkers 在派工时从真实 root 和 worker record 取得来源与值守状态；有人输入或真实聊天 Inbox 唤醒为 interactive，schedule、heartbeat、proactive 等自主来源优先判 unattended，未辨识来源从严。值守状态属于具体委派/激活，后台延迟请求不因无关根 turn 而改道；后续 send 不可把正在执行的请求升级。重启不恢复 pending。每个 CLI request 的答复闭包绑定进程、session、turn、原生 request ID 与冻结的参数，独立 AbortSignal 在请求撤回、turn end、stop、close、exit 时失效。不同 ID 可并发，禁止跨会话匹配；await 期间接收循环继续处理。超时由 askTimeoutSec 限制。取消、拒绝、超时均有协议原生终局，迟答不重新启动进程。

Codex 保留 auto_review；仅在具体 command/file/legacy 单次决策可用且动作参数可识别时提交。通用 permissions、持久授权选项、缺少目标或不支持的决策从严返回。Claude 保留 auto；can_use_tool 原输入原样放行一次，AskUserQuestion 与 elicitation 单独取消并回报。ACP 根据当前 session 内同一 toolCallId 合并权限帧和已观察的原始参数；interaction_* 转交提问，普通权限只选 allow_once。终局 Auto denial 仅作报告。三个驱动按同一宿主私有 MCP 配置（server、启动配置、宿主门控的精确工具名）生成各自的免重复拦截配置；未注册服务、近似标题或输入自报身份不能免审。首个绑定仅 nano-parent.send_message。保留已有 CLI 确实只提供内置固定格式标题的兼容形态，冲突信号一律从严。

AGY 以独立 Worker 动作名称与完整参数调用 NanoApproval 的既有审查策略一次，禁止误用原生工具同名快速通道。Agent 配置、策略、审核模型、宿主确认的原始人类消息/Inbox、模型不可用与拒绝计数沿用既有机制。CC 的策略内部阶段与 Codex 的证据检查属于一次策略决策。明确 deny 直接拒绝；ask 转发人工或无人值守 fallback。Codex/Claude 冒泡直接进入 ask 分支。审核证据从绑定 root 取得，Worker 任务文本、理由和参数属于待审内容；宿主身份独立封装。模型审查期间人类证据变化使旧结果失效。Auto 未启用时请求人工；配置缺失或无法匹配实际请求时安全拒绝。

每个外部进程激活时记录派工根 turn、派工调用和当时宿主读到的真实人类指令（含 Inbox 的发送者、目标、消息 ID）；只把属于派工现场的原话作为该委派的正向授权，派工文本自身是 Agent 转述。AGY 审核动作带该只读快照。同时提供所属根最新的人类限制上下文，后到的其它聊天不能增加原委派授权；新证据不足以区分作用域时转人工或安全拒绝。决策返回和审计写入之后校验人类证据仍有效。用先在甲派工、再读乙聊天、最后 Worker 请求的 fixture 检查实际出站审核输入及更新期间的决策失效。

## 主人私聊卡

Node 按 root binding 转交带 Worker 身份的 approval.request，不依赖未完成根 turn 的聊天输出。由 IM 在已认证 node/Agent/lifecycle 下为单次请求创建独立消息，按服务端 PA binding 或普通 Global 的 ownerAccount 确定真实用户并解析双方私聊。沿用现有 permission_request 的历史、事件、Web/iOS 展示与答卡入口。Worker 卡仅接受 allow_once/deny；答卡重新核实真实 owner、私聊、原卡/request、epoch、revision 和时限。不会接受来自 Worker 或父级的收件人、跨聊天的消息 ID 或决定。请求身份用于幂等，发布中途已取消仍要核销已发出的卡，发送失败终结请求。进程丢失后旧 RPC 消失，服务端到期拒收并使等待状态可收敛。Web/iOS 使用原有卡，question 显示来源与可读动作摘要，tool_input 提供具体结构化目标；文件内容和原始 stdout 不进入卡面。独立消息使用已完成的消息载体，审批等待由 permission 状态表示。结案时以 resolved 收起操作，并将 Worker、动作和实际终态写入同一消息的正文，Web 刷新后与 iOS 均能辨认。服务端以原 request_id 去重并按 expires_at 清理失联待决卡。飞书触发的 Worker 卡和终态同样只到主人 Nano IM 私聊，外部 chat 与 shadow 都不接收。无需界面原型或一次性迁移。

## 契约与验收

- [Gateway delta](specs/gateway/tool-approval.md) 归并到同路径 canonical。普通 DSH Global/child 不弹卡的条款仍仅覆盖原生工具。
- [IM delta](specs/im/conversations-messages.md) 归并到 conversations-messages。Work 可观察权限不授予执行权限。
- [外部渠道 delta](specs/gateway/external-channels.md) 为飞书原聊天审批加上 Worker 私聊例外。
- M1 单一交付，验证可按独立的 CLI 协议、产品卡投递、IM 身份边界并行准备。交付前用独立代码审查核对从 driver 到主人决定的完整调用链、父级 Context 和审核次数。
- Runbook：本机 Node 24.22.1、pnpm frozen install，构建 product-contracts 和 dsh-integration。Vitest 使用真实本机子进程的协议 fixture，真实 IM 应用和隔离临时 SQLite 验证卡历史与授权 HTTP 路由；产品接线以同一类型和请求身份贯穿。复用 Web/iOS 原生审批卡的既有展示并核验 question 和输入。需要手工联调可使用 scripts/e2e-up.sh --wt "$PWD" 及 scripts/e2e-down.sh --wt "$PWD"。回退为恢复旧驱动拒绝，已有卡不授予后续调用权限。

| ID | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|
| M1-worker-approval | 无 | G1 | dsh-integration、product-contracts、personal-assistant、IM server 及相关测试 | [reviewer] 人工卡只有主人可读写其决定且附来源与动作；一次放行、拒绝/迟答、无人值守和提问照 spec。 [worker] 三种 CLI 的真实 stdio 帧、审核判定次数、停止/取消、私聊收件/答卡与结果传回均有可重复证据。核验 A/B 聊天授权与撤回的模型输入、飞书来源隔离、代表性客户端答卡和取消后重读的终态。 |

# feat-797 · 外部 CLI Worker 的提权审批桥

## 原始需求（摘录）

> 打通外部 CLI Worker 的提权审批桥（切法 A，零双审）
>
> 业务提问与澄清类（`requestUserInput` / `AskUserQuestion` / `interaction_*` 选择题）——保持现状，先过主 Agent
>
> 工具与安全提权类（`requestApproval` / `can_use_tool` / `session/request_permission` 等权限请求）——禁止主 Agent 代批，按运行时单次分流后直达人类审批卡
>
> 保持 `nano-parent` 免 CLI 拦截，并为后续宿主自托管且由宿主自身做单次门控的 MCP 预留干净的免 CLI 重复拦截配置扩展点

## 待确认的产品决定

Global/PA 根会话服务多个聊天。需要确定审批卡的接收位置，因为卡上的真实命令和目标路径会对接收聊天的可读成员可见。建议由绑定根会话的 Agent 发到其与主人的 Nano IM 私聊，仅由主人答复；另一方案是发回触发委派的原聊天，仅开放主人操作。选定收件范围后定稿并进入设计审查。

## 已确认的使用场景

用户交办工作后，Worker 有时需要询问交付格式，有时需要修改工作区外的具体文件。前一个问题由父 Agent 利用上下文继续处理。后一个动作必须经过对应的权限决策，用户能看到由哪个 Worker 提出、会影响什么、为何需要权限，并能单独拒绝它。定时工作在无人值守时也能得出明确结果。

### Requirement: 根会话接收业务问题

#### Scenario: Worker 需要用户选择
- **WHEN** Codex、Claude 或 Antigravity 提交选择题或交互澄清
- **THEN** 结束原交互，向绑定的父 Agent 转交问题和可用选项。父级可补充信息续做。

### Requirement: 对具体动作只作一次自动审批决策

#### Scenario: 有人值守的权限升级
- **WHEN** Codex 或 Claude 内置 Auto 将一项具体动作升级给宿主
- **THEN** 人类审批卡标明 Worker 标签、运行时、ID 和来自实际请求的命令、路径或权限摘要。批准只允许这一调用。拒绝或超时使该动作停止，父级收到原因。

#### Scenario: Antigravity 无内置审核
- **WHEN** Antigravity 请求某项工具权限
- **THEN** 按所属根会话的既有 Auto 策略和原始人类证据作一次决策。放行仅适用于当前动作，需人工时走同一张卡，明确阻断时向父级说明。

#### Scenario: 无人值守、终局拒绝与中断
- **WHEN** 定时或 heartbeat 委派需要新权限
- **THEN** 采用所属 Agent 的无人值守策略并向父级报告结果，不留下待人点击的卡。
- **WHEN** Worker 已被内置 Auto 明确拒绝、已停止、对应请求已取消或进程退出
- **THEN** 后续回复或旧卡均不能使这次调用执行。

#### Scenario: 宿主托管的内部通信
- **WHEN** Worker 通过绑定的 nano-parent 向原父级汇报
- **THEN** 消息直接返回父级，其他工具不能凭报告正文或类似名称获取该权限。

## 调研依据与实施边界

基线 `bf20e1da2`。当前 [Gateway 审批契约](../../specs/gateway/tool-approval.md) 和三套 CLI 驱动会关闭待定 RPC；父级收到来源为 worker-report 的内部消息。Global/PA 的 Inbox 唤醒是系统事件，原生 DSH 人工审批需要开放中的 turn。IM 目前只接受单线程 Agent 的聊天审批。外部 Worker 可在根 turn 结束后继续工作。

Linger 的 task-delegation 和 permissionreview/service.go 展示另一种按 context 与精确 action digest 核销重试的做法。这里优先使用活的单次 RPC。Codex 通用 permissions 请求仅支持 turn/session 范围，因此返回空授权并指明应提出具体动作；ACP 没有 allow_once 选项时同样关闭请求。浏览器和桌面 MCP 实现由独立单元处理。

实测基线：Node 24.22.1 下构建 product-contracts 后，运行 local-worker-drivers、local-worker-antigravity 和 local-worker-conformance 三套现有测试，共 15 项通过。这些是协议 fixture 的旧行为。安装的 Codex 0.171.0 通过 `codex app-server generate-ts --experimental` 导出的 PermissionGrantScope 只有 turn 和 session；命令及文件审批另有独立的单次 accept。Claude Code 版本 2.1.325，Antigravity 版本 1.5.18。

生产接线：
- [根会话 Inbox 唤醒](../../../packages/personal-assistant/src/global-agent.ts)使用系统来源 inbox；[原生审批接线](../../../packages/dsh-integration/src/index.ts)拒绝 Global 的原生工具审批。
- [IM 建卡](../../../apps/im-server/src/chat-streaming.ts)和[用户答卡](../../../apps/im-server/src/conversation-actions.ts)均检查 Agent 工作模式。投递目的地与答卡身份需要分别校验。
- [Web 聊天](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx)和 [iOS 消息视图](../../../src/IM/ios/NanoIM/Features/Chat/ChatMessageView.swift)已有 permission_requests 展示入口。

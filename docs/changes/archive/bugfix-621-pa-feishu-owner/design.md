# bugfix-621: PA 飞书主人私聊与提醒恢复 — 技术方案

> 对齐 incident.md，代码基线 0fa706a67。

## Changelog

## 现状分析

### 涉及范围

IM personal-agent 管理来源和原始授权；personal-actions 冻结对外披露；Gateway/messaging 限制 PA 写入；PA external 持有可信 SDK 输入、真实 chatId 和输出回执；GlobalAgent 将来源进入同一个 Inbox/主会话。

### 既有约束

不改变 DSH 边界，不新增执行循环。保留首发送者绑定，不新增确认流程。隔离端口、数据、workspace、node identity 和专用飞书 Bot。无客户端界面修改。

### 可复用能力

复用 agent_channels 中 app_id/owner_open_id、conversations 的 provider/source/type/config_agent_id、原始 messages.sender_source_id；复用 pa_source_events 的持久接入与去重、ExternalStore 的真实目标和输出状态；复用现有一次性 schedule 与独立审查。普通工具权限维持原路径。

### 相关历史

feat-616 建立 PA 私密边界及 observation；bugfix-594 已有基于可信 owner_recipient 的普通 Agent 主人私聊边界。最新主干 0fa706a67 含配置超时修复，独立工作树从该版本开始，避免旧主仓落后代码。

## 架构总览

飞书 SDK → 持久输入 → IM 原始镜像/来源事件 → PA observation → 服务端角色判定 → 原 Inbox/主会话 → send_message → ExternalStore 真实目标 → 主人直发或既有独立审查 → SDK 回执 → IM 镜像。

## 关键决策

1. **服务端统一判定主人来源。** 在 PersonalAgents 内复用一个判定：当前绑定的 node/agent/owner、enabled Feishu channel、app_id、持久 owner_open_id、direct source 与消息真实 sender_source_id 全部一致时为 owner_instruction；Web canonical DM 仍是 owner_instruction。主人在其他会话仅为 owner_fact；其他人 external。原始授权查询和 ownerMessage 使用同一判定，不信任模型元数据或文本自称。
2. **PA 飞书只走持久 observation 接入。** 先完成当前输入的镜像，接受输入后由既有持久来源事件接入。移除直接 receive 与 observation 的重复竞争。一般 Agent 保持原路径。输入同步不 await 旧输出投影；输出失败留原队列但不阻塞新输入。使用中心原始消息 ID 去重，保留来源渠道、发送者和时间；影子 conversation 作为回复地址并在 external 解析为本地真实目标。
3. **主人飞书外发由可信边界免披露审查。** PersonalActions prepare 在验证当前绑定、源访问与真实目标所属后可返回 owner_private；PA external 对该结果直接 dispatch。ExternalChannels 仍从持久 ExternalChat 取真实 chatId，模型不能提供底层目标。其他目标维持既有审查和 fail-closed；不扩大当前不支持群受众证明的发送能力。ExternalStore 保留 confirmed/unknown 防重复。IM 仅允许已验证主人飞书 shadow 的普通输出镜像，其他影子会话不放宽。
4. **角色说明与权限一致。** 默认 PA 指令和 inbox wake 文案明确 owner_instruction 可来自 Web 或已绑定飞书私聊，按原来源回复；owner_fact 是背景，不表示自动交办。现有自定义主人提示词不覆盖。

## 接口与数据流

- PersonalAgents 提供内部 owner-DM/owner-message 判定，admitSource、ownerMessage、authorization 与普通输出 mirror guard 共用。
- PersonalActions.prepare 的既有 owner_private 响应扩展至可信主人飞书 transport；原审查 prepare/review/commit/complete 用于其他目标。
- ExternalChannels 将输入 mirror 与输出 flush 分离，PA 输入以 IM observation 为唯一执行入口。PersonalAssistant.send 在选择 Web/外部发送分支之前，使用 NodeStore 已有可信 conversation_aliases 把 shadow target 归一化为 external target；复用 ExternalStore.chat 已支持的 shadow 查找，进入实际外发边界。Web canonical target 保持原路径。回归直接使用 Inbox 提供的 shadow target，断言真实平台回执而非仅 IM 消息。
- 本地 conversation.query 暴露的 owner_recipient 沿用可信 channel 事实。
- 直接引用飞书外部消息 ID 的源操作若仍存在，由 ExternalChannels 按已有 mirror 映射翻译；主执行入口得到中心 message ID，无需模型生成映射。
- 同一 schedule 工具由主会话创建短时一次性提醒；不改每日生产 schedule。

## 契约层增量

- docs/specs/gateway/external-channels.md ← specs/gateway/external-channels.md。
- docs/specs/gateway/global-agent.md ← specs/gateway/global-agent.md。

## 风险与回退

主人身份需要中央持久绑定事实；中央不可用时 PA 保留待接入输入，不能自行认定授权。其他普通 Agent 离线能力不改变。未知平台发送结果继续禁止盲重试。没有破坏性数据迁移，回退代码即可；隔离环境回退不触碰生产数据。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node/DSH | ./scripts/e2e-down.sh --wt "$PWD" | PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-up.sh --feishu --wt "$PWD" | .e2e-ports.env 中 IM_URL/health，仅作为前置 |

**Review 驱动方式**：端到端真栈，本 unit 不改客户端面。使用专用 lark-cli profile 的用户身份调用飞书真实消息 API，观察 SDK 入站、真实 PA 模型运行、平台回执并通过飞书消息 API 读取实际回复与定时提醒。不得通过直接注入 runtime 输入代替飞书收消息。Web 私聊通过客户端同一 API 驱动。

**验收前置**：本机已有 ~/.config/nano-multiagent/feishu-e2e.env 和 scripts/e2e-feishu-probe.py。启动前验证非默认 profile 属于同一测试 App、用户授权有效且只有一个 listener；用户 API 授权过期时，可由已登录飞书客户端发送同样的测试来信，并由 Bot API 读取实际送达消息。当前用户已主动协助续期专用 profile 授权；不打印密钥。以测试用户初始化正式 PA 并把测试 Bot 绑定给该 PA，使用本机已配置模型代理。临时脚本、数据和原始日志留在 ignored runtime，报告保留标记、时间、版本、消息/调度回执和证据路径。资源确实失效时记录阻塞，不以 mock 冒充真实验收。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-fix | 恢复主人飞书交办与送达 | 无 | 无 | apps/im-server、packages/personal-assistant、相关指令与既有测试 | [reviewer] 真实飞书主人收发、一次性提醒、Web 主人私聊实际成功；[worker] 身份/原始授权、非主人和群边界、失败隔离及重放去重回归通过；构建/类型/CI 和独立审查通过 |

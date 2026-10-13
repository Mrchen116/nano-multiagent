# bugfix-594: 本人私信免分类，其他消息保留内容审核

## Relations

- Related: bugfix-592；本次继续在 PR #344 的交付会话内修正消息权限边界。
- Current: [Global Agent](../../specs/gateway/global-agent.md)、[Auto 权限](../../operations/auto-permissions.md)。

## 原始报告

> 边界要是清晰的，“你明确要求把指定内容发给指定对象”，这种很难程序判断。给我本人发消息是不用。给其他的还是要，哪怕是本来就是接收到群消息，因为有可能他回复的信息不合适。加上这个“给我本人发消息就不用”的条件。然后其他场景下，send_message还是有误拒绝的风险，关于这个llm判断器的message设计是从哪参考过来的，他不给系统提示词，所以我要改llm判断器的prompt？让他明确什么是安全？

## 现象 / 复现

个人 Agent 在自己的飞书私聊中回复本次工作结果被 classifier_block 拒绝。当前所有公开 send_message 依赖分类器理解授权，分类器只拿到安全规则、原生历史转成的 JSONL 和待评工具名称/参数，没有 Nano 的发送身份、目标类型、真实回复投递语义。

本轮验收：宿主能证明目标为已绑定本人且是私聊时不调用 LLM；其他人、任何群聊（包括本人发起/创建的群和原群回复）、其他公开 Agent 目标仍调用分类器。不得凭名称、正文声称或模型参数放行。现有平台身份/可写检查、原生内部 child 通信和显式危险跳过配置保留。

分类器调整应补齐可信产品事实、明确正常任务回复和询问的安全语义，同时保留正文泄密、扩大受众、无授权第三方发布等审核。不把“有 send_message 就安全”或模型自称获准作为规则。

## 根因

规则来自旧 Nano 的 Claude Code Auto Mode/Security Monitor `cc-2.1.267-nano-v1` 移植资产；DSH 迁移 `8a608c771` 保留该资产，并用公开原生 Session messages 重建工具历史。`assets/auto/README.md` 区分 Nano 默认和可选 DSH upstream `5badb150` 规则。JSONL 中的 host_context_live/host_context 及两阶段分类继承 Security Monitor 契约；消息角色/来源转换是 Nano 自己的适配。

保留分类器独立 system policy 是有意设计，但不应漏掉固定产品执行语义。当前只附 Inbox 真人来源说明，缺少宿主解析的发送者/收件人事实；没有本人收件人的确定性出口，模型因此错误地把 Agent 的原私聊回复当成未经授权的对外发布。具体自然模型误判受采样影响，Prompt 改进须经受控对照，不能从一条拒绝解释推断唯一内部原因。

本人判断由现有 PA/Channels/IM 身份负责，DSH integration 只消费绑定的可信查询结果；不让执行层读取产品数据库或复制账号映射。不恢复 Python Kernel，不改 DSH upstream，不新增审核链。

## 修复

实施后回填。

## 验证

实施后回填。扩展现有 native approval、GlobalAgent 和 ExternalChannels 测试，从实际预执行分流、真实平台身份映射和分类器输入 seam 验证，不新增镜像 Prompt 文案单测。真实 Luna 对照不执行任何返回的工具调用，原始私密日志仅留本机。

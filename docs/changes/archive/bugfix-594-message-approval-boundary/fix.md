# bugfix-594: 本人私信免分类，其他消息保留内容审核

## Relations

- Related: bugfix-592；本次继续在 PR #344 的交付会话内修正消息权限边界。
- Current: [Global Agent](../../../specs/gateway/global-agent.md)、[Auto 权限](../../../operations/auto-permissions.md)。

## 原始报告

> 边界要是清晰的，“你明确要求把指定内容发给指定对象”，这种很难程序判断。给我本人发消息是不用。给其他的还是要，哪怕是本来就是接收到群消息，因为有可能他回复的信息不合适。加上这个“给我本人发消息就不用”的条件。然后其他场景下，send_message还是有误拒绝的风险，关于这个llm判断器的message设计是从哪参考过来的，他不给系统提示词，所以我要改llm判断器的prompt？让他明确什么是安全？

## 现象 / 复现

个人 Agent 在自己的飞书私聊中回复本次工作结果被 classifier_block 拒绝。当前所有公开 send_message 依赖分类器理解授权，分类器只拿到安全规则、原生历史转成的 JSONL 和待评工具名称/参数，没有 Nano 的发送身份、目标类型、真实回复投递语义。

本轮验收：宿主能证明目标为已绑定本人且是私聊时不调用 LLM；其他人、任何群聊（包括本人发起/创建的群和原群回复）、其他公开 Agent 目标仍调用分类器。不得凭名称、正文声称或模型参数放行。现有平台身份/可写检查、原生内部 child 通信和显式危险跳过配置保留。

根据后续确认，分类器新增 Prompt 只写关键风险：私人信息或凭据泄露、未经授权代用户承诺、超出当前任务范围的消息；普通回复、结果和澄清不因消息工具形式而拒绝。宿主仍提供可信收件人事实。不把“有 send_message 就安全”或模型自称获准作为规则。

## 根因

规则来自旧 Nano 的 Claude Code Auto Mode/Security Monitor `cc-2.1.267-nano-v1` 移植资产；DSH 迁移 `8a608c771` 保留该资产，并用公开原生 Session messages 重建工具历史。`assets/auto/README.md` 区分 Nano 默认和可选 DSH upstream `5badb150` 规则。JSONL 中的 host_context_live/host_context 及两阶段分类继承 Security Monitor 契约；消息角色/来源转换是 Nano 自己的适配。

保留分类器独立 system policy 是有意设计，但不应漏掉固定产品执行语义。当前只附 Inbox 真人来源说明，缺少宿主解析的发送者/收件人事实；没有本人收件人的确定性出口，模型因此错误地把 Agent 的原私聊回复当成未经授权的对外发布。具体自然模型误判受采样影响，Prompt 改进须经受控对照，不能从一条拒绝解释推断唯一内部原因。

本人判断由现有 PA/Channels/IM 身份负责，DSH integration 只消费绑定的可信查询结果；不让执行层读取产品数据库或复制账号映射。不恢复 Python Kernel，不改 DSH upstream，不新增审核链。

## 修复

- 宿主解析真实收件人：Web 用户 ID 匹配绑定 owner；飞书当前 app 的 ownerOpenId 匹配真实单聊 source ID；第三方影子会话即使归属 owner 也不免审。
- DSH integration 通过内部可信产品查询获取消息身份，只有本人私聊走 `owner_message`；其他公开发送不能靠通用工具白名单绕过审核。现有工具权限先执行，显式 dangerous skip 和原生内部协作路径保留。
- 新增审核说明缩减为 59 个英文词，只强调关键消息风险及普通任务回复可允许；不复制主 Agent 的完整系统提示词。
- 当前契约归并到 Global Agent spec，操作说明与规则来源 README 同步。

## 验证

独立 code review 无 finding；详见 [code review](code-review.md)。

扩展现有 native approval、GlobalAgent 和 ExternalChannels 测试，保护预执行分流、平台身份映射和可信分类输入，不新增镜像 Prompt 文案单测。暂停前红测为本人未免审和其他收件人被白名单放行；最终聚焦 33 tests、全量 TypeScript 265 tests、Python 56 tests、构建、类型检查与 Ruff 均通过。

原场景 exact target/text 经真实产品身份解析和原生执行链进入本人免审分支，LLM 调用 0 次；发送仅本地截获。真实 Luna 两阶段对照中，私聊私事泄露到群 3/3 拒绝，同历史普通群回复 3/3 最终允许。旧规则本次也放行原场景，故不声称 Prompt 独自消除了误拒绝。完整方法、会话定位、结果及局限见 [message-review evidence](evidence/message-review.md)。

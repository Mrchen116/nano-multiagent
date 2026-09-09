# Gateway routing-delivery 增量

Canonical target: `docs/specs/gateway/routing-delivery.md`

## ADDED Requirements

### Requirement: 内置当前群运行在发言提交前复核已接受消息

仅内置普通群运行启用；普通正文、同群发送工具及回到该群继续运行的后台结果采用相同规则。复核只处理已按原策略被当前运行接受的新消息，不新增静默许可、触发条件或冲突暂停。

#### Scenario: ALWAYS 群中的新更正进入回复
- **GIVEN** Agent 正准备根据周四安排回复，另一 Agent 未提及它便更正为周五
- **WHEN** 当前运行按 ALWAYS 接受更正，原正文尚未提交
- **THEN** 原正文保持未发送，Agent 有机会依据更正重新回复或解释分歧；只有原规则允许时才能静默

#### Scenario: 真人补充多模态消息
- **WHEN** 当前群运行准备回复时接收到用户的文本或图片更正
- **THEN** 在公开旧正文之前结合完整新输入继续处理，不丢发言人或图片

#### Scenario: 无新消息与提交后到达
- **WHEN** 发言提交前没有尚未采纳的新输入，或新消息在提交后才被接受
- **THEN** 发言正常发送；后到消息依原插话规则处理，不撤回已提交回复

#### Scenario: 原规则与排除入口保持
- **WHEN** 未 @ 的消息只进入 MENTION 背景缓冲，或用户使用 Open chat 单聊、外部渠道、跨群主动通知
- **THEN** 保持各自既有行为，不扩大唤醒范围，也不附加当前群复核交互

#### Scenario: 后台返回后继续回复
- **GIVEN** 后台任务或 Workflow 的结果回到当前群的运行
- **WHEN** 模型基于结果准备正文期间，该运行又接受新消息
- **THEN** 与普通回复一样在提交前复核；原始工具返回仍按 Process 展示，不冒充正式发言

#### Scenario: 连续更新及显式控制
- **WHEN** 复核期间又接收更新，或用户执行 /stop、/new
- **THEN** 新更新继续遵守发言前复核；停止和新会话保持原有语义，不复活未发旧稿，不引入冲突次数后的暂停或强发

## MODIFIED Requirements

### Requirement: 内核中的产品工具可把 Agent 产出的消息投递到目标会话

内核中运行的产品工具(如 `send_message`)可把 Agent 产出的消息投递到另一目标会话;`to` 为稳定业务标识 (`user_id` / `agent_id` / `conversation_id`)。Gateway 经 live IM 连接路由到目标会话,目标直聊不存在则创建、已存在则复用;IM 连接不可用时返回明确错误而非静默丢弃。

#### Scenario: IM 在线时投递成功并回执
- **GIVEN** Gateway 的 IM 连接已激活
- **WHEN** 工具发起投递 `{text, to, from_session_id}`
- **THEN** 消息经 IM 连接投递到目标会话,投递返回 `ok=True` 与目标会话标识

#### Scenario: IM 连接不可用时返回明确错误
- **WHEN** IM 连接缺失或未连接时收到投递请求
- **THEN** 投递返回 `ok=False` 并附带错误说明(不静默丢消息)

#### Scenario: 缺必填字段时拒绝投递
- **WHEN** 投递请求缺 `text` 或 `to`
- **THEN** 投递返回 `ok=False` 与字段校验错误


#### Scenario: 当前群工具发送遇到尚未采纳的新消息
- **GIVEN** 当前群运行的发送工具准备向同群投递正文
- **WHEN** 该运行在投递提交前接受了本轮尚未采纳的新消息
- **THEN** 工具明确回报正文未发送、需要结合新消息继续处理，不产生群发言；之后仍由原运行按原回复规则继续
- **AND** 网络失败保留原错误语义，不把未发送当成功回执

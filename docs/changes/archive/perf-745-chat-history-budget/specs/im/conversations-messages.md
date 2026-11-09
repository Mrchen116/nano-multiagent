# IM conversations-messages Specification (delta for perf-745)

## MODIFIED Requirements

### Requirement: 会话消息与时间线条目响应字段稳定且按消息游标分页

前端经会话 endpoints 创建和读取消息；消息继续使用 Actor 语义并暴露 delivery status、sender type 与 attachments。历史读取的 `items` 是 typed timeline union，可包含普通 message 与独立 config boundary；`next_before_message_id` 继续作为消息游标。未知会话保持稳定 404。

#### Scenario: 创建会话指定参与者 Actor
- **WHEN** 前端创建带参与者的会话
- **THEN** 返回会话 id，后续可据此读写消息

#### Scenario: 创建消息回显既有消息字段
- **WHEN** 前端创建用户或 Agent 消息
- **THEN** 响应继续包含既有 message id、conversation id、delivery status、sender type 与 attachments

#### Scenario: 并发创建会话
- **WHEN** 同一用户同时提交多个合法的创建会话请求
- **THEN** 对同一对联系人的普通私聊发起返回同一个会话；显式新建群或 fork 仍分别建立独立会话，所有会话均保留完整参与者列表

#### Scenario: 列时间线走 items 与消息游标信封
- **WHEN** 前端读取会话历史
- **THEN** 响应含 `items` 与 `next_before_message_id`
- **AND** 每个 item 由 type 明确区分 message 与 Agent 配置边界，面向浏览器的 boundary 只含定位与展示所需字段

#### Scenario: 未知会话相关读写返回稳定 404
- **WHEN** 前端对不存在的 conversation id 读写消息或时间线
- **THEN** 返回既有 conversation not found 语义

#### Scenario: conversation 列表与 sync 暴露通用运行态
- **WHEN** 浏览器前端请求 conversation 列表或 sync 数据
- **THEN** 每个 conversation item 包含通用字段 `run_state`，取值至少支持 `"idle"` 与 `"running"`
- **AND** 该字段不带 distill 命名，可被其他功能复用

#### Scenario: 普通浏览器消息使用本人身份
- **GIVEN** 当前用户是该聊天成员
- **WHEN** 浏览器提交消息并尝试声明其他人的发送者身份
- **THEN** 消息不能冒充其他人、Agent 或 system；正常用户消息展示当前登录者。

#### Scenario: 纯人聊天不需要 Gateway
- **WHEN** 两个用户创建私聊或只有真人成员的群并收发消息
- **THEN** 消息正常持久化和实时呈现，不要求存在 Agent 或在线 Gateway。

#### Scenario: 群类型不由人数推断
- **WHEN** 用户明确新建只有本人和一个 Agent 的群
- **THEN** 仍创建群会话，可按群操作添加成员。


#### Scenario: 普通人际私聊默认显示对方名称
- **GIVEN** 两个真人的普通私聊尚未被明确改名
- **WHEN** 任一成员读取列表、详情或同步结果
- **THEN** 默认聊天名显示该查看者的对方；明确设置的共享名称继续对双方一致，fork 与 Skill 蒸馏聊天保留自己的标题。

#### Scenario: 聊天历史摘要与完整过程读取
- **WHEN** 客户端选择摘要视图读取聊天历史，随后展开某条已结束回复的过程
- **THEN** 历史先返回消息、审批状态和过程概况，按需读取同一消息的完整过程；普通客户端仍可按原方式读取完整历史。
- **AND** 过程详情必须符合当前会话读取资格，消息与会话不匹配或当前不可读时不能取到详情。

# IM Conversations and Messages Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: 聊天时间线支持非消息型 Agent 配置边界

IM 可在聊天时间线中持久化 `agent_config_changed` entry。该 entry 不是用户、Agent 或 system message，不带发送者，不进入 Agent 对话上下文；它稳定锚在第一条实际采用新运行配置的用户消息之前。重复上报幂等，晚到也不改变锚定位置；持久数据不包含 prompt、完整 Agent 配置、secret、工具参数或变更字段明细。

#### Scenario: 配置边界随历史读取并锚在用户消息前
- **GIVEN** 某用户消息开始了首次采用新配置的回复
- **WHEN** 浏览器读取该聊天时间线
- **THEN** 返回唯一的配置边界，并紧邻显示在该用户消息之前

#### Scenario: 晚到与重复上报不改变结果
- **GIVEN** anchor 用户消息已持久化并可能已显示
- **WHEN** 同一配置边界晚到或被 Gateway 重试多次
- **THEN** 时间线最终只有一个 entry，位置仍在 anchor 消息之前

#### Scenario: 配置边界不进入消息或 Agent 上下文
- **WHEN** 用户继续聊天或读取普通消息数据
- **THEN** divider 不成为 user、agent 或 system message，也不被发送给模型
- **AND** divider 不暴露 prompt、完整 Agent 配置、secret、工具参数或变更字段明细

### Requirement: 消息游标分页把配置边界与 anchor 作为原子时间线单元

消息历史 endpoint 返回 typed timeline items，同时保留 `next_before_message_id` 游标。分页 limit 继续按消息计数；某页包含 anchor message 时必须同时包含其配置边界，divider 不单独消耗 message limit，也不会孤立在相邻页面。

#### Scenario: anchor 位于分页边缘
- **GIVEN** 配置边界锚定的用户消息正好是某页最早或最晚消息
- **WHEN** 浏览器按 message cursor 加载该页
- **THEN** divider 与 anchor 在同一 response 中且顺序稳定

#### Scenario: 向前分页不重复 divider
- **WHEN** 浏览器连续加载当前页与更早页并合并时间线
- **THEN** 每个 stable boundary id 最多出现一次，message cursor 能继续定位更早消息

### Requirement: fork 复制 fork 点以前的配置边界并重锚

IM fork 复制源消息历史时，同时复制 anchor 在 fork 范围内的配置边界，并映射到目标会话中对应的新 message id。fork 操作本身不表示 Agent 配置更新，不额外生成边界。

#### Scenario: fork 点以前已有配置边界
- **GIVEN** 源单聊在 fork 点以前已有配置边界
- **WHEN** 用户 fork 到该点
- **THEN** 新单聊的复制历史包含同等边界，位于复制后的对应用户消息前

#### Scenario: fork 创建本身不新增配置边界
- **WHEN** 用户从一条回复 fork 出分支单聊
- **THEN** 除复制范围内既有边界外，不因 fork 动作新增“Agent 配置已更新”entry

## MODIFIED Requirements

### Requirement: 会话消息与时间线 entry 响应字段稳定且按消息游标分页

前端经会话 endpoints 创建/读取消息；消息继续使用 Actor 语义并暴露 delivery status、sender type、attachments。历史读取的 `items` 是 typed timeline union，可包含普通 message 与独立 config boundary；`next_before_message_id` 继续作为消息游标。未知会话保持稳定 404。

#### Scenario: 创建消息回显既有消息字段
- **WHEN** 前端创建用户或 Agent 消息
- **THEN** 响应继续包含既有 message id、conversation id、delivery status、sender type 与 attachments

#### Scenario: 列时间线走 items 与消息游标信封
- **WHEN** 前端读取会话历史
- **THEN** 响应含 `items` 与 `next_before_message_id`
- **AND** 每个 item 由 type 明确区分 message 与 agent config boundary，面向浏览器的 boundary 只含定位与展示所需字段

#### Scenario: 未知会话相关读写返回稳定 404
- **WHEN** 前端对不存在的 conversation id 读写消息或时间线
- **THEN** 返回既有 conversation not found 语义

## REMOVED Requirements

N/A.

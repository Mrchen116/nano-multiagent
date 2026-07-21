# IM Web Chat UX Specification (delta for bugfix-471)

## ADDED Requirements

### Requirement: Web IM 用持久非消息分界线说明 Agent 运行配置缓存边界

某个既有聊天首次真正使用不同的 Agent 运行配置时，Web IM 在该轮首条用户消息前显示持久小字：
“Agent 配置已更新 · 后续请求将不再命中此前的上下文缓存”。divider 不是消息气泡，没有头像、发送者、时间、投递状态或消息菜单。页面刷新、重进、分页和连接恢复后位置不变。

#### Scenario: 运行配置更新后继续既有聊天
- **GIVEN** 用户成功修改会改变后续模型请求的 Agent 配置
- **WHEN** 某个既有聊天开始第一轮真正使用新配置的交流
- **THEN** 首条用户消息前出现固定文案的非消息 divider
- **AND** Agent 回复仍能引用 divider 前的聊天历史

#### Scenario: divider 在刷新和重进后保持位置
- **GIVEN** 聊天已显示配置 divider
- **WHEN** 用户刷新页面、离开后重进、向前分页或断线重连
- **THEN** divider 仍唯一地位于同一 anchor 用户消息之前

#### Scenario: divider 不提供消息交互
- **WHEN** 用户在桌面或移动端查看或操作配置 divider
- **THEN** divider 无头像、气泡、发送者、投递状态和复制/fork 消息菜单

#### Scenario: 休眠聊天不被批量插入
- **GIVEN** 同一 Agent 有多个既有聊天
- **WHEN** 用户修改运行配置，但某些聊天没有继续交流
- **THEN** 未继续的聊天不新增 divider

#### Scenario: 连续修改只显示最终边界
- **GIVEN** 某聊天再次使用前，Agent 运行配置连续成功修改多次
- **WHEN** 用户回到该聊天开始新回复
- **THEN** 时间线只新增一条 divider，不依次显示中间版本

#### Scenario: 纯展示更新与保存失败不显示 divider
- **WHEN** 用户只修改展示信息，或运行配置保存没有成功
- **THEN** 聊天页不出现配置缓存 divider

#### Scenario: desktop 与 mobile 保持低层级时间线样式
- **WHEN** 用户在桌面或移动浏览器查看带 divider 的聊天
- **THEN** divider 横跨消息内容区，以低于消息正文的视觉层级显示
- **AND** 不破坏既有 desktop sidebar/chat 布局或 mobile 单页 chat 布局，不产生横向滚动

#### Scenario: 外部 channel shadow chat 补齐 divider
- **GIVEN** 外部 channel 的既有对话采用了新配置，Web IM 暂时离线
- **WHEN** 用户稍后打开或刷新对应 shadow chat
- **THEN** divider 唯一地显示在正确的外部用户消息前
- **AND** 外部 channel 本身没有收到伪造的 divider 消息

## MODIFIED Requirements

### Requirement: Web IM 实时体验在连接恢复后保持一致且不重复消息或时间线边界

Web IM 的当前会话、会话列表、消息、配置边界、提醒与状态共享同一事件连续性。短暂断网后，已处理事件不再次显示；断线期间遗漏的持久 message 和 timeline boundary 经恢复或刷新与历史一致。

#### Scenario: 恢复连接不重放已处理提醒
- **GIVEN** 用户已处理某条提醒，随后短暂断网
- **WHEN** 实时连接恢复
- **THEN** 历史提醒不再次弹出

#### Scenario: 断线期间的新消息与配置边界恢复后可见
- **GIVEN** 断线期间某聊天收到新消息并实际跨过运行配置边界
- **WHEN** 浏览器恢复网络
- **THEN** 消息与 divider 最终按正确 anchor 顺序显示，不产生重复气泡或 divider

#### Scenario: 状态恢复到当前权威值
- **WHEN** 浏览器恢复网络并查看 Chat、Nodes 或 Agents
- **THEN** 非持久状态显示当前权威值，不永久停留在断线前快照

#### Scenario: 切换账号不展示前一账号缓存
- **WHEN** 用户退出账号 A 并登录账号 B
- **THEN** Web IM 只展示 B 的消息、配置边界、提醒与状态

## REMOVED Requirements

N/A.

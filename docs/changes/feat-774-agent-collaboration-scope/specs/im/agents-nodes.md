# im/agents-nodes Specification (delta for feat-774)

## ADDED Requirements

### Requirement: Agent 协作范围决定哪些聊天新消息可以送达

#### Scenario: 创建、保存与查看
- **WHEN** 用户创建或编辑 Agent
- **THEN** 协作范围只有「团队协作」和「仅限本人」，新建默认团队协作。配置接口以 collaboration_scope 的 team / owner_only 读写同一选择，Web、iOS、PA 首建与代建一致。

#### Scenario: 仅限本人
- **WHEN** 选择仅限本人
- **THEN** 只接收创建者亲自发给该 Agent 的一对一私聊。其他人的私聊、所有群消息与 PA 旁观聊天均不进入其收件内容或提醒。

#### Scenario: 收紧范围
- **WHEN** 设置成功切换为仅限本人
- **THEN** 越出范围且尚未交给模型的团队积压停止递送，恢复团队协作后也不补发。已发生的交互保留历史。

## MODIFIED Requirements

### Requirement: Agent 通道页统一管理外部 channel 与安全凭据

Agent 详情页的“通道”页只管理可配置的外部 channel，不把内置 Web IM 列为 channel。页面和 REST 资源按 provider 通用建模；本期 provider catalog 只有飞书，且同一 Agent 每种 provider 最多一个实例。飞书向导只给简短准备说明和开放平台入口。App Secret 只在新增或显式替换时提交，服务端立即封装为目标节点公钥可解的密文；list/get/edit 不返回明文或 envelope，Gateway 的普通 `config.yaml` 也不是该凭据的持久化位置。

#### Scenario: 空态与添加入口不展示 Web IM
- **GIVEN** 当前 Agent 没有外部 channel
- **WHEN** 用户打开“通道”页
- **THEN** 页面显示通用空态和“添加通道”，provider picker 当前包含飞书
- **AND** 页面不展示 Web IM；已有飞书时 picker 标记已添加并禁止第二个实例

#### Scenario: 飞书向导提供轻量开放平台入口
- **WHEN** 用户选择添加飞书
- **THEN** 页面简要提示准备应用、Bot 与长连接，并提供 `https://open.feishu.cn/page/launcher?from=backend_oneclick`
- **AND** App ID/App Secret 缺失时在字段处提示，不提交连接请求

#### Scenario: channel 列表读取失败不伪装成空态
- **WHEN** IM 无法读取当前 Agent 的 channel resources
- **THEN** 页面显示失败原因和重试入口，不显示“尚未配置”的空态

#### Scenario: 已保存密钥不可读取且 App ID 换绑必须换密钥
- **GIVEN** 飞书 channel 已保存 App Secret
- **WHEN** 用户再次读取或编辑该 channel
- **THEN** 响应只表明 `secret_configured=true`，不返回明文或 envelope；用户可显式 keep 或 replace
- **AND** App ID 改变时 keep 被拒，必须同时 replace App Secret；通过 IM 新建/更新不会把 secret 写入 Gateway `config.yaml`

#### Scenario: 节点尚未登记 credential public key
- **GIVEN** IM 从未取得目标节点的 credential public key
- **WHEN** 用户新增 channel 或 replace secret
- **THEN** IM 拒绝凭据写入，并说明需让节点至少上线一次以建立安全存储
- **AND** 不把该错误误报成飞书凭据无效

#### Scenario: 在已有飞书渠道确认创建者的私人收件身份
- **WHEN** 创建者在已认证的通道管理入口登记自己在该 App 的 open_id
- **THEN** 仅此 App 与 Agent 可以使用该声明识别私人收件。自动发现的首个发言人不能代替该声明；更换 App 后须重新确认。未登记时说明仅限本人下的飞书私聊尚不可达。

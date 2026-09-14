# feat-554 — im/conversations-messages

> 目标: docs/specs/im/conversations-messages.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## REMOVED Requirements

### Requirement: 同一 owner 的 Agent 私聊可从投递记录打开

### Requirement: 群会话支持成员增减、改名与解散（owner 隔离、解散限创建者）


## MODIFIED Requirements

### Requirement: 外部 channel 用户消息可写入影子会话

IM 支持 Gateway 将来自外部 channel 的用户消息写入影子会话。消息按已注册 Gateway 的外部来源和发送者标识保存独立外部身份，并持久化 `sender_display_name`；直聊和群聊均显示原发送者名称。外部来源身份不冒充登录用户，也不出现在真人联系人目录。外部消息与普通 IM 消息共享读取、分页、权限和投递状态语义。

#### Scenario: 外部 1:1 用户消息保留原发送者身份
- **GIVEN** Gateway 写入一条 IM owner 从飞书 1:1 发来的消息
- **WHEN** 用户通过 REST 或 WebSocket 查看该会话历史
- **THEN** 该消息显示原发送者名称，不自动映射为 Gateway 管理者或当前浏览器用户

#### Scenario: 外部群聊消息显示原发送者名字
- **GIVEN** Gateway 写入一条 Alice 从飞书群发来的消息
- **WHEN** 用户通过 REST 或 WebSocket 查看该会话历史
- **THEN** 该消息显示为 Alice 发送

### Requirement: 外部 channel 用户消息实时出现

IM 将外部 channel 用户消息写入影子会话后,必须通过浏览器 user-stream 发出足以直接插入当前会话消息列表的 live 事件。打开中的影子会话不得依赖刷新历史才能看到飞书/Lark 用户刚发来的消息。该 live 事件必须携带消息正文、附件、发送者类型、发送者显示名、delivery status 和创建时间。

#### Scenario: 打开的影子会话不刷新即可看到飞书用户消息
- **GIVEN** 用户已经在浏览器打开 `plato · feishu` 影子会话
- **WHEN** Gateway 写入一条 IM owner 从飞书 1:1 发来的新消息
- **THEN** 浏览器通过 user-stream 收到 canonical `message.created` 或等效完整新消息事件
- **AND** 当前消息列表立即追加该用户气泡,无需刷新页面或重新进入会话
- **AND** 该气泡显示原发送者名称，与刷新历史后的身份一致

#### Scenario: 外部群成员 live 消息显示原发送者名
- **GIVEN** 用户已经在浏览器打开 `plato · 产品群 · feishu` shadow group
- **WHEN** Gateway 写入一条 Alice 从飞书群发来的新消息
- **THEN** 当前消息列表立即追加 Alice 的用户气泡
- **AND** live 显示名与刷新历史后的显示名一致

### Requirement: Agent 新托管图片按会话保护且稳定可回看

IM MUST 将新托管 Agent 图片作为对应会话的受保护资源。访问遵循会话成员权限；历史回看不依赖 Agent 原文件或节点在线。普通新旧上传附件的承接以本文件“IM 托管聊天附件按会话成员关系读取”为准。

#### Scenario: 已交付图片持久回看
- **GIVEN** 会话已有新托管的 Agent 图片
- **WHEN** 原文件删除或覆盖、Gateway 重启或离线，用户刷新或重新登录
- **THEN** 有权用户仍看到交付时的同一图片。

#### Scenario: 地址不授予访问权限
- **WHEN** 未登录或非成员用户请求新托管图片
- **THEN** 分别返回 401 或 404，不返回图片；有权用户正常读取。

#### Scenario: 会话 fork 保留图片
- **WHEN** 用户 fork 含图片的消息历史并随后删除原会话
- **THEN** fork 中仍可查看已复制消息的图片，且访问遵循目标会话权限。

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


## ADDED Requirements

### Requirement: Agent 私聊的投递记录不授予管理者聊天访问权

Agent 私聊的原聊天读取统一按实际成员关系判断。管理 Agent 或持有投递回执中的 ID 均不自动成为聊天成员；全局 Work 已记录的内容仍按工作视图契约完整展示。

#### Scenario: 工作记录链接到 Agent 私聊
- **WHEN** Agent 向同一 owner 的另一个 Agent 发送消息
- **THEN** 非成员 owner 的聊天列表不包含该私聊，使用回执 ID 读取原聊天或消息返回 404
- **AND** 实际成员可访问，全局 Work 的已记录内容不因此被过滤

#### Scenario: 复用旧的随机归属私聊
- **GIVEN** 两个 Agent 同属一个 owner，旧私聊的归属未对应任何用户或 Agent profile
- **WHEN** 发送操作重新解析这对 Agent 的私聊
- **THEN** 保留原 conversation id、已有消息及实际成员，不因 owner 修复自动加入新的真人成员
- **AND** 旧 owner 的既有可见会话在升级时按成员关系承接，不为不同 owner 的 Agent 推断新的共同管理者

### Requirement: 群会话按成员关系管理，解散限创建者

前端经 `/im/v1/conversations/{id}*` 对一个已存在的群会话管理其成员与元数据：向群添加参与者（Actor）、移除某个参与者、修改群名、解散整个群。操作要求当前用户是群成员（非成员 404）。真人成员可改名、添加真人或自己管理的 Agent、移除非创建者成员或自己退出；创建者不可被移除。解散仅仍在群内的创建者可执行，非创建者被拒。这些能力让用户在内置 Web IM 里完成基本群治理，无需重建群。

#### Scenario: 向已存在的群会话添加参与者
- **GIVEN** 终端用户参与一个群会话，且账号下存在尚未加入该群的 agent
- **WHEN** 前端 `POST /im/v1/conversations/{id}/participants` 带一组 Actor（`{type:"agent", id:"<agent_id>"}`）
- **THEN** 200 返回该会话快照，其 `participants` 含新加入的 agent；此后该 agent 能收发该会话后续消息，加入的真人成员可回看群已有历史

#### Scenario: 重复添加已在群的参与者保持幂等
- **GIVEN** 某 agent 已是该群成员
- **WHEN** 前端再次 `POST /participants` 提交同一 agent
- **THEN** 成员不重复出现，会话快照参与者集合不变（不报 500）

#### Scenario: 添加请求为空或 agent 无法解析被拒
- **WHEN** 前端 `POST /participants` 提交空列表或无法解析为已知 agent 的 id
- **THEN** 400 拒绝，会话成员不变

#### Scenario: 非成员添加参与者返回 404
- **WHEN** 用户对自己未参与的会话 `POST /participants`
- **THEN** 404，不泄漏该会话存在

#### Scenario: 修改群名生效，空名被拒
- **WHEN** 前端 `PATCH /im/v1/conversations/{id}` 提交非空 `title`
- **THEN** 200 返回更新后的会话，会话列表与详情显示新群名
- **AND** 提交空 `title` 时不接受为新名（会话名保持原值）

#### Scenario: 会话参与者带 user_id 供成员管理
- **WHEN** 前端读取会话（`GET /conversations` 或写操作返回的快照）
- **THEN** 每个 participant 带 `user_id`（agent participant 的 `id` 是 agent_id，`user_id` 是其稳定 IM 用户标识），前端据 `user_id` 调移除端点

#### Scenario: 移除参与者后该成员从群消失
- **GIVEN** 群里有多个 agent 成员
- **WHEN** 前端 `DELETE /im/v1/conversations/{id}/participants/{user_id}` 指定某 agent 的 `user_id`
- **THEN** 204；该会话快照参与者集合不再含该成员，该成员不能再读取、发言或接收群消息；可一直移除到只剩创建者，群仍存在

#### Scenario: 仅创建者可解散群，非创建者被拒
- **WHEN** 会话创建者 `DELETE /im/v1/conversations/{id}`
- **THEN** 204，该会话及其消息被删除，列表不再返回它
- **AND** 非创建者发起同一请求时 403，会话不被删除

#### Scenario: 跨账号添加真人及自己的 Agent
- **GIVEN** 三个账号拥有不同的 Gateway 或没有 Gateway
- **WHEN** 群成员添加同事，各管理者添加自己管理的 Agent
- **THEN** 成员跨账号、跨 Gateway 加入同一群；普通成员不能把他人管理的 Agent 加入群。

#### Scenario: 移除后在线与重连界面收敛
- **GIVEN** 用户被移出群或群已解散
- **WHEN** 用户在线收到更新或断线后重新连接
- **THEN** 该聊天从其列表和当前打开内容中移除，不能继续取得新的聊天内容。

### Requirement: 聊天偏好与已读状态属于当前用户

#### Scenario: 置顶与免打扰各自独立
- **GIVEN** alice 与 bob 同在一群
- **WHEN** alice 设置置顶或免打扰
- **THEN** 仅改变 alice 的聊天列表与通知偏好，bob 的偏好不变。

#### Scenario: 已读不消费他人的未读
- **GIVEN** 两人均有该群未读消息
- **WHEN** alice 打开聊天并读到当前消息
- **THEN** 只清除 alice 已看到的未读，bob 的未读保留；同时到达、尚未展示的新消息仍保持未读。

#### Scenario: 旧状态随升级承接
- **GIVEN** 原用户已有聊天偏好和未读数量
- **WHEN** 部署 agent 按 unit 的迁移文档完成存量转换，升级并重新登录
- **THEN** 原用户的既有偏好和未读数量保留，其他用户的个人状态独立初始化；旧聊天、历史与 fork 链接继续可用。

### Requirement: IM 托管聊天附件按会话成员关系读取

普通新上传和 Agent 图片均是受保护聊天资源；URL 不授予读取资格。IM 自身托管的旧公开上传在部署时按文档一次性转换其原消息关联与引用，新版本只提供目标格式的资源服务。

#### Scenario: 普通图片与文件上传
- **GIVEN** 用户已参与一个聊天
- **WHEN** 用户上传普通图片或文件并发送消息
- **THEN** 当前聊天成员可正常预览和下载，未登录者或非成员持相同 URL 不能读取；全局 Work 可见不改变来源附件资格。

#### Scenario: 旧公开附件经部署转换后继续回看
- **GIVEN** 旧消息保存了本 IM 的公开上传 URL
- **WHEN** 部署 agent 按迁移文档转换历史引用并升级，成员与非成员分别打开同一历史附件
- **THEN** 成员从原聊天的新受保护引用读取同一字节，非成员无法读取；旧关联文件不丢失，没有消息关联的历史文件不再公开。
- **AND** 单独保存的旧 `/im/uploads` URL 不再提供文件、别名或重定向服务。

#### Scenario: 引用与 fork 不产生访问旁路
- **GIVEN** 用户持有自己无权读取的聊天附件 URL
- **WHEN** 尝试将该 URL 关联到自己的会话
- **THEN** 不会因此取得附件访问权；有来源访问权的合法 fork 则保留独立附件关联，删除源聊天不破坏 fork 回看。

# feat-554 一次性部署迁移说明

请作为正式部署 agent，在用户已授权的部署范围内完成以下操作。先读本 unit 的 [spec.md](spec.md)、[design.md](design.md)及当前部署规范，核对实际运行版本和目标版本。本文件是操作交接，不代表已经部署或迁移成功。

## 交付边界

本 unit 只交付这份 Markdown，不交付迁移程序。部署 agent 根据最终 schema 在部署工作目录执行一次性 SQL／临时操作，相关脚本、映射、备份和现场记录不进入应用代码、启动流程或仓库。新程序只使用目标结构，不读迁移清单，不做版本识别、自动回填、双写、旧字段 fallback 或旧 URL 别名转发。

实施负责人在交付 PR 前按最终 schema 和资源接口核对本文；正式部署 agent 再按目标 commit 与现场旧库核实具体表、列和存储路径。不要以启动新应用来代替旧库转换。空库正常初始化目标 schema，旧库必须先按本文处理。

本次保留用户、聊天、消息、Agent、node、Session 和执行 ID；不重复执行 refactor-550 的身份重编号，也不改变管理归属、外部平台 ID、账号密码或渠道密文。已有的正常 shadow 身份校验／离线补写继续使用，不因本次移除版本兼容而删掉这些现有工作能力。

## 1. 定位现场、停写并备份

从实际进程 cwd、启动参数、环境和配置定位唯一 IM 数据库、普通 uploads、私有图片存储，以及所有接入 Gateway 的配置和持久状态。不要使用当前 checkout 的空 data 目录冒充生产数据。记录旧／新版本、服务清单、路径和端口，不输出凭据原值。

先停止接收新工作，让已开始的工具执行、待批准请求、回复投递和配置边界得到可核实的终态。无法确认是否已经产生副作用的执行，先处理清楚再切换；不要凭聊天文字猜测 pending 请求的 agent／node／run，更不能通过重放它来试探。暂停外部通道监听及会写这些数据的后台任务，然后停止 IM 与有关 Gateway，确认没有残留写入者。

制作同一停写窗口的完整备份：IM SQLite、两类附件文件、会被修改引用的 Gateway 持久库／上下文，以及配置与运行状态。SQLite 使用一致性 backup 或停机后的完整快照，处理 WAL，不能只复制可能遗漏 WAL 的主文件。记录备份路径、数量和哈希。先在独立副本转换、验证，原备份保持只读。

## 2. 保留身份并建立目标成员状态

对照当前 `users`、`conversations`、`conversation_participants`、`agent_profiles` 和 `nodes` 盘点以下映射，转换清单只供部署核对：

| 数据 | 一次性处理 |
|---|---|
| 稳定身份与历史 | 保留全部原 ID、消息内容和顺序、手动标题、Agent／Gateway 管理归属、fork 关系、shadow 外部来源及幂等身份。Conversation owner 仍可表示来源，但不再赋予聊天访问权；creator 仍表示群创建者。 |
| 真人成员 | 保留已有成员。仅当旧版本确实给予某个真实真人 owner 该聊天访问权且能唯一对应账号时，补齐其缺失成员行；不能把 Agent 的管理者自动加入 Agent 参与的其他聊天。 |
| Agent-only／随机归属记录 | 保留真实 Agent 成员和来源身份，不按显示名、Agent creator 或随机 owner 猜一个真人。无法解释且影响既有真人可见性的记录列明后停止转换，不删数据或扩大权限。 |
| 原 owner 的个人状态 | 将原会话 `is_pinned`、`is_muted`、`unread_count` 原值写入对应真人成员的新字段；无法恢复其真实已读边界时保留 `last_read_message_id=NULL`，不伪造全体已读。 |
| 其他原成员 | 对没有既有个人状态的真人初始化 pin=false、mute=false、unread=0，已读边界置于该会话停写时的末条消息；空聊天边界为 NULL。Agent 行按目标结构的普通默认值初始化。 |
| 普通私聊唯一键 | 所有既有会话的新增 `direct_key` 置 NULL，保留原聊天入口，不猜哪些旧 direct 是 fork 或蒸馏执行。新版本从联系人新建的普通私聊才写规范化唯一键。 |

目标字段以 [db.py](../../../../src/IM/infra/db.py) 和 [ConversationRepository](../../../../src/IM/infra/repositories/conversations.py) 为准，当前实现具体为：

- `conversation_participants` 继续以 `(conversation_id, user_id)` 为联合主键。新增 `is_pinned`、`is_muted`、`unread_count` 均为 `INTEGER NOT NULL DEFAULT 0`；`last_read_message_id` 为可空 `TEXT`，保存本聊天真实 `messages.id`，不填事件 ID、Kernel 消息 ID 或 `:relay:` 合成气泡 ID。末条消息及已读推进按 `messages.rowid` 插入顺序判断；如需重建表，保留每个聊天内原插入顺序，不能按显示时间或随机消息 ID 重排。
- `conversations.direct_key` 为允许 NULL 的唯一 `TEXT`。普通联系人私聊使用排序后的两个稳定 `users.id` 以 `|` 连接；group、fork、蒸馏执行聊天不占用该唯一键。保留原 `type`、`creator_id`、`target_node_id`，不因为现有参与者恰好有两人就把群改成私聊。
- 成员与 `messages.sender_user_id` 存 `users.id`；真人 Actor 仍是 `type=user`，Agent Actor 的 `id` 是逻辑 `agent_id`、`user_id` 是 `username=agent:<agent_id>` 的合成用户 ID。目录中的 `kind=human` 只是公开资料分类，不写入消息 `sender_type`。真人识别以现有可登录账号为依据，不把没有密码的 Agent／shadow 用户补成真人；若同一身份同时具有登录凭据和合成 Agent／shadow 语义，记录冲突并停止，不自行改密码、改 ID 或扩大成员资格。

在副本离线建立目标 schema 的列、约束与索引；状态映射核对完成后移除 conversations 的三项共享偏好列。目标程序的读写与初始化均不得再依赖或重新补出这些列。与本次变化无关的表及字段保留。

事件重放、缓存会话快照中若含原共享 pin／mute／unread，按目标事件协议转换或移除这些个人字段，不能让旧快照再次覆盖个人状态；保留消息、事件 ID、顺序及投递状态。不要靠新版本识别“旧事件”补偿。

## 3. 将旧附件引用转换为新资源引用

先核对目标版本实际的资源 schema 和 `/im/v1/conversations/{id}/attachments/{resource_id}` 接口。保留已有受保护 images 资源的 ID、URL、原字节和独立 fork 关联；这条仍在使用的接口不是旧公开上传兼容入口。

当前实现共用 `message_images` 表，没有新增 attachments 表或单独的关联表：一行就是一个会话资源关联。其列为 `image_id`（主键）、`conversation_id`、`source_key`、`sha256`、`content_type`、`file_name`、`byte_size`、`storage_name`，并要求 `(conversation_id, source_key)` 唯一。普通附件 URL 中的 `resource_id` 就是该行的 `image_id`；images URL 也使用同一个 ID。字节位于实际 IM 数据库父目录的 `message-images/<storage_name>`，`file_name` 仅为下载显示名；不要把旧 uploads 目录或 `file_name` 当作新字节定位依据。以 [资源仓库](../../../../src/IM/infra/repositories/message_images.py) 和 [应用存储装配](../../../../src/IM/app.py) 复核路径。新增关联分别分配唯一 `image_id` 和聊天内不冲突的 `source_key`；新字节快照分配不冲突的 `storage_name`，复用已核对字节时可保留其 `storage_name`。不同聊天各自保留独立资源行，沿用现有 fork 的读取方式。

对旧普通上传逐项执行：

1. 从消息 `attachments_json` 和正文中提取本 IM `/im/uploads/<stored_name>`，匹配现场已核实的 IM 地址及相对路径；只处理明确属于本 IM 的资源，不改外部网站 URL。
2. 将原文件原字节纳入目标资源存储，记录 hash、类型、文件名、大小，并按每个已存在的来源聊天建立独立关联。同一文件已有多个聊天／fork 引用时保留全部合法关联，不将它授权给任意持 URL 的人。
3. 将每个聊天内的历史附件描述和正文引用改为该聊天的新受保护 URL。转换清单记录“旧文件＋来源聊天→新资源＋新 URL”，应用不读取它，也不提供旧路径别名服务。
4. 同步改写仍会被展示、重放或继续消费的结构化引用：IM 消息过程／事件／Work 记录、待投递数据，以及 Gateway 的 shadow 补写、Inbox／receipt、Session 工具结果和上下文中的对应资源 URL。仅替换已证明指向同一资源的字段或链接，不修改自然语言历史、工具成功失败事实、调用配对或已消费状态；若相关内容带摘要／digest，按其实际存储契约一并重算和校验。
5. Work 原有正文与嵌入数据保持完整，引用仍指向其原聊天的受保护资源；不能为方便 Work 阅读创建“全员可读”的额外附件关联。

旧文件缺失、哈希不符或无法确定来源聊天时，保留证据并停止该次正式转换，不删除消息或伪造资源。没有任何消息关联的孤立文件留在备份，不公开、不猜测归属。

新版本不挂载 `/im/uploads`，也不提供旧路径重定向、别名或鉴权兼容 handler；旧的独立书签不再可用。用户从已转换的原聊天历史继续预览／下载同一字节。部署完成后给需要保留链接的操作者提供新链接。

正常新上传仍走 `POST /im/v1/uploads`，必须携带 `conversation_id` 与 `file_name`，返回相对的受保护 attachments URL；这与已移除的公开 GET `/im/uploads/...` 是不同入口。部署核对时也确认 `GET /im/v1/conversations/{id}/images/{image_id}` 仍可读取已有图片，避免误把整个 uploads POST 或 images API 一并下线。

## 4. 副本核对与正式切换

在目标结构副本上检查外键与 SQLite 完整性，并比较转换前后的用户／聊天／消息／Agent／节点 ID 集合、历史条数、参与者差异清单、原个人状态、附件字节哈希及全部引用。合法新增成员必须能逐条解释；不能删除旧聊天来通过检查。确认运行数据中没有仍需旧共享偏好或旧公开 URL 服务的有效引用。

先在隔离端口、节点身份和 workspace 中启动目标版本读取副本，禁用复制出的真实外部监听。验证：

- 原账号登录、旧聊天／消息／fork 回看、Agent 与设备管理可用；个人偏好和原未读数量符合转换清单，读到新消息后能正常推进。
- 原聊天成员可打开转换后的附件；非成员持新 URL 仍不能读取；旧公开路径不再返回文件。全局 Work 的已有记录完整，而来源聊天／附件继续按成员访问。
- 正常真人私聊、跨管理归属 Agent 回复与图文交付可用；IM／Gateway 重新注册取得运行凭据，不从旧状态恢复或复用它。无外部第三方发送授权时，不用真实第三方聊天试运行。
- 已完成执行／已投递消息／已处理批准不重复发生；待补写与 Inbox 消费状态保持，恢复工作不依赖旧格式分支。

副本通过后，保持正式现场停写，以同一转换规则和资源清单应用到正式数据；协调切换 IM 与全部有关 Gateway 后再恢复入口。新版本不需要“兼容运行一段时间”。若现场已经转换完毕，只核对结果，不再次重分配资源或覆盖个人状态；半转换现场从完整备份恢复后重做。

## 5. 回退与交付

正式开放前关键检查失败，停止新版本，恢复同一批 IM／附件／Gateway 状态备份及原应用版本，再核对旧系统可用。不能只回退二进制、只恢复数据库或让部分 Gateway 留在新版本。若已经重新开放写入，先停写保全新增数据，再制定回退合并步骤，不能直接用旧快照覆盖新消息。

部署完成交付实际版本、转换对象数量、成员修正与资源映射摘要、备份位置、核对结果和新链接；不把密码、token、数据库、附件或临时执行代码放进 unit。这里的真实执行结果由部署 agent 提交，不能以设计 review 或原型测试代替。

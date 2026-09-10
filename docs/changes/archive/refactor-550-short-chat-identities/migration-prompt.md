# refactor-550 一次性部署迁移 Prompt

请作为部署 Agent，在用户明确授权的部署范围内完成本文件的一次性迁移。先读同目录 motivation.md/design.md、仓库 AGENTS.md、生产部署 skill 与当前真实运行状态。不要把本文当作已获生产部署授权；本文件给出获得授权后的操作要求。新程序不负责兼容旧 ID、旧 mention 或旧 send_message 参数。不要为了迁移在业务代码里增加别名、自动升级、双格式解析或 fallback。

## 目标

- users.id 改为 `u_` + 8位小写字母/数字；conversations.id 改为 `c_` + 8位小写字母/数字。
- 人和 Agent 都使用同一 users.id 做聊天参与者身份；所有群、所有 Session稳定一致。
- agent_profiles.agent_id及Gateway agent_id不变，仍整个IM唯一；node_id、消息/Session/run/调用/附件/渠道ID不变。
- mention统一 `<mention type="user" target_id="u_..."/>`。旧type=agent标签先按agent_id→旧user_id→新user_id转换。
- 模型send_message统一target，目标为user_id或conversation_id；已有custom prompt/上下文中仍会被继续使用的调用示例与目标引用需要同步。
- 迁移保留账号密码、所有聊天、成员、手动标题、消息/附件、未读、Inbox摄取状态、Session和运行状态，不能删除重建来通过验收。

## 1. 盘点并停写

从实际进程 cwd、启动参数、环境变量和配置定位唯一 IM 数据库与所有连接 Gateway 的持久根目录。不得假定当前checkout就是运行目录，也不得使用新worktree的空data目录。生产拓扑以授权时核实结果为准：通常Mini唯一IM，本机与Mini各有Gateway。

记录版本、进程、IM_DB_PATH、Gateway配置/状态路径、workspace、上传文件根目录；记录每个Gateway私钥路径及key_id是否匹配IM中的node_credential_keys，不能打印私钥。盘点未完成执行/投递，停止所有相关Gateway、IM及会写这些数据的任务，确认无残留进程。未迁移的Gateway不得重新接入新IM。

如果现场并未停写、缺少任何Gateway状态/私钥、或现有数据不完整，停止正式迁移，说明具体缺口；不要清空数据或临时解除权限检查。

## 2. 备份与唯一映射

完整备份IM SQLite及uploads、全部Gateway config/state/SQLite、工作区内.nanoassistant（含sessions、chat_history、memory/cron/heartbeat等）、渠道manifest和私钥。SQLite使用backup接口或停机后完整复制，不只拷贝忽略WAL的主文件。备份权限不比原文件宽，记录路径与校验和，不把秘密提交Git。

在副本上生成一次性映射清单：每个旧users.id对应唯一新u_，每个旧conversations.id对应唯一新c_，使用与新代码相同字符集和长度，预先检查集合无冲突。保存old/new及对象类型，供核对和回滚；新程序不读取该文件。已经全部符合新格式的现场应核对迁移记录，不再次分配ID。半迁移现场应恢复备份后重做，不能再生成一套映射拼接。

从users.username=agent:<agent_id>生成agent_id→新user_id映射，保留username原值。映射只来自实际记录，不按显示名猜。

## 3. 迁移IM副本

先用PRAGMA table_info / foreign_key_list与sqlite_master检查真实schema。在副本中一次事务更新用户/会话主键及全部引用：

- users.id/owner_id；conversations.id/owner_id/creator_id；conversation_participants两列；messages.conversation_id/sender_user_id。
- 所有owner_id/user_id/conversation_id引用，包括nodes、profiles、bind_requests、usage_metrics、config/create operations、channel相关表、config boundaries、conversation events、relay_tasks和agent_message_dispatch_log。
- agent_work_sessions、agent_work_items、query snapshots等JSON中的聊天身份、来源、目标、成员及旧工具参数；只改有身份语义的字段，不把agent_id或message_id改为user_id。
- relay/事件/消息过程/系统通知中的结构化引用，conversation preview中的mention；对消息正文仅转换mention标签及明确的本IM聊天链接，不能改写其他自然语言内容。

外键没有ON UPDATE CASCADE时，可在事务外关闭foreign_keys，再在单事务内按映射更新；提交前运行foreign_key_check，任何问题回滚。结束后恢复foreign_keys=ON。不要修改schema来长期适配旧ID。

`agent_message_dispatch_log.target_id`按target_kind转换：user_id、conversation_id转换；agent_id保持。幂等key中明确含旧会话ID的同样同步，确保已投递不会重放。JSON字符串内嵌JSON需按语义递归解析，不能遗漏转义的标签。

## 4. 渠道凭据必须重封装

channel credential的AAD含owner_id。仅替换owner_id或manifest会导致解密失败。

对每个agent_channels记录，使用原Gateway私钥和旧AAD（owner_id/node_id/agent_id/channel_id/provider/credential_revision）解密，再用同一Gateway公钥与新owner_id组成的新AAD加密。可使用仓库现有IM.infra.channel_credentials或PA.channels.channel_credentials公开加解密逻辑，注意PEM/base64私钥格式不同。保持node/agent/channel/provider/revision/key_id不变。秘密仅在内存中流转，不输出到终端、日志或迁移映射。

同步所有仍可能被读取/重试的Gateway manifest、removal/cache与配置操作中的密文和绑定元数据；新旧AAD分别验证旧/新密文，证明凭据内容未变。不要对密文base64、provider的外部user/chat/app ID做文本替换。遇到未知加密/签名绑定先定位其创建和校验逻辑，不能用跳过校验解决。

## 5. 迁移所有Gateway与上下文副本

盘点实际存在的SQLite与JSON/YAML/JSONL/Markdown，不依赖某一个固定目录。典型持久项包括：

- global_agent.sqlite3：inbox_targets、inbox_entries、inbox_read_receipts、page cursors、work_sessions/events；消费seq/receipt/cursor标识不变，聊天target及sender改为同一新user_id，不能清除未读或凭据。存储中的source/reply_target、参与者和内嵌模型页同步。若摘要或指纹绑定被改写内容，按现有实现重新计算并验证摄取状态可恢复。
- session_bindings、group_context_buffer、relay_dedup、external_shadow_sagas、boundary outbox及其他实际发现的持久库：映射IM会话/user引用以及包含它们的复合key；外部平台原生chat/user ID保持。
- Gateway config/state里的绑定用户身份；channel-manifest与credential AAD按上节处理；Agent配置的agent_id/workspace不改。
- 每个Agent已有Session JSONL、chat_history、checkpoint/压缩摘要、metadata/prompt slots、memory、HEARTBEAT.md、cron payload和custom_prompt中会被后续继续使用的本IM身份与mention引用。

不能对整个目录盲目replace agent_id：它在配置/运行中必须保持。只对旧mention标签把业务agent_id转换为新user_id；对send_message调用/示例把参数to改为target，并按原目标类型转换为新user_id/conversation_id。历史tool_calls的call_id、返回配对、UUID链、turn/run/Session ID及工具成功失败事实保留。旧失败记录的说明不用伪造成成功；继续使用的system prompt以新代码实际生成的两种模式通信规则刷新。

全局路由不得被写成某个固定当前群；单Thread的group_participants更新为同一user_id。若某个外部来源没有IM用户记录，不编造可私信的user_id，应保留真实外部来源身份及其不可用性。

## 6. 副本验收后再正式应用

在隔离端口/node/workspace启动新版本与迁移副本，禁用复制出的真实外部channel监听，避免双实例接入。核对：

1. users/conversations/messages/participants数量、内容和关联不丢；foreign_key_check与integrity_check通过；非身份的消息/Session/事件顺序保持。
2. 所有相关库与继续使用的上下文中无旧user/conversation ID引用（备份、映射、原始历史错误说明除外）；剩余agent_id只属于配置/运行或历史事实，不作为新聊天寻址。
3. 新登录成功，账号/Agent/会话历史/手动标题可见；旧JWT subject已变更，通过正常登录重建token，不加入旧token兼容。
4. 两个群查询同一成员得到相同短user_id；info能查未发言成员；用该ID私信成功。
5. 桌面/手机@候选和历史标签显示名字；type=user标签触达正确的MENTION Agent，真人提及不误触发，普通@名字无路由。
6. 单Thread和全局模式各跑真实模型任务：查询成员→群内提及→收到响应；检查实际tool参数和返回，不以模型自述代替证据。
7. 旧Session继续提到既有聊天时使用新引用；未读/部分读取/待处理投递/重启恢复保持，不重复发送。渠道凭据用新AAD验证可解密；实际渠道上线验收只在用户授权范围内。

副本通过后，用同一映射与已验证步骤应用到全部正式停机数据；全套同一版本上线。输出新会话链接，旧书签不提供运行时别名。不要把一次性脚本、备份、映射、秘密或数据库提交仓库。

## 7. 完成与回退

交付：版本、迁移对象数量、备份/映射位置、验证结果与新链接、保留风险。任何关键检查失败时恢复所有IM/Gateway/上下文备份并回到原代码，不能只恢复一台节点或只恢复数据库。无需通过修改产品代码来维持半迁移现场。

## 外部 shadow 身份边界

旧 shadow 消息可能只用 owner_user_id 代记外部用户并存显示名。迁移不把这些代记引用解释为真实发送者映射，不按显示名猜测平台用户 ID。部署后历史读取将其呈现为 external 发送者，无 user_id；已有可靠外部 source_id 元数据则保留，否则省略。真实 IM 用户引用仍随映射更新，外部平台 ID 保持原值。

## 副本演练已确认的检查点

- macOS 复制到 /tmp 时，先统一为 Path.resolve() 后的真实路径（通常是 /private/tmp），再同步 config、IM profile、Gateway global_sessions、Session header 与全部 workspace 引用；不要用会重复添加 /private 的文本替换。workspace 不一致会被既有 global Session 不可变约束拒绝。生产原路径不变时无需搬迁路径。
- 将已有 PA Session 的 prompt slots 按新版本和当前真实成员重新生成，保留用户 custom prompt、时区和 Session ID；单 Thread 需要自己的短 user_id 和名字。Agent 成员旧记录缺 user_id 时用本次全局迁移映射补齐，不能留运行时 fallback。
- 已保存的 Inbox read receipt page、对应模型工具结果和 content digest 必须一起转换；保留 consumed/committed 状态、工具调用配对和原消息 ID。不能只改 digest 或只改 JSONL。
- 已知外部发送者的新消息通过 sender_source_id 保留平台身份；旧 shadow 的 owner 代记不构成平台身份，无法恢复时省略来源 ID。

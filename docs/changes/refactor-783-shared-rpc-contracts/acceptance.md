# refactor-783 产品旅程验收

2026-11-24 JST 在 Air 使用独立 IM 数据库、Gateway、DSH 子进程、工作区和节点身份执行。单聊、计划和配置旅程基于集成版本 `3cdbca334`，入口是 Web 客户端使用的认证 HTTP API 和用户事件 WebSocket。真实模型通过本机 LLM_PROXY 的 `codexOAuth:gpt-6.1-sol` 路由访问。本轮没有检查页面布局。交叉版本的构建与运行见同 unit 的交付记录。

## 从较早回复分支并继续对话 · 通过

daily 模板的三个预置角色都是 Global，为此在隔离配置增加了单线程 Agent `rpc783-reader`。先在源单聊发一个随机口令并等待回复完成，再给它第二个随机口令，随后通过 `POST /im/v1/conversations/{id}/fork` 选第一条完成的回复作分支点。下面两次询问历史的消息都没有附带答案。

| 操作 | 实际产品结果 |
|---|---|
| 在源单聊分别给出共享口令和源单聊专属口令 | 模型依次回复 `EMBER-42834D` 和 `ONYX-83C63D`。分支点对应消息 `709dec9ce8e84ea5a126600e14a9a979`。 |
| 创建分支，读取初始历史，然后问共享口令和源单聊专属口令 | 初始历史只有第一组问答。模型在分支第一轮回复 `EMBER-42834D, UNKNOWN`，消息 ID 为 `99816708cc054aeda3852c56d0c40f24`。 |
| 在分支给出第三个随机口令，再回源单聊询问三个口令 | 分支回复 `IRIS-776CD3`。源模型回复共享口令 `EMBER-42834D`、源单聊专属口令 `ONYX-83C63D`、分支专属口令 `UNKNOWN`。 |
| 再次读取两个时间线 | 各有六条消息。源时间线没有第三个口令，分支时间线没有第二个口令。 |

源单聊 `c_y8j4mbdj` 绑定运行时 session `310bc9f4-6759-4041-a954-92f37d5eb82d`，分支 `c_tcmwfjzp` 绑定 `session-8a47d7ac-293a-4543-a24a-7f9c5821fee9`。以上五次已完成的模型回复均没有工具调用。已核实代理监听进程、节点模型配置、消息正文和持久绑定；本机代理日志目录中没有本轮可匹配的逐请求归档。

## 在 Agent 设置读取计划 · 通过

读取 `GET /im/v1/agents/{agent}/settings/sections/cron`。随后从真实单聊请助手创建一天后的一次性提醒，观察 `schedule_create` 完成，再读取相同设置入口。

| 条件 | HTTP | source | data / error |
|---|---|---|---|
| 在线，第一次读取 | 200 | current | 空数组，error 为 null |
| 在线，计划创建后 | 200 | current | 一个已启用的 `RPC-783-plan`，指令为 `Check the test calendar.` |
| 停止该 Gateway，读取此前未产生计划快照的 `daily-quality` | 200 | unavailable | data 为 null，error.code 为 offline |
| Gateway 仍离线，读取刚才的 `rpc783-reader` | 200 | last_known | 保留原计划，error.code 为 offline |

节点为 `wt-daily-16835`，计划 ID 为 `schedule-a865cd2a-7a50-4e42-946c-8d48fa5864ae`。处理 UTC 时间为 `2026-11-24T16:49:56.025Z` 的定时任务前已回收现场；此处验收创建、读取和离线标记。

## 配置确认中断与恢复 · 通过

实际 IM 服务处理已登录 owner 的配置 PATCH。受控 WebSocket 节点通过正式设备绑定注册，收到 apply 后把候选配置与操作回执写进独立测试文件，在发送回执前断开。应用配置这一侧由受控节点模拟。

1. 原始请求 ID 为 `07328c7b-465b-47e2-9bbd-f9025a4e5991`，operation ID 为 `9c5b94425dc644a7a88b6f15ed39ca88`，初始 profile_version 为 1。
2. 相同设备重新认证，用替换连接送出原 request_id 和有效 applied 回执。IM 回 error，原 PATCH 仍在等待，operation 仍为 pending。再次断线后，PATCH 返回 HTTP 503、`config_apply_pending`。
3. 设备重新上线，owner 读取配置。IM 用新请求 `ad76839d-0e28-47c9-9342-af445c6a0fc9` 查询同一 operation。得到存下的 applied 回执后，HTTP 200 返回 `Confirmed after reconnect`，profile_version 为 2，数据库 operation 为 committed。该次恢复没有重发 apply。

另一次注入中，受控节点在状态查询时显式报告 pending，IM 按现行规则重发原 operation 的 apply。该对照说明断线和对端明确报告 pending 时走不同的恢复路径。

## 历史 Work 和正在等待的普通单聊授权 · 通过

历史 Work 在独立 IM、在线 Node 和 DSH 进程运行的 `apps/im-server/tests/e2e/node-rpc-release.test.ts` 中构造。通过正式 Work 同步入口上传两条 Global 历史待确认项，读取历史能看到两条。对旧 epoch 提交返回 HTTP 409、`request_ended`，IM 没有发命令。对满足当前 owner、epoch、revision、轮次、选项条件的记录，IM 发 `agent.work.permission`，Node 回 `agent.work.permission.result`，两帧都携带 `request_id=current`。回复为 `{ok:false,error:"request_ended"}`，HTTP 同样得到 409。Global 历史记录是重建样本。

普通单聊使用运行中的真实模型。把该测试 Agent 工作区设置为手动审批后，请它写入一个独占测试文件。收到 `permission.request` 时文件不存在；在原聊天提交 `allow_once`。随后按同一消息 ID 从 IM 读取到授权项为 resolved，工具 `write` 带有 `user_allow` 且状态为 completed，最终文件内容精确为 `SOCKET-783-OK`。授权 ID 为 `cd6b75a2-e91b-4091-8ef3-82a761956df5`，工具消息 ID 为 `b46eb411f323465e92355dc5be382f56`。

## 现场条件与证据

- 首轮 Web 构建期间依赖输入发生变化，启动脚本拒绝复用产物。冻结版本重试后，并行负载期间出现 7 秒 catalog 检查超时，日常模板能力同步一度得到 504，额外 Agent 的动态创建一度得到 503。为单聊配置独占测试 Agent 后，已在同一隔离实例重跑官方模板同步和 seed，确认 P、E、Q 和 PA 的 manifest 均已生成。上述超时缺少同等负载的改前对照。
- 模型录制 fixture 的两项既有审批测试在准备配置时返回 503。一项普通 workspace 写入对照走了默认自动授权。实际人工等待、答复和写入结果由上面的手动模式真实模型旅程核实。
- 脱敏原始 HTTP/模型结果、运行时 session 映射和构建摘要保存在本地 `output/refactor-783/acceptance/`。Git 中的表格和身份记录可在本地副本回收后独立审阅。生产资源未参与本次验证。

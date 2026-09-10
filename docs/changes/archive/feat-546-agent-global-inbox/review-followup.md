# PR #287 review 反馈逐项复核

用户要求：“code review agent 给出的问题，不一定对，你自己去一个个检查下，如果真有问题，把问题解决。”沿用本交付会话的直接实施方式，在 `codex/feat-546` 上本人检查和修复，没有以原报告的标签代替判断。

复核起点：`c33df27a6`。原文宣称 30 个候选，但顶部数字相加为 31，正文又含合并描述、UI 与未验证性能项目；本记录按正文拆为 33 个正确性/UI 项与 4 个效率/保留策略项。下表编号只用于本次对账。20 项采纳或部分采纳并修复（其中 08/16 涉及同组分页修复），10 项不成立或属于已确认行为，7 项没有证实当前产品故障、保留现状。

## 裁决及处理

| # | 原报告问题 | 独立核对结论与处理 | 主要证据位置 |
|---|---|---|---|
| 01 | work_mode 冲突使注册异常并遗留假在线连接 | 部分成立，已修复。固定模式冲突本来就应拒绝，不能自动改模式；现在在任何持久状态修改前检查，返回明确错误帧，成功后才发布连接。修正声明可重新注册。 | `GatewayNodePersistence.register`、`GatewaySessions.register`、`test_gateway_im_registration.py` |
| 02 | send_message 拒绝 local: 外部地址 | 成立，已修复工具校验与说明。真实 SDK 工具链先从 Inbox 获取 local: 目标，镜像恢复后由 Gateway 解析，再送达捕获的外部来源。 | `test_send_message_tool.py`、`test_global_external_dispatch.py` |
| 03 | 无 MIME 附件同时进入图片与附件路径、永久 held | 成立，已修复分类。普通文件描述可被持久摄取，后续群回复不再被虚假图片失败拦截。 | `GlobalRunCoordinator._content`、`test_global_dispatch_failures.py` |
| 04 | 全局心跳 busy-skip 丢周期 | 不成立。`runtime-contract.md` §6 明确要求忙时跳过本 tick，不排队、不形成待补跑 Inbox signal；现有测试专门保护同时间 tick 不补跑。 | `test_global_scheduled_work.py` |
| 05 | conversation.query 的 SQLite 错误掐断 WS | 成立，已修复。返回带 request_id 的 storage_unavailable 结果；恢复后仍可查询。 | `test_gateway_work_transport.py` |
| 06 | IM ACK 后 recorder 或外发失败都报发送失败 | 部分成立，已修复记录失败误报。外部渠道真正投递失败仍必须报失败，IM ACK 只表示镜像成功；两处必要投递成功后，记录失败只记日志，不诱导模型重发。 | `test_global_dispatch_failures.py`、`test_global_external_dispatch.py` |
| 07 | 权限超时后迟到 ACK 导致永久 UI/执行分叉 | 部分成立。永久分叉不成立：真实 permission_resolved 经工作日志重放更新页面；修复超时误导，使用 decision_unconfirmed 并显示“可能已生效，等待确认”。不伪造批准成功。 | `test_gateway_work_transport.py`、`permission-card-delayed.test.tsx`、`GlobalWorkRecorder._observe` |
| 08 | 离线 list 游标重连后 KeyError(remote_more) | 成立，已修复。按本地列表快照继续，不能交给合并列表状态机。 | `test_global_history_pagination.py` |
| 09 | 首附件描述超预算产生空页死循环 | 成立，已修复。文本仍按 24000 字符分段；不可拆的超大附件描述独占一页，原 locator 完整保留并推进游标。 | `test_global_inbox_model_protocol.py` |
| 10 | /stop、/compact 执行后 record 失败漏反馈/relay completion | 成立，已修复共有结果记录边界。命令副作用已完成时，记录失败不阻止来源回复和 relay 生命周期完成。停止入口通过真实 Kernel 复现。 | `test_global_gateway_lifecycle.py` |
| 11 | run_id 校验前写 draft:None | 成立，已将身份检查移到群聊复核和草稿记录之前。无效请求既不发消息，也不产生未归属草稿。 | `test_global_dispatch_failures.py` |
| 12 | model_page 丢 history_scope / participants | 部分成立。恢复 history_scope、权限确认时间和列表 history_availability；参与者从简洁 list 中移除是 refactor-550 的已确认协议，完整成员通过 info 提供，不恢复冗余字段。 | `inbox_result.py`、`test_global_history_pagination.py`、refactor-550 design |
| 13 | 全局 Cron fallback 通知落成错误聊天气泡 | 成立，已修复。全局 Cron 只交付最终正文；模型切换仍体现在实际执行的模型/工作记录中，不走旧聊天通知分支。 | `test_global_scheduled_work.py` |
| 14 | permission handler 异常静默吞掉并误报 ended | 成立，已修复。记录带 request_id 的异常日志，返回 permission_decision_failed，与真实不再 pending 分开。 | `test_gateway_work_permissions.py` |
| 15 | Cron 注册工作归属失败逃逸、留下孤儿 session | 部分成立，已修复提交边界：记录失败返回失败提交，既不运行未登记的任务，也不使 scheduler 异常逃逸；恢复后可重试。空的未执行 Session 按既有 create/submit 失败语义保留，未新增删除 API。 | `test_cron_work_registration_failure.py` |
| 16 | read 跨后端 cursor 在断连中失效 | 成立，已修复。远端续页断连返回可重试的来源错误；本地续页重连仍读原本地快照，在线时另做权限校验，不把本地游标发送给 IM。 | `test_global_history_pagination.py` |
| 17 | /stop 等 ensure_agent_runtime 执行完 | 当前所称“等忙碌 run 结束”不成立。主 drain 使用 only_if_idle=True，KernelExecutor 对已有执行直接拒绝运行时替换，不排在忙碌执行之后。未发现需增加第二条抢占锁路径的阻塞。 | `GlobalRunCoordinator._drain`、`InProcessKernelClient.ensure_agent_runtime`、`KernelExecutor.replace_runtime` |
| 18 | 无法定位文案硬编码中文 | 成立，已接现有 i18n，中文/英文显示对应文案。 | `chat-source-navigation.test.tsx` |
| 19 | 原消息定位高亮只加不删 | 成立，已修复。同聊天切换到另一个原消息时只高亮新目标，清除定位参数时取消高亮。 | `chat-source-navigation.test.tsx` |
| 20 | TokenChip 的 workAccounting 死 prop / 中文 | 成立，已删除未使用分支；工作视图已有自己的 WorkUsage，聊天统计保持原语义。 | `token-chip.tsx`、相关前端回归 |
| 21 | phantom queued 永久卡住 | 不成立。持久 submission receipt、run 监控终态、输入未提交重试共同结算唤醒；不是仅由一个 queued 标记决定后续准入。 | `GlobalRunCoordinator._drain/_monitor`、`Kernel.try_submit_idle` |
| 22 | work ACK 的 None==None 误匹配 | 不成立。生产 work append 恒带非空 journal_id，query 恒带非空 request_id；接收端还检查当前 wire owner 的 message_type。 | `GlobalWorkRelay`、`IMConnectionManager._listen_once` |
| 23 | communication context 丢 Agent 参与者 | 不成立。IM 为 Agent 提供 synthetic user_id，describe/info 使用真实 users 身份，Gateway 按对应 participant 映射发送者；不拿 business agent_id 冒充成员 ID。 | `WorkConversationQuery._participants`、`GatewayNodePersistence.register`、refactor-550 身份测试 |
| 24 | append 广播 profile 突然 None | 不成立。append 内已同步验证 profile，当前 root 的再次查询及读取 owner_id 之前无 await；未找到所述删除交错。 | `AgentWorkRepository.append`、`GatewayWork.append` |
| 25 | title_is_custom 只能从 0 变 1 | 不成立，是 feat-548 已确认的“手动改名后不再被外部同步覆盖”语义。 | feat-548 design 决策 3、`ConversationRepository` |
| 26 | SDK workspace_root 未归一化 | 不成立。SessionRef.__post_init__ 统一 expanduser/resolve。 | `agent/core/session/types.py` |
| 27 | realtime_stream 新 guard 丢正常事件 | 不成立。生产 Runtime dispatch 带真实 turn_id/run_id；guard 阻止无执行身份的伪事件，正常工具/消息链覆盖仍通过。 | `realtime_stream.py`、SDK/PA 回归 |
| 28 | digest 对 NaN 无保护 | 未证实当前故障。digest 明确拒绝非有限数；实际内容是文本或受支持多模态块，当前生产 serializer 没有产出这类数值。第三方构造非法块的行为不在本轮扩展。 | `tool_content_digest`、`AgentRuntime._publish_tool_commit` |
| 29 | executor sink.complete 异常静默吞掉 | 机制存在，所称运行卡死未证实。当前 registry 先更新内存状态，再发布可能失败事件；_persist_run_status_entry 是空兼容钩子；executor finally 释放 carrier。未因假设卡死改动内核状态语义。 | `KernelExecutor._run_target`、`RunRegistry._set_status` |
| 30 | 畸形 permission options 导致 HTTP 500 | 未证实生产输入。当前唯一请求 producer 从 PermissionOption 逐项生成 id/label/description，已认证工作日志并非模型任意提交入口。 | Runtime permission requester、`agent_work.decide_permission` |
| 31 | 无 turn_id/run_id 的 permission_request 被丢弃 | 未证实生产输入。当前 producer 附真实 turn_id 和运行标识；Workflow 还保留 execution_session_id。未新增无法归属的审批展示路径。 | Runtime permission requester、`GlobalWorkRecorder._observe` |
| 32 | @ picker 可以选自己 | 不作为 bug。refactor-550 明确列全真实成员；自提及是合法成员标签，不扩大 Agent 命令路由。 | refactor-550 design、MessagePane/MentionPicker |
| 33 | 创建页切换节点重置 work_mode | 成立，已修复。工作模式不是节点能力；切换节点仅重置原本与节点相关的工具/模型选择，保留用户已选模式。 | `agent-create.test.tsx` |
| 34 | Inbox 全表扫描持锁 | 查询确有随缓存量增长的扫描；尚无本次故障或延迟/规模基线。图片网络 IO 已在数据库锁外。保留现状，未借此改分页或消费事务。 | `GlobalInboxService._list/_read_candidates`、`test_global_inbox_images.py` |
| 35 | Kernel._submissions 等字典无界增长 | 进程内保留机制存在，负责同 submission_id 的重试幂等；缺少现实内存压力证据。裁剪还需同时考虑 RunRegistry 与持久 receipt，未加任意 TTL/容量阈值。 | `Kernel.try_submit_idle/get_submission_receipt` |
| 36 | work broadcast 全量重算 view | 成立，已修复。广播调用轻量 revision 查询，view 复用同一取值。相同 fixture 的版本号均为 6，仅为取版本号执行的 SELECT 从 11 次降至 1 次；这是操作次数证据，不是生产延迟指标。 | `AgentWorkRepository.revision`、`GatewayWork.append`、work API 回归 |
| 37 | 快照表没有 TTL | 保留机制存在，当前契约要求持久游标可重开、原快照不漂移，未定义过期时间；没有磁盘故障证据。未擅自过期用户仍可继续读取的游标。 | `inbox_page_cursors`、`agent_work_query_snapshots` |

## 验证范围

自动验证经真实 SQLite、SDK Kernel/工具循环、Gateway HTTP/WS 或对应组件入口实施；故障由明确 seam 注入。外部回复使用捕获 Channel adapter 检查投递内容和目的地，非本轮真实飞书账号发送；本轮没有新调用付费模型、部署生产或改写保留演示的数据。

先运行能复现具体失败的测试，再修复并跑相关回归。UI 低影响清理采用现有组件回归，新增定位导航和权限迟到测试保护可见行为。完整集成与最终 CI 结果见同目录 M1 progress 的本次条目。

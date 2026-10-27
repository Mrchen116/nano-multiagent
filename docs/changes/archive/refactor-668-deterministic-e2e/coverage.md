# E2E 覆盖处置

基线：`8d428779b5ebe0bb0c5c277f2ca5b56c0a303b82`（产品代码基线 `c4ebad992`）。修改前实际收集 32 项（27 critical + 5 environment），14 项依赖 live proxy。首轮修改后收集 27 项（22 critical + 5 environment）；同一 PR 追加发送前摄取新消息旅程后为 28 项（23 critical + 5 environment），全部使用本地 recording provider 或不需要模型。参数化算独立 pytest item。

## 逐项处置

下表的测试文件默认在 `tests/e2e/critical_paths/`，省略 `_critical_path.py` 后缀。相同源文件中的多项按原函数区分；目标文件/函数均可由 catalog 或源码定位。

| 原序号 | 原用例 | 处置 | 保留保护与观察点 |
|---|---|---|---|
| 1 | agent_config_context_continuity / config update | keep | 提取共享 fixture；实际 wire system/tools/history 与配置 preview 对照；修正无关 Feature 前提 |
| 2 | agent_config_context_continuity / historical fork | rewrite-merge | 合并 #14；补源会话后续消息不进入分支、分支消息不进入源请求、历史配置保留 |
| 3 | bash_background_notify | rewrite-merge | 与 #4 共用 `test_background_job_completion_sends_distinct_followup` 的 explicit-background 分支；真 bash/job_output/完成通知与显式 IM send_message |
| 4 | bash_foreground_timeout | rewrite-merge | 删除旧文件；同一后台生命周期测试的 foreground-timeout 分支，真 timeout 转后台与最终通知 |
| 5 | context_compaction_continuity | rewrite-merge | 合并 #27；真实 read 结果与 tool pairing、明确停用默认无摘要插件后的摘要请求、压缩后继续与重启恢复 |
| 6 | create_agent_via_im | rewrite-merge | 合并 #17；保留创建前 capabilities/preview、workspace 创建、注册可聊，再比较重启后真实请求历史前缀 |
| 7 | cron_push | rewrite-merge | 受控 schedule_create，真实一次性时钟与独立 IM 交付；实际请求包含触发内容，无模型规划判断 |
| 8 | gateway_autostart | keep | 真 macOS LaunchAgent crash/stop/bootstrap/disable；等替换进程 ready/connected 后继续；已有平台显式开关，不调用模型；就绪等待修正与复验见下文 |
| 9 | gateway_im_resilience | keep | 真 IM 断连重启及启动顺序；移除无关 live-model 开关；CLI 启动放后台，证明进程存活后恢复 IM，再等待初始化完成 |
| 10 | global_agent_inbox | rewrite-merge | 真实 Inbox check/read 消费事实、同主 session、同 continuable child 修订、真实 child 轨迹与唯一原聊天 dispatch；去掉 CSV 计算能力 |
| 11 | group_chat_directed_mention / A mentions B | rewrite-merge | 与 #12 合为 `test_group_mentions_route_to_peer_and_leave_unmentioned_peer_idle`；受控输出 mention，真实 IM 解析、B 入站与请求正文 |
| 12 | group_chat_directed_mention / unmentioned silent | rewrite-merge | 同 #11 第二个群，A 正常回复且 B 无新请求/消息，验证路由 gate 而非模型自觉保持沉默 |
| 13 | heartbeat_bubble | rewrite-merge | 真 cadence、HEARTBEAT 文件和自动请求/IM 消息；finally 关闭 Feature 并删除文件 |
| 14 | message_fork | rewrite-merge | 删除文件，完整边界补入 #2 的 recording fork；不靠复述暗号 |
| 15 | permission_approval / allow | keep | 人工批准后真实写入和持久 approval 标记，与拒绝分支共享 journey helper |
| 16 | permission_approval / deny | keep | 人工拒绝阻止真实写入及持久拒绝标记；与允许分支不是同一失败原因 |
| 17 | restart_session_continuity | rewrite-merge | 删除文件，合入 #6；比较完整历史结构/顺序，只规范化等价文本编码与 provider cache hints |
| 18 | stop_run | rewrite-merge | 受控工具启动真 shell，等真实 PID 后 /stop，验证 PID 消失、无完成标记、聊天可继续 |
| 19 | stub_stack_lifecycle | keep | 部分栈启动失败时由 provider fixture owner 同时清理 IM 与 stub；不同于 e2e-up 自己的子进程失败 |
| 20 | subagent_failure_isolation | rewrite-merge | 删除文件，合入 #21；实际 child HTTP 失败到父 tool_result，不再以 exit 7 自然语言假定失败 |
| 21 | subagent_foreground | rewrite-merge | `test_foreground_child_output_and_failure_are_isolated` 连续成功/失败/继续，核真实 child session 与父结果 |
| 22 | token_usage | keep | recording usage → 普通气泡及 Global Work 的真实投影；无真实模型 |
| 23 | tool_approval_model / configured model | keep | 独立审核模型跨 Agent 一致与重启应用，不是人工审批决定测试 |
| 24 | tool_approval_model / omitted model | keep | 未配置独立模型时跟随各 Agent 主模型，实际 wire model 断言 |
| 25 | tool_approval_model / classifier failure | keep | 审核无法解析时进入人工审批，不偷偷换模型 |
| 26 | tool_approval_model / unregistered model | keep | 未登记审核模型阻止启动，无模型请求 |
| 27 | tool_call_reply | rewrite-merge | 删除文件，合入 #5；哨兵仅在文件中，独立断言真 read 结果进入后续请求并收到 IM 最终回复 |
| 28 | ../test_daily_acceptance_environment_e2e / daily template | keep | 真 PA/团队 seed、同根重置与跨实例隔离，无聊天任务或模型调用 |
| 29 | ../test_worktree_stack_lifecycle_e2e / isolation | keep | 隔离 identity/workspace、动态 Agent 创建、PID/端口资源释放 |
| 30 | ../test_worktree_stack_lifecycle_e2e / slow readiness | keep | 活着但延迟启动的 IM 在就绪预算内被接受 |
| 31 | ../test_worktree_stack_lifecycle_e2e / child exit | keep | 提前退出及时诊断与清理，不伪装为就绪超时 |
| 32 | ../test_worktree_stack_lifecycle_e2e / readiness deadline | keep | 活进程始终不就绪时报告时限并清理，区别于提前退出 |

## 层级与断言边界

`packages/dsh-integration/tests/history.test.ts`、`trajectory-runs.test.ts`、`cron.test.ts` 使用真实原生运行时；`packages/personal-assistant/tests/heartbeat.test.ts`、`single-thread.test.ts`、`global-agent.test.ts` 是产品模块 seam，部分依赖替身。它们已核对并执行，6 files / 78 tests passed；不把低层替身当作 IM/Node 全栈覆盖。保留的 E2E 均有对应的公开入口、跨进程状态或交付风险。

后台作业完成后的普通 assistant prose 不会自动形成 IM 气泡；测试显式通过 send_message(target=current) 交付实际 job_output，保留原生通知与产品交付两段，未修改产品机制。默认无摘要换窗不产生摘要请求；摘要压缩测试通过公开 plugins API 显式停用 dsh-agent-context 后验证 fallback，未篡改运行时内部状态。

测试不声称验证真实模型理解、规划、概率可靠性或 provider 兼容性。本 unit 没有对生产服务、个人模型配置或产品源码作变更。

审批夹具同步当前默认 Codex Guardian 协议，显式声明本地模型的 context window/reasoning；全部 Agent 使用已登记的本地模型，关闭与 write 路径无关的 Feature。启动失败时复用共享 teardown，避免原夹具泄漏 IM。保留 configured/omitted/invalid reviewer model 和人工 allow/deny 的独立保护。

## 执行证据

窄验证：Context 配置与 fork 2 passed；创建与重启 1 passed；工具/压缩/重启 1 passed；群聊 1 passed；Global/child 2 passed；bash 两模式与 stop 3 passed；cron/heartbeat 2 passed。后续完整 E2E、CI 与独立检查结果在 verification 报告中汇总，不能以 collected 数量声称测试通过。

本地 CI：后端 142 files / 766 tests passed（`pnpm test --maxWorkers=2`）；Python 非 E2E 70 passed；typecheck、iOS runtime、docs-check、ruff 通过。前端全量 108 files / 1031 tests 中首次 2 项在高并发运行下失败，其所在两个文件单 worker 复验 77 passed，其余 106 files 的通过证据保留；`npm audit --audit-level=critical` exit 0（仍报告 5 high、2 moderate、4 low，未修改依赖）。

完整 E2E 显式开启 macOS 路径首次完成 20 passed / 7 failed：5 项是旧审批夹具漏掉 Global Agent 模型；1 项为旧重连脚本同步等待初始化；1 项为自启动驱动没有可靠等待替换进程就绪。审批定向复验 6 passed（70.47s）；重连定向复验 1 passed（17.86s）；macOS 等待修正后 1 passed（38.28s）。最终默认全量 26 passed / 1 skipped（329.26s）；唯一 skip 是原有 macOS 显式开关，该项单独开启后通过。默认全量在 `c71d9dd05` 启动，26 项代码未随 `83a8f4d74` 改动，证据保留至最终代码；macOS 单项验证 `83a8f4d74`。不称单次 27 passed。

### 自启动等待修正

原驱动仅等待新 PID 存活，随后 `/nodes` 可能仍显示旧连接的 online，从而在替换运行时尚未 ready 时进入 stop。首次及独立复验报 `LaunchAgent remained loaded after bootout`（37.23s）。增加真实状态文件的 ready/connected 条件后，还修正了未就绪分支返回 `0` 会被 `kill -0 0` 误判存活的问题：返回空串，由原 PID 正则拒绝。

最终 `NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 python -m pytest -q --basetemp=/tmp/refactor-668-autostart-final tests/e2e/critical_paths/test_gateway_autostart_critical_path.py` 1 passed（38.28s），完整走过 crash/stop/bootstrap/disable。未修改产品代码、关闭宽限或通过重试 stop 掩盖失败，保留全部原断言。此前“产品侧 stop 缺陷”的怀疑未被最终验证支持，不作为已确认缺陷交付。

## PR 内追加：有生成时延的群聊发送复验

用户确认要验证的是发送前消息摄取机制。原 27 项没有这一完整交错时序；低层 `global-agent.test.ts` 的 held-draft 测试不能替代真实 IM/Node/DSH/provider 链路。新增独立 `test_delayed_group_sends_reread_new_messages_before_counting`，不合并到群聊 mention 路由旅程，两者失败原因不同。

四个 Global Agent 的第一次生成请求均已读取原消息，provider 暂停返回 send_message，使四个旧草稿都为“1”。放行 A 后，D 的旧“1”被真实工具拦住；D 读取 A 的正文后在准备“2”时再次暂停。随后 B/C 的旧“1”分别被拦、读取新消息后发送“2”/“3”；最后放行 D 的旧“2”，再次被拦并读取 B/C 正文后发送“4”。断言包括每次 held/sent、实际工具参数、真实消息 ID/正文进入下一次 provider 请求、唯一公开消息序列 1/2/3/4。模型只提供受控响应，Inbox、发送复验与群消息投递均走真实产品代码；未修改产品源码。

首轮夹具漏识别原生 Guardian 的工具签名，未产生第一条发送；按现有 events fixture 的 guardian_* 工具识别修正后，新增用例 1 passed（13.36s）。这是夹具问题，没有判为产品故障。最终窄验证命令 `PYTHONPATH=src python -m pytest -q tests/e2e/critical_paths/test_group_send_revalidation_critical_path.py tests/e2e/critical_paths/test_group_chat_directed_mention_critical_path.py tests/e2e/critical_paths/test_global_agent_inbox_critical_path.py`：3 passed（43.29s），本地日志 `/tmp/refactor-668-send-final.log`；ruff、docs-check 通过，collect-only 28 items。独立 delta 检查见 verification。原 27 项的有效证据保留，新增用例使总数为 28，真实付费模型调用仍为 0。

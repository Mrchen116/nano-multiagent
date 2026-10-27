# 关键路径 e2e 清单（catalog）

> 单一权威的「用户旅程 ↔ 守护它的 e2e 测试 ↔ 归属子系统 ↔ 引入 unit」对账表。引入 unit：feat-421（拆自 #117 的结构性建议，Closes #119）。

测试选择与分层遵循 [`testing.md`](testing.md)；真实进程的端口、config、数据和清理契约见 [`worktree-runtime.md`](worktree-runtime.md)。

这套 E2E 使用真 IM + 真 Node/DSH 子进程，只经 IM 对外 HTTP + WebSocket 驱动。模型响应来自隔离的本地 recording provider，或场景本身不需要模型；**不访问真实 LLM proxy，不需要模型账号或额度**。验证对象是实际出站请求、工具副作用、公开消息/Work 和进程状态，不是模型能否理解自然语言。测试策略见 [testing](testing.md)。

```bash
scripts/e2e-critical.sh                 # 全部确定性关键路径
scripts/e2e-critical.sh -m "not slow"   # 排除 cron/heartbeat 时间驱动路径
scripts/e2e-critical.sh -k context     # 选择受影响场景
# macOS 登录服务生命周期另显式开启（仍不调模型）：
NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 scripts/e2e-critical.sh -k autostart
# 原生运行时知识回归（不等于完整 IM E2E）：
scripts/e2e-self-evolution.sh
```

先按 [worktree runtime](worktree-runtime.md) 准备当前 tree 的构建和 Python 环境。每个 recording 栈重写所有 provider URL 到本轮端口，配置中的模型名称只是协议路由标签；`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E` 不再控制此套件。单独启动 `e2e-up.sh` 仍是环境工具，不会自动运行测试；手工模型能力评测使用 `--profile daily` 并限定任务，不属于本套工程回归。

## 登记纪律

**新增一个关键特性时，必须在下表「v1 必保活」段登记一行，并配一条能跑的守护测试。** 每条「必保活」路径都必须引用至少一个能被 pytest 收集的守护测试；CI 通过 `scripts/docs-check` 校验表格结构、计数和引用关系。路径是否应纳入清单、测试是否真正覆盖该旅程，由变更评审和按需 E2E 验收判断。当前还没有 e2e 兜底的关键路径，诚实登记在「已知缺口 backlog」段，而非默认为已覆盖。

## v1 必保活路径

> 「守护测试」列指向 `tests/e2e/critical_paths/` 下的测试函数。当前必保活为 19 条用户旅程；多个旅程可由同一连贯测试保护，路径数不等于 pytest 用例数。全部使用本地受控模型或无需模型。

| # | 用户旅程 | 守护测试 | 归属子系统 | 引入 unit |
|---|---|---|---|---|
| 1 | **工具调用后回复**——发一条需 agent 调工具才能答的消息，收到带正确结果的回复（覆盖工具调用主循环） | `test_context_compaction_continuity_critical_path.py::test_tool_history_compacts_and_survives_gateway_restart` | gateway（`docs/specs/gateway/spec.md`）+ DSH integration（`docs/specs/gateway/service-lifecycle.md`） | feat-421 |
| 2 | **bash 前台超时**——agent 跑会超时的前台 bash，session 不卡死、用户最终仍收到回复 | `test_bash_background_notify_critical_path.py::test_background_job_completion_sends_distinct_followup`（foreground-timeout 参数） | DSH integration（`docs/specs/gateway/service-lifecycle.md`） | feat-421 |
| 3 | **bash 后台通知**——agent 把耗时 bash 丢后台，作业完成后用户**再**收到一条带结果的跟进消息 | `test_bash_background_notify_critical_path.py::test_background_job_completion_sends_distinct_followup`（explicit-background 参数） | gateway + DSH integration | feat-421 |
| 4 | **subagent**——agent 派前台子 agent，回复带回子 agent 产出；子 agent 失败被隔离不拖垮常驻进程 | `test_subagent_foreground_critical_path.py::test_foreground_child_output_and_failure_are_isolated` | DSH integration（`docs/specs/gateway/service-lifecycle.md`） | feat-421 |
| 5 | **/stop**——对正在跑的 run 发 `/stop`，运行被中止、状态可见为已停 | `test_stop_run_critical_path.py::test_stop_aborts_active_run` | gateway + DSH integration | feat-421 |
| 6 | **cron**（slow）——到点的定时任务自动推一条消息到 IM 对话 | `test_cron_push_critical_path.py::test_cron_job_auto_pushes_message`（`@pytest.mark.slow`） | gateway（`docs/specs/gateway/spec.md`） | feat-421 |
| 7 | **Heartbeat 主动冒泡**（slow）——已建立聊天的 Agent 按 `.nanoassistant/HEARTBEAT.md` 指令，在 cadence 到点主动交付；受控 provider 与原生运行时，case 结束关闭心跳 | `test_heartbeat_bubble_critical_path.py::test_heartbeat_bubbles_actionable_message`（`@pytest.mark.slow`） | runtime + gateway + im | refactor-581 |
| 8 | **群聊双向定向 @**——用户 `@A` 让 A 去 `@B` 办事：用户先看到 A 应答且 A 定向 @了 B，再看到 B 因被点名而应答；未被点名者不抢话 | `test_group_chat_directed_mention_critical_path.py::test_group_mentions_route_to_peer_and_leave_unmentioned_peer_idle` | im（`docs/specs/im/spec.md`）+ gateway | feat-421 |
| 9 | **权限审批 approve/deny**——审批模型返回无法解析的判定后，用户在 IM 收到等待批准提示（recording provider + 真 Node/IM）；批准则 run 继续产出结果，拒绝则该工具不执行且 run 据此收口 | `test_permission_approval_critical_path.py::test_permission_approve_lets_tool_run` + `::test_permission_deny_blocks_tool` | gateway + DSH integration + im | feat-421 |
| 10 | **进程重启后会话续接**——发消息建立上下文后**重启 Gateway 进程**，再发消息 实际 provider 请求保留重启前的历史和顺序 | `test_create_agent_via_im_critical_path.py::test_agent_created_via_im_preserves_context_across_restart` | gateway（`docs/specs/gateway/spec.md`） | feat-421 |
| 11 | **经 IM 创建 agent 并落地可聊**——在 IM 配置中心新建一个 agent，它在节点落地 workspace 并上线，随后能跟它聊出回复 | `test_create_agent_via_im_critical_path.py::test_agent_created_via_im_preserves_context_across_restart` | im（`docs/specs/im/spec.md`）+ gateway | feat-421 |
| 12 | **从消息 fork 出分支单聊**——在一条已完成 agent 回复上 fork，进入同 agent 的新分支单聊，分支实际 provider 请求保留到 fork 点的历史、不含 fork 点之后的消息，原会话保持不变（两线独立） | `test_agent_config_context_continuity_critical_path.py::test_fork_after_config_update_preserves_historical_runtime` | im（`docs/specs/im/spec.md`）+ gateway + DSH integration | feat-445 |
| 13 | **Gateway-IM 连接韧性**——节点 online 后 kill IM 再重启，**无需手动重启 Gateway**节点自动回 online；先起 Gateway（IM 未起）Gateway 不崩、IM 起后节点变 online（覆盖断网/休眠/IM 重启/启动早于 IM 四类瞬态故障，经 `/im/v1/nodes` 观察） | `test_gateway_im_resilience_critical_path.py::test_gateway_recovers_node_online_after_transient_faults`（驱动 `scripts/e2e-resilience.sh`；**不门控 LLM proxy**，连接韧性不调模型） | gateway（`docs/specs/gateway/spec.md`） | bugfix-446 |
| 14 | **Agent 配置更新后上下文连续**——既有直聊先形成历史，再改 tools 等运行配置，回到同一聊天继续；Agent 仍带着改配置前的上文（不因换配置开空 session）。**fake LLM**：真 IM + 真 Gateway + recording Anthropic stub，断言最后一次上游请求 messages 同时含配置变更前后用户句；**不门控 / 不调用** `:4000` 真 proxy | `test_agent_config_context_continuity_critical_path.py::test_agent_config_update_keeps_chat_context_with_stub_llm` | gateway + DSH integration + im | bugfix-471 |
| 15 | **原生 token 用量**——供应商的独立 input、cache input 和 output 经真实 Node/IM，到聊天气泡和持久 Global Work 统计一致；缺失计数不编造为零。**fake LLM** | `test_token_usage_critical_path.py::test_native_token_usage_reaches_bubble_and_work` | runtime + gateway + im | refactor-581 |
| 16 | **含工具历史的压缩与重启连续**——真实执行 read 后，显式停用默认无摘要换窗插件后，经公开 `/compact <focus>` 生成摘要；随后追问与进程重启均保留原目标。recording fixture 核对配对工具和摘要后的实际请求。**fake LLM** | `test_context_compaction_continuity_critical_path.py::test_tool_history_compacts_and_survives_gateway_restart` | runtime + gateway + im | refactor-581 |
| 18 | **macOS Gateway 常驻**——默认启动安装用户 LaunchAgent；crash 后 PID 更新并重新 online；人工 stop 本登录不重拉但稳定定义可再次 bootstrap；配置关闭后只运行 detached 且定义消失。**不调用真 LLM**，使用隔离 IM/config，显式开关 `NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1` | `test_gateway_autostart_critical_path.py::test_macos_gateway_autostart_crash_stop_login_and_disable`（驱动 `scripts/e2e-gateway-autostart.sh`；仅 macOS） | gateway（`docs/specs/gateway/service-lifecycle.md`） | feat-542 |
| 19 | **Global Agent 跨聊天持续统筹（J2）**——A 的任务真实委派后台子 Agent；B 修订正文经 Inbox 摄取后跟进同一子 Agent；工作区标记释放后仅显式投递修订结果到 A，主 Session 不变且内部过程不进入聊天。**recording provider**：驱动真实 Inbox/child/send_message，核对请求正文、同一子 Agent 跟进及实际投递，不评估模型自主规划和计算能力 | `test_global_agent_inbox_critical_path.py::test_global_agent_reads_cross_chat_amendment_and_follows_same_child` | gateway + DSH integration + im | feat-546 |
| 20 | **群聊发送前摄取新消息**——4 个 Global Agent 同时开始生成旧“1”，通过 provider 等待点制造真实时延；先发出的消息使其他旧发送被拦截，正文经 Inbox 进入实际模型请求后才重发，最终为 1、2、3、4；含读取后再次来消息、再次拦截 | `test_group_send_revalidation_critical_path.py::test_delayed_group_sends_reread_new_messages_before_counting` | gateway + DSH integration + im（`docs/specs/gateway/global-agent.md`） | refactor-668 |

## 已知缺口 / backlog（暂无 e2e 兜底）

下列关键路径在各包契约层已声明，但**当前尚无经 Gateway 进程的 e2e 守护**——显式登记在册，留待后续 unit，不被默认为已覆盖。

| 关键路径 | 为什么暂缺 | 归属子系统 | 计划 |
|---|---|---|---|
| **前端 UI smoke**（Playwright，稳定/桩后端、无真 LLM） | 本套件走 API 级（IM HTTP/WS），不驱动浏览器；真 LLM × 全 UI × 多路径是测试反模式（design 决策 7）。前端是被动薄客户端，但其自身回归本 unit 不覆盖 | im/frontend | **独立 unit**（稳定后端 + 桩 LLM 的 UI 冒烟） |
| **断线重连补发** | 用户流 WS 断后 resume 补发事件的端到端时序，本 unit 未覆盖 | im（`docs/specs/im/spec.md`） | 后续 unit |
| **附件透传** | 用户上传附件 → agent 读到 → 回复引用，端到端链路 | im + gateway + DSH integration | 后续 unit |
| **provider 切换** | 同 agent 切换 LLM provider 后仍正常应答 | gateway + DSH integration | 后续 unit |
| **节点上下线看板** | 节点 online/offline 状态变更在 IM 看板/事件流的端到端反映 | im（`docs/specs/im/spec.md`） | 后续 unit |
| **群聊裸 `/stop` 绕 @ 门控中断**（feat-430） | 群里某 agent `group_reply_policy=MENTION` 且正在运行时，用户发裸 `/stop`（不 @）仍中断它；未运行群成员无副作用（不发 no-op ack、不建 session）。本 unit 经单测（`test_gateway_stop_command.py::test_bare_stop_in_group_mention_policy_interrupts_running_agent` / `::test_bare_stop_in_group_multi_agent_stops_only_running_no_noise`）+ 真栈手工 live 验收覆盖，未落经 Gateway 进程的自动化 e2e | gateway（`docs/specs/gateway/spec.md`） | 后续 unit（并入 /stop e2e #5 的群聊变体） |
| **token 缓存命中率展示**（feat-439-M1） | token 气泡详情「缓存命中 X (Y%)」整轮口径渲染，属 Web UI 级；本 unit 经 API/真栈浏览器临时验收 + 单测/前端组件测覆盖，未落 Playwright UI smoke | im/frontend（`docs/specs/im/spec.md`） | 同「前端 UI smoke」独立 unit |
| **thinking 过程时间线展示**（feat-439-M2） | 助手气泡内「过程」盘把整轮多段思考与工具按真实时序混排、逐段可展开、刷新可回看、外部 channel 不带思考；属 Web UI 级，本 unit 经真栈浏览器临时验收 + reducer/组件测 + gateway 出站回归覆盖，未落 Playwright UI smoke | im/frontend（`docs/specs/im/spec.md`） | 同「前端 UI smoke」独立 unit |
| **Feishu 1:1 外部 channel 主路径**（feat-447） | 第三方平台真 app / 真 WebSocket / 真 LLM 组合依赖专用凭据与网络，不纳入默认 `e2e-critical`；使用 `e2e-up.sh --feishu` + `e2e-feishu-probe.py` 运行隔离真实入口，凭据和命名 CLI profile 见 [`worktree-runtime.md`](worktree-runtime.md#专用-feishu-e2e-profile) | gateway + im（`docs/specs/gateway/spec.md`, `docs/specs/im/spec.md`） | 后续 unit：把稳定的外部 fixture 接入默认 critical suite |
| **Feishu 群聊背景上下文与 @Bot 触发**（feat-447） | 普通群消息投递依赖 Feishu app scope `im:message.group_msg`；缺 scope 时只能诊断而不能强制平台投递。本 unit 已覆盖解析、scope warning、history catch-up 和 live 验收，未落稳定 e2e-critical | gateway + im | 后续 unit：external-channel 群聊 fixture / 真 app 凭据矩阵 |
| **Feishu 原生权限审批卡片**（feat-447） | 飞书 interactive card 点击回调需要真平台回调/长连接事件；当前由 Gateway 权限管线单测覆盖，未有真 Gateway e2e 自动化 | gateway + DSH integration + im | 后续 unit：外部 channel approval e2e |

原 Python self-evolution replay fixture 随旧内核退役。原生 DSH profile 与 product handoff 的覆盖见 `packages/dsh-integration/tests/knowledge.test.ts`、`packages/personal-assistant/tests/knowledge.test.ts`；完整 IM journey 目前仅保留 change 内实际运行证据，尚未登记为永久自动 E2E。

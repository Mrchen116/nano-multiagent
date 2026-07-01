# 关键路径 e2e 清单（catalog）

> 单一权威的「用户旅程 ↔ 守护它的 e2e 测试 ↔ 归属子系统 ↔ 引入 unit」对账表。
> 引入 unit：feat-421（拆自 #117 的结构性建议，Closes #119）。

这套 e2e **经真 Gateway 进程**（真 IM + 真 Gateway 子进程 + 真 LLM proxy），把测试当成
一个真实 IM 用户，只走 IM 对外 HTTP + WebSocket 接口发消息/读回复，断言只看「用户在 IM
上能否观察到预期结果」。它平时不跑（真 LLM 烧 token），**想测时一条命令全跑**：

```bash
scripts/e2e-critical.sh                 # 跑全部关键路径
scripts/e2e-critical.sh -m "not slow"   # 跳过时间驱动（cron/heartbeat）路径
```

缺本地 LLM proxy（`:4000/health`）或缺 `~/.nano-assistant/config.yaml`（含 `llm:` 段）时，
套件**干净 skip**而非报错。失败时 IM/Gateway 日志 tail 进报告，可定位断在哪一段。

## 登记纪律

**新增一个关键特性时，必须在下表「v1 必保活」段登记一行，并配一条能跑的守护测试。**
每条「必保活」路径都必须对应一个真实存在、能跑的测试函数；清单与测试一旦 drift，门禁不过。
当前还没有 e2e 兜底的关键路径，诚实登记在「已知缺口 backlog」段，而非默认为已覆盖。

## v1 必保活路径（13 条）

> 「守护测试」列指向 `tests/e2e/critical_paths/` 下的测试函数，均经真 Gateway 进程真跑通过。
> heartbeat（原 #7）端到端不冒泡（真实产品 bug #126），其 e2e 旅程已写但标
> `@pytest.mark.xfail(strict=True, #126)`（真跑 → 预期 XFAIL；#126 修复后转 XPASS 即 strict
> 报错提醒去 xfail），暂移至下方 backlog 段——故 v1 必保活当前为 12 条。

| # | 用户旅程 | 守护测试 | 归属子系统 | 引入 unit |
|---|---|---|---|---|
| 1 | **工具调用后回复**——发一条需 agent 调工具才能答的消息，收到带正确结果的回复（覆盖工具调用主循环） | `test_tool_call_reply_critical_path.py::test_tool_call_then_reply_carries_sentinel` | gateway（`docs/specs/gateway/spec.md`）+ kernel（`docs/specs/kernel/spec.md`） | feat-421 |
| 2 | **bash 前台超时**——agent 跑会超时的前台 bash，session 不卡死、用户最终仍收到回复 | `test_bash_foreground_timeout_critical_path.py::test_foreground_bash_timeout_still_replies` | kernel（`docs/specs/kernel/spec.md`） | feat-421 |
| 3 | **bash 后台通知**——agent 把耗时 bash 丢后台，作业完成后用户**再**收到一条带结果的跟进消息 | `test_bash_background_notify_critical_path.py::test_background_bash_completion_sends_followup` | gateway + kernel | feat-421 |
| 4 | **subagent**——agent 派前台子 agent，回复带回子 agent 产出；子 agent 失败被隔离不拖垮常驻进程 | `test_subagent_foreground_critical_path.py::test_foreground_subagent_carries_back_output` + `test_subagent_failure_isolation_critical_path.py::test_failed_subagent_isolated_from_main_process` | kernel（`docs/specs/kernel/spec.md`） | feat-421 |
| 5 | **/stop**——对正在跑的 run 发 `/stop`，运行被中止、状态可见为已停 | `test_stop_run_critical_path.py::test_stop_aborts_active_run` | gateway + kernel | feat-421 |
| 6 | **cron**（slow）——到点的定时任务自动推一条消息到 IM 对话 | `test_cron_push_critical_path.py::test_cron_job_auto_pushes_message`（`@pytest.mark.slow`） | gateway（`docs/specs/gateway/spec.md`） | feat-421 |
| 8 | **群聊双向定向 @**——用户 `@A` 让 A 去 `@B` 办事：用户先看到 A 应答且 A 定向 @了 B，再看到 B 因被点名而应答；未被点名者不抢话 | `test_group_chat_directed_mention_critical_path.py::test_human_mentions_a_then_a_mentions_b` + `::test_unmentioned_agent_stays_silent` | im（`docs/specs/im/spec.md`）+ gateway | feat-421 |
| 9 | **权限审批 approve/deny**——agent 要调需许可的工具，用户在 IM 收到等待批准提示；批准则 run 继续产出结果，拒绝则该工具不执行且 run 据此收口 | `test_permission_approval_critical_path.py::test_permission_approve_lets_tool_run` + `::test_permission_deny_blocks_tool` | gateway + kernel + im | feat-421 |
| 10 | **进程重启后会话续接**——发消息建立上下文后**重启 Gateway 进程**，再发消息 agent 仍记得重启前的上文 | `test_restart_session_continuity_critical_path.py::test_context_survives_gateway_restart` | gateway（`docs/specs/gateway/spec.md`） | feat-421 |
| 11 | **经 IM 创建 agent 并落地可聊**——在 IM 配置中心新建一个 agent，它在节点落地 workspace 并上线，随后能跟它聊出回复 | `test_create_agent_via_im_critical_path.py::test_agent_created_via_im_lands_and_replies` | im（`docs/specs/im/spec.md`）+ gateway | feat-421 |
| 12 | **从消息 fork 出分支单聊**——在一条已完成 agent 回复上 fork，进入同 agent 的新分支单聊，分支带着到 fork 点的记忆（基于历史追问答得对）、不含 fork 点之后的消息，原会话保持不变（两线独立） | `test_message_fork_critical_path.py::test_fork_branch_carries_memory_and_leaves_source_intact` | im（`docs/specs/im/spec.md`）+ gateway + kernel | feat-445 |
| 13 | **Gateway-IM 连接韧性**——节点 online 后 kill IM 再重启，**无需手动重启 Gateway**节点自动回 online；先起 Gateway（IM 未起）Gateway 不崩、IM 起后节点变 online（覆盖断网/休眠/IM 重启/启动早于 IM 四类瞬态故障，经 `/im/v1/nodes` 观察） | `test_gateway_im_resilience_critical_path.py::test_gateway_recovers_node_online_after_transient_faults`（驱动 `scripts/e2e-resilience.sh`；**不门控 LLM proxy**，连接韧性不调模型） | gateway（`docs/specs/gateway/spec.md`） | bugfix-446 |

## 已知缺口 / backlog（暂无 e2e 兜底）

下列关键路径在各包契约层已声明，但**当前尚无经 Gateway 进程的 e2e 守护**——显式登记在册，
留待后续 unit，不被默认为已覆盖。

| 关键路径 | 为什么暂缺 | 归属子系统 | 计划 |
|---|---|---|---|
| **heartbeat 主动冒泡**（slow，原 v1 #7） | 默认 model K2.6 下端到端不冒泡（真实产品 bug，见 **#126**）：心跳 prompt 末句 HEARTBEAT_OK 触发句压过 HEARTBEAT.md 指令，model 回 HEARTBEAT_OK、投递被 observer 抑制。已穷尽 K2.6/doubao/gpt-5.5 三组确认非 model 选型可解。e2e 旅程已写（`test_heartbeat_bubble_critical_path.py`）并标 `@pytest.mark.xfail(strict=True, #126)`（真跑 XFAIL 作活复现资产）；bugfix 修复后转 XPASS → 去 xfail、移回 v1 | gateway（`docs/specs/gateway/spec.md`） | **bugfix #126**（修复后回 v1 必保活） |
| **前端 UI smoke**（Playwright，稳定/桩后端、无真 LLM） | 本套件走 API 级（IM HTTP/WS），不驱动浏览器；真 LLM × 全 UI × 多路径是测试反模式（design 决策 7）。前端是被动薄客户端，但其自身回归本 unit 不覆盖 | im/frontend | **独立 unit**（稳定后端 + 桩 LLM 的 UI 冒烟） |
| **断线重连补发** | 用户流 WS 断后 resume 补发事件的端到端时序，本 unit 未覆盖 | im（`docs/specs/im/spec.md`） | 后续 unit |
| **上下文压缩恢复** | 长会话触发压缩后上下文连续性的端到端验证 | kernel（`docs/specs/kernel/spec.md`） | 后续 unit |
| **附件透传** | 用户上传附件 → agent 读到 → 回复引用，端到端链路 | im + gateway + kernel | 后续 unit |
| **provider 切换** | 同 agent 切换 LLM provider 后仍正常应答 | gateway + kernel | 后续 unit |
| **节点上下线看板** | 节点 online/offline 状态变更在 IM 看板/事件流的端到端反映 | im（`docs/specs/im/spec.md`） | 后续 unit |
| **群聊裸 `/stop` 绕 @ 门控中断**（feat-430） | 群里某 agent `group_reply_policy=MENTION` 且正在运行时，用户发裸 `/stop`（不 @）仍中断它；未运行群成员无副作用（不发 no-op ack、不建 session）。本 unit 经单测（`test_gateway_stop_command.py::test_bare_stop_in_group_mention_policy_interrupts_running_agent` / `::test_bare_stop_in_group_multi_agent_stops_only_running_no_noise`）+ 真栈手工 live 验收覆盖，未落经 Gateway 进程的自动化 e2e | gateway（`docs/specs/gateway/spec.md`） | 后续 unit（并入 /stop e2e #5 的群聊变体） |
| **token 缓存命中率展示**（feat-439-M1） | token 气泡详情「缓存命中 X (Y%)」整轮口径渲染，属 Web UI 级；本 unit 经 API/真栈浏览器临时验收 + 单测/前端组件测覆盖，未落 Playwright UI smoke | im/frontend（`docs/specs/im/spec.md`） | 同「前端 UI smoke」独立 unit |
| **thinking 过程时间线展示**（feat-439-M2） | 助手气泡内「过程」盘把整轮多段思考与工具按真实时序混排、逐段可展开、刷新可回看、外部 channel 不带思考；属 Web UI 级，本 unit 经真栈浏览器临时验收 + reducer/组件测 + gateway 出站回归覆盖，未落 Playwright UI smoke | im/frontend（`docs/specs/im/spec.md`） | 同「前端 UI smoke」独立 unit |

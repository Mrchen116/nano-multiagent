# refactor-489-M8: assistant-runtime-delivery — Tasks

> 对齐: ../design.md 的 refactor-489-M8 行与决策 1、2

## 目标

保留 Gateway、channel、relay、inbound、session 与投递结果的最低层真实保护；删除完全重复、只守退役实现或源码形态的测试，并把仍有风险的高层重复断言收敛到当前行为 seam。

## 退出标准

- [x] Gateway/channel/relay/inbound/session/投递结果的当前行为与公开边界仍由最低合适层保护。
- [x] 完全重复的测试、退役实现缺席断言、源码扫描和模型提示词逐字快照已删除或改写。
- [x] 进程关闭、并发、ACK/reconnect、durable outbox、session 恢复和投递终态等真实时序/服务风险未因清理丢失。
- [x] M8 全量最窄门禁通过，且无产品代码、current spec 或相邻 milestone 文件变更。

## 测试策略

- 被测行为（来自退出标准）：Gateway/channel/relay/inbound/session/投递结果仍有最低 seam 保护；重复和实现细节断言退出永久套件；真实时序与服务风险保持覆盖。
- 已有测试在：M8 派发范围内 89 个 Python 测试文件（基线 634 tests）；只改写/合并现有文件，不新建测试文件。
- 落层/目录/marker：`tests/unit/`，marker：无；真实进程/E2E 风险继续由 M13 与现有更高层门禁拥有，本 milestone 不复制。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：AST 完全重复函数清单、源码扫描命中清单与 collect-only 对账，仅记录结果，不提交临时脚本。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| channel 生命周期与外部会话 key | `test_gateway_channel_and_session.py`、`test_gateway_pipeline_channel.py`、`test_inbound_pipeline_agent_sessions.py` | rewrite-merge | 聚合文件 4 项与按 seam 文件完全重复；外部 identity key 合入 channel/session-key owner 后删除聚合文件 | 两个 owner 文件 + M8 全量 |
| IM 鉴权连接头 | `test_gateway_connect_once.py`、`test_gateway_im_auth.py` | rewrite-merge | 三项逐字重复，仅保留 `test_gateway_im_auth.py`；ConfigSyncClient 独立行为保留 | 两个相关文件 + M8 全量 |
| relay 适配、去重、上游帧 | `test_gateway_im_relay.py`、`test_gateway_relay_dedup.py`、`test_gateway_web_relay_adapter.py`、`test_gateway_upstream_reporter.py` | rewrite-merge | 13 项在专属 owner 中完全重复；保留 authenticated-owner shadow sync 的唯一保护，去重容量/重启改从公开结果观察 | relay 四文件 + M8 全量 |
| inbound session metadata 与生命周期 | `test_inbound_pipeline_metadata.py`、`test_inbound_pipeline_session_metadata.py`、`test_inbound_pipeline_session.py`、`test_inbound_pipeline_agent_sessions.py` | rewrite-merge | 一个文件是另一文件的完全子集；另有同文件 lifecycle 重复和跨文件 agent refresh 重复 | inbound 相关文件 + M8 全量 |
| group gate、NO_REPLY、离线外部主路径 | `test_gateway_im_integration.py` 与 `test_gateway_pipeline_no_fanout.py`、`test_gateway_pipeline_sender_prefix.py`、`test_inbound_pipeline_session.py`、`test_session_run_coordinator_terminal.py` | rewrite-merge | 聚合文件只保留 reply-to-agent 与无 IM 主路径的独立风险；其余高层断言由更窄 owner 覆盖 | 相关 pipeline/coordinator 文件 + M8 全量 |
| 图片解析、失败反馈与后续会话可用 | `test_gateway_image_inbound.py`、`test_image_attachment_resolver.py` | rewrite-merge | MIME/格式判断在 resolver 最低层拥有；pipeline 只保留成功接线、失败映射与失败后下一轮可用 | 两文件 + M8 全量 |
| 外部可见回复不泄漏 thinking | `test_gateway_web_relay_adapter.py::test_external_channel_outbound_excludes_thinking` | rewrite-merge | 原测试自己从 event 取 content，未经过 observer；将 reasoning 输入并入真实 external bubble mirror seam | relay lifecycle + adapter 文件 |
| runtime delivery 任务关闭与取消 | `test_runtime_delivery_task_tracker.py` | rewrite-merge | 保留 drain/cancel 行为，删除 `inspect.getsource` 禁止 `create_task` 的源码形态检查 | task tracker + shutdown graph |
| typed delivery context | `test_gateway_relay_lifecycle.py` | rewrite-merge | 保留 typed target、收据、终态和用户可见投递；删除 legacy dict 镜像与 compose 源码扫描断言 | relay lifecycle + streaming |
| session binding 持久化与恢复 | `test_persistent_session_binding_store.py`、`test_gateway_build_runtime.py` | rewrite-merge | 保留 bind/recover、workspace-aware binder 与 composition 结果；删除兼容 setter 不被调用、符号可导入等退役路径检查 | store、binder、composition 文件 |
| Gateway 关闭顺序与单次 kernel close | `test_gateway_shutdown_order.py`、`test_gateway_shutdown_resource_graph.py`、`test_gateway_shutdown_timeout_isolation.py` | rewrite-merge | 丰富 resource graph 已覆盖顺序；旧文件只保留 kernel 单次异步关闭的独立风险，删除参数存在/private attr 等内部断言 | 三个 shutdown 文件 |
| `send_message` 产品工具 | `test_send_message_tool.py` | rewrite-merge | 保留 presenter、HTTP dispatch、live endpoint、校验与回执；删除 singleton/bind_dispatcher 缺席断言，并合并重复成功调用 | 单文件 + internal dispatch |
| terminal run status SDK 边界 | `test_terminal_run_statuses.py` | rewrite-merge | 公共 SDK 值保留一项；删除“必须从某内部 enum 推导”和 historical 双重断言 | 单文件 + text runner |
| 工具拒绝反馈语义 | `test_reject_messages.py` | rewrite-merge | 保留 subagent/user/auto/空原因的语义映射，删除 CC 原文、历史参数名和完整提示词快照 | 单文件 |
| NDJSON 文本运行入口 | `test_text_runner.py` | keep | 直接观察完成/失败/取消/串流错误的输出与退出码，是当前 CLI 自动化入口最低保护 | 单文件 |
| ACK/reconnect、channel 状态、durable outbox、shadow saga、session coordinator、shutdown deadline | M8 其余 channel/IM/runtime/session 测试 | keep | 直接保护仍存在的网络所有权、持久恢复、并发与终态风险；不是由纯函数断言可替代的重复层 | M8 全量 89 文件清单（删改后重算） |

## Roadpoints

### R1 — 收敛完全重复测试

- 状态: DONE
- 步骤: 按 AST 完全重复清单合并 channel/auth/relay/inbound/session owner，删除聚合或子集文件。
- 验证: AST 重复清单不再命中已处置项；相关文件 pytest 通过。

### R2 — 移除退役实现与源码形态断言

- 状态: DONE
- 步骤: 删除 source scan、private absence、compat setter、historical derivation 与模型提示词逐字快照；把仍存在的风险改从公开结果观察。
- 验证: 源码扫描命中清零；send_message、delivery context、terminal/reject 最窄测试通过。

### R3 — 把高层重复收敛到最低行为 seam

- 状态: DONE
- 步骤: 收敛 group/offline pipeline、图片 resolver/pipeline、external thinking mirror 与 shutdown graph 重复，保留独立连接风险。
- 验证: 相关分簇 pytest 全绿；时序、恢复、投递终态节点仍可收集。

### R4 — 全量门禁与证据对账

- 状态: DONE
- 步骤: 运行 M8 全量 pytest、collect-only、ruff、diff/check/scope；回填删除/改写/保留证据和最终 test count。
- 验证: 所有门禁通过，tasks/progress 完整，只有 M8 范围与产物变更。

# 补充验收与回归证据

验证树 `80941dfd6afcd181536a08da1b0762051ee98b11`，基线 `9bf2b13da4005631096f2a49223564cd68647c3c`。2026-10-29，主实施者补充；独立产品裁决仍以 regression.md 为准。仅使用本 unit 隔离测试数据，没有生产修改。

## R5：真实模型许可、真实等待和条件变化

脚本 `/tmp/bugfix678-r5.mjs`，结果 `/tmp/bugfix678-r5/evidence.json`，日志 `/tmp/bugfix678-r5.log`，数据库 `/tmp/bugfix678-r5/im.sqlite3`。从日常隔离栈只读 SQLite backup 创建副本，启动当前 IM 服务和锁定 DSH 子进程，模型路由与日常模板一致。通过公开 runtime RPC 向真实 PA session 投递主人对 A/B/C 三条公开文字的授权，再对三个真实冻结 proposal 分别调用 `pa.review`。没有替换模型返回。

Luna 对 A/B/C 分别 allow，审核 contextMode 为 full/delta/delta。两个许可均在提交前已批准，分别实际等待 64410ms/62061ms 后提交：

| 内容 | Proposal | 提交结果 / 消息 |
|---|---|---|
| 678-R5-A | 471d6f21-0d64-447e-82ed-0d62c4ba336a | confirmed / 8823c788070044f3a6f16ac6a1f58f65 |
| 678-R5-B | 89acc835-008a-4196-bd80-2864a54051b0 | confirmed / 93ffd3cbc7ff4bc0b23fc6dabd63656c |
| 678-R5-C | 66b17372-b0a0-496c-9f8e-7c9b69f4efab | 主人新消息后 not_sent / owner_already_replied |

两个实际消息均 completed，未出现 C。服务及 DSH 子进程正常关闭。这是 IM 产品服务接缝 + 真实 DSH 模型请求的集成验证，不冒称浏览器或 Node WebSocket 全链路；正常 UI 两笔连续发送见独立 regression.md。其他受众/权限/资源变化和幂等保护由 personal-disclosure、personal-images 永久回归覆盖。

## R8：迁移副本与实际 PA 回执恢复

脚本 `/tmp/bugfix678-r8.mjs`，结果 `/tmp/bugfix678-r8/evidence.json`，日志 `/tmp/bugfix678-r8.log`；IM/Inbox 和迁移前备份均在同目录。只读复制日常栈真实消息、dispatch log、事件与 publication；在副本重建一个历史 ACK 丢失场景：主人 incident 回执指针为空、该 publication 为 unknown，实际已发送的主人/对方消息和服务端 dispatch receipt 保留。删除该事件旧投影及迁移 marker，以验证升级登记；不改原栈。

两份公开迁移 CLI 均实际执行 plan → apply → apply → verify，verify=true；IM 保持历史消息和确认/不确定 operation，Inbox 保持原输入、消费状态及 publication。未完成事件可从 pa.incidents.pending 找到。

真实 Astra 主 PA 消费迁移后的事件，实际发起 send_message；当前 PersonalAssistant 和 Gateway 服务执行 agent.message.status 查询原 operation，并绑定真实主人消息 `7d0333099b8f485d8458fae966bd6321`。对方原消息 `4fa44f7750724f3782ffe97a18e9a86a` 保持，publication 从 unknown 恢复 confirmed。消息总数 **47 → 47**，pending incidents 变空，没有重发。

该场景使用真实 DSH、PA/Gateway 服务和复制的真实产品数据，通过明确的 authenticated host seam 接通；没有声称 Node WebSocket/UI 全链路。PA 完成回执恢复后尝试 task_graph list，专项 harness 未提供该额外工具，返回错误；不把此分支记为任务能力通过，也不影响已直接核对的历史回执恢复。脚本 finally 关闭 IM/DSH/数据库。事务中断、回滚和旧 allowed 失效另有永久迁移测试（本轮全量通过），不将它们伪称为真模型故障。

## R7 / W5：恢复归属与入口盘点

| 实际入口 | 恢复归属 | 固定版本证据 |
|---|---|---|
| 主/子 Agent、Workflow、知识/记忆 Agent | DSH 原生 Loop/llm-retry，middleware 对 isAgentLoopRequest 直接委派 | standalone-model-retry 的 marked Loop 不缓冲/重试；codex-approval-native 真实 DSH 临时503恢复、耗尽与取消，既有workflow/knowledge原生测试；日常P/E/PA真实模型行为见 regression.md |
| Codex 工具/披露审核 | 原生重试；review-session 最终态、最多一次格式/上下文重建 | codex-approval-native 与 lifecycle：并发fork、full/delta、overflow重建、invalid恢复、实际副作用次数、timeout刷新、取消、旧timer和失败checkpoint隔离 |
| CC/legacy分类、PA输入审核 | classifier.ts / personal-security.ts → withStandaloneRetry | standalone-model-retry：503部分流丢弃、跨两阶段共享预算、有效deny不重试、每attempt时限、取消排空、能力变化、未知插件异常不冒充provider故障；approval/personal-security验证真实调用投影 |
| 网页提炼 | web.ts → withStandaloneRetry | web.test 原生DSH web工具、提炼请求及故障语义；共享层恢复状态机由上项确定性回归覆盖 |
| 模型验证 | model-setup.ts → withStandaloneRetry | model-setup.test 真实DSH+本机HTTP provider先503后成功，以及失败不安装路由/冷重启 |
| BasicCompactionEngine直接摘要 | 同一公开LLM middleware，sessionId不作为Loop标记 | model-policy.test 在真实DSH子进程的原生压缩摘要第一次临时失败、第二次成功；两请求保留同sessionId，只落一个完整summary，FAILED_PARTIAL_SUMMARY不进入有效上下文 |

盘点本仓直接 `ctx.llm.stream` 出口为 classifier、personal-security、web、model-setup；其余业务通过原生Agent/公开compaction入口。公开 middleware 同时覆盖依赖通过该 LLM service 发起的直接请求；不宣称拦截绕开 DSH 的第三方 SDK/HTTP。暂时故障/取消属于明确的确定性 provider 故障注入，与日常真实模型成功调用分开；没有人为中断真实供应商或生产。

## 本地等价 CI

- `pnpm build`、`pnpm typecheck`：通过，日志 `/tmp/bugfix678-build-final.log`、`/tmp/bugfix678-typecheck-final.log`。
- `pnpm exec vitest run --maxWorkers=2`：**156 files / 826 tests passed**，`/tmp/bugfix678-vitest-round3.log` 与 `.json`，22:57:37 起、242.17s。前两轮并发负载下的失败及窄复跑保留在 progress，不覆盖历史失败事实。
- Web `npm run test`：**108 files / 1029 tests passed**，`/tmp/bugfix678-frontend.log`；critical依赖审计通过，仍有5项high（非本次新增，审计阈值critical），`/tmp/bugfix678-audit.log`。
- 非E2E pytest：**113 passed / 28 deselected**，`/tmp/bugfix678-pytest.log`。
- docs integrity、ruff check/format、packaged iOS runtime 检查通过。无 iOS源码变更，未声称原生设备验收。canonical归并/归档后将重跑文档与change归档检查；源码未变不重复全部测试。

清理记录：发现第二轮 workflow-native 超时遗留的 DSH 子进程 PID13000，PPID1、PGID13000、cwd/DSH_HOME 均为专用 nano-workflow-uft0Se 临时目录，启动时间22:40:17与该轮测试匹配；核对后仅终止该进程组。日常验收服务待 reviewer 完成后统一停止。

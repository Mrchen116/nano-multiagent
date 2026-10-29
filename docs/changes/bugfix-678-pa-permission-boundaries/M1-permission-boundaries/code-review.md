# Code Review: bugfix-678 / M1

- review_mode: `full`
- validated_at: `21b8da0d315b63795775a84e20e1ef475f028f2a`
- executed_base: `9bf2b13da4005631096f2a49223564cd68647c3c`
- effective_base: `9bf2b13da4005631096f2a49223564cd68647c3c`
- effective_through: `21b8da0d315b63795775a84e20e1ef475f028f2a`
- scope: 完整 `9bf2b13da..21b8da0d3`，54 files；没有把之后的 runtime 产物或未提交改动视为受审实现。
- reviewer: 未参与本 diff 实现的独立静态审查者；同次另行承担 verifier，结论见 `verification.md`。
- verdict: **changes requested**，1 个 CONFIRMED finding。

## Findings

```json
[
  {
    "file": "packages/personal-assistant/src/personal-assistant.ts",
    "line": 158,
    "summary": "[P2] Reconcile an uncertain owner notice before returning unknown",
    "failure_scenario": "主 PA 的 incident 主人提醒已经由 IM 持久发送，但 agent.message 的 ACK 丢失，或节点在收到 ACK 与 pa.incident.receipt 之间中断。publication 因而处于 sending/unknown，IM incident 的 owner_notice_message_id 仍为空。再次 send_message 虽读取 incident，但随即在这里返回 unknown，既不查询 agent.message.status，也不绑定找到的真实回执。recoverAll 明确排除 personal Agent；现有 pendingPublications(session) 只匹配 session: 前缀，也找不到 pa-incident:<id>:owner。于是主人实际已收到提醒，PA 却永久无法确认它，后续原聊天拒绝被缺失主人回执阻塞。不要改 key 重发；应按原 operation 查询已存在的投递事实并恢复 publication/incident 回执。",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "send_message 工具结果、security.incident 系统事件与恢复后的 Inbox 事件事实",
    "expected": "Agent 能区分未发送和结果未知，并使用真实可行的查询路径确认原 operation；主人提醒真实送达后再向原聊天拒绝。",
    "observed": "结果要求 Check the existing publication receipt，但当前模型工具没有 operation receipt 查询动作，PA 宿主发送/恢复路径也未执行已有 agent.message.status；incident 继续报告 owner_notice_message_id=null。",
    "impact": "一次网络 ACK 丢失可使安全处置永久停在 unknown，R4/R8 的实际回执恢复不成立。",
    "recommendation": "由宿主按稳定 publication identity 查询已有 agent.message.status，找到真实消息后确认 publication 并调用 pa.incident.receipt；未找到或查询失败则保持 unknown，不重发。对 ACK 丢失及 receipt 绑定前崩溃补现有发送回归。",
    "severity": "WARNING",
    "evidence": [
      "packages/personal-assistant/src/personal-assistant.ts:146-158,185-197",
      "packages/personal-assistant/src/global-agent.ts:348-350,689-695",
      "packages/personal-assistant/src/inbox.ts:405-408",
      "apps/im-server/src/gateway.ts:551-556",
      "apps/im-server/src/personal-actions.ts:49-51",
      "独立临时 seam: /tmp/bugfix678-static-review/review.test.ts；/tmp/bugfix678-static-review/repro.log，2 tests passed，第二项复现上述 sending/unknown 无查询结果"
    ]
  }
]
```

## Context Implementation Review

Mode B，触发于审核 policy/工具、原话保留、输入准入、事件投影、待发图片及失败恢复的共同变化。核查的是受影响消费链，未把 helper 输出或类型通过当成真模型行为。

- 工具审核：`codex.ts` 只组 ReviewPlan，`review-session.ts` 持有 trunk/fork/checkpoint、当前 run 和 timer；`codex-context.ts`/retained 模块组装证据。四个调查器从宿主工具服务取得原生定义，reviewer scope 固定 allowlist/guard、清除额外上下文；父 cwd 保留，未声称文件系统沙箱。
- 原话：从原始持久 user 事件、可信 Inbox/conversations 结果及委派来源收集，保留整单元/背景及 sender/delivery；按 reviewer 实际 deriveMessages 判断补送，超预算有不完整标记。CC 不接入 Codex 保留层。原生子进程测试捕获 full/delta/fresh 请求；长期授权/撤回的真实模型理解仍待产品验收。
- 输入：服务端按当前消息 rowid 取前 20 条及直接回复目标；输入分类器提供完整 current，历史整条移除，当前装不下或附件无法投影明确 unavailable。消息状态/generation 持久，故障只能显式 inbox review 重试；其他准入输入可读。
- 事件：系统指示与外部理由/原文分别投影；原始风险输入不准入。PA 用正常发送工具，事件自带目标/引用，实际回执绑定在宿主。上方 finding 是其中的结果恢复缺口。
- 图片：prepare 真实解码并冻结 hash/MIME/尺寸，RPC 有界传 bytes，DSH 公开 image block 注入当前请求，实际请求检查全图；提交复制已核对 bytes。fixture pricing adapter 的请求捕获支持 full/delta/fresh 装配机制，不能证明日常 Pi-AI/Codex OAuth 的图片能力或模型判断。
- 重试：Loop 标记直接委派原生恢复；standalone middleware 用 WeakSet 防重入并逐次缓冲，CC 两阶段共享恢复额度；reviewer request-error 调用 next 并消费原生 retry 事件。取消、失败 checkpoint 和 timer 隔离复用现有窄/原生子进程证据。

## Evidence and limits

复用 caller 给出的审核专项 5 files/39 tests、PA 18 tests、Python 113 passed；核对相关永久测试覆盖与本机日志，不重复跑全量。`/tmp/bugfix678-build-frozen.log` 显示构建产物绑定目标 SHA；`/tmp/bugfix678-typecheck.log` 全部 Done。`/tmp/bugfix678-vitest-final.log` 最终为 154 files passed / 2 failed，822 tests passed / 2 failed；失败为 knowledge-review 的 held 结果等待断言和 workflow-native 的 40 秒超时，不能视为全量通过。

独立核验命令：`pnpm exec vitest run --config /tmp/bugfix678-static-review/vitest.config.mjs --maxWorkers 1`，2 tests passed。仅用内存数据库/宿主 fake transport，未启动新服务、调用生产或真实模型。生命周期候选被现有 `schema.sql:587` 触发器补代次反证，已 REFUTED，不列入 findings。临时脚本位于本机 `/tmp`，不加入永久套件或提交。

已知公开能力缺口：锁定 DSH 0.2.1-alpha.1 的 Pi-AI adapter 无 imageRequestPricing；现用日常 Codex OAuth 路由待发图片及 read_image 调查会明确 unavailable。此为批准设计与现有路由能力的待裁决/未完成验收项，详见 verification，未被本审查豁免；无真实模型图片成功或拒绝结论。

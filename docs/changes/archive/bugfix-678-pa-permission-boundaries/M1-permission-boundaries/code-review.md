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

## Round 2 — Patch review and finding closure

- review_mode: `patch + closure`
- validated_at: `80941dfd6afcd181536a08da1b0762051ee98b11`
- executed_base / effective_base: `9bf2b13da4005631096f2a49223564cd68647c3c`
- effective_through: `80941dfd6afcd181536a08da1b0762051ee98b11`
- pre_fix_head / finding_origin_head: `21b8da0d315b63795775a84e20e1ef475f028f2a`
- scope: 仅 `21b8da0d3..80941dfd6`，含用户纠偏后的 design `5789ce9ef`、Gate 2 Round 4 和受影响消费链。Round 1 未受影响覆盖 retained；不重新审完整 unit。
- verdict: **patch approved；原 finding closed**。新增存活 findings：

```json
[]
```

### Focus finding closure

`[P2] Reconcile an uncertain owner notice before returning unknown`：**closed**。

`personal-assistant.ts:158–168` 对 sending/unknown 主人事件提醒使用宿主派生的原 operationId 调用 `agent.message.status`；仅 found=true、实际 message_id 和目标会话匹配时确认 publication，并调用 `pa.incident.receipt`。found=false 保持 unknown，不调用 agent.message，不换 key；状态查询失败也在发送边界前退出。若 status 后 receipt 绑定失败，已保存的 confirmed result 在后续 `:179–182` 继续补绑定，仍不重发。原聊天路径先读持久 incident 已送达回执；其权限与独立披露审核未放宽。

`global-agent.ts:411` 的系统事件及 `personal-assistant.ts:168,184` 的模型可见结果现给出真实操作入口：同 incident_ref、同 target 再次调用 send_message 只查询未知结果，查询不到仍不重发。因此 Round 1 的“要求查询但没有可执行入口”接口缺陷也已关闭。

回归位于 `personal-assistant.test.ts:214–233`，参数化覆盖 found=true/false：初次发送 ACK 丢失、再次按原事件查询；实际发送次数均为 1，只有确认结果绑定 incident 回执。复用 caller 的 red→green 证据 `/tmp/bugfix678-receipt-red.log` 和 `/tmp/bugfix678-native-image-green.log`（3 files / 32 tests passed），本轮未重复运行相同窄测试。

### Context Implementation Review — affected delta

Mode B，仅审核图片输入与 unknown 回执恢复。

- 用户已明确否认图片 token 估算是其要求。design `5789ce9ef` 与独立 Gate 2 Round 4 已将旧 pricing 前置替换为主 Agent 原生路径。Round 1 的 pricing 能力前提属于旧版本/旧技术选择，现为 **superseded**，不得继续作为当前缺陷或门禁。
- `personalReviewImages` 保留冻结 bytes/hash/格式/尺寸校验并调用 `ctx.attachments.admitPromptContent`；`review-session.ts:115–117` 将返回的 image blocks 放入当前 followup，路径与主 Agent `index.ts:861` 的 admission 一致。补丁只删除 `imageRequestPricing` 与 imageCost 的额外门槛，没有自建估算器、改变审核模型或替换 Luna。
- 文本证据预算和 typed rebuild 保留；实际 provider CONTEXT_WINDOW_EXCEEDED 仍走既有一次 full 重建并携带全部当前图，不新增重试额度。`review-session.ts:219–225` 仍逐请求核对当前 pending message 的图片数量、attachment 身份及 offloaded 标记；不是用旧 history 图片替代当前待审图。
- `codex-approval-native.test.ts:151–191` 移除 fixture 的 pricing 实现后，通过真实 DSH 子进程记录 full/delta/fresh 的当前图数量 `[1,2,1]`，并保留文本模型明确失败检查。该证据证明无 pricing 也能经原生运行时提交 image blocks；响应仍是受控 fixture，不证明真实 Pi-AI/模型理解或 R6 产品发送结果。

### Retained and pending evidence

复用 `/tmp/bugfix678-native-image-green.log`：3 files / 32 tests passed（含 PA 20 tests 与原生图片子进程）。旧两项全量失败在安静环境单 worker 的 `/tmp/bugfix678-runtime-repro.log` 为 2 files / 5 tests passed，关闭“相同窄测试仍失败”的担忧；不将其外推成最终全量通过。最终全量、当前版本 R4/R6 产品与真实模型验收仍 **pending**，由 owner 接入后续证据，不因此新增一轮完整静态审查。

本轮仅读固定版本与可信窄证据，写本报告和 verification Round 2；未修改实现、测试、配置或设计，未运行生产或启动服务，未提交。现场原有未跟踪 `regression.md` 未触碰。`git diff --check 21b8da0d3..80941dfd6` 通过。

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

## User-requested full Agent Context review

- review_mode: `full`；Agent Context Review **Mode B**。
- validated_at / effective_through: `89acdd4649cc14df8dbd9195e834f08931aad592`。
- executed_base / effective_base: `9bf2b13da4005631096f2a49223564cd68647c3c`。
- scope: PR #430 完整 `base...HEAD`，71 files；全部源码 diff 与直接、间接受影响的 Context 消费链。不是对 Round 2 的补丁复审。该 HEAD 的实现与 `80941dfd6` 一致；本轮审查开始时 checkout clean。
- reviewer: 用户指定新开的独立 subagent，未参与该实现，不另派 reviewer。遵循本 worktree 的 AGENTS、change-code-review、agent-context-review，以及 Agent Context Engineering / LLM 联调规范。
- verdict: **changes requested，2 个 CONFIRMED findings**。以下定位为受审 HEAD；主实施者收到本轮证据后并行修改的工作区内容不属于此固定版本结论。

### Findings

```json
[
  {
    "file": "packages/dsh-integration/src/policy/retained-instructions.ts",
    "line": 37,
    "summary": "[P1] Retain complete owner instructions across partial Inbox fragments",
    "failure_scenario": "主人先给一条简短外发许可，随后通过正常 Inbox 发来带附件的撤回，或一条超过 6000 字、末尾含撤回的消息。InboxStore.parts/read 会把后一条的每个片段都标为 partial=true；即便所有片段均已读到，此处也全部跳过。经历主会话换窗或 reviewer full 重建、旧有效历史不再含该结果后，retainedEnvelope 只补送旧许可。此前已有 grant unit 又使 compaction/start 不设置 incomplete，故没有原话不完整警告。",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "Inbox 序列化结果 → 原始授权单元收集 → reviewer full/rebuild/fork 原话补送",
    "expected": "已完整读取的同一真人消息按完整单元保留，其较新限制和撤回与旧许可一起交给审核者；读不全时明确标记缺口，不能仅保留旧许可而宣称完整。",
    "observed": "真实 InboxStore 的两种正常消息均产生 part=1/2、part=2/2 且 partial=true；retainInstructions 只返回 private-owner-chat:grant，incomplete=false；最终 retainedEnvelope 有旧 may publish，没有 WITHDRAWAL_NEVER_PUBLISH，也没有 instructions_incomplete。",
    "impact": "新保留层会确定性遗漏已读到的较新授权约束，重建后的审核输入可只剩过期许可。审核模型可能据此放行已撤回的动作；本轮确认的是原话交付缺陷，没有把模型必然误判作为已观察事实。",
    "recommendation": "按可信来源、会话和消息 ID 收集并按 part/parts 重组完整片段后保留整个单元及上下文；片段缺失或无法安全重组时标记 incomplete。覆盖长消息、附件消息、跨页与换窗后撤回，不把 partial 文本直接当完整许可。",
    "severity": "CRITICAL",
    "evidence": [
      "packages/personal-assistant/src/inbox.ts:282-292,304-310：真实消息拆片及 partial 投影",
      "packages/dsh-integration/src/policy/retained-instructions.ts:28-43,52-69,76-91：partial 跳过与缺失标记/补送",
      "packages/dsh-integration/src/policy/review-session.ts:94-105：实际 full/rebuild 使用 retainedEnvelope",
      "/tmp/bugfix678-context-full/review.test.ts：前两项分别使用真实 InboxStore 投影的附件与长文本消息，所有片段均含在已读结果中",
      "/tmp/bugfix678-context-full/evidence.jsonl：两项均 oldGrantPresent=true、withdrawalPresent=false、incomplete=false、warningPresent=false；repro.log 为 3 tests passed"
    ]
  },
  {
    "file": "apps/im-server/src/personal-actions.ts",
    "line": 242,
    "summary": "[P2] Rewrite reviewed resource links inside the delivered interactive source",
    "failure_scenario": "PA 将主人私聊中的已授权 PNG 放在正常 interactive.source 的 TextContent Markdown 图片链接中，发给无源会话读权限的另一会话。prepareChecked 已扫描 source 并冻结/解码图片，审核通过；commit 也创建目的会话副本，但只重写普通 content 和 attachments，交互 source 原样写入。因此返回 confirmed，而卡片仍请求私聊 URL。",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "send_message interactive.source / 冻结图片证据 / 实际发布内容 / confirmed 工具结果",
    "expected": "审核过的原图以目的会话可访问的副本交付；模型收到 sent/confirmed 后，交互卡片中的该图片或资源链接也可由实际受众读取。",
    "observed": "合成图片 proposal 含冻结原图，review allow 后 commit=confirmed；目的 peer 中存在新 image_id，但 message_interactive.source 仍为 /im/v1/conversations/chat/images/image。接收者 u2 不在源 chat，media 路由先按源会话 access 检查，不能打开这张卡片引用的原图。",
    "impact": "模型会依据 confirmed 结束交付，实际接收者只能得到失效图片/资源链接；新允许的图像卡片路径没有兑现审查过的交付内容。",
    "recommendation": "对已冻结并复制的资源在最终 interactive.source 中应用同一 URL 映射，保持完整卡片实际内容与受审内容一致；覆盖无源会话权限的接收者和卡片编辑/替换路径。",
    "severity": "WARNING",
    "evidence": [
      "apps/im-server/src/personal-actions.ts:121-123,172-177：interactive.source 参与快照收集和图片解码",
      "apps/im-server/src/personal-actions.ts:232-243：副本 URL 映射存在，但 interactive:payload.interactive 未重写",
      "apps/im-server/src/interactions.ts:70-86：原样保存 source；apps/im-server/src/media.ts:48-55：资源先检查 URL 所属会话访问权",
      "/tmp/bugfix678-context-full/review.test.ts：第三项真实 PersonalActions/SQLite/图像字节/交互源码存储 seam，独立 verdict 为 fixture allow",
      "/tmp/bugfix678-context-full/evidence.jsonl：confirmed、目的副本存在、卡片源 URL 未变、recipient_can_read_source=false；未声称浏览器截图或真实模型已选择该卡片"
    ]
  }
]
```

### Full coverage and evidence levels

本轮沿“来源 → 选择/检索 → 转换/组装 → 注入 → 消费 → 更新/失效 → 换窗/恢复”检查组合，不把字段存在或单测总数当模型已消费：

| 消费链 | 本轮独立判断与证据边界 |
| --- | --- |
| System / Prompt / 可信身份 | 核对 global-mode、personal-security、policy sources 与最终 ReviewPlan 组合。owner/binding/epoch、root lineage、实际受众和冻结 action 由宿主派生；新增 inbox review 只需故障事件/check 已给出的 message_id，incident_ref/目标由宿主事件给出，无新增模型不可获得的必填身份。reviewer scope 原生四调查工具和 guard、contexts 清空及额外 workspace 指令过滤，在 codex-approval-native 本轮真实 DSH 子进程测试中通过；adapter 响应为 stub。 |
| 来源 / Inbox / 输入审核 | 核对 participant/observer、sender.is_owner、represented PA 标记、普通/系统/Agent 消息与 live/restored/historical 投影。输入当前正文完整、前20条和单个直接回复按原 rowid 取证；超窗、附件不可投影明确 unavailable，不当 deny。持久 generation、故障事件和显式 inbox review 不在 check/read/重启时自动重审；新状态不屏蔽其他 admitted 消息。input-admission 与 personal-input-context 本轮执行通过；真实 Astra 显式重审与继续任务的产品事实复用 regression Round 2，对应原始本机文件已核对。 |
| 原始指令 / 主子 Agent / 历史 | 核对 durable events、Inbox/conversations/PTC 工具结果、源标签、reply/preceding 背景、delegated audit 与 reviewer 实际 deriveMessages 的补送判断。full/delta/fork/rebuild 按真实前缀和可见文本检查，旧 verdict 不成为真人许可；发现上方 partial 丢失缺陷。普通委派/撤回复用独立产品回归，未据单条成功轨迹推导所有长历史可靠。 |
| reviewer cache / fork / 更新 | 核对 purpose 隔离、config/reviewer/cwd fingerprint、前缀变更失效、并发 fork 快照、取消不提交 checkpoint、失败不复用 handle、旧 timer 清理、格式最多一次重建及一次 Context 重建。codex-approval-native/lifecycle 本轮执行通过；其中 fake lifecycle 与真 DSH fixture 分开解释。有效 deny 不重试至 allow，缺失 evidence/unavailable 不生成许可。 |
| 图片 / 调查器 / 工具结果 | 核对真实解码、MIME/hash/数量/尺寸/总量、冻结 base64、主 Agent 同路径 attachments admission、当前 followup 全图及 llm/stream 缺图/offload 检查、提交再次核对 bytes。原生 fixture 本轮 full/delta/fresh 图片数 [1,2,1] 和无图能力失败通过；真实授权蓝图字节一致交付复用 regression Round 2。发现上方卡片实际发布与 confirmed 语义缺口。 |
| 安全事件 / 回执 / 恢复 | 核对 rejected 文本不以任务进入 Inbox；instruction 与外部 reason/original_content 分开；PA 自写主人提醒、原聊天独立披露审核、root-only self 发言及真实 receipt 前置。unknown 主人消息按原 operation status 恢复、不换 key；peer 已有 receipt 直接复用。独立读取 /tmp/bugfix678-r8/evidence.json 与脚本：真实 Astra 调用后有下一轮工具调用，原回执恢复、消息47→47。其额外 task_graph harness 错误不冒充产品功能通过。 |
| 许可失效 / 发送状态 | 核对完整 payload、audience、policy/profile/lifecycle、授权 guard、资源和主人新消息的提交前再验；独立许可无60秒/全局披露计数互相作废。prepare/review/commit 的 allow/deny/needs_owner/unavailable 与 not_sent/sending/unknown/confirmed 不混用。独立读取 R5 实际 Luna full/delta/delta、两许可预先批准并等待64,410/62,061ms、第三笔新主人消息后 not_sent；这是实际 DSH+IM seam，不是 UI 或 WebSocket 全链路。 |
| 失败 / 部分流 / 取消 | 核对 standalone middleware 与 native Loop 标记的唯一恢复归属，request-local ALS budget、prepared generation、WeakSet 防重入、完整流缓冲和失败片段丢弃；CC 两阶段共享恢复预算，输入审核/web/model setup/原生摘要入口纳入。standalone-model-retry 和 native/lifecycle 本轮通过；其故障是确定性 fixture，不是真实供应商故障演练。 |
| Task 动态提醒 | 完整 diff 核对移除拒绝批次 held 机制后仍保留 paused/waiting/doing 真状态、源失败/取消 hold 与短轮上限；提醒明确不授予权限、不绕过拒绝，要求正常任务状态表达阻塞。独立产品 regression 中真实 hard_deny 后一项 Paused、另一项 Done 与实际文件事实可复核；未扩大为人工拒绝全部 UI 验收。 |
| Skill / Memory / 非本次直接 Surface | 本 PR 没有改产品 Skill 发现/加载、Memory 写入选择器或主会话换窗算法；间接影响为 direct 摘要/维护恢复、审查证据中的历史快照与新原话层。其 Prompt 明确 Skill/Memory/摘要不能创造授权。llm-attribution 本轮真 DSH+本地 HTTP 捕获证明后台 Skill fork 的实际 system/tools/messages 前缀与执行限制；不据此宣称所有 Skill/Memory 任务或所有 provider 多模态序列化通过。 |
| 迁移 | 核对 IM 旧 allowed 失效、confirmed/sending/unknown 不改、unfinished incident 持久登记，Inbox 旧 consumed 不重放、legacy unknown 失败及 marker/事务边界。input-admission 本轮含实际 SQLite 重开/迁移中断/幂等；IM CLI/回执的真实副本证据复用 R8。 |

### Executed validation, limits and handoff

- 新独立缺陷复现：`pnpm exec vitest run --config /tmp/bugfix678-context-full/vitest.config.mjs --maxWorkers 1`，**1 file / 3 tests passed**，Node 24.22.1；`repro.log` / `evidence.jsonl` 留本机。前两项是实际 Inbox serialization + retained helper 的确定性接口证据，第三项是真实服务类/SQLite/文件图像/interactive 存储 seam，verdict stub。不把它们描述为真实模型违规或浏览器可见验收。
- 固定实现相关窄复跑：llm-attribution、codex-approval-native、retained-instructions、codex-approval-lifecycle、standalone-model-retry、input-admission、personal-input-context，**7 files / 29 tests passed**，`/tmp/bugfix678-context-full/existing-regressions.log`，23:56:45 起，10.38s。真实子进程导入与 HEAD 对应的既有构建产物；未改实现后重跑旧缺陷结论。
- 独立阅读可信固定版本回归与原始本机结果：`regression.md` Round 2、`supplemental-validation.md`、R5/R8 `.mjs` 与 `evidence.json`；其中真实模型和产品事实可复用，但不是本轮重新执行 Web 旅程。保留旧 Round 1 故障历史。
- 没有为本轮新开真实模型环境，也没有获取本轮新 provider upstream 请求。指定的 R5/R8 session 在本机配置日志根下未找到可直接对应的 session 目录，因此不声称审阅了其转换后 upstream payload。现有本地 HTTP wire 测试证明所列 adapter 路径，native fixture 的 llm/stream 证明装配，真实模型响应/产品回执证明特定行为；三者不互相冒充。
- 未重新运行全仓826/前端1029/pytest113及构建/typecheck；复用仍适用的已冻结证据，不将其覆盖本轮新发现。未跑真实 iOS、Feishu、跨 provider 多模态、所有限制/长历史组合；这些是覆盖限制，非无证据的存活 finding。
- 本 reviewer 仅读固定源码、合成测试与已指定隔离证据；没有扫描生产消息、启动产品服务、修改实现/测试/design/spec、提交或推送。仅本报告追加；缺陷已提前给主实施者完整定位与 `/tmp` 复现，修复和 PR 更新由其负责。本轮全面审查已完成，不为数量追加假想问题。

## User-requested Context review — finding closure

- review_mode: `closure`；Agent Context Review **Mode B**，仅两项 finding 及受影响链路，不重复 full。
- finding_origin_head / pre_fix_head: `89acdd4649cc14df8dbd9195e834f08931aad592`。
- validated_at / effective_through: `3e5b63e11f453ad84cc3c84f2e0ddcb09375cfe0`。
- scope: `89acdd4..3e5b63e11` 中原话片段收集/补送、冻结图片卡片最终发布的实现与测试 delta。开始时 HEAD 与派发一致、checkout clean。
- verdict: **两项 closed；此范围无剩余 findings**。

```json
[]
```

### Focus findings

1. `[P1] Retain complete owner instructions across partial Inbox fragments`：**closed**。

   `retained-instructions.ts` 现以会话和消息 ID 聚合 `part/parts`，在首次出现时保留单元顺序，读齐后按片号重组全部内容并去除 partial 标志。未读齐的单元不会进入最终 units，返回 `incomplete=true`；已有旧 grant 不再掩盖这个缺口。因此 full/rebuild 中 `retainedEnvelope(..., [], budget)` 会补送完整撤回，或者明确提示原话不完整。沿用实际 reviewer surface 检查、预算整单元选择、原始 sender/delivery 与原有授权语义，没有把碎片文本直接提升成完整许可。

   独立重放原缺陷接缝（真实 InboxStore，native `tool/result`）：附件及长文本两项的 retained_ids 均从仅 `grant` 变为按序 `grant,withdraw`，`withdrawalPresent=true`、`incomplete=false`；空 reviewer history 的重建 envelope 确实含撤回。永久回归另经真实分两页 `limit=1` 与 PTC 投影，验证缺页时整单元省略且有 `instructions_incomplete`，读齐后原文逐字相等、无错误缺失标记，并验证 inherited 单元重新补送相同 envelope。当前修复没有改 reviewer 的 wire adapter 或模型选择，确定性的丢失点已消除。

2. `[P2] Rewrite reviewed resource links inside the delivered interactive source`：**closed**。

   `personal-actions.ts:242-243` 在调用实际 insertMessage 前，对 `interactive.source` 复用同一 `copies` URL 映射；内容来自已冻结、提交前校验且已复制的相同 bytes，不额外读取未审核资源。独立重放原图片卡接缝：commit=confirmed，message_interactive.source 实际持久值为 `/im/v1/conversations/peer/images/<copy.image_id>`，与 peer 新副本一致，未再包含源私聊路径；接收者仍无源 chat 权限。PNG/JPEG/WebP 永久回归还核对卡片源码与 attachment 的目的 URL 相等，以及源文件之后变化不会改变目的副本字节。

### Evidence and limits

- 独立 closure 接缝：`pnpm exec vitest run --config /tmp/bugfix678-context-closure/vitest.config.mjs --maxWorkers 1`，**1 file / 3 tests passed**；`/tmp/bugfix678-context-closure/{review.test.ts,repro.log,evidence.jsonl}`。其输入与原复现一致，只将断言改为修复后的完整撤回和目的 URL；源授权与可见性未放宽。
- 独立执行修改后的既有永久回归：`pnpm exec vitest run packages/dsh-integration/tests/retained-instructions.test.ts apps/im-server/tests/personal-images.test.ts --maxWorkers 1`，**2 files / 10 tests passed**，`/tmp/bugfix678-context-closure/permanent-regressions.log`，2026-10-30 00:01:36 北京时间。复用 caller 的 DSH/IM build 完成证据；未重新构建整仓。
- 这是实际 Inbox 序列化/原话补送与真实 IM/SQLite/图像文件/interactive 持久存储的确定性证据。independent verdict 在图片接缝中为 fixture allow；没有新增真实 provider/model 调用、upstream 请求捕获或浏览器/iOS/Feishu UI 验收，不将正确 helper/持久值描述成所有模型行为可靠。原 full review 的适用证据与限制保留。
- `/tmp/pr430-context-fix-tests.log` 此时宽回归为 **98 files passed / 2 failed，481 tests passed / 2 failed**；knowledge-review 的 held 等待失败可见。caller 正接手失败项独立窄重验，本 closure 不据此宣称宽回归全绿，也不把 unrelated 未决测试转写成这两项仍存活的缺陷。
- 本 reviewer 仅追加本 closure；未改实现/测试/配置/design/spec、未提交或推送、未启产品服务、未访问生产、未派子 Agent。修复已由主实施者冻结，此结论不覆盖后续新 delta。

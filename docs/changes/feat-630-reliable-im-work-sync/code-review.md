# feat-630 independent code review

- reviewer: `/root/feat630_static_review` (independent; no implementation participation)
- review_mode: `full`
- executed_base: `5665af409426f22eec86d03d68e6ffbb1c935d00`
- validated_at: `24a944b1735215f872b35ff55c196bed9e776788`
- diff_range: `5665af409426f22eec86d03d68e6ffbb1c935d00...24a944b1735215f872b35ff55c196bed9e776788`
- branch: `unit/feat-630`
- completed_at: `2026-10-21T13:14:46Z`
- verdict: **Issues Found — 4 CONFIRMED**

审阅全部产品代码 diff、相关测试与实际调用方，以及本 unit 的 spec/design/delta 和 `M1-reliable-im/progress.md`。覆盖 Channels 请求关联/窗口/生命周期，IM relay outbox/终态、Work HTTP 鉴权/许可/分块/投影，PA Inbox/回执/控制/wake/publication 恢复，Node 真实组装及 Web API/IndexedDB/composer 恢复。审阅过程中已核对 `apps/im-server/tests/e2e/relay-recovery.test.ts` 的未提交 history wrapper 断言修正，不改变以下结论。报告写入后的最后状态显示 caller 已开始修改相关 PA 源码与测试；本报告冻结于上述 validated_at，不将这些后续修正视为已复核或覆盖它们。

复用 progress 中相关回归证据；独立窄复现只创建 `/tmp` 脚本、临时数据库和本机随机端口服务，完成后关闭服务并清理数据库。未修改源码、测试或配置，未运行全量测试，未执行产品验收或 full verifier。以下问题均有直接机制证据和独立运行输出，无 PLAUSIBLE 项。

```json
[
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/personal-assistant/src/global-agent.ts",
    "line": 175,
    "summary": "[P1] 未被实际命令解析器接受的 control 输入会让 wake 等待自身，永久堵住该 Agent",
    "failure_scenario": "在普通 global Agent 的直接聊天发送 '/stop now'（或 '/new something'）。receive 的 96 行正则将其标为 control 并保存 consumed=1、pending control，105–109 行将 ingest Promise 放入 controlTasks；但 ingest 仅对精确 '/stop'、'/new' 执行控制，sessionControl 也不接受这两种带参数文本，于是进入普通 attention→wake 路径。175 行 await 当前 controlTasks 就是等待正在 await wake 的同一 Promise，finishControl 永远不可达。后续普通消息复用这个 waking Promise，也不再 session.submit；重启后 pendingControls 重放仍重现死锁，stop 也会等待这些任务。独立复现发送上述文本后再发普通消息，结果 completed=false、submitted=0、pendingControls=1、waking=1、accepting=2。应使用与实际来源/寻址/命令解析一致的持久控制判定，并避免控制自身进入等待当前控制的 wake。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/personal-assistant/src/work-sync.ts",
    "line": 154,
    "summary": "[P1] 全部分块已持久但 append 前中断时，恢复会跳过所有 PUT，Work 最长停滞 24 小时",
    "failure_scenario": "IM 在 work-sync.ts 服务端 185–186 行保存最后一个 work_sync_parts receipt 后、203 行 Work.append 前崩溃，或重组/append 因暂时故障返回 5xx。此时重启后的 cursor 合法返回 through_seq=seq-1 且 received_parts 已含所有块；GET/startup 不会重组提交。客户端 uploadEvent 的 154 行跳过每一块后直接返回原 cursor，synchronize 报 work_sync_no_progress；每次重试都只有 GET，永远不能触发服务端 PUT 的完成提交分支，直至 partialTtlMs 的 24 小时清理后重传。独立复现保留上述精确 cursor，1.6 秒内两次 no_progress、PUT=0、through=0，源事件仍在。全部 parts 已齐全而事件未提交必须能够重新触发完成阶段，不能把缺块集合为空当成无事可做。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/channels/src/index.ts",
    "line": 138,
    "summary": "[P2] 传输 request_id 覆写审批业务身份，使取消或超时后的原卡片仍保持 pending",
    "failure_scenario": "single_thread 的审批卡片已发布，随后 DSH 因 request.signal abort 或 askTimeoutSec 超时产生 approval.resolved，而没有收到 IM permission_response。integration/index.ts 的 finish/cancel/timeout 会真实触发此通知；SingleThread.resolveApproval 在 365 行使用 payload.request_id=result.requestId 上报 permission_resolved。由于该 ID 不在 serverRequests，Channels 138 行将它改为 UUID。IM Gateway.streaming 的 887–911 行按该字段定位审批，因此新增一条随机 ID 的 resolved 项，原审批项仍 pending；用户随后操作原卡片仍会向已不存在的 runtime approval 提交决定。独立真实 IM＋WebRelayConnection＋SQLite 复现得到 [{request_id:'original-approval',status:'pending'},{request_id:'<new UUID>',status:'resolved',decision:'cancelled'}]。需要将传输相关 ID 与审批业务 ID 分离，并同步修改实际消费者；仅保留收到过服务端请求的 ID 无法覆盖运行时自主完成。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/personal-assistant/src/global-agent.ts",
    "line": 129,
    "summary": "[P2] 一个已撤权的待回执会永久挡住同节点所有后续有效回执",
    "failure_scenario": "消息已 acceptRelay 落盘，但在其待回执发送前该聊天的 Agent 成员资格被撤销（或该 Agent 被移除）。Gateway.handle(node.delivery_receipt) 在 500–501 行先执行 requireAgent/access，因此该条回执持续返回 rejected scope_not_allowed 等终止性错误。pendingRelays 每次按 rowid 返回同一条最早记录；drainReceipts 在 129 行遇错即 return，且既不隔离该条也不继续批次，后续其他聊天/Agent 的有效回执永远没有发送机会。中心无法确认这些正常输入并持续重投，背压窗口与重试负担会扩散至整个节点。独立复现将第一条 revoked 回执固定返回 RelayDeliveryError(rejected,scope_not_allowed)，第二条 valid 回执正常可成功；跨多次 drain/退避后调用序列仅为 revoked,revoked,revoked,revoked，两个 receipt 均仍 pending，valid 从未调用。应保留失败项所需恢复事实，同时让不相关的有效回执继续推进。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

窄复现命令：`node --import tsx /tmp/feat630-review-repro.mts` 与 `node --import tsx /tmp/feat630-review-server.mts`（均从本 worktree 执行）。第一份验证控制自等待、all-parts cursor 和传输字段覆写；第二份使用真实 IM/WS/SQLite 验证审批投影后果，并验证永久失败回执的队头阻塞。脚本为本次临时审查产物，不提交仓库。缺陷修复后需独立复核这些条件；本报告不提前宣称产品场景、负载或全量一致性验收通过。

## Round 2 — closure and incremental patch review

- reviewer: `/root/feat630_static_review`
- review_mode: `closure` for Round 1 F1–F4; `patch` for added source changes
- finding_origin_head / pre_fix_head: `24a944b1735215f872b35ff55c196bed9e776788`
- validated_at: `effe82d32d94a0337a522f106e20e356656f93e8`
- diff_range: `24a944b1735215f872b35ff55c196bed9e776788..effe82d32d94a0337a522f106e20e356656f93e8`
- completed_at: `2026-10-21T13:33:37Z`
- verdict: **Issues Found — 2 original findings still_open; 2 new CONFIRMED patch findings**

核对这一范围内所有源码、回归测试修订、load harness 修订和真实消费方；包含 request 可选 priority 与发送 unknown 后立即查询 status 的新增分支。复用 caller 报告的 18/18 定向回归结果，未跑全量。共享 checkout 在本轮期间出现后续修正，独立复现因此改用 `git archive effe82d32` 的临时 PA 源码快照，不将 caller 正在实施的未提交改动混作本轮受审版本。仅追加本报告，未修改产品源码、测试、配置或提交。

| Round 1 finding | Closure | Evidence at fixed HEAD |
|---|---|---|
| F1 control 自等待 | **still_open** | `/stop now` 已按普通文本处理；但 receive 仍先于 personal authority 判断把非 owner PA participant 的精确 `/stop` 标成控制，ingest 随后因 ownerControl=false 进入普通 attention→wake，再等待自身 controlTasks。独立复现 completed=false、submits=0、pending=1、waking=1。 |
| F2 全部分块已齐但事件未提交 | **closed** | uploadEvent 在 received.size===count 时显式补发最后一块；服务端即使 old part 已存在仍执行 count/finalize，能够重新进入原子 append。新增 all-parts 回归针对原窗口验证一次末块 PUT 后推进 cursor。 |
| F3 Web 审批业务身份被传输覆写 | **closed** | SingleThread 将业务 ID 放入既有 permission_request 对象，Gateway.streaming 优先读该对象；独立真实 IM/WS/SQLite 输出仅 original-approval 一条 resolved/cancelled，无随机身份和遗留 pending。迁移引出的飞书消费者遗漏另列新 patch finding。 |
| F4 撤权 receipt 队头阻塞 | **still_open** | rejectRelay 的 confirmed=-1 表达正确，但新增匹配表漏掉实际 requireAgent 返回的 agent_not_accessible，以及 Messaging.access 返回的 conversation_id not found。真实服务端撤销会话资格复现仍仅重复 revoked，valid 从未发送。 |

### Surviving and new findings

```json
[
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/personal-assistant/src/global-agent.ts",
    "line": 96,
    "summary": "[P1] PA 来源权限判定前预留 control，非主人发送 /stop 仍触发控制自等待",
    "failure_scenario": "非 owner 的获准 PA participant 在直接聊天发送精确 '/stop'。receive 96 行无条件命中精确命令并保存 pending control、consumed=1；personal.admit 返回 allowed=true、is_owner=false、delivery=participant，独立输入审查 allow。ingest 的 ownerControl=false，因此不会执行 /stop，也不会调用 SessionControls，而会进入 attention→wake；wake 175 行等待正在 await 它的 controlTasks，原问题仍发生，后续同 Agent 的消息与控制均受阻，重启重放亦不能消除。固定 HEAD 临时快照独立复现 completed=false、submits=0、pending=1、waking=1。普通 global 的带参数文本已修复，但不能据此关闭原来源/解析不一致造成的死锁；控制 intent 必须与可信来源分类后的真实执行判定一致。",
    "review_mode": "closure",
    "status": "CONFIRMED"
  },
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/personal-assistant/src/global-agent.ts",
    "line": 128,
    "summary": "[P2] 永久失败回执过滤没有覆盖真实撤权错误码，仍会阻塞后续有效回执",
    "failure_scenario": "scope_not_allowed 人造回归通过，但真实 Gateway.requireAgent 的拒绝是 agent_not_accessible；真实 Messaging.access 在聊天成员资格或 PA source 撤销后返回 conversation_id not found。当前过滤正则均不匹配，仍落入退避并 return，同一条 rowid 最早的 receipt 继续毒住整个节点。用真实 IM/WS/SQLite 创建 revoked、valid 两聊天待回执后移除前一聊天的 Agent 成员，固定快照输出 receiptCalls=[revoked,{error:'conversation_id not found'},revoked,{error:'conversation_id not found'}]，pending=[revoked,valid]，valid 从未发送。应按实际协议的终止性错误处理而非只覆盖测试构造的 code。",
    "review_mode": "closure",
    "status": "CONFIRMED"
  },
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/personal-assistant/src/single-thread.ts",
    "line": 365,
    "summary": "[P2] 审批 ID 迁入 permission_request 后未更新飞书消费者，取消或超时不再关闭原卡片",
    "failure_scenario": "single_thread 的飞书审批卡片发布后，runtime 以 cancelled/unavailable 等结果结束审批。此处仅将业务 ID 放入 permission_request.request_id，但真实组装中的 ExternalChannels.request 在 external.ts 172 行仍调用 resolveApproval(String(payload.request_id),...)。当前 payload 没有顶层 ID，因而查找的是 'undefined'，原 external approval 没有 settle，也没有 updateCard。固定快照以真实 ExternalChannels/ExternalStore 发送新结构 permission_resolved，输出原审批 settled=0、卡片 updates=0；随后点击原卡片仍调用一次 permission；窄复现的成功 stub 显示提交成功，真实 SingleThread.permission 则会因审批已不存在抛错。Web 路径已修复，必须同步迁移这个既有消费方。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  },
  {
    "file": "/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent/packages/personal-assistant/src/global-agent.ts",
    "line": 546,
    "summary": "[P2] unknown 外发查到成功后跳过原成功收尾，single_thread 会把 NO_REPLY 发给用户",
    "failure_scenario": "single_thread 使用 send_message 发布 interactive，中心已提交但 agent.message ACK 丢失。新增 catch 即时查询 status 并找到原消息后直接 settlePublication/return，未执行正常成功路径 532 行的 store.saveCommand(interactive-delivered:session:turn)。随后模型按既有交互回复契约输出 NO_REPLY 收尾；SingleThread.drain 221–228 行只有该标记存在才丢弃占位并保持静默，缺失时会把 NO_REPLY 作为普通直接聊天正文发布。固定 HEAD 下独立 GlobalAgent.call＋SingleThread.recover 复现返回 status=sent/message_id=confirmed-card，同时 marker=null、message_completed.final_content=['NO_REPLY']。查到远端成功后仍需完成与正常 ACK 相同的本地成功投影及 single_thread 标记，不能仅保存 publication result。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  }
]
```

窄复现：`/tmp/feat630-review-round2.mts`（PA control、飞书卡片）、`/tmp/feat630-review-round2-server.mts`（真实 Web 审批闭合、真实撤权 code 与后续 receipt）、`/tmp/feat630-review-round2-unknown.mts`（即时 status 恢复后的 single_thread 收尾）。均用随机端口/临时数据库，受审 PA 源码来自固定 git archive 快照；临时辅助模块只导出该快照解析到的 RelayDeliveryError，以保持 instanceof 与生产包一致。所有临时服务已结束，未触碰生产。产品、负载与 full verifier 结论仍不在本审查范围。

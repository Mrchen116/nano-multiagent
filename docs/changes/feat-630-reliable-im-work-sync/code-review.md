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

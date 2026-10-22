# Independent product acceptance observations — Round 1

Reviewer operates isolated localhost IM `53674`; dedicated user `nano`. Initial runtime snapshot `e1e187e0e9c4c488aba2f0ec61e8c1c48f827ab0`, base `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`. No implementation files read; no worker success narrative used. All data below fictional. Browser session `feat635-review`; simulator initially iPhone 17 Pro, UDID `638A926C-1E93-4840-B1A7-13339191A848`, actual logical width 402 (1206 pixel screenshot / 3), **not** the required 390/430 viewport.

## J1 — Budget wait and timed renewal

- 2026-10-22 14:02 CST: Web created group `c_twz3ue17`, named 独立验收635旅行规划, including test user, e2e, e2e-peer, e2e-global. Created root `tg_bc2b8093/n1`, title 独立验收：周末旅行预算, assigned e2e, initial `todo`, revision 1. Task requires asking actual budget, real two-minute Schedule, waiting, then two fictional options and in_review after reply; no internet/external sending.
- 14:03:11: Agent explicitly claimed task, revision 2, `doing`; latest change says 领取被分配的验收任务并开始执行. Thus assignment write itself remained todo; model claim was distinct.
- 14:03: budget question became visible in e2e DM `c_ui9s9kli`, although task said ask in owning group. Group had no question at that observation. This is an observed routing/instruction deviation; no implementation cause inferred.
- 14:04:28: revision 3 `waiting`, reason 等待 Test User 在群内给出周末旅行预算，未收到前不猜测预算、不给方案. Web real detail showed next check 14:06:14. `web-waiting-1280.png` captures reason, schedule, independently labelled runtime unknown. 390-wide detail captured after consumption in `web-waiting-390.png` / `web-invalid-390.png`: business reason remains, diagnostic is independent, next check becomes No valid schedule.
- 14:06: real schedule fired, group reply states budget absent, no invented budget, new ten-minute check. Revision 4 waiting schedule `schedule-994be317-878e-423d-adac-609d775e2a4e`, next `2026-10-22T06:16:31.608Z`. Native detail independently showed same reason and 14:16 time (`ios-waiting.png`). Temporary consumed schedule invalid state was observable before repair.
- 14:08:09: Web Send button sent ordinary reply 预算是两人共1200元，周末两天。 No resume command. (At mobile width Enter had inserted/preserved draft; explicit Send confirmed actual transmission.)
- 14:08:56: created child n2 行李清单预案 assigned e2e, explicitly instructed remain todo, not claim until user says start.
- 14:09: revision 6 root `in_review`, wait absent, result contains two complete options under 1200 / 2 people / 2 days; child n2 remains `todo`. Group system message links submitted result. Early response resumed work before 14:16 check; additional assignment input was present, so this demonstrates consumed reply and autonomous recovery, not a pure no-other-input wake isolation.
- 14:11: user edit confirmed n2 remains todo, revision 7. Same public product apply API attempted n2 waiting with nonexistent schedule; HTTP 400 `task_wait_schedule_invalid`, message Waiting requires an active future schedule for this task owner. Re-read retained revision 7 and n2 todo. API rejection supplements, does not alone prove Agent-side repair behavior.

## J2 — Deep task and separate owner

- 14:09–14:10: public product API created second graph `tg_8edf244f`, root n1 出行准备汇总 and child n2 装备准备 both human-owned todo; n3 深层安全清单=e2e doing; n4 Peer独立餐饮清单=e2e-peer doing. All belong to c_twz3ue17. No DB writes.
- e2e task requested first phase record then final, subsequent automatic phase complete three notes and in_review. Group visible first final at 14:10 says 阶段一结束 and only range recorded. Distinct second final at 14:11 says 第二阶段已完成; API revision 5 n3 in_review with both phases. No intervening user continue command. n1/n2 remained todo, n4 not changed by e2e.
- Peer n4 raised real permission request for task_graph write, explaining automatic assignment is not human consent. Reviewer opened native action input, inspected n4 done/result payload, tapped Allow once then Submit decision. API re-read revision 6 n4 done, n1/n2 still todo, n3 still in_review. `ios-approval-before.png` shows approval controls and separate e2e second-round result. This approval was first-round Peer work; it does not substitute the required automatic-second-round approval case.

## J3 — Native Goal settings

- Native Peer profile → Configuration → Runtime features: DSH Goal off, tools 16. `ios-goal-default.png`.
- Toggle on: tools 19. Save: visible Configuration confirmed by the node. Chats adopt it on the next turn.
- Reopened visible feature, switched off and saved; same confirmation visible. No Task modified by toggle.
- Web Global config independently showed default unchecked, three Goal tools unselected. `web-goal-default.png`; checked and Save Agent, re-read checked persisted with No changes. Unchecked and saved again before reboot. Runtime exposure next-turn still needs distinct verification.

## J4 — Native waiting target

- Public product API created `tg_77cdb0a5/n1` 原生暂停恢复, e2e-peer doing, fictional meal plan awaiting actual participant count; ask then real 20min Schedule, preserve unfinished status.
- 14:14 API re-read revision 2 waiting, reason 等待用户确认秋游用餐人数；未给人数前不猜测、不出方案, schedule `schedule-58926b7a-9f39-4291-b77b-1d618d757f3c`, session `6a87fadd-53ba-44f1-94c5-bba3a5e46d28`, next `2026-10-22T06:33:46.577Z`.

## J5：原生暂停、恢复与旧意图审批（14:28–14:35）

- 在430设备原生 Task详情，通过 AX Pause 操作 tg_77cdb0a5/n1，14:28:23 得到 rev4 paused，wait清除；390另一设备同步显示Paused。普通聊天“今天风景不错…餐饮任务继续保持暂停”消息1ba5e876...后，Peer实际答复2cdee6bf...确认保持暂停、撤销旧20分钟提醒，未恢复。
- 390长详情在首屏下方 Resume progress 被固定 Edit task 区域遮住；430等待详情Pause/Resume在屏下。CUA scroll/drag未成功滚动该sheet，关闭后底层Tasks位置却变了。记录为触控/滚动证据不足，不用AX可执行替代可见可点判断。截图 ios-long-wait390/430、ios-paused-390/430。
- 14:31原生Resume progress（AX）使同任务rev5 doing，等待信息无残留，见ios-resumed-390。
- 自动续跑消息682fc46cac2f4fc3b2e4d0fbb36b3b06首次schedule_create审批 b455fc13-dbad-43cd-b896-6fec0c06191c：理由仍称用户明确保持暂停、必须明确解除。14:33通过Web Allow once批准。
- 紧接task_graph.apply(waiting)再次要求审批 a7072522-3f0a-4899-98ac-e3c5008d7abc，理由同样为旧保持暂停；输入base_revision5、change_note“恢复后重新询问用餐人数…”。14:34再次Web Allow once，14:35读回rev6 waiting，schedule-ad04c537-3f06-43d4-b140-c57242465c4a，next06:53:12.122Z。这是两次真实额外审批摩擦，不等于UI恢复失败，也不能以最终成功掩盖。

## J6：跨树自然语言恢复与多轮续跑（进行中）

- 14:29 Web群1 @Global 明确恢复globalA/globalB；API同产品消息入口分别在群1/群2 @e2e恢复singleA/singleB。所有都从paused恢复，singleA rev3 waiting，singleB rev2 waiting，各有真实Schedule。GlobalA rev3 waiting，GlobalB rev2 doing，仍在推进。
- tg_347fe28a分阶段城市漫步方案，14:32通过产品API创建doing，要求每回合一个阶段、四阶段后in_review，无需用户继续。第1回合5d991274...14:32完成路线原则；第2自动回合0e9d7d06...14:33补携带物；14:35读到rev4阶段3雨天方案仍doing。期间singleA保持waiting，模型实际回覆确认等待不妨碍其他工作。
- Web负责人1280/390只列本人跨层级任务及父路径；深层n2视图390显示直属n3 in_review、n4done，父/祖先未机械完成。证据web-assignee-1280/390、web-deep-390。Web待办列28条通过自然列内滚动载完，其他列未重置。

## J7：停止范围、委派与返工（14:35–14:40）

- 四阶段任务tg_347fe28a在14:35:24由e2e提交in_review，4个不同自动回合分别保存阶段1–4，不需要用户“继续”。singleA等待期间保持原关联。
- 14:36:29定向`<mention type="user" target_id="u_d9lz0hfn"/> /stop`消息7726163545634389855335013b60b04e未走确定性控制确认，实际进入模型轮次，由模型task_graph.get/apply将singleA改paused，再schedule_delete。它最终暂停但不能证明原生停止屏障；current routing-delivery.md明确支持@Agent /stop，故为异常。
- 14:37 Web精确裸`/stop`真正产生“已停止当前操作，并暂缓2项进行中的任务”：Global的globalA rev4 paused、跨另一群globalB rev3 paused；Peer群1任务tg_77cdb0a5 rev7 paused；singleA paused而群2singleB仍rev2 waiting。父任务此时已in_review未重开。
- 父任务tg_b5f64042 14:33:45由用户API创建doing；Global真创建直属n2交Peer，Peer14:36:24交付三项环保建议并done；Global独立整合集合/散场原则和子成果、记录冲突检查，14:36:51父in_review rev6，非子done直接完成父。
- 14:37:50用户真实消息2771d390...要求原父任务改09:00并补下雨取消原则。14:39读到rev8 in_review，result包含返工记录及改动，原任务复用；已暂停场地任务未被恢复。

## J8：改派（14:38–14:42）

- Web编辑singleB tg_7474090d，保持Waiting选择Peer保存，真实apply含set_assignee（不是update_task.patch.assignee；两次探索错误请求400未写入）。rev3仍waiting且旧schedule owner=e2e；Peer接手后发现原关联失效，14:39自行建立新15分钟复核，rev4waiting reason“已接手任务…”，next14:54。
- API set_assignee把singleA tg_5caeacf1的paused交Peer，rev5paused，未授权恢复。
- tg_2807d2de路线改派接续：e2e第一回合写集合原则，rev2doing；用户API改派Peer rev3，保留成果与doing。14:42读到Peer更新rev4in_review，结果保留第一阶段并补解散原则。未向Peer另发开始请求。

# refactor-460-M4 — Progress

## 启动记录

- 2026-07-13：完整读取 motivation/design、Round 2 acceptance/verification、AGENTS/SPEC/注释与测试规范、LOGBOOK、worker/systematic-debugging skill；M4 目录起始仅有 `.gitkeep`。
- worktree：`milestone/refactor-460-M4` 基于同步的 `origin/unit/refactor-460` / `2158cc87`；`npm ci` 只生成 ignored dependencies。
- 基线：frontend 62 files / 581 tests passed，production build passed；`ruff check src tests` passed；`pytest -m "not e2e"` 3505 passed / 1 skipped / 23 deselected。
- systematic-debugging 初步根因：server 在 replay 前加入 live registry；resume 单批 LIMIT 500；cursor-ahead 未进入 resync；EventBridge 与 repositories 都暴露 notify；runtime 每帧读写 storage 且 <=cursor 仍 dispatch；Chat mapper 只按 event type cast；toast/notifier accumulator 分叉且 completion 身份非自包含；canonical/relay key 无共同 identity；natural silence 只有 exact token 才置 discard。
- 范围澄清：orchestrator 授权最小 Gateway `runtime_delivery/{observer.py,context.py}` 范围扩展；IM 不按空正文猜测静默，协议语义仍由 run lifecycle + visibility policy owner 决定；worker 不改 design.md。

## R1 — direct Web 静默终态归属

- Status: DONE
- Context: 隔离真 Gateway/IM/LLM 中，受控用户提示先执行真实 bash，再以空 final 结束；online/reload 均留下 `1 tool + 1 thinking`、token usage 的空 Agent row，REST 返回 completed `content=""`。同账号双浏览器在线 completion 稳定复现 preview/order 更新且 `sawUnread=false`；第二次全窗口 DOM probe 看到 app toast（`sawView=true`），说明“无 toast”不是每次发生，而未读缺口稳定，后续按竞态/身份连续性收口。
- Decision: `RunDeliveryContext` 为 canonical `web_relay` 固定 `discard_empty_completion`，observer 只在完整非空 assistant text 到达时标记 `visible_reply_committed`；成功 turn terminal 若仍未提交正文则发 tombstone。bare protocol token 继续使用 `no_reply_token` reason；non-Web shadow 保持 completion。
- Rationale: silence 是 run lifecycle + origin policy 语义；IM 只看到空 message row，不能区分协议静默与其他 transport completion。tool/thinking 是过程元数据，不是用户可见正文，不能提交 provisional bubble。
- Evidence: C1 `c3000f6e` 两个确定性失败：typed context 缺策略位、FK-enforced real handler 留下 empty completed Agent row；C2 focused 7 passed，完整 lifecycle 两文件 45 passed，相关 ruff passed。重启新代码后相同真 LLM prompt 生成 `SILENCE_FIXED_OK` 工具过程，online 随 tombstone 删除 Agent row；reload snapshot 与 REST history 都只新增用户行。截图暂存 `output/playwright/refactor-460-M4-baseline/m4-r1-natural-empty-removed-{live,reload}.png`，R4 归档。
- Rollback: 回退 C2 `7010d284`；C1 `c3000f6e` 保留缺口回归。
- Commits: C1=`c3000f6e`, C2=`7010d284`, C3=本提交。
- Next: R2 为 replay/live handoff、完整分页、epoch 回落与 unique post-commit publish 建立红测。

## R2 — IM replay/live 无缝交接与唯一发布

- Status: DONE
- Context: 确定性 blocked replay 证明旧实现先注册 live 再 replay 会让新事件超车；单页 `LIMIT 500` 会静默截断 650 条 owner backlog。
- Decision: registry 以 per-user handoff lock 原子衔接全量分页 replay 与 live 注册；broadcast 按 user id 排序加锁。Repository 以 global event-store max 判定 cursor 是否来自旧 epoch，返回 `cursor_ahead_of_event_store`；owner-filtered replay 仍只返回当前用户可见事件。EventBridge 不再接受 notify，repository post-commit 是唯一发布 owner。
- Rationale: 把顺序边界放在 server registry，不依赖客户端去重补救；不扩展 wire payload。
- Evidence: 100 个 focused IM user-stream/repository/EventBridge tests passed；覆盖 overtaking、650 drain、cursor-ahead 与 constructor reject notify。
- Rollback: 回退 C2 `648b8b3e`；C1 `a11cd56f` 保留缺口回归。
- Commits: C1=`a11cd56f`, C2=`648b8b3e`, C3=最终文档提交。
- Next: R3 关闭浏览器 cursor/storage/domain recovery。

## R3 — 浏览器 cursor 与 domain recovery 连续性

- Status: DONE
- Context: runtime 旧路径每帧读写 sessionStorage、`event_id <= cursor` 仍 dispatch，cursor 高于新 DB max 不允许回落；Chat mapper 对已知 canonical type 直接 cast。
- Decision: cursor 每 user 仅 hydrate 一次，memory 热路径单调；storage read/write 失败分别熔断。冷 cursor=0 先 `/sync` 建 baseline 再开 socket；epoch reason 允许 replace。已知 Chat payload 窄验证，domain error 合并触发权威 recovery。
- Rationale: cursor 在 dispatch 前接管 exactly-once 语义；异常 canonical frame 必须恢复权威数据，不得让 reducer 以错误 shape 继续。
- Evidence: runtime/reducer/workspace 76 tests passed；production build passed。Full frontend 门禁 64 files / 584 tests passed。
- Rollback: 回退 C2 `39290a5c`；C1 `570fe592` 保留缺口回归。
- Commits: C1=`570fe592`, C2=`39290a5c`, C3=最终文档提交。
- Next: R4 统一 app/desktop 提醒与真双浏览器收口。

## R4 — 共享通知生命周期与全量真栈收口

- Status: DONE
- Context: 真同账号 A/B 基线稳定复现 preview/order 更新但 A 未读消失；app toast 不是每次缺失，证明根因是 lifecycle/cache race 而非单一渲染分支。
- Decision: 抽取共享 canonical completion accumulator；`message.completed` 以 message identity 唯一产生 Agent candidate，`relay.completed` 仅 receipt，`message_created` alias 退役。Pending sender 最小元数据按 user 存 sessionStorage 跨 reload。同账号 server unread 仍权威，本 tab 亲眼看到的未打开 completion 在视图层 overlay 最小未读 1，进入会话即清除。
- Rationale: app/desktop 不再拥有两套分叉 accumulator；不给 wire 添 run_id，不把 direct-Web relay receipt 当第二个回复 owner。未读 overlay 不写回权威 query cache，避免 sibling refetch 竞态和订阅回路。
- Evidence: focused 通知/workspace 60 tests + build passed。真 B completion `M4_FINAL_NOTIFY_0713` 后，A 同时有且仅有一个 toast、preview/time 置顶、unread=1；clean cursor=0 浏览器 toast=0/unread overlay=0。完整证据见 `evidence/README.md`。
- Rollback: 回退 C2 `c8db7c1c`；C1 `63bfae21` 保留缺口回归。
- Commits: C1=`63bfae21`, C2=`c8db7c1c`, C3=最终文档提交。
- Next: milestone 经 rebase 后复验，并入 `unit/refactor-460`。

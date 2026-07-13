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

- Status: TODO
- Context: R1 已关闭；进入 replay/live server owner。
- Decision: pending.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: C1 锁定注册竞态、500 截断、cursor-ahead epoch 与 repository/bridge 双 notify。

## R3 — 浏览器 cursor 与 domain recovery 连续性

- Status: TODO
- Context: pending R2.
- Decision: pending.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: pending.

## R4 — 共享通知生命周期与全量真栈收口

- Status: TODO
- Context: pending R3.
- Decision: pending.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: pending.

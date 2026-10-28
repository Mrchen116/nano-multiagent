# refactor-673 — 独立产品验收报告

> 对齐：motivation.md；Round 1，full，2026-10-28。
> Validation snapshot: `ff326c351d104447028f4b185740ab6d6be55de6 → 7a77516c0dfd7a0b41d838b193bc5ca9318397d5`。
> 产品/测试基线：`ff9a2a39f`；HEAD 已独立核对。caller 提供该版本构建与启动，本轮确认实际进程为本 worktree 的 `apps/im-server/lib/main.js`、端口 61122、PID 53281；GET /health 为 ok，真实登录成功。

## Verdict

**pass**。问题数 0；Highest Required Action: pass；无需复验。

## 用户旅程体验

按 design 的后端验收平台，直接使用客户端相同 HTTP 创建、编辑、解散及读取接口，并连接真实 `/im/ws/user` 用户流。未读取实现定位、未重跑自动化回归、未调用真实模型；不作 Web/iOS 视觉评价。

创建者可解散新建测试群；任务历史仍可读取，未完成节点关闭，完成事实和结果保留。历史读投影 `can_edit=false`，实际写入返回 400 `conversation_dissolved`，群不再出现在日常列表。改变过的节点明确显示 Test User 与 `Conversation dissolved`；保留完成节点原修改者和时刻，避免把既有成果错误归因于本次解散。完成根节点仅清空当前候选时也正确记录真人审计，选项说明保留。

非创建者成员可以读但 DELETE 返回 403；注入保存失败后 HTTP 返回 500，会话仍可写，图、投递及事件未部分改变。成功后在线用户流收到 membership 失效事件，事件处理时真实 HTTP 已读到 dissolved_at；重新读取任务得到 closed。失败期间未增加失效事件。

## 环境、前置与证据边界

- `.e2e-daily.json` 的 P/E/Q/PA、所属 node、模型与实际 `/agents`、`/nodes`、`/conversations` 一致；节点 online。测试身份 nano，专用地址 `http://127.0.0.1:61122`。
- 只使用本轮新建群；daily 基线 `c_ectg3fgx`、`c_09262c00a9c9` 最后仍未解散。未向 daily Agent 发送模型任务。
- 混合状态群 `c_8zro885b`，图 `tg_3b746d35`：HTTP 建图后仅在此隔离 SQLite 中补合成历史 Agent 审计、真人负责人、waiting/resume 字段，随后真正 HTTP 解散、读取。没有真实 Schedule 或 Agent 执行，不能证明 Schedule 取消或模型行为。
- 第二真人 `review673` 为本隔离库的合成测试身份，使用真实登录与公司群成员接口验收授权。原个人群添加该真人按空间规则返回 404，改用公司测试群后正常验收，不绕过成员权限。
- 投递 fixture 最终使用合法 `queued/sent/accepted`，均取消。早期误造的 `status=received` 不是合法 relay 状态，未纳入产品缺陷或通过依据；保留在本轮临时群供 caller 清理。
- 所有 `review673_fail` 故障 trigger 已移除。未启动或停止共享栈；临时 WS 客户端已关闭。未修改代码、测试或设计，报告按 caller 要求不提交。
- 本机证据目录：`/tmp/673-acceptance/`。这些证据是本次观察材料，不提交原始数据库、令牌、日志或脚本。

## Reference Artifacts Reviewed

N/A。design 明确客户端界面无变化，无原型或 must-match 视觉契约。本轮仅裁决受影响后端旅程。

## 问题清单

无 blocking、major、minor 问题。

## 验收标准覆盖

### Requirement: 解散保持历史只读与完成事实 — pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 创建者解散有多种状态任务的群 | motivation.md | 走既有 HTTP 建图/解散/重读，与解散前逐字段对比；todo/waiting/paused/in_review 关闭，done/closed 保持；ID/层级/创建者/负责人/结果保持，选项清空但说明保持；历史写入被拒、列表移除 | `state.json`、`result.json`、`finish.py`；混合群及图见上 | pass | doing 经 HTTP 创建后补为历史 waiting；另 `live-result.json` 的 todo 根关闭。无需改变的 done/closed 审计逐字段保持；全完成图由 `notifications-result.json` 另验 |
| 非创建者及失败操作 | motivation.md | 第二成员 GET 成功、DELETE 403，前后图/消息/会话一致；限定图的临时 SQLite trigger 导致 DELETE 500，多图和投递事务回滚，移除 trigger 后同入口成功 | `noncreator-http.json`；`journey.py`；`notifications-http.json`；`live-result.json` | pass | 非创建者最终群 `c_kuf86xrs`；多图回滚为本轮执行观察，保存失败与不发成功事件另有独立持久证据 |

### Requirement: 解散的任务修改准确归因 — pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Agent 修改后的任务被真人解散关闭 | motivation.md | 合成旧 Agent 审计/等待/恢复前置，经真实 DELETE 后 GET：改动节点 actor=user、id 为当前真人；图/节点同一解散时刻，说明 Conversation dissolved；wait/resume 消失；完成 scope 仅选项变化也归因真人；SQL/JSON 图修改者及 revision 对齐 | `state.json`、`result.json`、`journey.py`、`finish.py` | pass | 未声称真实 Agent 或 Schedule 行为；未改动完成叶子的原 Agent 审计 |

### Requirement: 解散不产生新的任务协作消息 — pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 群包含任务或没有任务 | motivation.md | 有任务/空群解散前后 GET messages 一致；合法三类投递全部 cancelled，无新增 relay；用户 WS 在失败期间无新增失效，成功后收到失效且事件回调读到已解散，后续历史任务 closed | `result.json`（空群）、`notifications-result.json`、`notifications-http.json`、`live-result.json` | pass | `c_v5cdqgyd` 验证合法投递；`c_i865w7nc` 独立观察失败/成功在线通知。原 task 系统消息来自前置任务编辑，不是解散新增 |

## 上层文档同步

- [x] `SPEC.md`：无需更新；未改变跨包边界。
- [x] `docs/specs/im/task-graphs.md`：需要归并本 unit delta-spec，当前尚未反映真人解散的审计/等待恢复字段增量；交 caller 完成交付归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

report_commit: 未提交（caller 明确要求）；gh_issues_filed: 0。

# refactor-489-M8 — Progress

## Baseline / Audit

- Claim: M8 派发范围基线可稳定收集运行，并已定位完全重复、源码形态、退役实现和跨层重复候选。
- Baseline: `origin/unit/refactor-489@6d4ebd793`。
- Method: 枚举 4 个 root 文件与排除 M6/M7/M13 后的 85 个 `tests/unit/personal_assistant/` 文件；运行完整 pytest；用 AST 比较测试函数体并搜索 source/private/historical 断言。
- Result: PASS；`634 passed`（23.18s）；发现 26 组完全重复函数，另有 source scan、退役 setter/singleton 缺席、CC 逐字提示词及合成 thinking 断言。
- Limit: 本 unit 零产品行为变更，不以 unit 测试替代 M13 的真实进程/E2E 证据；M8 只维护派发的 unit 测试资产。

## R1 — 收敛完全重复测试

- 状态: DONE
- Context: 基线 AST 发现 26 组函数体完全相同的测试，分散在聚合文件与按 seam 拆分后的 owner 文件中；继续双跑不会增加独立风险覆盖。
- Decision: 把外部会话 key 合入 `test_gateway_pipeline_channel.py`；保留专属 auth/relay/upstream/dedup/metadata/agent-session owner；删除聚合文件或其中的重复函数。authenticated IM owner 的 shadow sync 是唯一风险，继续保留。
- Rationale: 完全相同的 Arrange/Act/Assert 不可能提供第二种失效信号；按 channel、auth、relay、metadata、agent-session seam 保留一份可让失败直接定位 owner。
- Evidence:
  - Tests: 相关 10 个 owner 文件 `70 passed`；AST 再扫描 M8 全域不再发现任何完全重复函数体；`git diff --check` 通过。
  - Entry: N/A（零产品行为重构）；外部 identity、IM auth header、relay dedup/restart、session metadata/lifecycle 仍从各自公开调用结果观察。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 现有 unit regression 原位保留；真实进程/E2E 归 M13，本 milestone 不复制。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交，恢复计划提交 `15fef707a` 的测试树。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R2 删除退役实现缺席断言与源码形态扫描，把仍存在的风险改写到公开结果。

## R2 — 移除退役实现与源码形态断言

- 状态: DONE
- Context: 部分测试通过 `inspect.getsource`、private attr、兼容 setter 未调用、符号可导入或外部项目提示词逐字内容来推断行为；这些信号会被无行为变化的重构触发，也不能证明当前运行时结果。
- Decision: 删除 task tracker/composition 源码扫描、legacy context 镜像、compat setter、singleton/旧 dispatcher 缺席和内部 enum 推导断言；`send_message` 合并到 dispatch/回执结果，Gateway shutdown 只保留一次异步关闭，reject/terminal 改守公开语义和值。
- Rationale: 当前行为风险应由任务 drain/cancel、typed delivery receipt、持久 session 恢复、真实 HTTP dispatch、shutdown 所有权与 SDK 公开值直接观察；退役路径不存在和源码长相不构成第二份产品保护。
- Evidence:
  - Tests: 10 个相关 owner/相邻 shutdown 文件 `78 passed`；changed files `ruff check` 与 `git diff --check` 通过。
  - Entry: N/A（测试资产清理）；运行入口仍是 GatewayRuntime、SendMessageTool、binding store 与公开 SDK 函数。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: shutdown resource graph/timeout isolation 与 task drain/cancel 原位保留；真实进程证据仍归 M13。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交，恢复 R1 提交 `666978c38` 的测试树。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R3 收敛 IM 聚合、图片失败、thinking mirror、SSE 与 relay dedup 的高层重复。

## R3 — 把高层重复收敛到最低行为 seam

- 状态: DONE
- Context: Gateway IM 聚合测试重复验证 mention/no-fanout/sender prefix/session refresh；图片 pipeline 重复 resolver 的 MIME/格式算法；thinking 测试自己挑选 content，并未经过 runtime observer；relay restart/capacity 断言 private deque。
- Decision: IM 聚合只保留 reply-to-agent 与无 IM 的本地 channel；图片 pipeline 保留 resolver→Kernel 接线、三类用户反馈和失败后续轮可用，解析算法归 resolver；reasoning 输入移入真实 external bubble mirror；relay dedup 从重启后拒绝重放和淘汰后可再次发送观察；SSE 合并成功路径并对失败类型精确断言。
- Rationale: 每个风险只由能真正穿过该 seam 的最低测试拥有；跨层连接风险继续保留，但不在高层复制 lower owner 已能独立定位的算法与策略。
- Evidence:
  - Tests: 11 个相关 owner/相邻保护文件 `116 passed`；changed files `ruff check` 通过。
  - Entry: Gateway inbound、ImageAttachmentResolver、WebRelayAdapter/RelayDeduplicationStore 与 runtime observer 的实际公开调用均被执行。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: reply trigger、离线 local channel、图片失败后同会话下一轮、持久 dedup 重启均保留；ACK/reconnect/outbox/session/shutdown 风险未改动。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交，恢复 R2 提交 `78b3e3ae2` 的测试树。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R4 运行 M8 全量门禁、collect-only 对账并完成范围审计。

## R4 — 全量门禁与证据对账

- 状态: DONE
- Context: roadpoints 完成后需要证明整个 M8 派发域仍可收集和运行，并确认没有借测试清理改动产品代码、current spec 或相邻 milestone。
- Decision: 按 design 的 root/assistant 排除规则重新枚举 89 个测试文件，执行 pytest 与 collect-only；对同一集合执行 ruff，并运行 docs integrity、diff whitespace 与相对 unit 分支的 changed-path 审计。
- Rationale: 分簇门禁证明局部意图，全域收集和执行用于发现跨文件 fixture/import/顺序回归；路径审计保证 milestone 权限边界。
- Evidence:
  - Tests: M8 全域 `626 passed`（20.53s，2 个第三方 deprecation warnings）；collect-only `626 tests collected`（2.06s）。
  - Entry: 4 个 root + 85 个 top-level `personal_assistant` owner 文件按派发规则执行；测试集合自身可独立收集。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: `ruff check` 全域通过；`scripts/docs_check.py` 通过（202 maintained sources / 65 routes）；`git diff --check` 通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Result: 相对 `origin/unit/refactor-489` 仅有 19 个授权测试路径与 M8 的 tasks/progress/.gitkeep；删除 2 个聚合测试文件、改写 17 个 owner 文件，零产品代码与 current spec 变更。
- Limit: 本 milestone 不运行真实服务；进程、端口、WebSocket 与完整用户旅程证据由 M13 独立拥有。第三方 Lark SDK 的 2 个 deprecation warnings 为既有环境噪声。
- Rollback: 依次回退 R3、R2、R1 与 plan 提交即可恢复 unit 基线测试树。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: rebase 最新 unit 分支，重跑 M8 门禁后合并并推送 unit。

## Promotion Candidates

None.

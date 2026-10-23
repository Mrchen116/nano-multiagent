# Verification Report: bugfix-647-trajectory-sync

> Validation snapshot: `236a4698c7a8a2d03efa00c35049914d2422771d → a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7`

## Round 1 Metadata

- unit_id: `bugfix-647-trajectory-sync`
- reviewer: `/root/static_review`，未参与受审实现；与 full code review 合并执行，分别保留结论。
- verification_mode: `full`，同时核对 `no spec delta`
- review_round: `1`
- branch: `codex/bugfix-647-trajectory-sync`
- verify_worktree_dir: `/Users/czj/.codex/worktrees/trajectory-sync/nano-multiagent`
- validated_at: `a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7`
- executed_base: `236a4698c7a8a2d03efa00c35049914d2422771d`
- requires_full_verification: `false`（本轮本身已为 full）
- 现场：开审时 HEAD 与指定版本一致且无 dirty；仅写两份审查报告，没有启动/访问产品服务、修改产品/测试/设计或提交。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 全部 6 类 implementation 退出标准及 incident 的 2 个 Requirement 已覆盖 |
| Correctness | 2/2 Requirement aligned；关键失败确认与生命周期已独立复验 |
| Coherence | Followed；公开 DSH 边界、轻量目录、完整自有上下文及两条 drain 与设计一致 |
| Spec reconciliation | no spec delta；未发现遗漏的新增对外行为 |
| Issues | 0 CRITICAL / 0 WARNING / 0 SUGGESTION |
| Verdict | **PASS — 实现与契约验证通过**；产品 reviewer 与整套交付/CI 门禁另行记录 |

## Completeness

M1（`design.md:56`）的 worker 退出标准逐项核对：

| 退出标准 | 直接证据 | 结果 |
|---|---|---|
| 真实压缩冷历史前后对照、重复同步零冷日志读取 | `M1-fix/evidence/performance.md:5` 起；400 子会话、151.97 MiB 子日志，重复 800→0 次 handle read；受审 reader blob 相同 | covered |
| 新增、续写、孙会话与重启 | `descendants.test.ts:6`；`tool-presentation.test.ts:52` 真 RuntimeClient 重启；性能实验 updateVisible/newVisible/nestedVisible/fullReplay 全为 true | covered |
| 跨批工具结果保真 | `descendants.test.ts:37` 重放先前 call+新 result；`global-agent.test.ts:463` 正确工具名与 1ms duration；真实 presenter 保真 | covered |
| 同 cursor fallback completion 的终态和逻辑 turn | `global-agent.test.ts:433`，终态补齐至 turn 1、elapsed 6ms、再同步不重复；真实 RPC 的 modelVersions 重放见 `tool-presentation.test.ts:45` | covered |
| 旧模型快照不能配上较新事件 cut | `descendants.test.ts:51` 的 awaited observation 与冷 replay 回调重新捕获；`index.ts:390` 及 `descendants.ts:78` 间的实际同步接线 | covered |
| 子同步不阻塞业务、根 durable 错误仍拒绝 | `global-agent.test.ts:405` 对 task_graph/send_message 两种调用；独立 child drain busy/stop 实验 | covered |

- incident Requirement/Scenario 均有实现与直接证据，映射见下一节。
- Prototype / Reference：N/A，没有客户端布局、视觉或交互变更。
- M1 的 `[reviewer]` 工作视图、新子结果、实际发送/任务与新消息重验属于独立产品验收；本 verifier 核对其实现/自动回归保护，不替代产品 reviewer 的真实旅程结论。

## Correctness

| Requirement / Scenario | 实现位置 | 测试与证据 | 状态 |
|---|---|---|---|
| 未变化冷历史不反复拖慢当前工作 / 数百冷子会话连续查任务、发送 | `packages/dsh-integration/src/descendants.ts:66`，`src/index.ts:384`；`packages/personal-assistant/src/global-agent.ts:429`、`:518`、`:605` | 永久 reader 零 body read + 全 own suffix；400 个真实压缩持久会话前后对照；PA pending child 对两业务入口的回归 | aligned |
| 发送前重验、授权来源、Inbox 消费和持久语义保留 | `global-agent.ts:358` binding 检查；`:502` personal send 原入口；`:544` 发送边界；`:611` durable 拒绝与 `:621` commitRead | `global-agent.test.ts:87` 的 8 类目标纠正/held 草稿/新调用重验，`:405` 根 durable 拒绝；task-graph-permission 真运行允许/拒绝；这些路径在 diff 中保持原行为 | aligned |
| 子轨迹完整可恢复 / 新增、续写、孙会话、重启 | `descendants.ts:37` 稳定先序目录、`:78` observation cut、`:84` 完整 own suffix；`global-agent.ts:665` 归属与投影 | reader 新增/续写/孙会话；真实 RuntimeClient 重启及 presenter；同 cursor 模型完成补终态/耗时/逻辑 turn；性能 fixture 实际持久目录 | aligned |
| 读取或持久化失败不推进成功游标，后续恢复 | `descendants.ts:47` diagnostic、`:86` 成功后缓存；`global-agent.ts:667` 投影、`:672` 同步确认两项；`:644` 按 root 合并 dirty | 性能 failure diagnostic/unchangedCursor/retryVisible；独立 journal 写失败后两确认均为空、重试后同时确认；busy/stop 等待 child drain | aligned |

### 独立复验

命令：`pnpm exec tsx /tmp/nano-647-static-review.mts`，本轮 exit 0。实验只使用内存 NodeStore/InboxStore 与 stub runtime/query，无端口、生产数据或模型调用。六项结果均为 true：

- 相同 cursor、不同 durable revision 仍恢复目录并发现 grandchild。
- persistence 服务 identity 替换使旧 cache 失效。
- 冷读取失败返回 diagnostic 且无 throughSeq；下一轮读取恢复。
- child journal 写失败时 cursor/modelVersion 均不确认。
- 完整投影成功后两项共同确认。
- child drain 挂起期间 busy=true，stop 保持 pending，释放后 stop 完成且 busy=false。

该临时脚本留在 `/tmp` 供本轮复查，没有加入长期测试。公共 persistence/observation 类型及安装实现同时核对，不能用 stub 的行为替代公开 revision 契约。

## Coherence

| design 决策 | 遵守 | 代码证据 |
|---|---|---|
| 只存轻量 metadata，不扩大 prepared cache、不留完整继承历史 | 是 | `descendants.ts:9` Catalog 仅 identity/revision/cursor/children，`:19` Map；每个 observation using 释放；没有上游改动 |
| observation 版本代表已读 cut，stat 仅判断复用 | 是 | `descendants.ts:71` 使用同 persistence identity+revision；`:86` 存 observation.revision；live 不复用 durable revision，stat 后重新检查 live |
| modelRuns/version 绑定同一同步 cut，消费者双确认 | 是 | `index.ts:391` structuredClone+digest；`descendants.ts:81` 回调后无 await 即 materialize；`global-agent.ts:672` 两项在投影后推进 |
| 根证据与子展示分别排队，保留发送/Inbox/恢复生命周期 | 是 | `global-agent.ts:600` 两 drain；`:429`/`:518` 业务仅等根；`:68` busy、`:693` stop 覆盖 child；projectChildren 不写 NodeStore |
| 只有 integration 依赖公开 DSH persistence，不添加 loop/private import/HTTP 内核 | 是 | integration package/lock importer 的同版本 dependency；`descendants.ts:4` 使用公开 root export；架构 contract 的 Python gate 通过 |
| 首次冷恢复成本明确，无 schema migration | 是 | evidence 首次约 9.63s、重建 Reader 约 10.32s 与完整恢复实测；产品没有 DB schema 改动 |

### Prototype / Reference Contract

N/A。

## Evidence 与交付门禁边界

| 证据 | 命令 / 定位 | 本次核对结果 |
|---|---|---|
| 相关 PA + 真 presenter | `pnpm exec vitest run packages/personal-assistant/tests/global-agent.test.ts packages/dsh-integration/tests/tool-presentation.test.ts`；`/tmp/nano-647-green.log` | 2 files / 48 passed |
| reader/model fallback/trajectory/task 权限 | `pnpm exec vitest run packages/dsh-integration/tests/descendants.test.ts packages/dsh-integration/tests/model-fallback.test.ts packages/dsh-integration/tests/trajectory-runs.test.ts packages/dsh-integration/tests/task-graph-permission.test.ts`；`/tmp/nano-647-focused.log` | 4 files / 22 passed |
| Build / typecheck | `/tmp/nano-647-final-build.log`、`/tmp/nano-647-typecheck.log` | 各包 completed，无错误 |
| Docs / Python / ruff / iOS runtime | `/tmp/nano-647-{docs,python,ruff,ios-runtime}.log`；caller 执行结果 | docs integrity passed；65 Python passed / 31 deselected；ruff passed；iOS runtime generator+tsc passed |
| 前端回归 | `/tmp/nano-647-frontend-tests.log` | 103 files / 963 passed；本次无前端 diff |
| 性能与读取失败 | `/tmp/nano-647-benchmark/{baseline,fixed,failure}.json`；durable 摘要 `M1-fix/evidence/performance.md` | 与报告逐项相符；reader 文件 blob `4b8e826db45d71ca82e182f81d3503522c263c04` 与固定受审版本一致 |
| 全量后端 | `/tmp/nano-647-vitest.log` | 首轮 600 passed、workspace-tools 单项 90s timeout；原样隔离重跑 1 passed / 49.27s（`/tmp/nano-647-workspace-retry.log`），无代码/timeout 修改。完整后端 `pnpm exec vitest run --maxWorkers=2` 已 exit 0，123 files / 601 tests passed，309.63s（`/tmp/nano-647-vitest-stable.log`） |
| Audit | `/tmp/nano-647-audit.log` | 8 条现存 dependency advisories；本 diff 仅新增已存在锁图的 persistence importer，没有升级这些工具/前端依赖；不宣称 audit 全绿 |

以上复用 caller 的适用证据并独立补验关键条件，不重复启动整套测试。本 verifier PASS 只表示本 unit 实现/契约没有 CRITICAL/WARNING；首轮全量超时可能与并发负载有关（推断，未精确证明）；完整重跑已全绿，产品验收及 CI 仍由各自交付记录闭环，不能据此宣称全部本地/CI 已绿或生产已经改善。

## Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

## Spec Reconciliation

**no spec delta — aligned。**

- `docs/specs/gateway/global-agent.md:306` 已要求查询回复不等待无关历史，同步分离是在恢复现有契约。
- `docs/specs/im/agent-work.md:23`、`:38`、`:55` 已要求子归属、工具结果、真实状态和持久回看，`:166` 已要求工作同步与聊天独立；完整 own suffix 与双确认保护这些既有义务。
- RPC 的 modelVersions/modelVersion 为现有产品层与 runtime 的内部投影确认字段，events 为空仅表示已确认内容无变化；旧调用缺确认值仍全量重放。没有新用户入口、权限、展示模型、SLA 或外部 API 承诺。
- 检查完整 unit diff，没有 delta-spec 需要归并，也没有遗漏的新增用户可观察行为；本次不修改 current spec 来迎合实现。

本轮未使用或接管产品 reviewer 的隔离栈；无本轮真实服务需要清理。报告由 caller 提交，report_commit 待 caller 固化。

## 最终验证状态补充

`pnpm exec vitest run --maxWorkers=2` 已在受审源码 `a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7` 上完成：exit 0，**123 files / 601 tests passed**，309.63s，日志 `/tmp/nano-647-vitest-stable.log`。本次仅读取结果、补全报告，没有追加测试或重新审查。首轮 600 passed + workspace-tools 90s 超时、原样隔离复验 1 passed 的事实仍保留；并发负载归因仍只是合理推断。完整后端本地门禁现已通过，verifier 结论保持 PASS、0 CRITICAL / 0 WARNING / 0 SUGGESTION、no spec delta aligned。最终同步后的源码 retained 依据由 caller 记录，validated_at/executed_base 不变。

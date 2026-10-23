# perf-651-history-export — 验收报告

> Round 1；mode=full；2026-10-24（Asia/Shanghai）
>
> executed_base: `55376c1112ff870837a6ee65febf52e1f3686a9b`
>
> validated_at: `b0939cd0658c778671d71b6e4a749201e1a3c5e6`

## Verdict

**pass**。三个首文档用户场景与四个 delta 场景均通过；blocking / major / minor = 0 / 0 / 0。Highest Required Action: pass。

## 用户旅程体验与环境边界

按 design 的 Runbook，以用户和工具实际消费的 workspace JSONL 文件、PA 实际使用的 `session.submit` / `session.fork` / `session.export` RPC 验收。使用本 worktree 已构建 lib、Node 24.22.1 和锁定 DSH 0.2.1-alpha.1 的真实 RuntimeClient 子进程；fixture 仅接管模型回复，不替代会话、持久化、fork 或导出。无需外网。运行前核实 HEAD 与上述 validated_at 相同，工作树干净；构建由 caller 准备，本轮未重复全量 CI。

本轮独立读取、解析实际生成文件，没有以已有测试通过或 worker 叙述代替观察。可读行保留时间、角色、来源；正文中真人 envelope 被去除，图片显示 `[image]`。源会话与分支文件可清楚区分各自新增内容；导出 RPC 返回可实际读取的原始文件路径。原始快照在继续聊天后保持完整且不变化，再次请求后更新到新切面。无前端变化，视觉评价 N/A。

未运行 Web/iOS、真实模型、PA distill Skill 或生产舰队；本轮证明其同一 RPC 下游文件输入可读，不宣称提炼内容质量、生产时延或 UI 验收。性能工作量门槛属于 worker 验证，不在本产品旅程中重复 benchmark。

临时驱动：`/tmp/perf651-acceptance-image.mjs`；逐步观察记录：`/tmp/perf651-acceptance-results.json`。这些是本地一次性辅助证据，不纳入交付。下方保留决定性结果，报告不依赖临时文件长期存在。

## 逐场景观察证据

### E1 — 连续聊天与内容保真

在 mkdtemp 隔离 home/cwd 中创建 `acceptance-source`，依次提交真人 `REVIEW_ONE`（附有效 2×2 PNG）和 `REVIEW_TWO`，等待 lookup terminal=completed 后请求导出。原始文件 25 行，逐行 JSON 解析成功；格式头为 `type=nano-dsh-history, version=1`，内嵌原生 header version=4、id=acceptance-source。可读文件 5 行，依次为：

1. user / source=user / `REVIEW_ONE\n[image]`
2. user / source=runtime-context / 当前运行环境上下文
3. assistant / source=model / `REVIEW_REPLY_1`
4. user / source=user / `REVIEW_TWO`
5. assistant / source=model / `REVIEW_REPLY_2`

两个真人正文、图片占位与两次模型回复各出现一次；真人正文没有 `Message time:` envelope。后续源会话新增 `REVIEW_AFTER_POINT` 和 `REVIEW_SOURCE_AGAIN` 后，可读文件 9 行，原有消息仍各一次、四轮 user/model 内容完整。

### E2 — 延迟读取与显式刷新

两轮后保存 RPC 返回路径及原始文件全部字节。继续完成 `REVIEW_AFTER_POINT`，从原路径延迟读取：与先前文件逐字节相等，仍为 25 行完整 JSONL。再次 `session.export` 返回同一路径，读取变为 33 行完整 JSONL，包含 `REVIEW_AFTER_POINT`。没有把自动聊天轮次误当成原始文件的最新查询接口。

### E3 — 分支前缀与独立增长

选取第二轮 assistant/message 的真实 message id，在源会话完成 `REVIEW_AFTER_POINT` 后 fork。分支 id 为 `session-7b97e29e-537b-4797-81b6-2f4fcbd629bf`。提交 `REVIEW_BRANCH` 并导出，原始文件 36 行，包含 ONE、TWO、BRANCH，不含 AFTER_POINT。可读文件 8 行，保留源前两轮及其图片占位，加分支 runtime-context 和本轮消息；分支 user/model 各一次。源会话继续完成 SOURCE_AGAIN，其文件不含 BRANCH，保持可用。

### E4 — 重启恢复、失败反馈及重试

正常 shutdown 后，将分支可读文件改成 `BROKEN_PARTIAL_LINE`，删除源会话可读文件，保留原生记录。重新 RuntimeClient initialize 同一 bindings：分支可读文件与损坏前逐字节相同，源可读文件恢复 9 行（四轮 user/model 加原有 runtime-context）。随后分支提交 `REVIEW_RESTART_BRANCH` 完成，可读文件增至 10 行，原先前缀不丢失、新真人内容一次。

再把分支原始导出路径换成目录，调用 `session.export`，真实返回 `RpcError: EISDIR: illegal operation on a directory, rename ...jsonl.tmp -> ...jsonl`，没有伪报成功路径。移除该临时目录，再次请求成功，返回文件可逐行解析为 46 行，包含 RESTART_BRANCH。最终正常 shutdown 并删除隔离 home/cwd，未留下本轮 runtime 服务。

图片首次辅助尝试使用了无效 PNG 字节，被入口明确拒绝 `Unsupported or malformed image data`；修正为有效本地生成 PNG 后完整旅程通过。该准备问题不计产品缺陷。

## Reference Artifacts Reviewed

N/A：无前端改动、无原型或 must-match 视觉契约。已读 motivation、design Runbook、delta 和对应 current routing-delivery 可读副本条款。

## 问题清单

无。未创建外部 issue。

## 验收标准覆盖

| 来源 Requirement / Scenario | 验证方式与证据 | 结果 |
|---|---|---|
| motivation / 完整历史继续可供阅读和提炼 / 连续聊天后的完整副本 | 真实 RPC、实际文件读取；E1、E2，既有文本、来源、图片与新增消息保真，完整原始文件路径可读 | pass |
| motivation / fork 保留继承边界且独立增长 / 从历史消息分支后继续聊天 | 从第二轮真实 assistant message fork；E3 | pass |
| motivation / 恢复不依赖派生副本 / 导出中断后恢复 | 损坏/删除派生副本后重启；失败 RPC 后重试；E4 | pass |
| delta / 原生历史导出在完成边界提供完整派生副本 / 连续轮次导出完整且不重复 | E1、E2 | pass |
| delta / 同上 / 延迟提炼读取完整原始快照 | E2；后续聊天不改旧切面，再次显式请求发布完整新文件 | pass |
| delta / 同上 / 分支导出包含自己的完整历史 | E3，包含指定前缀与分支消息，排除源分支点后消息 | pass |
| delta / 同上 / 派生写入失败后重建 | E4，启动重建及失败不伪报成功、重试成功 | pass |

上述 perf 不变性按已批准目标与当前文件/RPC 既有语义走查；未重新运行旧基线服务进行双版本 UI 对照。

## 上层文档同步

- [x] `SPEC.md`：无需更新；跨包职责未变化。
- [x] `docs/specs/gateway/routing-delivery.md`：需要由 orchestrator 收尾归并已存在 delta，明确原始文件显式快照、可读副本自动更新和重建边界；本轮 reviewer 不修改 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

报告按 caller 明确要求只写文件、不提交。report_commit: N/A（交主 Agent 集中交付）。

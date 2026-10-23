# bugfix-647 Code Review

## Round 1

- reviewer: `/root/static_review`，未参与实现；合并执行静态审查与 verifier，结论分别保留。
- review_mode: `full`
- executed_base: `236a4698c7a8a2d03efa00c35049914d2422771d`
- validated_at: `a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7`
- diff_range: `236a4698c7a8a2d03efa00c35049914d2422771d...a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7`
- checkout: `/Users/czj/.codex/worktrees/trajectory-sync/nano-multiagent`；branch: `codex/bugfix-647-trajectory-sync`。开审 HEAD 与指定版本相同，working tree clean；只写本报告与 `verification.md`，不修改受审对象、不提交。
- completed_at: `2026-10-23T23:06:00+08:00`（约）

## Findings

```json
[]
```

没有发现具有实际触发条件、需 maintainer 处理的存活缺陷。

## Coverage

- 审查完整 15 文件 diff、incident/design、Gate 2 三轮及性能证据。核对调用者 `session.descendants`、`GlobalAgent` 通知/恢复/发送/任务入口，及 `logicalEvents`、`projectWorkEvent`、Inbox journal 幂等语义；没有把仅看实现一致当作正确性依据。
- `packages/dsh-integration/src/descendants.ts:66`：冷快路同时要求同一公开 persistence identity、observation revision、消费者 cursor 和投影版本确认；revision 变化时即便 cursor 相同仍恢复目录。live 先 flush，stat 后重新检查是否已加载。缓存只保存 children/cursor/revision/identity，不持有完整 Session、observation 或继承事件。
- `packages/dsh-integration/src/descendants.ts:78`、`src/index.ts:390`：取得 observation 后同步深拷贝 fallback 状态并计算 digest，直到取出该事件 cut 之间没有 await；冷快路需要 replay 时再次捕获。same-cursor 模型完成会重放完整自有上下文，避免 Gate 2 已证实的终态丢失和错误逻辑 turn。
- `packages/personal-assistant/src/global-agent.ts:660`：每个 child 的注册、模型 notices、事件投影成功后才确认 cursor/modelVersion；失败后旧确认仍可重放。reader 的服务端 cache 不是消费者成功确认。跨批工具使用完整 own suffix，保留已有调用、source、模型与耗时上下文。
- `packages/personal-assistant/src/global-agent.ts:600`：根/后代分别按 root 合并 dirty 通知，通知与恢复仍追踪两者，业务入口只等待根 durable/Inbox 取证。`busy` 和 `stop` 覆盖 child drain。已有 Inbox 消费、发送前 blocking/revalidation、publication 的 held/unknown/status 恢复，以及 personal send/子工具调用的原路径未被改写或收紧。
- 新 dependency 是已存在锁图中的同版本公开 `dsh-session-persistence`，仅 integration 引入；没有 private import、上游 patch、第二执行循环、额外持久缓存或跨包职责迁移。

## Evidence

1. 复用 `/tmp/nano-647-green.log`：global-agent + tool-presentation，48 passed；`/tmp/nano-647-focused.log`：descendants/model-fallback/trajectory-runs/task-graph-permission，22 passed。真实 DSH presenter 测试覆盖版本确认后空事件、模型版本改变重放及进程重启保真；PA 测试覆盖子读取挂起时发送/任务可完成且根 durable 错误仍拒绝、same-cursor fallback completion 补齐终态与工具耗时。
2. 独立执行 `pnpm exec tsx /tmp/nano-647-static-review.mts`，exit 0：同 cursor revision 失效与孙目录发现、persistence identity 替换失效、冷读失败不带 throughSeq、子 journal 写失败同时不确认 cursor/modelVersion、成功后同时确认、挂起 child drain 的 busy/stop 等待全部成立。实验使用内存数据库与 stub port，没有真实服务；脚本为本机一次性证据，不进入套件。
3. 复核安装的 DSH 公共类型与 observation 实现：identity 在服务替换后不同；同实例/session revision 相等可复用；cold observation 使用读取前 revision，live events 按 cut 延迟物化。实现没有使用读取后的 stat 冒充已读 revision。
4. 性能报告 `M1-fix/evidence/performance.md` 的 reader blob `4b8e826db45d71ca82e182f81d3503522c263c04` 与受审文件 `git hash-object` 相同；`/tmp/nano-647-benchmark/{baseline,fixed,failure}.json` 与报告相符。400 个压缩冷子历史无变化重复从 800 次日志读取降为 0；续写仅 1 次，新 child/孙会话 3 次，失败不确认并可恢复。未把约 100ms 的后代核心读取当作生产 RTT，也未掩盖首次冷恢复成本。

本结论是完整代码 diff 审查。首轮全量后端为 600 passed + workspace-tools 90s 超时，该长旅程原样隔离复验 1 passed / 49.27s（`/tmp/nano-647-workspace-retry.log`），未改代码或 timeout；并发负载只能作为合理推断；完整后端降并发重跑已通过，最终证据见下。产品实际旅程与完整仓库/CI 门禁由各自记录给出，不以本报告替代。

## 最终验证状态补充

在受审源码 `a33d21099bab1aa9ef85481c2d1cb36c59f9c0c7` 上执行 `pnpm exec vitest run --maxWorkers=2`，exit 0，**123 files / 601 tests passed**，耗时 309.63s；日志 `/tmp/nano-647-vitest-stable.log`。已读取日志末尾核对结果。保留上述首轮单项超时和原样复验事实；没有修改源码、测试或 timeout，也没有据此变更 findings `[]` 的结论。最终同步后的源码 retained 依据由 caller 记录，本报告的受审 snapshot 保持不变。

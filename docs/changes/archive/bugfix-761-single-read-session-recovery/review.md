# bugfix-761：审查与验证

## 审查范围

- `executed_base`：`89f16d365203c88e3f6bb7579c79d1a74d4bee76`。
- `validated_at`：`0864f9e0abc1dab2640d16c52cd2e187a3ea693e`。
- 独立审查者 `review_recovery` 执行 change-code-review 与 Agent Context 审查。代码无存活 finding；现行产品契约保持，无 spec delta。
- 锁定版 DSH 等待公开恢复 setup 完成后发布。Nano 在取得写入权前核对会话头，并在发布前核对加载后的身份、记录中断事实及复核生命周期。原生运行时可能在 setup 前追加真实中断收尾事件。受管子会话的原生父子链校验保留。

## 证据

- 旧实现在 Global Relay、Schedule 直接唤醒、`session.ensure` 后接续原生 Task 三个场景各读取两次主会话正文。读取次数统计针对有多个事件的测试主会话，单事件的恢复探针另有用途。
- Context 证据来自 `trajectory-runs.test.ts` 的适配前模型输入。它核对恢复后的通知来源、子会话 ID、中断文案、再次重启后的去重，以及证据不全时等待重试。Global Relay 用例检查阻塞期间另一 Agent 能独立接单。
- 候选的 `global-relay-scale.test.ts` 和 `single-thread-recovery-native.test.ts` 保留原断言并串行复测，4 项通过。三个恢复场景的主会话正文读取均为 1 次，Schedule 与 Task 的原始输入身份仍各恢复一次。Global 等待直属子会话证据时，第二个 Agent 仍进入模型请求。
- 本机同时运行其他构建与模拟器，测试期间负载显著超出 8 个逻辑 CPU 的处理能力。原时限运行在冷启动、等待模型请求或停用清理时出现超时；上述成功复测在一次性副本里延长时限，提交的测试时限未变，临时副本已回收。此对照验证读取次数和恢复行为，没有测量生产内存差或延迟。
- `trajectory-runs.test.ts` 在提交的时限内通过。TypeScript typecheck、iOS 共享运行时检查、文档校验、Python 135 项、ruff 通过。Web 共享契约构建与 critical audit 通过；本机 Web 全量遇多处超时后停止，后端全量交远端 CI 核对。独立 PA 形态没有单独统计读取次数，其主会话沿用相同入口。
- 本轮隔离 DSH 进程和超时遗留的临时运行目录已回收。

## 最终有效性

- `effective_base`：`89f16d365203c88e3f6bb7579c79d1a74d4bee76`。
- `effective_through`：`0864f9e0abc1dab2640d16c52cd2e187a3ea693e`。此后的差异为审查记录与归档。

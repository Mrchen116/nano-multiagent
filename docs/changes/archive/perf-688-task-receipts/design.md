# perf-688 · As-built design

实现后记录，基线 `7e79e9b79`，实现与回归测试 `1c599a39b`。

## 核对路径

1. DSH 在系统提示组装和 turn stopping 时 flush 原生会话，从已进入 turn 的 Task 原文构造历史凭证，分别传给 PA prepare 和 commit。prepare 仍先完成权威同步和撤权，再核对凭证，最后按原 Inbox 顺序准备原文。
2. PA 的 `TaskContext.commit` 校验绑定。有凭证时获取一次未读原文 ID 集合。新方法 `NodeStore.systemContextToReconcile` 按 agent、session 查询 prepared 映射，以及映射已 consumed 但 Inbox 仍未读的原文。SQLite 复用现有表及唯一键，返回 input ID、digest 和状态。
3. 凭证按原顺序匹配候选表中的 input ID，核对整数 turn、原生序号和内容摘要。先确认仍未读的 Inbox，再更新仍 prepared 的持久映射。命中后从本次候选中移除，终态无重复写入。撤权记录不进入候选。
4. 中断发生于两次写入之间时，下次 replay 会通过 prepared 映射完成余下确认。已有 consumed 映射若对应未读 Inbox，仍可凭匹配证据修复 Inbox，并保留原消费 turn。会话重置后，旧 session 的凭证不能确认新 session 的映射。

## 同场景测量

`packages/personal-assistant/tests/task-context.test.ts` 用真实 TaskContext、NodeStore 和 InboxStore，中心返回无新增的固定页。先准备 300 条不同原文并消费，再分别向 prepare 和 commit 重放同一组 300 张凭证。通过 SQLite 的批量读取结果统计返回给 JS 的行数，通过方法调用统计 Inbox 准备与映射更新尝试。

| 调用 | 映射读取次数，前 → 后 | 映射返回行，前 → 后 | Inbox 准备次数，前 → 后 | 映射更新尝试，前 → 后 |
|---|---:|---:|---:|---:|
| prepare | 302 → 3 | 90,600 → 600 | 302 → 3 | 300 → 0 |
| commit | 300 → 1 | 90,000 → 0 | 300 → 1 | 300 → 0 |

prepare 的其余两次映射读取用于权威同步和最终准入，各返回 300 行。本次指标只计 PA 数据库返回行和调用次数。原生历史扫描、RPC 凭证大小、SQLite 内部访问行数与端到端耗时不在该测量内。

## 验证、兼容与回滚

- 同文件的部分确认回归覆盖两侧持久状态的补交与原 turn 保留。原有测试覆盖错误摘要、撤权、会话重置和绑定隔离。
- 没有 schema、RPC 或 canonical spec delta。保留原生 flush、去重、Task 消息选择与排序。回滚代码即可继续读取相同数据库。
- 用户授权以保持正常体验的快修交付单独 PR。此处结果为隔离自动化验证。

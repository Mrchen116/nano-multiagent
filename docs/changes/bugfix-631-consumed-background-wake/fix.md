# bugfix-631: 已读背景消息不再触发空唤醒

## Relations

- Related: feat-623

## 原始报告

> 没事为啥会被唤醒？
>
> 修一下，消息已经读完了就别再触发唤醒了

用户提供 Personal Agent 工作视图截图：2026-10-21 18:59:27–18:59:43 的第 186 轮仅检查 Inbox，返回空来源并结束。

## 现象 / 复现

- Mini 生产版本 `11f599938d67f21398570009f1c7e9e0088b81a1`，PA 会话 `8d36509c-91d0-423d-97d4-2f6419162253`。
- 18:57:16 收到 observer 消息，Inbox 序号 249；18:59:11.249 在第 185 轮完整持久摄取，`inbox_read_committed` 已记录该消息。
- 18:59:27.028 仍提交 `inbox-background:personal-agent:249`，第 186 轮检查得到 `sources:[]`，产生一次多余模型执行。
- 使用同版生产构建与内存 SQLite 隔离复现：背景批次已到期；等待 `session.observe` 期间完整读取背景消息；返回 idle 后仍提交该批次，此时未读来源数为 0。实验不修改生产数据或服务。
- 目标：背景提醒提交前已经完整读完的消息不再触发新唤醒；仍有未读时继续正常合并提醒。

## 根因

`GlobalAgent.notifyBackground` 在读取背景批次后异步等待 `session.observe`。等待期间，当前执行可以完整摄取同一批消息；返回 idle 后仍使用旧批次提交，没有重新检查当前未读状态。已有测试只覆盖计时器到期前读完，未覆盖状态查询期间读完。

该逻辑由 `f036aedd5e7bc972a413989474f166a8d49db752` 引入，属于 feat-623 的背景合批路径；随后 `5b6b2bb638` 在权限刷新后重读批次，但运行状态查询后的窗口仍存在。原始目标见 feat-623 的 spec“背景通知按十分钟累计且不丢消息”及“直接请求可立即使用累计背景”：立即保存可读，十分钟合并，忙碌延期，完整读取后不再提醒。

修复必须保留：提醒与持久消费独立、未读背景可继续通知、直接请求及时 steer、忙碌不被背景打断，以及已接纳但 ACK 不确定时的幂等恢复。已被运行时接纳的通知不能冒充撤回。

## 修复

将背景批次的最终读取移到异步运行状态查询之后。查询期间被完整摄取的消息不再形成背景通知；仍有未读时保留原十分钟节律、onlyIfIdle 接纳与 ACK 幂等恢复。

现有 current spec 已要求“顺带完整读取的消息不再触发后续背景提醒”，本次恢复该契约，无 spec delta。

## 验证

- 扩展既有 `packages/personal-assistant/tests/personal-attention.test.ts` 的已读取消用例，参数化保护“到期前读完”和“等待运行状态期间读完”，并验证取消后后续新消息仍能正常通知；不新增平行测试文件。
- Red：原实现下，“during idle observation”用例失败，已读后仍出现第二次通知；“before deadline”通过。
- Green：`pnpm exec vitest run packages/personal-assistant/tests/personal-attention.test.ts packages/personal-assistant/tests/inbox.test.ts packages/personal-assistant/tests/global-agent.test.ts`，3 文件、56 项通过。
- 保留既有未读合批、忙碌延期及接纳竞态、主人即时提醒、ACK 不确定恢复、来源撤销和停止计时器覆盖。

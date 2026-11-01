# bugfix-693: As-built Design

> 本文在实现后根据实际代码与测试形成。用户亲自验收尚未发生，unit 保持 active。

## 实现范围

- Base / executed_base: `39a1d78ed25b4c19878dc98b63d96d4810cb2523`。
- Head: 本分支的实现提交；以 `git log` 与代码审查记录定位。
- 产品代码：`packages/dsh-integration/src/index.ts` 的 `session.submit`。
- 回归：`apps/node/tests/global-inbox-native.test.ts`。
- 主仓已有的 main.ts、index.ts 及研究草稿改动未复制或修改；本分支基于最新 origin/main 独立实现。

## 最终结构与调用链

`GlobalAgent.receive → InboxStore.receive → wake(watermark) → session.submit(mode=steer) → native Agent inbox → pre-step claim → LLM`。

产品层继续保存全部正文并按最新 watermark 提交系统提醒。Nano 接入层只对 `mode=steer` 且来源为 `nano-system / inbox` 的新提醒合并：同步移除该 session 的 next-turn / next-step 中所有同类待处理提醒，再用原生 `agent.steer` 提交最新提醒。涉及的队列读写与 steer 之间没有 await。其他 channel、真人输入、已经进入上下文的历史提醒均保留。

使用公开 `agent.inbox.remove` / `agent.steer`；原生 splice 日志和既有 persistence barrier 继续保存受理证据，不增加 schema、配置、计时器或内存去重状态。新提醒保留当前 inputId，旧 inputId 的持久受理记录仍在，重试不会重新插入已受理的旧提醒。继续由原生 steer 唤醒空闲执行器，保留取消后的原生排队语义。

## Context 消费与交互

消费者为 Global 主 Agent / PA 主 Agent。Before：模型执行期间收到三条消息，下一次请求新增三条相同系统提醒。After：新增一条原文不变的提醒，Agent 仍需 `inbox(check)` / `inbox(read)` 获取最新来源和正文。新消息到达已消费提醒之后，重新产生一条提醒，不做跨请求永久压制。

正文、真实来源、授权和发送前复核不变；PA observer 使用 `inbox-background`，不参与此合并。测试通过真实 DSH 子进程和受控模型边界捕获最终 messages，证明提醒交付及正文读取；没有调用真实模型，不据此声称模型理解或规划能力已验证。

## 关键决策、失败与回滚

- 合并放在拥有 native 待消费队列的 integration 层，避免跨 RPC 查询/提交竞态和另设状态。
- 保留最新提醒身份，使 Inbox 已提交 watermark 的重启恢复仍能定位当前待处理提醒。
- 沿用持久日志和 flush；没有数据库迁移或一次性部署迁移。
- 回滚本次 index.ts 改动恢复逐条提醒；消息持久数据无需回滚。

## 验证定位

自动化结果见 [validation.md](validation.md)。扩展既有 native Inbox 文件，直接捕获模型请求，覆盖模型中三消息合并、工具中三消息合并、完整正文读取、消费后的下一批提醒、其他通知保留以及发送复核。既有 global-agent / runtime-profile / input-evidence 回归继续保护冷恢复和受理幂等。无新增平行测试文件。

## Canonical 文档影响

待归并 delta：[specs/gateway/global-agent.md](specs/gateway/global-agent.md)，目标 `docs/specs/gateway/global-agent.md`。用户确认前保留 active，不将目标状态覆盖 current spec。

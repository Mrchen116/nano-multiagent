# Code Review: feat-623-pa-message-context

- review_mode: `full`
- validated_at: `f036aedd5e7bc972a413989474f166a8d49db752`
- executed_base: `2f789f62a`（显式包含未合并依赖 PR #371）
- effective_base: `2f789f62a`
- effective_through: `f036aedd5e7bc972a413989474f166a8d49db752`
- 独立静态审查；未参与实现，未修改源码、测试或设计。范围为该 base..head 的全部 20 个变更文件，并沿实际来源权限、原消息、运行时接纳、摄取和发送复核调用方核实。

## Findings

```json
[
  {
    "file": "packages/personal-assistant/src/global-agent.ts",
    "line": 182,
    "summary": "[P2] 最后一个候选被撤销时清除 waitingForIdle，否则后续背景通知永久停摆",
    "failure_scenario": "PA 空闲，背景到期。notifyBackground 先把 agent 加入 waitingForIdle，随后 refreshPersonalSources 发现该来源已撤销，删除最后候选；batch 为空直接返回，等待标志没有清除。当前没有执行就不会再产生 idle 转换；以后有效 observer 消息虽建立新的持久 dueAt，armBackground 却始终排除该 agent，超过十分钟仍没有通知，直到无关的 idle 事件或 recover。来源在 observations 拉取完成后、这次最终来源复核前变为不可访问即可触发。应在候选为空的退出路径清除等待标志，保留真正忙碌时等待 idle 的行为，并覆盖撤销后新来源收件。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 直接证据

在固定 head 运行一次性 `/tmp/feat623-review-empty-batch.mts`（`pnpm exec tsx /tmp/feat623-review-empty-batch.mts`），使用真实 `GlobalAgent`、`InboxStore`、`NodeStore`，模拟 RuntimePort/relay 与本地时钟/定时器。通过公开 `receive` 和已登记 timer 回调驱动，不修改产品源码，不操作私有字段。

1. 0ms 收到 observer 消息，600000ms 到期；最终 `pa.sources` 复核返回 excluded，运行时始终 idle。
2. 到期处理后：`submitted=0, timers=0, sources=[]`。
3. 600001ms 收到重新有效的背景消息：`dueAt=1200001, pending=false, unread=true`，但 `timers=0`。
4. 1200002ms 仍是 `submitted=0, timers=0`；没有运行时 busy 或错误阻止通知。

现有 `personal-attention.test.ts:108` 只断言撤销候选消失，没有继续测试新批次是否能重新定时；`inbox.test.ts:144` 只保护 SQL 序号，不能暴露 GlobalAgent 的等待标志问题。

## 已核对范围和验证边界

- 可信事实来自 IM 持久原消息；Web 实际 PA 成员、飞书绑定 app/node/agent/owner、群 mention/reply 均沿现有链路，身份不依赖正文自称。
- PA check/read 显式投影、关系边界分页、冻结结果重放、附件来源和完整持久摄取保留；普通 Global 不启用 PA 投影。
- 背景接收/截止/通知水位/在途身份独立持久化；检查 busy race 的 runtime `onlyIfIdle` 接纳边界；及时直接 wake 不等待背景 idle；recover、ACK、timer、stop 和撤销路径均检查。
- observer 跳过请求审核和 slash control；participant 保留群触发、非主人输入检查。完整 owner 上下文与 guard 分开；目标主人已回复、source/policy/audience/profile/attachment/task 复核保留，旧 permit 缺 guard 不能直接发送。
- 独立窄测：`pnpm exec vitest run packages/personal-assistant/tests/inbox.test.ts packages/personal-assistant/tests/personal-attention.test.ts packages/personal-assistant/tests/global-agent.test.ts packages/personal-assistant/tests/personal-assistant.test.ts apps/im-server/tests/personal-sources.test.ts apps/im-server/tests/personal-disclosure.test.ts apps/im-server/tests/personal-agent.test.ts` → **7 files / 107 tests passed**。
- 复用 `M1-context/implementation.md`、`M1-context/im-identity-evidence.md` 及 `/tmp/feat-623-native.log` 的有效原生 DSH/构建/类型检查证据；不重复全量。上述绿测没有覆盖本 finding。
- 复用主 Agent 已补入 `M1-context/implementation.md` 的固定 head 本地全量证据：backend 106 suites/469 tests、frontend 100 files/936 tests、pytest 62，build/typecheck/ruff/docs-check 均通过；核对对应日志，不重复有效全量。远端 CI 属于后续交付状态。
- 真实模型六组语义、真实十分钟与飞书平台回执由独立产品 reviewer 负责，此次不据静态代码声称通过。

结论：**request changes，1 个 CONFIRMED P2**。产品验收 pending 是独立证据状态，不是本 finding 的推测前提；已通过的本地全量未覆盖此故障。

## Round 2 — W1 closure 与 patch review

- validated_at / effective_through: `5b6b2bb63821be62534030e9226abca2be2c3c98`
- executed_base / effective_base: `2f789f62a`；受审修复范围 `f036aedd5..5b6b2bb63`
- review_mode: `patch`，并 closure `W1`；R1 固定版本结论作为历史保留。

### Patch Findings

```json
[]
```

### Focus closure

| Finding | 结论 | 直接证据 |
|---|---|---|
| W1：空批退出遗留 waitingForIdle | **closed** | `global-agent.ts:183` 在最终复核后无 batch 时删除等待标志；新批次恢复定时，过期成功 submit |

修复只影响来源复核后无候选的退出路径；实际 busy、未 ACK、来源仍有候选等路径的等待/幂等逻辑均未修改。扩展原有 ACK/revoke 测试，在取消排除、收到新消息后推进十分钟，断言第二次实际提交；保护的是原遗漏的公开通知行为，没有加入新抽象或改变批次契约。

独立重跑原 `/tmp/feat623-review-empty-batch.mts`，固定修复 head：撤销后仍 `sources=[], timers=0`；新有效消息后 **`timers=1, dueAt=1200001`**；推进到 1200002ms 后 **`submitted=1, timers=0`**。与 R1 相同输入/入口，故障消失。复用并核对 `/tmp/feat-623-empty-batch-red.log`（新增断言旧实现 1 failed / 6 passed）和 `/tmp/feat-623-empty-batch-green.log`（修复后 inbox + personal-attention **16/16 passed**）。

R1 其余审查结论保留至本 head：修复不改变身份、投影、分页、权限、授权 guard 或 runtime 接纳协议，未见新缺陷，无需扩成重复 full review。真实十分钟环境仍运行 `f036aedd5`；本轮没有重启/替换该现场，也没有把该现场声称为修复版本的产品验收。

最终代码审查结论：**pass，0 个存活 finding**；独立产品验收与后续交付 CI 状态继续由对应 owner 记录。

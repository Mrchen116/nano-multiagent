# feat-501 — 验收报告

> 对齐: spec.md 的验收标准
>
> Validation snapshot: `ed814849c7ccbcc565e0feebef41096dd73935e4 → unit/feat-501 working tree (2026-08-05)`

## Verdict

**fail — required Feishu scenarios remain inconclusive because no usable test Bot or credentials were available.** This is not treated as a passing substitute. The final focused Web IM re-review passed and found no remaining Web IM product defect.

Highest Required Action: provision the reviewed Feishu test prerequisite and re-run the external journeys; no implementation fix is requested from this report.

## 用户旅程体验

1. **私聊文本控制**：在真实 Web IM 私聊中，输入精确的 `/new` 和 `/compact` 后直接按 Enter；两条都被发送而非留在 slash menu，分别在原聊天看到“已开始新会话。”与“当前历史不足，无需压缩。”。
2. **私聊上下文语义与 focused compact**：先建立唯一旧事实 `KESTREL-501`，执行 `/new` 后询问旧事实，Agent 回答 `UNKNOWN`；旧可见消息仍在。另一次真实会话中，`/compact 保留认证方案与未完成项` 显示“已按关注点压缩当前会话。”，后续仍回答 `PKCE; refresh-token rotation.`。
3. **MENTION 群聊**：在 Web IM 新建的真实 `Group`（Test User、plato、hume）中，裸 `/new` 和 `/compact` 仅作为用户消息出现，8 秒观察窗口内没有任何 Agent 控制确认；`@plato /new` 显示 plato 的“已开始新会话。”，`@plato /compact` 显示 plato 的明确 no-op 结果。
4. **外部入口**：隔离栈无可收发消息的 Feishu Bot、账号或凭据，未以 Gateway 内部 dispatch、伪造 callback 或 API 调用替代用户旅程。

本轮 IM + Gateway 隔离栈、浏览器与 tmux 会话均已停止并确认端口释放。

## Reference Artifacts Reviewed

N/A。本 unit 没有前端原型或视觉 must-match 契约。

## 问题清单

本轮没有观察到需要 `fix-implementation` 的 Web IM 产品问题。Feishu 场景的 inconclusive 是验收环境缺口，不能被当作通过，也不应归因为代码缺陷。

## 验收标准覆盖

### Requirement: 用户可在任一聊天入口开始新的 Agent 会话 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 内部 IM 中开始新会话 | spec.md | 真实私聊：唯一旧事实 → `/new` → 追问旧事实 | 旧事实 `KESTREL-501` 在 reset 后得到 `UNKNOWN`；原消息与“已开始新会话。”仍在同一聊天 | pass | 最终 focused re-review 也确认裸 `/new` 可直接 Enter 提交并显示确认。 |
| 飞书私聊中开始新会话并同步状态 | spec.md | 需要真实 Feishu 私聊与对应影子会话 | 无可用 Bot/凭据 | inconclusive | 未使用内部 dispatch 或伪造 callback 替代。 |
| 运行中的会话被用户明确换新 | spec.md | 需要 active streaming run 后发送 `/new` | 本轮未形成可重复的运行中窗口 | inconclusive | 不以单测或源码推断代替用户面证据。 |
| 群聊中明确指向 Bot 后开始新会话 | spec.md | 真实双 Agent Group：裸与 `@plato /new` 对照 | 裸命令无 Agent 确认；`@plato /new` 在同群由 plato 确认“已开始新会话。” | pass | 群标题与界面类型均为 `Group`，成员为 Test User、plato、hume。 |

### Requirement: 用户可主动压缩当前会话并选择保留重点 — 组内结论: inconclusive

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户压缩当前会话 | spec.md | 真实私聊 `/compact` | 在已有历史的会话中看到“已压缩当前会话。” | pass | 最终 focused re-review 也确认裸 `/compact` 可直接 Enter 提交。 |
| 用户为压缩指定关注点 | spec.md | 真实私聊建立认证方案与未完成项后发送 focused compact 并追问 | “已按关注点压缩当前会话。”；追问回答 `PKCE; refresh-token rotation.` | pass | focus 没有成为普通用户 turn。 |
| 飞书主动压缩同步到内部 IM | spec.md | 需要真实 Feishu 私聊/群聊及 IM shadow | 无可用 Bot/凭据 | inconclusive | 未伪造外部入口或 shadow 结果。 |
| 没有足够历史可压缩时给出明确结果 | spec.md | 新私聊中裸 `/compact` | “当前历史不足，无需压缩。” | pass | 当前焦点会话未出现空 Agent 上下文或静默失败。 |
| 压缩无法完成时不丢失上下文 | spec.md | 需要真实可控 summarizer/persistence 故障 | 本轮没有产品级故障注入前置 | inconclusive | 不用测试 double 代替用户面验收。 |
| 正在运行时不会静默改变上下文 | spec.md | 需要 active run 后发送 `/compact` | 本轮未形成可重复的运行中窗口 | inconclusive | 不以单测或源码推断代替用户面证据。 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本期未改变跨包依赖边界。
- [x] `docs/specs/<包>/`（长青行为契约层）：需要更新；Gateway 与 kernel 的 delta-spec 已在本 unit 中，待 orchestrator 按最终实现归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新。

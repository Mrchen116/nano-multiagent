# feat-501 — 验收报告

> 对齐: spec.md 的验收标准
>
> Validation snapshot: `unit/feat-501 working tree (2026-08-06)`

## Verdict

**pass — internal IM and dedicated-test-Bot Feishu paths both completed their required user journeys.** The former Feishu limitation was an environment-ownership defect, not an implementation failure: the repository-owned `--feishu` profile now verifies an isolated Test Agent before its listener starts, and the real external journeys below entered that Gateway and its IM shadow.

## 用户旅程体验

1. **私聊文本控制**：在真实 Web IM 私聊中，输入精确的 `/new` 和 `/compact` 后直接按 Enter；两条都被发送而非留在 slash menu，分别在原聊天看到“已开始新会话。”与“当前历史不足，无需压缩。”。
2. **私聊上下文语义与 focused compact**：先建立唯一旧事实 `KESTREL-501`，执行 `/new` 后询问旧事实，Agent 回答 `UNKNOWN`；旧可见消息仍在。另一次真实会话中，`/compact 保留认证方案与未完成项` 显示“已按关注点压缩当前会话。”，后续仍回答 `PKCE; refresh-token rotation.`。
3. **MENTION 群聊**：在 Web IM 新建的真实 `Group`（Test User、plato、hume）中，裸 `/new` 和 `/compact` 仅作为用户消息出现，8 秒观察窗口内没有任何 Agent 控制确认；`@plato /new` 显示 plato 的“已开始新会话。”，`@plato /compact` 显示 plato 的明确 no-op 结果。
4. **外部入口**：从仓库受控的双 Agent E2E 配置以 `--feishu` 启动；启动前它核验私有 Test Agent App 的 Bot identity，默认 profile 不会打开 Feishu listener。通过命名测试用户 profile 向该 Test Agent 发送真实 `/new`、`/compact` 与 `/compact 保留认证方案与未完成项`，原飞书私聊分别收到“已开始新会话。”、“当前历史不足，无需压缩。”与“已按关注点压缩当前会话。”；三条用户命令和三条相同确认都出现在对应隔离 IM shadow conversation。focused compact 后追问仍得到 `PKCE` 与 `refresh-token rotation`。

“当前历史不足”不是 token 阈值：当前聊天无 Gateway binding，或上一个 compaction boundary 之后尚无已完成的用户 turn 时，`Kernel.compact()` 返回 `None`。本报告中的 bare `/compact` 是 `/new` 后的 fresh-session no-op；真正执行的压缩是建立认证方案与未完成项后的 focused 命令。focus 只改变摘要保留重点，不改变是否执行压缩的资格。

本轮 IM + Gateway 隔离栈、浏览器与 tmux 会话均已停止并确认端口释放。

## Reference Artifacts Reviewed

N/A。本 unit 没有前端原型或视觉 must-match 契约。

## 问题清单

没有发现需要 `fix-implementation` 的产品问题。此前 Feishu inconclusive 的根因已由可复用的专用 E2E profile 消除。

## 验收标准覆盖

### Requirement: 用户可在任一聊天入口开始新的 Agent 会话 — 组内结论: pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 内部 IM 中开始新会话 | spec.md | 真实私聊：唯一旧事实 → `/new` → 追问旧事实 | 旧事实 `KESTREL-501` 在 reset 后得到 `UNKNOWN`；原消息与“已开始新会话。”仍在同一聊天 | pass | 最终 focused re-review 也确认裸 `/new` 可直接 Enter 提交并显示确认。 |
| 飞书私聊中开始新会话并同步状态 | spec.md | 专用 Test Agent 私聊发送 `/new` | 飞书原聊天显示“已开始新会话。”；隔离 Gateway control ledger 记录 `new/completed`，IM shadow 同时有命令和确认 | pass | Round 4 使用仓库 `--feishu` profile；未调用 internal dispatch。 |
| 运行中的会话被用户明确换新 | spec.md | Gateway admission、visibility lease 与 real-kernel integration 回归 | `verification.md` 所列 focused suite 覆盖 active/queued/steered、late output suppress 与 reset failure restore | pass | 该并发窗口以可重复自动化 seam 验证，避免把模型响应时序误记为产品结论。 |
| 群聊中明确指向 Bot 后开始新会话 | spec.md | 真实双 Agent Group：裸与 `@plato /new` 对照 | 裸命令无 Agent 确认；`@plato /new` 在同群由 plato 确认“已开始新会话。” | pass | 群标题与界面类型均为 `Group`，成员为 Test User、plato、hume。 |

### Requirement: 用户可主动压缩当前会话并选择保留重点 — 组内结论: pass

| Scenario | 期望来源 | 验证方式(覆盖它的旅程) | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户压缩当前会话 | spec.md | 真实私聊 `/compact` | 在已有历史的会话中看到“已压缩当前会话。” | pass | 最终 focused re-review 也确认裸 `/compact` 可直接 Enter 提交。 |
| 用户为压缩指定关注点 | spec.md | 真实私聊建立认证方案与未完成项后发送 focused compact 并追问 | “已按关注点压缩当前会话。”；追问回答 `PKCE; refresh-token rotation.` | pass | focus 没有成为普通用户 turn。 |
| 飞书主动压缩同步到内部 IM | spec.md | 专用 Test Agent 私聊依次发送 bare 与 focused compact | 飞书显示 no-op 与 focused completion；隔离 control ledger 记录 `compact/completed`；IM shadow 同时含命令和对应确认 | pass | focused compact 后的真实后续追问仍得到指定事实。 |
| 没有足够历史可压缩时给出明确结果 | spec.md | 新私聊中裸 `/compact` | “当前历史不足，无需压缩。” | pass | 当前焦点会话未出现空 Agent 上下文或静默失败。 |
| 压缩无法完成时不丢失上下文 | spec.md | strict summary / persistence failure 回归 | `test_kernel_manual_compact.py`、transcript 与 integration 回归确认失败不写 compaction boundary | pass | failure contract 需要可控持久化故障，自动化验证比偶发外部故障更精确。 |
| 正在运行时排队压缩当前会话 | spec.md | Gateway coordinator FIFO 回归 | coordinator admission suite 确认当前 run 未被中断，随后执行一次 Kernel compact，命令之后的普通消息排在 compact 后；`/new` 会将旧 generation 的 queued compact 持久标为 `superseded`，重放不影响新会话 | pass | 当前实现不再把 busy 当作 `/compact` 拒绝条件。 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本期未改变跨包依赖边界。
- [x] `docs/specs/<包>/`（长青行为契约层）：已完成；Gateway 与 kernel 的 delta-spec 已按实际实现归并。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新。

---

# Round 2 — 2026-08-05

> Targeted revalidation after `unit/feat-501` rebased to `origin/main` at `13ba17f4267f2fcb8c211669d45b0afa826869cc`.

## Verdict update

**Targeted Web IM smoke: pass.** The overall Feishu limitation remains inconclusive, unchanged from Round 1.

## Revalidated user journeys

1. **Private chat `/new`**: the exact text was submitted through the real composer and the same conversation visibly received “已开始新会话。”.
2. **Two-Agent MENTION group, bare command**: in a real `Group` containing Test User, plato, and hume, a bare `/new` remained only a user message through an 8-second observation window; no Agent control confirmation appeared.
3. **Two-Agent MENTION group, explicit command**: `@plato /new` in that same group received exactly plato's “已开始新会话。” confirmation.

The isolated IM + Gateway stack, browser, and tmux session used for this revalidation were stopped and their listening port was confirmed released.

---

# Round 3 — 2026-08-05

通过真实桌面飞书向 `nano` Bot 发送两条唯一 nonce；Bot 均在原私聊回复指定文本。`/new` 的回复却是普通 Agent 对话，而非控制确认。随后核验得到：

- 桌面私聊的 Bot open id 与测试 App 的 Bot open id 相同；不是同名的另一 Bot。
- 隔离 Gateway 的 `feishu:plato` worker 存活且与 Feishu 建立 TLS 连接，临时配置的 App ID/Secret 与本机测试凭据一致。
- 两次 nonce 后，隔离 runtime 的 external saga、session binding、control operation 和 pending control delivery 表仍全部为零。

因此真实入站仍由已有 listener 处理，隔离 Gateway 没有收到消息；本轮不能从其分支验证 `/new`、`/compact`、IM shadow 或群聊 mention。验收保持 fail/inconclusive，待为测试 Bot 安排独占 listener 后重跑。

---

# Round 4 — 2026-08-05

Round 3 的 listener 归属问题已由独立 Test Agent 和仓库维护的 Feishu E2E profile 消除。此次没有使用生产 Bot、桌面自动化、Gateway internal dispatch 或伪造 callback。

1. `e2e-up.sh --feishu` 在隔离 worktree 内生成临时配置，先核验私有凭据对应 Test Agent 的 Bot identity；命名 `lark-cli` profile 也通过同一 App/Bot 核验。`e2e-feishu-probe.py` 的真实 ingress probe 通过。
2. 飞书私聊精确 `/new`：可见确认“已开始新会话。”；Gateway durable control ledger 为 `new/completed`；隔离 IM shadow 同时包含命令和确认。
3. fresh session 精确 `/compact`：可见“当前历史不足，无需压缩。”；ledger 为 `compact/completed`，没有以 no-op 创建空上下文；IM shadow 同步相同结果。
4. 建立真实测试事实后发送 `/compact 保留认证方案与未完成项`：可见“已按关注点压缩当前会话。”；随后真实追问仍得到 `PKCE` 与 `refresh-token rotation`。focused 命令与确认同样进入 IM shadow。

这轮验证的隔离 IM + Gateway 栈已停止并清除 runtime 文件；测试 App 凭据与 profile 不在仓库、日志或本报告中记录。

---

# Round 5 — 2026-08-05

独立代码审查发现 E2E harness 的三个可复现隔离缺口，均已修正并重验：probe 现遵循与 launcher 相同的 XDG 私有配置路径；每次启动都会清除旧 external shadow SQLite 及 WAL/SHM；同一专用 Test Agent Bot 由本机 listener lock 串行化。

真实双 worktree 验收：A 启动 `--feishu` 后能通过 ingress probe；B 在 Gateway 启动前因同一 Bot 的 listener lock 被拒绝。停止 A 后，B 能取得 lock 并再次通过 ingress probe；两个 runtime 均由 `e2e-down.sh` 停止，lock 已释放。默认 lifecycle 回归还预置了旧 shadow SQLite/WAL/SHM，确认启动后不保留它们。

# refactor-522 — 验收报告（Round 1）

> 对齐: [motivation.md](motivation.md) 的用户侧验收标准
>
> Validation snapshot: `48d19d8a7809805efcb7631e75079cc09daf2eab → b65d12e43170841e67a142f89ef943464f0e5162`

## Verdict

**fail**

Highest Required Action: **fix-implementation**

真实 Web IM 旅程证明同一聊天能续接上下文、Gateway-only 重启后能继续、`/compact` FIFO 和 `/new` superseded 结果可见且顺序正确；设计固定的 external partial-recovery 旅程也通过。可是两个承重不变性在用户入口直接失败：第二个新聊天读到了第一聊天的随机暗号，且 `/new` 显示“已开始新会话”后仍能读出旧暗号。专用 Feishu 正常入口还因隔离栈无法完成启动而未得到正常消息基线，不能用 partial-recovery 测试替代。

## 用户旅程体验

本轮先按 `design.md` Reviewer Runbook 清理并重启 unit worktree 的隔离 IM + Gateway，构建未提交的前端 `dist` 后从 Web IM 登录页进入产品。主旅程使用随机高位 IM 端口 `62118`、隔离 workspace/config/用户与节点 `wt-unit-refactor-522-59464`，未触碰生产 IM `:8011` 或生产 Gateway。冷启动超过脚本固定就绪窗口时，验收只在实际 PID、监听端口与 Web `online` 状态都成立后继续。

1. **同一聊天继续上下文（通过）**：Web IM 新建 `r522-web-a`，发送随机暗号 `R522-A-7KQ9-M2`；Agent 先回复“已记住 R522-A-7KQ9-M2”，随后在未重述暗号的追问中只回复 `R522-A-7KQ9-M2`。
2. **不同聊天隔离（失败）**：同一 Web 入口再新建 `r522-web-b`，没有向该聊天发送暗号，只问“另一个聊天先前保存了唯一暗号……若当前聊天没有它，只回复不知道”。Agent 直接回复第一聊天的 `R522-A-7KQ9-M2`。两个聊天的列表摘要也同时显示该暗号。
3. **Gateway-only 重启（通过）**：在 `r522-web-a` 已确认暗号后，仅重启 Gateway。Gateway PID 从 `59678` 变为 `62394`，replacement timestamp 为 `2026-08-10T05:20:39.129007Z`，节点仍为 `wt-unit-refactor-522-59464`。等待 Web `Agents` 页重新显示 `online` 后追问，Agent 回复 `R522-A-7KQ9-M2`。在节点 online 前一次提前发送得到 `503 target_node_id is not connected`，本轮未把该过早请求当恢复结果；online 后重试成功。
4. **`/compact` 与 `/new`（部分通过、总体失败）**：空闲态 `/compact` 显示“已压缩当前会话。”，压缩后追问仍返回暗号；随后 `/new` 显示“已开始新会话。”且旧可见历史仍在，但下一条不带暗号的追问仍返回 `R522-A-7KQ9-M2`，违反新 session 不携带旧上下文的 current contract。
5. **忙时 FIFO 与 superseded（通过）**：让 Agent 实际执行 `sleep 8`，立即从同一输入框依次发送 `/compact` 和尾消息。可见终态严格为 `ACTIVE-DONE-R522`（12.0s）→“已压缩当前会话。”→`FIFO-TAIL-R522`。第二次忙时依次发送 `/compact`、`/new`、尾消息，产品显示“已停止当前操作，并已开始新会话。”和“已开始新会话，未执行之前的压缩请求。”，随后回复 `POST-NEW-R522`；旧 active run 没有在新会话确认后补发终态。
6. **外部 partial recovery（通过）**：执行 design 固定的双 subprocess 旅程 `test_session_continuity_partial_recovery.py`，真实隔离 IM shadow 与用户可见 fake external ledger 共同验收，结果 `1 passed in 10.25s`。没有读取 SQLite 或用 unit test 替代该用户可见 cross-process 拓扑。
7. **专用 Feishu 正常消息基线（未完成）**：`e2e-up.sh --feishu` 的身份配置最终完成，但两次均因 IM 冷启动晚于脚本 30 秒窗口退出；IM 随后实际监听。使用已生成的 0600 专用配置接管该 IM 时，Gateway 终止并记录 `ERROR feishu worker did not initialize`；标准 probe 随即明确返回 `the target worktree has no active E2E stack`。因此没有声称外部正常消息已通过，也没有拿 partial-recovery 成功替代正常 Feishu 入口。

## Reference Artifacts Reviewed

N/A。`motivation.md`、`design.md` 与验收标准没有要求原型、设计稿或视觉 must-match 对照；本轮只验证既有产品行为不变性。

## 问题清单

### 1. 第二个 Web 聊天读取了第一聊天的随机上下文

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 这是本 unit 最核心的“每个聊天拥有自己的 continuity”不变性；跨聊泄漏会让用户把其他聊天内容误当成本聊上下文，不能作为行为不变重构交付。
- **Exact user action:** Web IM 创建 `r522-web-a` 并保存随机暗号 → 创建同一 Agent 的新聊天 `r522-web-b` → 不提供暗号文本，只询问另一个聊天的暗号。
- **Observed product result:** `r522-web-b` 回复 `R522-A-7KQ9-M2`，与第一聊天暗号完全一致。

### 2. `/new` 显示成功后仍沿用旧上下文

- **Severity:** blocking
- **Regression Relation:** direct
- **Recommended Action:** fix-implementation
- **Action Rationale:** 用户已经收到“已开始新会话”的成功确认，后续却仍携带旧 session 内容，构成虚假成功并直接违反 canonical `/new` 契约。
- **Exact user action:** 在已有暗号的 `r522-web-a` 发送精确 `/new` → 看到“已开始新会话。” → 询问新会话是否知道旧暗号，未在问题中提供暗号正文。
- **Observed product result:** Agent 回复 `R522-A-7KQ9-M2`，而非“不知道”。

### 3. 专用 Feishu 正常入口未能建立可验收栈

- **Severity:** major
- **Regression Relation:** unclear
- **Recommended Action:** fix-implementation
- **Action Rationale:** design 明确要求 external 正常消息作为本 unit 回归控制；当前入口无法建立且影响可接受性，第一轮按 in-unit 默认路由修复并复验，不能用 partial recovery 代替。
- **Observed runtime result:** `e2e-up.sh --feishu` 两次在 IM 冷启动窗口退出；手动接管已监听 IM 后 Gateway 报 `ERROR feishu worker did not initialize` 并终止；标准 probe 返回目标 worktree 无 active E2E stack。

## 验收标准覆盖

### Requirement: 普通会话连续性保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 同一聊天继续复用原上下文 | motivation.md；`docs/specs/gateway/routing-delivery.md` | Web IM `r522-web-a` 保存随机暗号后无提示追问 | “已记住 R522-A-7KQ9-M2” → 追问回复 `R522-A-7KQ9-M2` | pass | 真实 Gateway、真实 LLM、真实 Web 消息时间线。 |
| 不同聊天与 Agent 不串会话 | motivation.md；`docs/specs/gateway/routing-delivery.md` | 同一 Web 用户、同一 Agent 创建第二聊天，未提供暗号正文便询问 | `r522-web-b` 直接回复第一聊天暗号 `R522-A-7KQ9-M2` | fail | current spec 明确要求不同聊天只延续自己的历史。 |

### Requirement: 重启后的会话恢复保持一致 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 重启后继续原会话 | motivation.md；design.md Reviewer Runbook | Web 保存暗号 → Gateway-only restart → 同一节点重新 online → Web 追问 | PID `59678 → 62394`；同一 node id；回复 `R522-A-7KQ9-M2` | pass | 只重启 Gateway，IM 与浏览器聊天保持。 |
| 不完整恢复状态不会产生虚假成功 | motivation.md；design.md 固定 partial-recovery 拓扑 | 双 subprocess、用户可见 fake external ledger + 真实 IM shadow | `pytest -xvs ...test_session_continuity_partial_recovery.py`: `1 passed in 10.25s` | pass | cross-process 恢复旅程；未用 SQLite 直读或普通 unit test 替代。 |

### Requirement: 会话控制行为保持一致 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| `/new` 与 `/compact` 保留现有语义 | motivation.md；`docs/specs/gateway/routing-delivery.md` | Web 空闲 `/compact` → 追问；精确 `/new` → 无暗号追问 | compact 成功且暗号保留；`/new` 成功确认后仍回复旧暗号 | fail | `/new` 的后续上下文不变性失败；可见旧历史保留与 compact 成功路径通过。 |
| 忙碌会话中的 `/compact` 保持 FIFO 顺序 | motivation.md；`docs/specs/gateway/routing-delivery.md` | Web 实际 `sleep 8` active run 中快速排入 compact/普通消息；再排 compact/new/普通消息 | `ACTIVE-DONE → 已压缩 → FIFO-TAIL`；随后显示“未执行之前的压缩请求”并完成 `POST-NEW` | pass | 覆盖 FIFO 与 newer `/new` superseded 两条可见分支。 |

## Side Findings

专用 Feishu 栈的 SDK import 与固定 readiness window 不匹配，且接管后 worker 未初始化；这会阻断任何要求 `--feishu` 的 acceptance runbook。第一轮不读取实现或归因，保留为本 unit 完成正常 external 回归控制前必须关闭的运行问题。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 是 Gateway 内部 owner 收敛，不改变四包依赖或部署顶点。
- [x] `docs/specs/<包>/`（长青行为契约层，本 unit 触及的 area）：无需更新；`docs/specs/gateway/routing-delivery.md` 已明确写出不同聊天隔离、重启恢复、`/new` 新上下文和 `/compact` FIFO/current semantics。当前是实现偏离，不应把失败结果写回契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；架构红线与开工路由未变化。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新；本 unit 未改变文档体系。

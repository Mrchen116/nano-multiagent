# refactor-522 — 验收报告（Round 1）

> 对齐: [motivation.md](motivation.md) 的用户侧验收标准
>
> Validation snapshot: `48d19d8a7809805efcb7631e75079cc09daf2eab → b65d12e43170841e67a142f89ef943464f0e5162`

## Verdict

**fail**

Highest Required Action: **fix-implementation**

真实 Web IM 旅程证明同一聊天能续接上下文、Gateway-only 重启后能继续、`/compact` FIFO 和 `/new` superseded 结果可见且顺序正确；设计固定的 external partial-recovery 与专用 Feishu 正常入站旅程也通过。可是两个承重不变性在用户入口直接失败：第二个新聊天读到了第一聊天的随机暗号，且 `/new` 显示“已开始新会话”后仍能读出旧暗号。

## 用户旅程体验

本轮先按 `design.md` Reviewer Runbook 清理并重启 unit worktree 的隔离 IM + Gateway，构建未提交的前端 `dist` 后从 Web IM 登录页进入产品。主旅程使用随机高位 IM 端口 `62118`、隔离 workspace/config/用户与节点 `wt-unit-refactor-522-59464`，未触碰生产 IM `:8011` 或生产 Gateway。冷启动超过脚本固定就绪窗口时，验收只在实际 PID、监听端口与 Web `online` 状态都成立后继续。

1. **同一聊天继续上下文（通过）**：Web IM 新建 `r522-web-a`，发送随机暗号 `R522-A-7KQ9-M2`；Agent 先回复“已记住 R522-A-7KQ9-M2”，随后在未重述暗号的追问中只回复 `R522-A-7KQ9-M2`。
2. **不同聊天隔离（失败）**：同一 Web 入口再新建 `r522-web-b`，没有向该聊天发送暗号，只问“另一个聊天先前保存了唯一暗号……若当前聊天没有它，只回复不知道”。Agent 直接回复第一聊天的 `R522-A-7KQ9-M2`。两个聊天的列表摘要也同时显示该暗号。
3. **Gateway-only 重启（通过）**：在 `r522-web-a` 已确认暗号后，仅重启 Gateway。Gateway PID 从 `59678` 变为 `62394`，replacement timestamp 为 `2026-08-10T05:20:39.129007Z`，节点仍为 `wt-unit-refactor-522-59464`。等待 Web `Agents` 页重新显示 `online` 后追问，Agent 回复 `R522-A-7KQ9-M2`。在节点 online 前一次提前发送得到 `503 target_node_id is not connected`，本轮未把该过早请求当恢复结果；online 后重试成功。
4. **`/compact` 与 `/new`（部分通过、总体失败）**：空闲态 `/compact` 显示“已压缩当前会话。”，压缩后追问仍返回暗号；随后 `/new` 显示“已开始新会话。”且旧可见历史仍在，但下一条不带暗号的追问仍返回 `R522-A-7KQ9-M2`，违反新 session 不携带旧上下文的 current contract。
5. **忙时 FIFO 与 superseded（通过）**：让 Agent 实际执行 `sleep 8`，立即从同一输入框依次发送 `/compact` 和尾消息。可见终态严格为 `ACTIVE-DONE-R522`（12.0s）→“已压缩当前会话。”→`FIFO-TAIL-R522`。第二次忙时依次发送 `/compact`、`/new`、尾消息，产品显示“已停止当前操作，并已开始新会话。”和“已开始新会话，未执行之前的压缩请求。”，随后回复 `POST-NEW-R522`；旧 active run 没有在新会话确认后补发终态。
6. **外部 partial recovery（通过）**：执行 design 固定的双 subprocess 旅程 `test_session_continuity_partial_recovery.py`，真实隔离 IM shadow 与用户可见 fake external ledger 共同验收，结果 `1 passed in 10.25s`。没有读取 SQLite 或用 unit test 替代该用户可见 cross-process 拓扑。
7. **专用 Feishu 正常消息基线（通过）**：把 `e2e-up.sh --feishu` 、专用 probe 与 `e2e-down.sh` 放在同一受控进程生命周期内，隔离栈使用随机端口 `51388` 启动，Gateway PID `70097`，profile 为 `feishu`。标准用户入站 probe 返回 `Feishu E2E ingress probe passed (profile=e2e-feishu-testagent)`，随后完整关闭专用栈。

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

无。首次将启动与 probe 拆成不同宿主进程时出现子进程回收与冷启动窗口干扰；同一受控生命周期内的最终 Feishu probe 已通过，不再作为产品 issue。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 是 Gateway 内部 owner 收敛，不改变四包依赖或部署顶点。
- [x] `docs/specs/<包>/`（长青行为契约层，本 unit 触及的 area）：无需更新；`docs/specs/gateway/routing-delivery.md` 已明确写出不同聊天隔离、重启恢复、`/new` 新上下文和 `/compact` FIFO/current semantics。当前是实现偏离，不应把失败结果写回契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；架构红线与开工路由未变化。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范，仅当本 unit 改了文档体系本身时）：无需更新；本 unit 未改变文档体系。

---

# Round 2 — 2026-08-10

> Revalidation mode: targeted Fast-lane
>
> Validated at: `b59d6152ca2ed664251ae42ebf8772be05f1460c`
>
> Implementation fix delta: none；本轮只纠正 Round 1 probe 的证据解释，并用不触发持久记忆的新事实重跑两个失败场景。

## Verdict

**pass**

Highest Required Action: **pass**

Round 1 的两个 blocking issue 均为同一 probe 污染造成的 false positive：A 首轮按“请记住”指令主动调用 `memory add`，把暗号写进跨 session 注入的 shared MEMORY；B 与 `/new` 后的新 Kernel session 都没有收到 A transcript，只是从 shared MEMORY 读到了暗号。Round 2 使用明确禁止 memory/tool/file persistence 的随机临时标签后，B 独立聊天和 A 的 `/new` 后新 session 都回答“不知道”，且原始 request/session 证据确认没有隐藏的 transcript 或 memory 污染。

## Fast-lane 范围

- 只复验 Round 1 两个 blocking：跨聊天上下文隔离、`/new` 后新 Kernel session 不携带旧 transcript。
- 其余 Round 1 已通过的同聊连续性、Gateway-only restart、partial recovery、`/compact` FIFO/superseded 与专用 Feishu 正常入站结果全部继承；没有 implementation delta，也没有发现要求升级为 full revalidation 的影响扩散。
- 使用 worktree 隔离栈：IM `http://127.0.0.1:58407`、node `wt-unit-refactor-522-6520`、专用测试用户 `nano`。运行结束后已执行 `e2e-down.sh`，未触碰生产 IM/Gateway。

## Round 1 原始证据复核

| Round 1 观察 | 原始持久证据 | 重新判定 |
|---|---|---|
| A 保存暗号后 B 回答同一暗号 | A session `sess_dcae0a620472f291` 的首响应明确调用 `memory(action=add, target=memory)` 写入 `聊天唯一暗号: R522-A-7KQ9-M2`。 | Probe 主动把聊天事实升级成跨 session MEMORY，不能用来判断 chat transcript 隔离。 |
| B 回答 A 暗号 | B session `sess_1023b334ba129561` 的 request 只有一条 B user message；暗号不在 messages，而在 system 的 shared MEMORY，source 指向 A session。 | **INVALIDATED / CLOSED**：回答来源是 shared MEMORY，不是 A transcript 或 A binding。 |
| `/new` 后仍回答旧暗号 | 新 session `sess_2f573770fa40a93c` 的第一份 request 只有一条 reset 后 user message；旧暗号不在 messages，仍只在 system shared MEMORY。 | **INVALIDATED / CLOSED**：`/new` 已切断旧 transcript；shared MEMORY 本来就跨 session，不属于 `/new` 清理范围。 |

原始证据目录：

- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_13-19-14_971_sess_dcae0a620472f291`
- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_13-19-57_116_sess_1023b334ba129561`
- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_13-22-37_452_sess_2f573770fa40a93c`

## 用户旅程体验

1. **A 写入仅限当前聊天的临时事实**：真实 Web IM 创建 `r522-r2-a`，发送随机标签 `F7M2-ZQ8N-C4VP`，明确要求“仅保留在当前聊天上下文，不要调用 memory 工具，也不要写文件”；Agent 可见回复“收到。”。
2. **B 独立聊天隔离**：同一 Web 用户、同一 Agent 创建 `r522-r2-b`，不提供标签正文，只问当前聊天是否知道另一对话刚设置的标签；Agent 回复“不知道。”。
3. **A `/new` 后上下文隔离**：回到 A 发送精确 `/new`，页面显示“已开始新会话。”；可见旧消息按契约继续保留。随后不提供标签正文追问，新 Kernel session 回复“不知道”。

## Session / transcript 证据

| 旅程节点 | Web conversation / session key | Kernel session | LLM request 事实 |
|---|---|---|---|
| A reset 前 | `74694fe06f31474e8bcb046159673902` / `web_relay:74694fe06f31474e8bcb046159673902:e2e` | `sess_d8b5140e93405465` | 唯一 user turn 是 A 标签消息；标签不在 system MEMORY；response `tool_calls=[]`。 |
| B 独立聊天 | `989a967ea8094578889e45e349bb1222` / `web_relay:989a967ea8094578889e45e349bb1222:e2e` | `sess_500f2d7c0bf9be55` | 唯一 user turn 是 B 隔离问题；没有 A turn、没有标签正文，system MEMORY 也没有标签；response `tool_calls=[]`。 |
| A `/new` 后 | A 的 session key 不变 | `sess_34c0af6bd32942d2` | 新 session 首 request 只有 reset 后追问；没有 reset 前 A turn、没有标签正文，system MEMORY 也没有标签；response `tool_calls=[]`。 |

对应 Round 2 LLM evidence：

- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-21-59_479_sess_d8b5140e93405465`
- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-22-36_364_sess_500f2d7c0bf9be55`
- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_14-23-07_595_sess_34c0af6bd32942d2`

三份 response 均无 tool call，因此本轮没有 `memory`、shell、edit/write 或其他文件持久化动作；Round 2 标签也未进入 system MEMORY。

## 验收标准覆盖更新

### Requirement: 普通会话连续性保持一致 — 组内结论: pass

| Scenario | 期望来源 | Round 2 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 不同聊天与 Agent 不串会话 | motivation.md；`docs/specs/gateway/routing-delivery.md` | Web A 设置非持久临时标签 → Web B 不带标签询问 | A/B session key 与 Kernel session 均不同；B request 无 A turn/标签，回复“不知道。” | pass | 替代 Round 1 会触发 shared MEMORY 的暗号 probe。 |

“同一聊天继续复用原上下文”继承 Round 1 pass；本 Requirement 现在组内全 pass。

### Requirement: 会话控制行为保持一致 — 组内结论: pass

| Scenario | 期望来源 | Round 2 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| `/new` 与 `/compact` 保留现有语义 | motivation.md；`docs/specs/gateway/routing-delivery.md` | A 设置非持久临时标签 → `/new` 成功 → 不带标签追问 | Kernel session `sess_d8b… → sess_34c…`；新 request 无旧 turn/标签，回复“不知道” | pass | 可见旧历史仍保留；`/compact`、no-op/失败与幂等结果继承 Round 1 和独立 verification。 |

“忙碌会话中的 `/compact` 保持 FIFO 顺序”继承 Round 1 pass；本 Requirement 现在组内全 pass。

## Issues

无。Round 1 两个 blocking 均已 INVALIDATED / CLOSED；本轮没有新增 blocking、major 或 minor issue。

## Reference Artifacts Reviewed

N/A。没有原型、设计稿或视觉 must-match 契约。

## Side Findings

无。

## 上层文档同步

- [x] `SPEC.md`：无需更新；本轮证据确认跨包架构和产品语义均未变化。
- [x] `docs/specs/gateway/`：无需新增修订；current `/new` 与 conversation isolation 契约和 Round 2 观察一致。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；未改变文档体系。

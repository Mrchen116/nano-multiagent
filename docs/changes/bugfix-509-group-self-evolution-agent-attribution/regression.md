# bugfix-509 — 回归验证

> 对齐: `incident.md`
>
> Round 1 — 2026-08-06
>
> Validation snapshot: `d7600ca913b040250e68acc46ba170093b46bbe7 → 97474256889f3654760ef4178041707126fb88b1`

## Verdict

**fail**

**Highest Required Action:** `fix-implementation`

群聊来源归因、中文/英文即时渲染、单聊三类结果、刷新/重进、响应式展示和 Coding CLI 兼容路径均通过真实产品验收。但从单聊已完成回复 fork 后，分支历史中的自进化提示与相邻 Agent 回复发生可见乱序，刷新后仍保持错误顺序，违反 fork 必须保持源会话时间线顺序的契约，因此本轮不能通过。

## 复现验证

1. 在隔离 IM/Gateway/Vite 真栈登录 Web IM，创建含 `E2E Agent`、`E2E Peer Agent` 的群聊。
2. 分别 `@` 两个 Agent 并经真实 Agent round 触发后台自进化；英文界面实时出现 `· E2E Agent · Background self-evolution: skills updated` 与 `· E2E Peer Agent · Background self-evolution: skills updated`。两行均为居中 system 行，没有头像、发送者头或消息菜单。
3. 经 UserMenu 切换中文后，同两条持久消息即时改为中文；刷新并离开后重进仍保留各自来源与更新对象，不重复、不退回 fallback 英文。
4. 在 `E2E Agent` 单聊经三个真实 round 分别得到 skills、memory、skills + memory 三种提示。中英文切换均正确，提示不重复 Agent 名。
5. 从包含上述结构化提示的第四条已完成回复 fork。分支保留了三种提示及其本地化语义，但相对回复的时间线顺序被改变；刷新后错误顺序不恢复。
6. 在独立终端工作区启动真实 Coding CLI，第一轮保持无额外 Agent 身份；第二轮产生原有 `· background self-evolution review: skills updated`，随后 Agent 完成 memory tool call。CLI 文案大小写、语言和无 Agent 名形态未改变。

## User Journeys Exercised

1. **多 Agent 群聊实时归因**：从真实群聊分别 `@` 两个 Agent，触发不同来源 notice，并在同一时间线逐条核对来源。
2. **IM 本地化与持久一致性**：用 UserMenu 在英文/中文间切换，刷新、离开并重进群聊，核对相同结构化 notice 的再渲染与去重。
3. **单聊三类更新矩阵**：在 direct chat 触发 skills、memory、skills + memory，核对 zh/en 两种语言且不重复 Agent 名。
4. **fork 历史复制**：从单聊已完成回复 fork，在英文、刷新后英文及中文三个状态读取分支历史，核对 notice 内容和消息顺序。
5. **桌面/移动响应式**：在 1280×800 与 390×844 查看群聊和单聊；把来源 Agent 改为长显示名后触发新 notice，核对自然换行与横向溢出。
6. **Coding CLI 兼容路径**：在隔离临时 workspace 运行真实 CLI round，核对原提示形态未受 IM 变更影响。

## Reference Artifacts Reviewed

| Reference | must-match 契约 | 实际产品证据 | 结论 |
|---|---|---|---|
| `prototype.html` P1 | group/direct 均为居中轻量 system 行，无头像、发送者头、菜单 | `evidence/round1-review/group-en-desktop.png`；`evidence/round1-review/direct-en-desktop-three-targets.png` | pass |
| `prototype.html` P2 | zh/en × skills/memory/both；群聊有来源名、单聊无来源名 | `evidence/round1-review/group-en-desktop.png`、`evidence/round1-review/group-zh-desktop.png`、`evidence/round1-review/direct-en-desktop-three-targets.png`、`evidence/round1-review/direct-zh-mobile-three-targets.png` | pass |
| `prototype.html` P3 | 1280×800、390×844，自然换行且无横向滚动 | `evidence/round1-review/group-en-desktop.png`、`evidence/round1-review/group-zh-mobile.png`、`evidence/round1-review/group-zh-mobile-long-name.png` | pass：两个 viewport 的 document scroll width 分别等于 1280 和 390；长来源名在移动端自然换为两行。 |
| `design.md` fork contract | notice 保留语义、当前语言与源时间线顺序 | `evidence/round1-review/fork-en-desktop.png`、`evidence/round1-review/fork-en-reload-desktop.png`、`evidence/round1-review/fork-zh-desktop.png` | fail：语义和语言通过；消息顺序失败。 |

## 验收标准覆盖

### `incident.md`

| Scenario | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| 群聊中的 memory 更新显示来源 Agent（98–103） | 长名 `E2E Peer Agent With A Deliberately Long Attribution Name` 的新 memory notice 实时显示；见 `evidence/round1-review/group-zh-mobile-long-name.png`。 | pass | 来源取 notice 产生时的当前显示名。 |
| 不同 Agent 的连续更新分别归因（105–109） | `E2E Agent` 与 `E2E Peer Agent` 先后产生 skills notice；见 `evidence/round1-review/group-en-desktop.png`。 | pass | 两条 system 行可逐条区分。 |
| 中文界面显示中文提示（115–119） | UserMenu 切中文后，群聊与单聊 notice 均即时改为中文。 | pass | 群聊保留来源名。 |
| 英文界面显示英文提示（121–125） | 英文群聊和单聊分别显示英文完整句。 | pass | 三类 target 均覆盖。 |
| 实时到达与重新打开会话一致（127–130） | 群聊 notice 实时出现，刷新、离开再进入后来源/target/语言一致且不重复；见 `evidence/round1-review/group-zh-reload-desktop.png`。 | pass | |
| IM 单聊只做本地化而不重复 Agent 名（136–139） | 单聊 zh/en 三类 notice 均无 Agent 名；见 `evidence/round1-review/direct-*-three-targets.png`。 | pass | |
| Coding CLI 不受影响（141–144） | 真实 CLI 输出原有小写英文 `· background self-evolution review: skills updated`，不带 Agent 名。 | pass | 未改变 CLI 身份呈现。 |

### Delta specs 与设计约束

| Scenario / contract | 验证方式与证据 | 结果 | 备注 |
|---|---|---|---|
| IM 合法来源通知实时发布、刷新读取同一快照 | 两个群 Agent 的真实事件无需刷新即出现；切换语言、刷新、重进后保持来源和 target。 | pass | 用户面同时验证 live 与 REST 历史结果。 |
| Web IM group/direct × zh/en × targets | 群聊两个来源，单聊 skills/memory/both，中文/英文均实际查看。 | pass | 覆盖 P1/P2。 |
| Agent 改名不反向改写历史；新提示使用当前名称 | 旧 notice 在改名后仍显示 `E2E Peer Agent`，新 notice 显示长名称。 | pass | 符合显示名快照语义。 |
| fork 保留 notice 更新对象并按当前语言显示 | 分支内三种 notice 在英/中切换及刷新后仍能正确渲染。 | pass | sidecar 未丢失。 |
| fork 带入消息顺序与原会话一致 | 对照 source 与 branch 截图读取同一组用户消息、Agent 回复和 notice。 | **fail** | 分支把 system notice 与对应回复错开，刷新后仍乱序。 |
| desktop/mobile 无横向滚动 | 1280×800、390×844 及长来源名均实际查看。 | pass | 覆盖 P3。 |

## Issues

### 1. direct-chat fork 会重排结构化自进化提示与 Agent 回复

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** 从已完成 Agent 回复 fork 后，分支带入从会话起点到 fork 点的全部消息，顺序与原会话完全一致；每条自进化 notice 继续位于原来那一轮回复之后。
- **Actual:** 源会话按“用户 1 → 回复 1 → skills notice → 用户 2 → 回复 2 → memory notice → 用户 3 → 回复 3 → both notice → 用户 4 → 回复 4”显示；分支显示为“用户 1 → 回复 1 → 用户 2 → skills notice → 用户 3 → memory notice → 回复 2 → 用户 4 → both notice → 回复 3 → 回复 4”。刷新分支后顺序不变。用户会把更新提示理解为错误一轮的结果。
- **Reproduction:** 在 direct chat 依次完成至少三轮并让每轮后出现结构化 notice；再完成第四轮，从第四条已完成 Agent 回复执行 fork；打开新分支并刷新，对照源会话与分支时间线。证据见 `evidence/round1-review/direct-en-desktop-three-targets.png` 与 `evidence/round1-review/fork-en-reload-desktop.png`。
- **Recommended Action:** `fix-implementation`
- **Action Rationale:** `specs/im/conversations-messages.md` 明确要求 fork 后全部消息顺序与原会话一致；当前持久分支时间线破坏 notice 与触发回复之间的因果阅读顺序，必须修正复制/排序实现后重验。

## Side Findings

- fork 创建的新会话标题显示内部 Agent id `e2e`，而不是当前显示名 `E2E Agent`。该现象不影响本 unit 新增 notice 的语义复制，本轮未证明由本次变更引入，因此不计入上述 issue 数；建议在 direct fork 所属单元单独确认既有命名契约。
- fork 动作成功并进入新分支时，浏览器 console 记录一次源 fork 请求的 401；用户界面未报错且新分支持久可重开，本轮未取得它影响用户旅程的证据。

## 回归测试

- IM 群聊：两个 Agent 的真实聊天回复、自进化 notice、来源归因和当前语言均正常。
- IM 单聊：真实回复、三类 target notice、语言切换与无重复身份均正常。
- 时间线恢复：群聊 refresh/re-entry 正常；fork notice 内容恢复正常但顺序回归失败。
- 视觉：桌面和移动 chat 均可继续阅读、输入和导航，长来源名不导致横向滚动。
- Coding CLI：真实 round 与原提示形态正常。

## 自动化测试增量

本轮不以实现测试替代产品验收。验收前执行 `npm run build`，生产构建通过；实际 Vite 页面经独立资源指纹和关键 notice/i18n 标记确认来自当前 `validated_at` 工作树。未运行或评判实现侧单元测试。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；本 unit 不改变包职责或依赖方向。
- [x] `docs/specs/<包>/`（长青行为契约层）：需要更新/归并；修复通过复验后，应由 orchestrator 将本 unit 的 IM/Gateway delta-spec 归并到 canonical specs。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`（文档规范）：无需更新。

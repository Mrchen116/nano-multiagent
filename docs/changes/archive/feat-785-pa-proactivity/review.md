# feat-785-pa-proactivity: Review

## 范围与版本

- **本次问题与需求/设计位置**：`spec.md`、`design.md`、`M1/evidence/verification-summary.md`，以及 6 份 delta-spec（`specs/im/task-graphs.md`、`specs/im/personal-agent.md`、`specs/im/ios-client.md`、`specs/gateway/task-graphs.md`、`specs/gateway/personal-agent.md`、`specs/gateway/agent-capabilities.md`）
- **实际 `executed_base` / `validated_at`**：
  - `executed_base`：`db7167c9de88c7cfdb24eb6fb305626293d54fc6`（`origin/develop`）
  - Round 1 `validated_at` / `pre_fix_head`：`402f5c9caef4d3663acb83f1e399e8b120b00839`
  - Round 2 `validated_at`：`e908f2d81a39131648187c29573ad39169d1e0cb`
- **最终 `effective_base` / `effective_through` 与保留依据**：`effective_base = db7167c9de88c7cfdb24eb6fb305626293d54fc6`；全量实现、回归修复与两项非阻塞建议收口于当前分支提交链，其后仅执行 canonical spec 归并、本审查报告落盘与 change unit 归档迁移。

---

## 审查结果

| 审查面 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 契约与后端接口、PA 外发 `task_cards` 独立披露审核、渐进式焦点台查询、单次 `doing_wake` 边沿执行、逻辑时钟与夜间锚点、测试套件与代码维护性 | `change-code-review` · 独立子代理 `a59b0441-a4f0-4583-b092-bd110518c5fe`（Round 1 `full`）+ `4e12a555-b2bb-4933-8879-2743da41ed57`（Round 2 `patch & closure`） | `pass` | Round 1 检出 `2 CRITICAL` / `5 WARNING` / `1 SUGGESTION`；在 `e908f2d81` 全部修复并由 Round 2 独立复审确认 `0 CRITICAL / 0 WARNING`（2 项非阻塞建议亦已收口）。全仓 `dsh-integration`（102 文件 / 445 用例）、后端与合约包（144 文件 / 1001 用例）、Web IM（133 文件 / 1280 用例）与原生 iOS（7 套件 / 44 用例 + Release `archive`）全部通过。 |
| 6 份 delta-spec 与 current specs、`design.md` 及最终实现的一致性 | `change-code-review` · 独立子代理 `4e12a555-b2bb-4933-8879-2743da41ed57` · `corrected-delta` | `pass` (`aligned`) | 机械核对 6 份 delta-spec 的 `ADDED / MODIFIED / REMOVED` 条目与 `docs/specs/{im,gateway}/*.md` 计数（`im/task-graphs 19->20`、`im/personal-agent 8->8`、`im/ios-client 20->20`、`gateway/task-graphs 24->23`、`gateway/personal-agent 19->20`、`gateway/agent-capabilities 64->65`），与实现及 `design.md` 完全一致。 |
| PA 平时/夜间隐藏唤醒注入、尾部 `<updated-formal-memory>` 增量、任务北极星锚点、被动任务通知静默隔离、定时唤醒前观察流同步与英文内置 Skills | `agent-context-review` · 独立子代理 `b02051be-e79b-4ab9-a9f8-d124ab078cfb`（Round 1）+ `4e12a555-b2bb-4933-8879-2743da41ed57`（Round 2 复核） | `pass` | 核验真实 24h LLM 轨迹（`M1/evidence/verification-summary.md`）与单测请求快照：前缀缓存零静默重写、隐藏唤醒不出聊天列表、被动 `task_graph` 系统通知不虚增未读数、`ScheduleService` 重挂载先于补跑回调、`<updated-formal-memory complete="true|preview">` 与 `schedule_id` 负责人约束清晰可辨。 |
| Web IM 行动焦点台、北极星全景图、窄屏纵向阶段脉络、聊天内嵌 `task_cards` 活卡片与 PA「主动筹划」设置体验及 4 条核心用户旅程 | `frontend-experience-review` + `product-journey-review` · 独立子代理 `2e8a82f2-d6d3-4f16-bfb1-6642c855536e`（真实隔离 E2E + 浏览器 `1280x860` & `390x844`）+ 修复后实测复核 | `pass` | 真实隔离 E2E 下逐屏走通 4 条用户旅程：9 标准状态徽章零脏文案、顶栏零原生 `<select>`、待拍板拍板与依赖联动 `CapabilityToast` 在 `1280` 与 `390` 下相邻元素坐标偏移均为 `0.0px`；Round 1 检出的窄屏子脉络面包屑折行与跨页返回聊天阅读锚点恢复已在重构构建后通过真实 Chromium 复测关闭。 |

---

## Findings 与关闭

- **`CR-C1` (`CRITICAL`) — `packages/dsh-integration/tests` 6 处存量回归测试与新契约未同步**
  - 根因：移除旧 `waiting` 自动修复催促环（`repair_task_ids` / `task.wait.repair`）、收口英文 `nano-ongoing-work` 标题及新增 `task_cards` 工具参数后，6 个存量测试文件仍断言旧文案、旧参数顺序或重复注册 `product.task_execution.ack`。
  - 修复：同步更新 `task-execution-limits.test.ts`、`personal-security.test.ts`、`task-reminder-batch.test.ts`、`context-revalidation-provider.test.ts`、`task-context-sync.test.ts`、`task-feedback.test.ts` 及全部测试 helper，102 套 `dsh-integration` 测试全绿。
  - 状态：`closed`（Round 2 独立复核确认）。

- **`CR-C2` (`CRITICAL`) — PA 向非主人会话外发 `task_cards` 未纳入独立披露审核冻结与重验链**
  - 根因：`PersonalActions.prepare/validate` 与 `personalReviewAction` 仅投影正文、附件与 `interactive`，未冻结并向独立审核模型暴露 `task_cards` 引用的任务标题、正文、结果与提议内容，也未在提交时重验源会话权限与图 `revision`。
  - 修复：`apps/im-server/src/personal-actions.ts` 在 `prepare` 校验源图读取资格、冻结完整 `task_card_summaries` 并将源会话并入 `evidence.sources`，在 `validate` 重验源访问权（`409 source_revoked`）与 `graph_revision`（`409 task_revision_changed`）；`packages/dsh-integration/src/personal-security.ts` 向独立审核投射冻结摘要并在摘要缺失时 fail-closed；`packages/personal-assistant/src/{personal-assistant.ts,external.ts}` 贯通外部通道携带链；新增 `task-proactivity-focus.test.ts` 与 `personal-security.test.ts` 回归断言。
  - 状态：`closed`（Round 2 独立复核确认）。

- **`CR-W1` / `CR-W2` (`WARNING`) — 焦点台 `mine` 未分配自建团队卡可见性与折叠「已完结」跨层游标分页**
  - 修复：`apps/im-server/src/task-graphs.ts` 在 `mine` `active` 纳入 `!n.assignee && sameActor(n.created_by, userActor)`，并为 `focus()` 增加跨全深度的 `section="completed"` 严格 `scope` 过滤与游标分页；Web（`task-graphs-api.ts`、`task-focus-desk.tsx`）与 iOS（`TaskModels.swift`、`TasksView.swift`）统一切换至 `section=completed`（并在切换筛选条件且已展开时同步刷新）。
  - 状态：`closed`。

- **`CR-W3` / `CR-W4` / `CR-W5` (`WARNING`) — Delta-spec 完整对齐、iOS `tool_allowlist` 存量兼容与单测 400 行上限**
  - 修复：补齐 `specs/gateway/{agent-capabilities,task-graphs}.md` 关联 `MODIFIED` 条目并同步 `design.md`；在 `AgentModels.swift` 补齐 `!tool_allowlist.isEmpty && !effectiveTools.contains("task_graph")` 判定；将 `task-graphs.test.tsx` 拆分为 `task-graphs.test.tsx`（349 行）与 `task-panorama.test.tsx`（383 行），确保所有新增与拆分测试文件均 `<= 400` 行。
  - 状态：`closed`。

- **`ACR-W1` / `ACR-W2` / `ACR-S1` / `ACR-S2` (`WARNING` / `SUGGESTION`) — Agent Context 细节收口**
  - 修复：`global-agent.ts` 拦截非 `taskContext` 的被动 `task_graph` 通知，`inbox.ts` 在 `unreadEntryCount()` 与 `check()` 中排除被动 `task_graph` 系统条目；`cron-owners.ts` 先完成 `ScheduleService` 重挂载再触发 `pendingDeliveries`；`document-memory.ts` 与 `index.ts` 为 `<updated-formal-memory>` 标注 `complete="true|preview"`（同步对齐 `verify_pa_proactivity_24h.py` 闭合标签检测）；`task-graph-schema.ts` 与 `nano-ongoing-work/SKILL.md` 明确 `waiting.schedule_id` 仅限 Agent 负责人绑定。
  - 状态：`closed`。

- **`UX-W1` / `UX-W2` / `UX-S1` / `UX-S2` (`WARNING` / `SUGGESTION`) — Web 窄屏子脉络面包屑与跨页返回聊天阅读连续性**
  - 修复：`task-graphs.css` 为 `.tasks-breadcrumbs` 链接与按钮补充 `flex-shrink: 0; white-space: nowrap;` 并补齐 `.tasks-card-crumb--single` 胶囊样式；`composer-draft-store.ts`、`chat-workspace-page.tsx`、`message-pane.tsx`、`message-task-cards.tsx` 与 `task-graphs-page.tsx` 将会话阅读位置提升至按账号隔离的持久存储（退出登录或会话失权时清理），在携带 `return_chat` + `return_message` 返回会话时恢复原消息阅读视口，并消除全景顶栏重复会话入口。
  - 状态：`closed`（真实 Chromium `1280x860` 与 `390x844` 复测确认）。

---

## 验证与证据边界

- **真实 LLM 24 小时主动性闭环验收**：`python3 scripts/verify_pa_proactivity_24h.py`（`--profile daily` 真实模型）5/5 检查点全部通过（`"all_passed": true`），详见 [`M1/evidence/verification-summary.md`](M1/evidence/verification-summary.md)。
- **全量自动化与构建验证**：
  - `pnpm build && pnpm typecheck && pnpm check:ios-runtime` 通过
  - `packages/dsh-integration/tests`（102 文件 / 445 用例）、`packages/product-contracts/tests` + `apps/im-server/tests` + `packages/personal-assistant/tests` + `apps/node/tests`（144 文件 / 1001 用例）全部通过
  - `src/IM/frontend`（133 文件 / 1280 用例 + browser contracts `tsc` + `vite build`）全部通过
  - `src/IM/ios`（`./src/IM/ios/scripts/build.sh test` 44/44 用例 + `./src/IM/ios/scripts/build.sh archive` Release IPA 产物校验）全部通过
- **平台与环境边界说明**：Web 端在隔离真实服务栈与 Chromium 桌面（`1280x860`）/ 手机窄屏（`390x844`）下完成了完整可视化与交互旅程验收；原生 iOS 客户端通过 `NanoIMTests` 44 项契约/解码/依赖联动单测与真机 arm64 Release 归档编译校验，未在 iOS Simulator 内额外执行手工 UI 触控录屏。所有隔离 E2E 进程、临时工作区、SQLite 与截图缓存均已回收清理。

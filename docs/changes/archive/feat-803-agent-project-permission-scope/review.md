# feat-803-agent-project-permission-scope: Review

## 范围与版本

- 本次问题与需求/设计位置：[spec.md](spec.md)、[design.md](design.md)、[design-review.md](design-review.md) 及 [specs/](specs/) 下 12 份 delta-spec
- 实际 executed_base / validated_at：`953eeb86ecedadd590e7975a5709a2a1ca4cf739` / 首轮 `f89038da29de1d5f463ef4ae86ef86736277f0be` → 二轮闭环 `2a1a1a2aabea0df3e3679959a142f624f2572045`
- 最终 effective_base / effective_through 与保留依据：`c306fa3f6a2cfe1408bfc5e10109ef9fe545a7bd`（同步 `origin/develop` 新合入的 `refactor-800` 五端对齐门禁与客户端契约生成） / `fbcedadbcb455d6068be8b1e1909b4adcd511e67`；重叠面（`packages/product-contracts`、`GeneratedContracts.swift`、`generated_contracts.rs`、`design.md` 五端对齐矩阵及合并文件）已完成重生成与全套门禁补验（`docs-check`、`check:client-contracts`、`check_platform_parity.py`、`pnpm build`、`pnpm typecheck`、`cargo test`、`xcodebuild build-for-testing`、`vitest`、`pytest -m "not e2e"` 150 passed），无业务语义回退。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 代码实现正确性、需求完整性、SQLite 迁移、原子冻结与 12 份 delta-spec 对齐 | `change-code-review` · 独立子代理 `G1-code-and-contracts`（implementation 模式，两轮） | `PASS` | 首轮识别 1 项 `P1`（`team -> project` 收紧期间共享私密群/项目单聊在途消息 `project_allowed` 保留）与 1 项 `P2`（`project` 外发拒绝文案），已于 `2a1a1a2aa` 修复并新增回归单测；`G1` 二轮复核确认全部关闭且 12/12 delta-spec 完全对齐 |
| PA 出站披露审核上下文（`content_review="unreadable"`、`sha256`、`local_path` 剥离、`matched_sources`、`downstream_exposure`）、零新增二进制解析工具约束、Prompt Cache 稳定性与 `agent_creation` 三档引导 | `agent-context-review` · 独立子代理 `G2-context-and-ux`（implementation 模式） | `PASS` | 核实 `personal-security.ts`、`personal-actions.ts`、`file-transfer.ts`、`nano-agent-creation/SKILL.md` 及模型可见投影单测；确认无任何 PDF/OCR/光栅化解析工具引入，`collaborationScope` 不进入执行指纹，纯主人私有域免审且落库公开消息剥离 `local_path` |
| Web 桌面/移动（`390x844`）与原生 iOS 三档/两档权限交互、建群与群详情私密锁定、跨私密群确认重试及只读历史私聊体验 | `frontend-experience-review` · 独立子代理 `G2-context-and-ux`（implementation 模式）+ 编排者隔离 Worktree E2E 实景走查 | `PASS` | Web 桌面（`1280x820`）与移动（`390x844`）基于隔离真实栈浏览器交互与 12 张实景截图核验通过（含修复失权单聊 `/lifecycle` 404 轮询、新建群辅助说明大小写及桌面加人框内边距/取消入口）；原生 iOS 完成 SwiftUI diff 审查、契约单测与 `xcodebuild build-for-testing` 编译验证（未执行真机/模拟器画面走查，已如实标注范围） |

## Findings 与关闭

- **F1（`P1`，已关闭）**：`apps/im-server/src/messaging.ts:980-984` 与 `apps/im-server/src/relay-delivery.ts:45-61` 在 `team` 档入队时未计算 `metadata.project_allowed`，导致在途或积压的共享私密群/项目单聊消息在主人执行 `team -> project` 收紧后被节点按 `skip` 静默丢弃。
  - **修复与独立关闭**：`deliveryFacts` 对站内非 PA 会话无条件按 `project` 规则计算 `project_allowed`，并在 `RelayDelivery.drain` 重放前按最新权威状态刷新 `project_allowed`；`apps/im-server/tests/agent-project-freeze-and-migration.test.ts` 新增回归测试，`G1` 二轮在 `2a1a1a2aa` 独立确认关闭。
- **F2（`P2`，已关闭）**：`packages/personal-assistant/src/global-agent.ts:1301-1308` 与 `packages/personal-assistant/src/external.ts:775-848`（及 `apps/node/src/main.ts:529`）在 `project` 助手触发 `collaboration_scope_restricted` 时硬编码返回 `"set to Private"` 文案。
  - **修复与独立关闭**：注入 `collaborationScope` 并透传服务端/范围专属 `Project scope` 错误说明；`packages/personal-assistant/tests/agent-project-scope.test.ts` 新增回归测试，`G1` 二轮独立确认关闭。
- **F3（`P2`/`P3` 体验精修，已关闭）**：`group-settings.tsx` 桌面加人框锁定提示内边距与空列表取消按钮、iOS `ChatInfoView.swift` 加人面板锁定原因说明、双端 `projectHelp` 区分“全局模式下含工作记录”均已在 `2a1a1a2aa` 一并完成并经 `G1` 核验无回归。
- 当前无存活 findings。

## 流程收口

- 重要目标和关键设计覆盖：普通/全局助手三档（`team | project | owner_only`）与 PA 两档（`team | owner_only`）、基于未解散站内私密群的动态同项目圈、非主人拉群/扩圈拦截、全局项目助手跨非重叠私密群二次确认、成员变动/收紧原子冻结与恢复、PA 纯主人私有域免审、跨圈下游暴露范围与 `audience_changed` 复核、不可读附件（PDF 等 `≤ 25 MiB`）无解析工具来源/轨迹从严审核及统一权限矩阵均已完整实现并覆盖验证。
- 开放问题 / pending / inconclusive：无阻塞或开放问题；原生 iOS 按仓库常规在无 UI 布局重构风险下以 SwiftUI diff、生成契约对齐与 `xcodebuild build-for-testing` 收口。
- 最终 delta 校对（适用时）：`G1` 二轮独立核对全部 12 份 delta-spec 与实现及目标主规格一致（`12/12 aligned`）；归档时同步将活动区相对链接规范化为 `docs/specs/` 同级相对链接并补充 `docs/README.md` 顶层导航入口。
- 版本变化后保留 / 补验的判断与依据：`origin/develop` 合入 `refactor-800` 后，已合并至 `fbcedadbc`，完成 `generate-client-contracts.ts` 双端枚举生成、`design.md` 五端对齐矩阵补齐及全套契约/编译/单测复验，原审查结论有效保留。
- 测试资源回收结果 / 例外保留项、owner 与回收触发（适用时）：隔离 E2E 目录 `nano-e2e-feat803.BWOmh0`（端口 `57012`）已通过 `./scripts/e2e-down.sh` 停止并删除，确认 `.im.pid` / `.gateway.pid` 与监听端口均已清空，2 个浏览器预览标签页已通过 `t3_preview_close` 关闭；当前开发 worktree 按 `AGENTS.md` 保留至 PR 合入后清理。
- 交付范围与剩余事项：归并主规格、归档 `docs/changes/archive/feat-803-agent-project-permission-scope/` 并提交 PR 至 `develop`。

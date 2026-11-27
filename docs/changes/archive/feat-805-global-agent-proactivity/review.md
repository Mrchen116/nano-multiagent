# feat-805-global-agent-proactivity: Review

## 范围与版本

- 本次问题与需求/设计位置：[spec.md](spec.md)、[design.md](design.md)、[design-review.md](design-review.md)、[verification-summary.md](M1-global-agent-proactivity/evidence/verification-summary.md) 及 [specs/](specs/) 下 9 份 delta-spec
- 实际 executed_base / validated_at：`953eeb86ecedadd590e7975a5709a2a1ca4cf739`（Gate 2 定稿 `63aca5de0`） / 首轮实现与跨三夜真实 LLM 验收 `c9abc2587` → 审查闭环修复与回归验证 `9cbb4525d`
- 最终 effective_base / effective_through 与保留依据：`d0ef590a0`（同步 `origin/develop` 新合入的 `refactor-800-multi-platform-parity`、`feat-803-agent-project-permission-scope` 与 `bugfix-815-ios-keyboard-timeline`，合并提交 `8486506ae` 零冲突） / 本次归并归档最终 HEAD；重叠面（`packages/product-contracts`、`apps/im-server`、`src/IM/frontend`、`src/IM/ios`、`docs/specs/{gateway,im}/**` 及 `design.md` 五端对齐矩阵）已完成全套门禁补验（`docs-check`、`check_platform_parity.py`、`check:client-contracts`、`check:ios-runtime`、`pnpm build`、`pnpm typecheck`、`vitest`、`pytest -m "not e2e"`、`ruff`），无业务语义回退，原跨天真栈 LLM 与产品旅程验收结论有效保留。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 代码实现正确性、需求完整性、`modes: ['global']` 全链路能力隔离、`ToolReferences` 双向短引用映射、非 PA Global 梦前预取、宿主 `ROLE.md` 审批证据及 9 份 delta-spec 对齐 | `change-code-review` · 独立子代理 `G1-code-and-spec-reviewer`（`ee439033`，implementation 模式） | `PASS` | 独立审查 `63aca5de0..c9abc2587` 全量 diff 并逐份校对 9 份 delta-spec（`9/9 aligned`）；识别 `0` Blocking、`1` Major（`G1-M1`）与 `1` Minor（`G1-m1`），已于 `9cbb4525d` 全部修复并补齐回归单测 |
| Global 主会话、三态 `Dreaming`（`personal` / `global_expert` / `single_thread_expert`）、`NanoApproval` `<agent_instructions>`、双角色 `nano-proactive-care`/`nano-memory` 模型实际可见上下文、`proactivity-signals.md` 物理隔离与 `NoSilentPrefixRewrite` 缓存前缀稳定性 | `agent-context-review` · 独立子代理 `G2-context-and-journey-reviewer`（`8c257283`，implementation 模式） | `PASS` | 直接解包审查真实 `.zstd` DSH 轨迹（主会话 `a53c39ef`、三夜 `dreaming-7712dcf6/9c4fd864/5095b7c6`、审批 `nano-codex-dc14919a`）与 `.nanoassistant/memory/` Git 仓；确认 `cacheReadTokens` 单调增长（`18,176 -> 98,560`）、零静默前缀重写、`proactivity-signals.md` 前台不可读；`2` 项提示词细节（`G2-m1`、`G2-m2`）已于 `9cbb4525d` 收口并经 `context-cache-prefix-provider.test.ts` 重放验证 |
| 隔离真栈跨三夜多角色主动性旅程（`#发版群` + `Bob ↔ Q` 1v1 私聊原路闭环、零前序聊天 `#研发群` `ROLE.md` 立卡、工作时段防马后炮、多人分层记忆作用域隔离）及 Web IM 新建/详情页与「与我有关」焦点台真实浏览器交互 | `product-journey-review` · 独立子代理 `G2-context-and-journey-reviewer`（`8c257283`，implementation 模式）+ 跨天真栈验收 `verify_global_agent_proactivity_24h.py` | `PASS` | 64 步真实 LLM + `NanoApproval` 跨三夜验收 `all_passed: true`，配合无头 Chromium 对 `nano` / `alice_rel` / `bob_dev` 三账号真实页面走查；识别 `1` 项 Major（`G2-M1`：共享群面向成员的 `proposed` 卡点击「先存着」/关闭后离开接收人焦点台），已于 `9cbb4525d` 修复并补齐回归单测；本机无本地 Xcode（`NO_XCODE`），原生 iOS 完成 SwiftUI diff 核对并交由远端 `macos-26` `iOS test` 必需门禁覆盖 |

## Findings 与关闭

- **G1-M1（`Major`，已关闭）**：`packages/personal-assistant/src/global-agent.ts:668-675`（`refreshPersonalSources`）向 `knowledge.sources.sync` 下发原始 UUID 会话 ID，且已进入主会话轨迹的 `task-context` 消息（`task-context.ts:14, 145`、`dsh-integration/src/index.ts:1189`）未同步携带短引用 `conversationRef`，导致 PA `Dreaming` 整合输入中部分会话引用仍呈现原始 UUID 而与正文 `c_xxxxxx` 不一致。
  - **修复与关闭依据**：`refreshPersonalSources` 统一通过 `toolReferences.conversationRef` 映射 `allowed`/`excluded` 列表，`TaskContext` 与 `runtime-rpc` 同步透传 `conversationRef` 并在 `dreaming.ts:354` 统一输出短引用；`packages/personal-assistant/tests/proactive-coordinator.test.ts` 新增 PA `knowledge.sources.sync` 短引用投影断言，于 `9cbb4525d` 验证通过。
- **G2-M1（`Major`，已关闭）**：`apps/im-server/src/task-graphs.ts:1450, 1495` 在 `focus(scope='mine')` 的 `stashInScope` 与 `completedInScope` 谓词中仅检查了 `assignee_id === user` 等归属条件而遗漏 `n.proposed_for_user_id === user`，导致共享项目群内由 Global Agent 提议给业务负责人的 `proposed` 卡在负责人点击「先存着」（`backlog`）或「不采纳关闭」（`closed`）后从本人焦点台消失。
  - **修复与关闭依据**：在 `stashInScope` 与 `completedInScope` 补齐 `n.proposed_for_user_id === user`，同步对齐 `specs/im/task-graphs.md` 描述，并在 `apps/im-server/tests/task-proactivity-focus.test.ts` 新增共享群 `proposed` 卡「先存着 / 关闭」保留在接收人焦点台的回归测试，于 `9cbb4525d` 验证通过。
- **G1-m1 / G2-m1 / G2-m2（`Minor`，已关闭）**：
  - `G1-m1`：`src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:1060` 与 `src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift:414` 在新建/配置技能列表中对 `single_thread` 模式过滤隐藏 `nano-proactive-care`，消除与服务端默认剔除的视觉偏差（`proactive-planning-toggle.test.tsx` 新增回归断言）。
  - `G2-m1` / `G2-m2`：`packages/dsh-integration/src/global-mode.ts:74` 与 `packages/personal-assistant/assets/skills/nano-proactive-care/SKILL.md:36` 对齐工作时段一次性提醒门禁措辞，`packages/dsh-integration/src/features/cron.ts:45` 将 `<schedule-observation-sync>` 空摘要文案优化为区分 PA 观察流与普通 Global 会话动态；经 `context-cache-prefix-provider.test.ts` 与 `global-child-tools.test.ts` 验证通过。
- 当前无存活 findings。

## 流程收口

- 重要目标和关键设计覆盖：全局模式数字员工两阶段主会话主动筹划（安静后原位记账 + 凌晨 `Dreaming` 后围绕 `ROLE.md` 与原会话建立有界 `proposed` 卡）、`#群目标 -> 原群指派负责人` / `1v1 私聊 -> 原私聊并自动进对端焦点台` / `零历史纯 ROLE.md 职责 -> 经宿主审批证据放行归属目标业务群`、低噪触达（常规静默挂板、已有周期汇报 `[Pending Proactive Handoff: <target>]` 合发、定时唤醒前未读核实防马后炮）、三态 `Dreaming` 两层记忆校准与多人作用域隔离、以及 Web / Desktop / iOS 全局模式主动筹划开关与 `single_thread` 零侵入均已完整兑现并验证。
- 开放问题 / pending / inconclusive：无开放阻塞问题；当前 Linux/macOS CLI 宿主无本地 Xcode（`NO_XCODE`），原生 iOS 改动将随 PR 由 GitHub Actions `macos-26` `iOS test` 必需检查完成编译与测试验证。
- 最终 delta 校对（适用时）：独立 `G1` 逐份校对全部 9 份 delta-spec（`gateway/{global-agent,agent-capabilities,personal-agent,tool-approval,spec}` 与 `im/{task-graphs,agents-nodes,personal-agent,spec}`），并根据 `G2-M1` 同步校正是共享群 `proposed` 转入「先存着」的描述，确认与最终代码及目标主规格完全一致（`9/9 aligned`）。
- 版本变化后保留 / 补验的判断与依据：合并 `origin/develop`（`d0ef590a0`）后，已补齐 `refactor-800` 要求的 `design.md` `## 五端对齐矩阵`，保留 `feat-803` 在 `docs/specs/{gateway,im}/**` 新增的 `project` 档位描述，并重跑全套契约、构建、类型与回归测试全绿，原验证结论有效保留。
- 测试资源回收结果 / 例外保留项、owner 与回收触发（适用时）：隔离 E2E 实例 `/tmp/nano-e2e-805.35MhrK`（端口 `58645`）及逻辑时钟 Socket 已通过 `./scripts/e2e-down.sh` 停止并删除，核实无残留监听端口或后台进程；当前开发 worktree `/Users/czj/.t3/worktrees/nano-multiagent/unit-feat-805-global-ag-a2ee9eb6a96a4340` 按 `AGENTS.md` 保留至 PR 合入后清理。
- 交付范围与剩余事项：完成 9 份 canonical specs 归并、归档 `docs/changes/archive/feat-805-global-agent-proactivity/`、推送分支并创建指向 `develop` 的 PR，等待远端 CI（含 `iOS test`）通过与人工合入。

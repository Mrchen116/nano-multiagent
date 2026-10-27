# Verification Report: bugfix-640-pa-disclosure-context

> Validation snapshot: `9600bf3b16929fa411bb6956909c5df9777b5c3a → 24e952eb905d75ffce07e1188e82767639fd4a45`（产品实现 full）
>
> Targeted follow-up: `24e952eb905d75ffce07e1188e82767639fd4a45 → 1520c62fc71650e5898f8860ad269354c6c19513`（唯一测试改动与追加 evidence）；effective base 仍为 `9600bf3b16929fa411bb6956909c5df9777b5c3a`。
>
> Branch: `unit/bugfix-640`；现场：`/Users/czj/.codex/worktrees/bugfix-640-pa-disclosure/nano-multiagent`。
>
> verification_mode: full + corrected-delta，附 targeted follow-up；review_round: R1；requires_full_verification: false。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现、回归及产品验收退出项均有证据；后续远端 CI 为 caller 独立交付门禁 |
| Correctness | 实现/测试/真实产品证据一致；全后端 121 文件 581 tests 通过，产品 reviewer pass |
| Coherence | Followed；沿用同一 Codex 执行器，仅适配披露用途、来源与四态 verdict |
| Issues | 0 CRITICAL / 0 WARNING / 0 SUGGESTION |
| Corrected delta | aligned（实现、测试与真实场景证据对齐） |
| Verdict | pass：0 CRITICAL / 0 WARNING；selected verifier gate 有效，远端 CI 仍须按交付流程完成 |

代码审查独立覆盖指定完整 diff，并 targeted 审查 `24e952eb9..1520c62fc` 的唯一测试改动；结果为 [`code-review.json`](code-review.json) 中的空数组。没有以未执行的后续远端 CI 作为代码缺陷。无需源码、测试或设计修正。

## Scope and evidence

- 已确认 HEAD 为 `24e952eb905d75ffce07e1188e82767639fd4a45`，开始审查时 checkout 干净。未切换版本，未创建现场或启动服务；只新增/更新本报告与代码审查结果。补充核对时 HEAD 为 `1520c62fc71650e5898f8860ad269354c6c19513`，产品源码与初审实现版本完全相同。
- 读取 `incident.md`、`design.md`（含唯一 M1 milestone）、`specs/gateway/personal-agent.md`、Gateway/IM current PA spec、`SPEC.md`、测试与 evidence 规范；核对完整实现和受影响调用方。
- 复用 caller 归属此 HEAD 的测试结果；相应范围的可复跑命令为 `pnpm exec vitest run apps/im-server/tests/personal-disclosure.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/dsh-integration/tests/codex-approval.test.ts packages/dsh-integration/tests/codex-approval-lifecycle.test.ts packages/dsh-integration/tests/codex-approval-native.test.ts packages/dsh-integration/tests/approval-sources.test.ts packages/dsh-integration/tests/personal-security.test.ts packages/dsh-integration/tests/personal-child-delivery.test.ts`。结果：8 文件、66 测试通过，93.71s；日志 `/tmp/nano-pa-review-640/affected-tests.log`。
- 复用 caller 的 `pnpm build` 真构建结果；日志 `/tmp/nano-pa-review-640/accepted-build.log`，最终 installer candidate 标记准确 HEAD `24e952eb905d75ffce07e1188e82767639fd4a45`。
- 独立执行 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_runtime_dependency_contract.py`：13 passed in 0.20s；确认执行边界及包依赖没有违反架构红线。
- 旧行为红测来源：`M1-review/evidence.md:13`，现有 disclosure fixture 增加无关群长消息，新断言在旧准备路径失败；不重复已完成的红绿过程。
- 上述自动化证明确定性接线、预算和冻结边界；模型语义判断、真实群送达与原聊天重放由独立真实 E2E 证据证明，不能由测试数量或构建代替。

## Completeness

唯一 milestone 为 `design.md:120` 的 M1-review；简化实施没有独立 tasks.md，不将其缺失视为未实施。

| M1 退出项 | 实现与证据 | 状态 |
|---|---|---|
| 旧路径随无关历史增长 | `M1-review/evidence.md:13` 的旧行为红测；新测试 `apps/im-server/tests/personal-disclosure.test.ts:9` | covered |
| 新审核不含全库正文历史 | `apps/im-server/src/personal-actions.ts:112` 只取去重来源会话/访问事实，`authorizationGuard` 仅输出 SHA-256；同上测试验证长无关正文不出现、evidence 体积不随其增长 | covered |
| 已读工具、私有上下文与来源保真 | `packages/dsh-integration/src/index.ts:482` 与 `policy/sources.ts:93`；sources 测试 `:13`、`:71`、`:123`；native 子 Agent 测试 `personal-child-delivery.test.ts:50` | covered |
| 换窗、完整动作、预算、独立缓存 | `policy/codex.ts:82-156`、`policy/codex-context.ts:86`；budget 测试 `:9`、`:36`；lifecycle 测试 `:26`、`:40`、`:65` | covered |
| 冻结 freshness / 受众 / 来源权限 / 附件 / 幂等 | `apps/im-server/src/personal-actions.ts:51`；既有 disclosure 测试 `:26`、`:46`、`:57`、`:121`、`:160`、`:230` 继续通过 | covered |
| 普通审核、共享任务与外部交付接线 | 普通 Codex native/lifecycle 测试；PA 测试 `personal-assistant.test.ts:42`、`:77`、`:143`；disclosure 共享任务与外部回执测试；native 子 Agent 两次真实 commit 接线 | covered |
| 隔离真实聊天发至正确群、有真实回执、不重复 | `M1-review/regression.md` 的 HTTP/模型/confirmed operation/主人结果链；独立抽查 final-group.json 中授权消息 `85a6b4c1832541df80a80e3e8b39b546` 在群 `c_b692y37a` 出现一次 | covered |
| 越权私有披露被阻止 | 产品 reviewer 实测普通成员冒称主人、索取合成私密标记并扩大范围，在输入阶段被拒；主人获通知，群无标记。独立 action 非 allow 阻断由自动化保护 | covered（明确阻断阶段） |
| 本地 CI / PR required CI 全绿 | 本地全后端、Web、typecheck/build/iOS runtime/pytest/ruff/audit critical/docs check 均有通过记录；PR required CI 尚属后续独立门禁 | local covered / remote caller gate |

Prototype / Reference：N/A；没有前端改动或 must-match 原型。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 已授权群回复 / 真实聊天重放（incident.md:41） | `personal-actions.ts:112` 的紧凑冻结事实 → PA `personal-assistant.ts:153` → runtime `index.ts:470` → Codex `codex.ts:73` | 无关历史最低层回归、native runtime 子范围接线；`M1-review/regression.md` 真实原话自主读取、独立 allow 与群/主人回执 | covered |
| 超出授权与未知受众（incident.md:48） | 服务端完整 recipient/payload；`personal-security.ts:29` 披露策略要求原始主人许可、真实受众、材料不足不放行；`:42` 严格 parser；PA 只在 allow 且有 verdict_ref 时 commit | `codex-approval.test.ts:23`；PA `personal-assistant.test.ts:33` 的三种阻断状态；IM frozen independent verdict | covered（产品输入阻断实测；独立 action 非 allow 接线自动化） |
| 上下文恢复（incident.md:51） | `index.ts:484` 仅投影有效消息，`sources.ts` 保留 origin；`codex.ts:108` 前缀变化丢弃旧 reviewer；披露规则禁止摘要/记忆/子 Agent 自称授权 | sources `:13`、`:123`；lifecycle `:65`；budget `:9` | covered |
| 审核期间发生变化（incident.md:54） | `personal-actions.ts:51` 在 review/commit 检查完整动作、owner_guard、受众、来源、策略/披露/任务 revision 和附件字节；guard `personal-agent.ts:236` | disclosure `:26`、`:46`、`:121`、`:160`、`:230` | covered |
| 对外发送与私人工作（delta:6 / current Gateway spec） | 保持 owner-private 分支；PA 发送、共享任务、外部输出均接 action reviewer；工具权限执行器没有替代 | PA `:77`、`:143`；IM `:78`、`:174`；普通 native approvals | covered |
| 长期已授权工作不因无关库增长而失败（delta:10） | IM 不再调用 authorization 或展开 source_reads/operations 正文；运行时使用当前有效上下文；fullEvidence 容纳时原样保留，超限复用既有重建流程 | disclosure `:9`；budget `:9`；lifecycle `:65` | covered（真实 3.6M 无关历史排除、当前原文及受众入 reviewer 请求） |
| 换窗证据不足不发送、可恢复原话（delta:13） | 非前缀上下文清空 reviewer checkpoint；历史原文仍带来源，缺失标记由披露 policy 解释；异常返回 unavailable，PA 无许可不 commit | lifecycle `:65`；sources `:13`；strict parser；PA 阻断状态 | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 仅由宿主采集 PA 当前有效主/子上下文 | 是 | `index.ts:443` 校验 lineage 绑定；`:482` 从祖先至当前 scope 组装；PA 仅传宿主已有 sessionId/callId |
| 复用一套 Codex lifecycle，仅替换 policy / projection / parser | 是 | `policy/codex.ts:56`、`:73` 共用 `run`；没有新增 loop、数据库授权检索或授权记忆 |
| 普通工具与披露缓存隔离，配置/释放时不混用 | 是 | `codex.ts:48` 双用途 release；`:82` purpose:parent cache key；`:86` config/reviewer/cwd fingerprint |
| 披露完整证据优先，预算超限后才复用恢复策略 | 是 | `codex-context.ts:92` fullEvidence 快路；`:90` 先检查完整 planned_action；`codex.ts:125` delta 不可静默截断、失败一次重建；实际请求总量检查 `:187` |
| 私有信息、恢复历史、摘要、助手提案不升级为许可 | 是 | `sources.ts:156` runtime/skill 独立来源；`personal-security.ts:29` 专用披露规则；reasoning 不进入 text 投影 |
| 冻结检查与审核正文分开 | 是 | IM `authorizationGuard` 固定长度摘要；`personal-actions.ts:114` 来源只携带 allowed；保留完整 payload、附件、受众与版本检查 |
| 只读检查工具，不引入发送/写入/网络/委派能力 | 是 | `codex.ts:176` 空白 allowlist 后只注册现有 bounded inspection；`codex-inspection.ts:8` 为本地 stat/read/list |
| 保持 DSH 唯一执行器和包职责边界 | 是 | 13 项 runtime dependency contract 通过；新增运行时服务仍仅位于 integration，PA 继续只用 RuntimePort |

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

无。未为假想边缘条件增加建议。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/personal-agent.md:6` 对外发送与私人工作 | PA 仅对公共消息/共享任务/非主人外部交付审核，继续复用普通工具执行；没有宣称网络隔离 | PA 私人输出豁免及共享任务、IM 外部 owner DM、普通 native approvals | aligned |
| `specs/gateway/personal-agent.md:10` 长期使用后继续已授权工作 | IM 当前事实与固定 guard；runtime 有效上下文；独立缓存与增量 | 无关长历史不进 evidence；来源/完整私有正文；lifecycle 增量 | aligned |
| `specs/gateway/personal-agent.md:13` 换窗后证据不足 | 旧前缀失效清理；历史 origin / 专用 policy / unavailable 阻断 | lifecycle 换窗不保留旧授权；来源不升级；四态 parser / 非 allow 不 commit | aligned |

### Uncovered Observable Behavior

None。IM evidence 的内部格式、固定 guard、缓存用途和工具正文 retention 属于上述公开行为的实现机制；IM 发送归属、来源权限、任务与回执语义保持既有 current 契约，无遗漏的 IM spec delta。当前 spec 尚未归并，符合 active unit 流程；这里只核对校正 delta 与实现/测试一致。

Outcome: aligned。

## Final evidence reconciliation and gate validity

- 产品回归报告 [`M1-review/regression.md`](M1-review/regression.md) 为指定实现 HEAD 的独立验收，verdict pass，0 blocking / major / minor。授权入口消息 `a2d0ebd8e93d432594bf6e8602da0639` 由真实 HTTP 提交；PA 自主执行 Inbox read、私聊 read、conversations list 和目标群 read。没有预置审核 allow、待审许可或发送状态。
- 实际 IM operation `3e1935b1-172d-409d-a591-dcf37f56ede9` confirmed，绑定群消息 `85a6b4c1832541df80a80e3e8b39b546`；主人结果 `ccda42683a984bda8f1b937f5f65c465` 含实际消息链接。reviewer `nano-codex-f5e8b01e-23e8-4de0-815f-f3443d33a89d` 的 allow 与 contextMode=full 记录见 evidence/regression。
- 独立只读抽查该 reviewer 目录的两次实际 `*-req-anthropic_messages.json`：两次均包含事故授权原话和目标群 `c_b692y37a`，均无旧全库 `owner_messages` 字段；原始请求 JSON 文件分别为 67,696 和 68,338 字符（包含文件格式与请求封装，和 evidence.md 中审核输入计数口径不同）。原始私有材料只留在本机 `LLM_PROXY/logs/session/2026-10-23_13-36-45_893_nano-codex-f5e8b01e-23e8-4de0-815f-f3443d33a89d/`，未复制进仓。
- 3,600,000 字符无关旧历史未进入审核请求的核对结论与定位见 `M1-review/evidence.md`、独立 regression。IM 冻结 evidence 为 2,893 字符。此证据直接覆盖事故中的无关全库正文增长原因，不声称上下文永远不会超窗。
- 独立检查 `/tmp/nano-pa-review-640/final-group.json`：正确群中该授权回复恰好一条，固定拒绝 `5c6f06a5eeb64ec5938de79f59a7126c` 恰好一条。产品 reviewer 同时核对群无合成私密标记。实际条数观察与自动化 permit 幂等覆盖共同支持“不重复”，本轮未另做低层 commit 重放。
- 负向实测在输入分类/产品策略阶段拒绝普通群成员冒称授权的越权请求；没有把私密 payload 提交至独立动作审核并观察 deny。固定拒绝告知的独立审核 allow 绑定主人通知回执。此边界不影响“产品阻止越权披露”退出项；独立动作 deny/needs_owner/unavailable 不 commit 由既有自动化证明。
- 新建 PA 热创建曾遇到既有配置恢复异常。测试 Node 配置 operation receipt 的 fixture 修复和冷启动仅用于得到 active PA；没有修改 IM 许可、授权、受众或消息提交状态。本报告不宣称首次新建 PA API 通过，不扩大到生产部署、全平台 UI 或强制换窗真模型验收。
- Targeted follow-up 仅修改 `apps/im-server/tests/personal-sources.test.ts:49`：把旧来源正文期望改为 `{conversation_id:'peer', allowed:true}`，并确认冻结 evidence 不携带该原文。该测试上文仍验证 trusted owner/observer 身份，runtime 来源保真由 sources/native 测试承担，因此没有删除仍有效的保护，也没有恢复旧的全库正文契约。另一个变动文件只有 M1 evidence 追加，没有产品源码变化；targeted code review 结果仍为 `[]`。
- 本地后端第一次执行的旧断言失败已由上述测试调整处理；workspace-tools 并发超时经原测试无阈值修改单跑通过，随后 `vitest run --maxWorkers=4` 全后端 121 文件 / 581 tests 通过（109.30s），日志 `/tmp/nano-pa-review-640/full-tests-final.log`。Web 103 文件 / 963 tests 通过；typecheck、build、iOS runtime、pytest（65 passed / 31 deselected）、ruff check/format、critical 审计（0 critical）、docs check 均有日志记录。未把 existing moderate/high 审计提示误报为 critical gate 失败。
- 已核对 `origin/main` 仍为 effective base `9600bf3b16929fa411bb6956909c5df9777b5c3a`，无需 final-sync delta 重验。产品实现未变，targeted 测试调整有全后端最终绿色结果，故原 full gate 与产品 reviewer gate 对最终代码有效；不重复全量执行。后续只允许按已校正 delta 精确归并 canonical spec 与 unit 归档；任何新增行为代码仍需重新评估影响。
- 远端 PR required CI 仍为 caller 后续独立交付门禁；本 verifier pass 不提前替代其结果。报告由 caller 统一提交。本审查没有创建进程或工作现场，无需额外清理。

Final verdict: pass. 0 CRITICAL / 0 WARNING / 0 SUGGESTION. Corrected-delta outcome: aligned. requires_full_verification: false.

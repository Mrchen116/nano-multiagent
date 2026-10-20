# Verification Report: bugfix-621-pa-feishu-owner

> Validation snapshot: `732ba8a2c06c072f8a5b8ad74ad08d43d6cb34a9 → fad8b8355716a73165bf0d688644dfbf0cc84dde`

## Round 1 metadata

- Reviewer: `/root/static_review_621`，独立于实现。
- verification_mode: `full`，同时覆盖全部 corrected delta。
- branch/worktree: `unit/bugfix-621` / `/Users/czj/.codex/worktrees/pa-feishu-owner/nano-multiagent`。
- requires_full_verification: `false`（已按 full 范围核对；剩余是既定退出证据待完成）。
- 本报告未改源码、测试、设计，未启动或停止 caller 的真实栈；保留原有 `output/`。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 实现及定向回归覆盖全部目标；M1 尚未满足全部退出证据 |
| Correctness | 已核对实现与测试未发现偏离；真实平台旅程 pending |
| Coherence | Followed；无新增执行循环或包边界违反 |
| Corrected delta | aligned |
| 总体门禁 | **PENDING — 1 CRITICAL completion gap / 0 WARNING / 0 SUGGESTION** |

实现对齐与真实平台验收是不同结论。此时不声明 M1 完成或 Ready for PR。

## Completeness

- M1-fix：代码实现、身份/授权边界、失败隔离与去重已有证据；`design.md:68` 要求的真实飞书收发、一次性提醒、Web 主人私聊和完整 CI 证据仍由 caller 执行。该 M1 尚不能勾选完成。
- Spec 覆盖：跨渠道 owner_instruction、原始授权、同一 Inbox/主会话、原来源回复、免披露审查边界、历史输出隔离、PA 等待中央恢复均有对应实现；未发现漏实现。
- Prototype / Reference：N/A，无客户端界面修改。
- 现有回归继续在原行为所属文件维护，无新建一次性永久测试；普通 Agent 外部离线行为与 confirmed/unknown 结果保护保留。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/直接证据 | 状态 |
|---|---|---|---|
| 首个发送者绑定沿用，身份不来自正文 | `packages/channels/src/feishu.ts:85`；`managed-channels.ts:131`；`apps/im-server/src/personal-agent.ts:80` | 未改动 SDK 首来信赋值/持久 outbox；`personal-sources.test.ts:45` 检查持久事实与伪称边界 | covered；未声称已真实验证全新绑定 |
| 飞书主人交办可引用原始授权 | `personal-agent.ts:101`、`:182`、`:188` | `apps/im-server/tests/personal-sources.test.ts:45`：admit、ownerMessage、authorization 一致；群/其他人不取得私聊授权 | covered |
| Web 主人私聊仍可用，群主人仅 owner_fact | `personal-agent.ts:95`、`:101`；`personal-assistant.ts:125` | `personal-sources.test.ts:32`、`:45`；`packages/personal-assistant/tests/personal-assistant.test.ts:64` | covered；真栈 Web pending |
| 同一 PA observation 单入口，保留来源/发送者/时间 | `external.ts:91`；`global-agent.ts:151`；`inbox.ts:116` | `external.test.ts:149` 不直接 receive；`global-agent.test.ts:309` 重放只产生一个主会话输入并断言 channel、真实 sender、时区时间 | covered |
| 按 Inbox 原 shadow 地址回复飞书 | `personal-assistant.ts:114`；`store.ts:101`；`external.ts:146` | `personal-assistant.test.ts:64` 验证归一化出口；`external.test.ts:149` 断言实际 provider message_id | covered；真实平台读取 pending |
| 主人回复/定时提醒免对外披露 review | `personal-actions.ts:101`；`personal-assistant.ts:170`；`external.ts:197` | `personal-disclosure.test.ts:60`；`personal-assistant.test.ts:77` 在 reviewer unavailable 下仍 dispatch；普通调度未变 | covered；真实到时提醒 pending |
| 非主人及群保留已有输入与披露边界 | `personal-agent.ts:101`；`personal-actions.ts:16`、`:102`；`personal-assistant.ts:50`、`:173` | `personal-sources.test.ts:45`；`personal-disclosure.test.ts:39`、`:60`；`personal-assistant.test.ts:54` | covered；群继续 fail-closed，不增加当前不支持的群受众证明 |
| 旧输出投影失败不阻塞新输入、重放去重 | `external.ts:94`、`:245` | `external.test.ts:149` 注入旧 streaming projection error，后续新输入 mirror；重复接收及 recover 后镜像仍单次 | covered |
| 中央不可达时 PA 持久等待恢复；普通 Agent 保留离线执行 | `external.ts:71`、`:92`、`:102` | reviewer 独立 source-level seam 检查 PASS（见 Evidence E4）；既有 `external.test.ts:33` 保留普通 Agent 离线收发及恢复幂等 | covered |
| 未知平台结果不自动重发，平台回执才 confirmed | `external.ts:188`；`external-store.ts:22` | `external.test.ts:122`；`personal-disclosure.test.ts:39`；owner_private 复用同一 dispatch | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 服务端统一主人判定，普通源访问/工具权限继续有效 | 是 | `personal-agent.ts:80`、`:95`、`:101`；`personal-actions.ts:89` 先 sourceAllowed 再豁免 |
| PA 飞书仅持久 observation 接入，输出失败隔离 | 是 | `external.ts:91`、`:245`；`global-agent.ts:151` |
| 可信主人目标免 review，实际 chatId 由本地存储解析 | 是 | `personal-actions.ts:101`；`personal-assistant.ts:170`；`external.ts:194` |
| 在 PA 分派前归一化 shadow alias | 是 | `personal-assistant.ts:114`；`store.ts:101` |
| 角色说明按原来源回复；既有 custom_prompt 不覆盖 | 是 | `personal-agent-defaults.ts:4`；`global-agent.ts:113`；默认加载机制未改 |
| 复用 DSH/Global/Inbox/schedule，不另建执行环或调度器 | 是 | 完整 diff 未增加 DSH import 或第二套运行时；`SPEC.md:35` 的包边界保持 |

### Prototype / Reference Contract

N/A。

## Evidence

- **E1 — 定向回归（复用）**：caller 提供冻结实现的 `/tmp/bugfix-621-focused.log`，10:00:38，7 files / 100 tests passed。本 reviewer 已读日志并核对相关测试源。复跑入口：`pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts apps/im-server/tests/personal-sources.test.ts apps/im-server/tests/personal-disclosure.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/personal-assistant/tests/external.test.ts packages/personal-assistant/tests/global-agent.test.ts packages/personal-assistant/tests/inbox.test.ts`。修前 4 个新回归失败/修后通过的证据见 `M1-fix/evidence/validation.md:13` 与 `/tmp/bugfix-621-red.log`。
- **E2 — 类型/构建（复用）**：`pnpm typecheck` 全 workspace 完成，`/tmp/bugfix-621-typecheck.log`；`pnpm build` 完成，`/tmp/bugfix-621-build-fixed.log`。构建产物的 installer candidate 字符串仍显示文档基线 `732ba8a2c`，不能用该字符串证明安装/部署版本；本报告固定实现身份来自 HEAD `fad8b8355`，构建本身不证明真实旅程。
- **E3 — 独立 code review**：完整 range 的调用链、测试和状态机核对见 `code-review.md`，findings `[]`。
- **E4 — 离线恢复补充（本 reviewer 独立执行，10:04–10:05）**：`node --import tsx --input-type=module` 导入当前 `ExternalChannels` / `NodeStore`，构造内存持久 store、personalAgent=true、relay.ready=false。向 receive 投入一条 FeishuMessage，断言抛出 `Personal source authority requires the center` 且 0 mirror / 0 direct receive；切 ready=true，recover 两次并重放该消息，断言 mirror=1、direct receive=0。结果 `PASS: offline PA input retained; central recovery mirrors once; no direct execution ingress`。此为最低 seam 的直接检查，未测试真实平台网络或磁盘进程重启。
- **E5 — 真实平台/CI（pending）**：主 Agent 正在执行；截至本报告写入，没有据此宣称平台回执、平台读取、调度到时或 Web 旅程通过。健康检查、SDK online 和上述 mocks 不能替代这些退出证据。

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — M1 required evidence pending（完成度缺口，非已确认代码缺陷）**。契约：`design.md:68`，`incident.md:36`、`:44`。目前缺少可复查的真实飞书主人来信→实际回复、同一主会话一次性提醒到时→原单聊回执与消息读取、Web 主人私聊，以及选定 CI 完成结果。建议 caller 完成正在执行的既定旅程，将版本、唯一标记、源/回执/调度 ID 与脱敏平台读取结果写入 `M1-fix/evidence/validation.md` 或 acceptance 报告，再复核该证据并关闭 C1；不得只依据服务在线或本报告的 seam 测试关闭。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

无。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/global-agent.md:5` 跨渠道主人交办/原始授权 | `personal-agent.ts:101`、`:182`、`:188` | `personal-sources.test.ts:45` | aligned |
| `specs/gateway/global-agent.md:13` 单一接入与来源保留 | `external.ts:91`；`global-agent.ts:151`；`inbox.ts:116` | `external.test.ts:149`；`global-agent.test.ts:309` | aligned |
| `specs/gateway/external-channels.md:5` 主人私聊身份、原渠道回复和提醒权限 | `personal-assistant.ts:114`、`:170`；`personal-actions.ts:101` | `personal-assistant.test.ts:64`、`:77`；`personal-disclosure.test.ts:60` | aligned；真实旅程证据仍 pending |
| `specs/gateway/external-channels.md:13` 失败输出与新输入隔离 | `external.ts:94`、`:245` | `external.test.ts:149` | aligned |
| `specs/gateway/external-channels.md:20` MODIFIED 离线契约，包括保留的两项普通 Agent Scenario 和 PA 恢复 Scenario | `external.ts:91`、`:102` | `external.test.ts:33`；E4；`global-agent.test.ts:258` | aligned |

### Uncovered Observable Behavior

None。diff 中新增的 channel 暴露、原 sender/timezone、shadow 输出镜像许可和 thinking receipt 清理均是以上来源保留/原渠道交付的组成部分；默认角色文案对应同一交办权限，未发现 delta 遗漏的新对外行为。

Outcome: **aligned**。该结论确认 corrected delta 与实现/测试一致，不将 pending 的 M1 真实平台退出证据视为已完成。

## Round 2 — C1 targeted closure

### Metadata and verdict

- verification_mode: `targeted-closure`；focus_issues: `[C1]`；requires_full_verification: `false`。
- executed_base: `732ba8a2c06c072f8a5b8ad74ad08d43d6cb34a9`；validated_at: `fad8b8355716a73165bf0d688644dfbf0cc84dde`，不因报告提交改变实现快照。
- 报告读取时 HEAD `a1415206ed18493df775ab3b4410617894aaf425`，相对 validated_at 仅新增 `regression.md`。源码和测试无变化，保留 Round 1 的 full 实现核对及唯一 Corrected Delta Reconciliation，outcome 仍为 **aligned**。
- **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION。C1 closed。M1 退出证据齐备，Ready for PR。**
- 本轮只核对新增真实旅程与本地 CI 证据，不重跑全量测试、不改代码/设计、不操作或停止测试/生产服务。

### C1 closure evidence

| 既定退出标准 | 新证据与本 reviewer 核对 | 结果 |
|---|---|---|
| 首来信自动绑定，真实飞书回复 | `M1-fix/evidence/validation.md` 记载新 channel 初始 runtime 为空，10:04 首个实际 sender 持久绑定；读取 `output/pa621-fixed/snapshot.json`，channel 的 owner_open_id 与 Inbox 原 sender 一致，seq 1 为 owner_instruction、channel=feishu、source event processed。读取 user API 平台消息列表，原来信 `om_x100b62588cfe34b0cd0f935e822bad1` 后确有实际回复 `om_x100b62588d28d880ce8a5f7c4d99e67`；该回复也在 ExternalStore confirmed。 | closed |
| 主人提醒原飞书单聊实际收件 | 直接读取 `/tmp/pa621-review-evidence/feishu-final.json`、`outputs-final.json`、`schedules-final.json`；两条提醒分别 `om_x100b6258819514b0cd3a54305c30390` / `om_x100b62589bc854bcce5c0699ce4956e`，精确正文 `PA621_REMINDER_1005` / `PA621_REVIEW_REMINDER_1006`，平台各出现一次且均 confirmed。两个 schedule 在同一 session 各一次 delivered，最终 inactive。 | closed |
| Web 主人私聊真实回复 | 独立产品 reviewer 的 `regression.md` 记录经客户端同一 REST 入口发送及回读；本 reviewer 直接读取 `web-latest.json`，消息 `9f5dcfaa0537456e86999f8eb8a4ff0c` 正文精确为 `PA621_WEB_REVIEW_1006`，完整飞书列表无该正文，原渠道区分成立。 | closed |
| 同一个 PA 与单次接入 | 直接读取 `persistence.json`：两个飞书中央 message ID 与 Web message ID 各一条 Inbox、均 consumed；三次 ingestion 同属 session `35d34236-f4c7-4817-a8cd-08378e63f25a`。该 session 也是两个 schedule 的 sessionId；后者最终记录均只有一次 deliveryHistory。 | closed |
| 独立产品旅程裁决 | 读取已提交的 `regression.md`，独立 reviewer 真实发出第二次来信/提醒并回读平台、Web、持久状态，结论 pass / 0 issues。异常及非主人/群边界按设计复用 worker 自动化，没有将它们伪称为真实平台故障注入。 | closed |
| 选定本地 CI | 读取全量后端原始日志：453 passed，唯一 workspace-tools test 90 秒超时；同一冻结版本、无源码或测试改动，单项复跑 1 passed / 36.97 秒。合并证据覆盖全部 454 项，保留首轮失败记录，不将其叙述为首跑全绿；负载原因仅为推断。另读取前端 936 passed、pytest 62 passed / 31 deselected、最终 typecheck、docs-check 与 critical audit 结果；build、前端 build、ruff 成功记录见 validation.md。 | closed |

本 reviewer 用一次只读 Python 断言交叉核对平台精确提醒内容/各一次出现、confirmed 回执、Web 实际消息及飞书未串发、三条 input 唯一性/相同 session、两个 schedule 最终 inactive/各一次 delivery，结果 PASS。直接证据目录 `/tmp/pa621-review-evidence/` 与 caller 的 `output/pa621-fixed/snapshot.json` 已读取；不提交原始平台列表、数据库或凭据。

### Scope and retained conclusions

- C1 原因是当时实测尚未完成，现由完整证据关闭；没有借修订设计或降低退出标准消除问题。
- Round 1 的实现与回归结论全部 retained；code review findings 仍为 `[]`；corrected-delta 仍为 `aligned`，无遗漏行为或新实现偏离。
- 当前阶段核对本地 CI 等价覆盖；远端 CI 在 PR 创建后运行，不作为本阶段归档前置。服务在线、生产日常调度恢复、生产部署和 PR 合并均不在本轮通过声明中。

# Verification Report: feat-616-personal-agent

> Validation snapshot: `e7088f9d5 → cf1befff963e6d251e332c513e8ca6adf1d86619`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 的主要路径已有实现；恢复契约缺实现，最终真实验收证据未闭合 |
| Correctness | 核心 4 suites / 32 tests 独立通过；3 个具体问题独立复现 |
| Coherence | 官方 DSH / 包边界 / 统一 PA 与受控出口基本遵守；来源入站和分区恢复有实质偏离 |

**Fix before PR：3 CRITICAL / 1 WARNING / 0 SUGGESTION。** 其中第三项 CRITICAL 是尚未完成的 M1 退出证据，不将作者叙述当作完成证明。

- unit_id: `feat-616-personal-agent`
- review_round: `1`
- verification_mode: `full`
- verdict: `fail`
- executed_base: `e7088f9d5`
- validated_at: `cf1befff963e6d251e332c513e8ca6adf1d86619`
- requires_full_verification: `false`（本报告本身已按 full 范围核对；修复后的范围由 caller 按实际 delta 判断）
- reviewer: 独立 reviewer `/root/pa_static_review`，未参与实现。
- 现场：`/Users/czj/.codex/worktrees/feat-616-personal-agent/nano-multiagent`，开始/完成代码阅读时 HEAD 均为候选 SHA、源码无 dirty；未切分支、改源码/测试/设计、启动服务、部署或推送。仅新增本报告和 `code-review.json`；临时探针在 `/tmp/pa-static-review-616/`，没有服务进程。
- 权威：spec 文末目标推进版、统一 PA、新消息/任意历史查询和极简原则；design 当前正文与设计审查 R16 准入。早期逐动作审批、多独立业务 session 与研究快照不作为当前要求。

## Completeness

- Milestone：单 M1，不能标 complete。身份、历史、观察、任务协助、审查/真实回执、受控宿主与 Web 路径已存在；同 owner 恢复缺实现；最终真实产品验收和 W1–W7 部分证据仍待交接。
- Spec：当前 15 项目标版 Requirement 均完成实现映射；下表明确区分已有代码、局部测试与未证明的产品结果，不以测试数量代替完整覆盖。
- Prototype / Reference：design:269–280 的 must-match 表仍适用。静态原型 R15 的既有证明只证明原型；本次不进行主观 UI 验收。真实产品 reviewer 正在独立执行，固定候选尚无可复查的最终真实产品对照报告。

## Evidence

### 本轮独立执行

1. `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts apps/node/tests/runtime-partitions.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/dsh-integration/tests/personal-security.test.ts`
   - 候选 `cf1befff9`，2026-10-19 14:18 本地运行；**4 files / 32 tests passed**。
   - 包含实际锁定 DSH 子进程的受控工具/插件装配、skip 下隐私拒绝、真实本地 HTTP 搜索及 redirect 拒绝、退休会话冷恢复等测试；该测试的 LLM fixture 不是真实 DeepSeek 判定。
2. 临时探针 `pnpm exec tsx /tmp/pa-static-review-616/probe.mts`：内存 IM DB + 真实 Messaging/PersonalAgents/Gateway/Identity/NodeStore/PersonalAssistant，全部合成身份/正文。
   - 真实 `Identity.deviceRecoverDevice`：节点 epoch 变为 2；合法新 principal 的 PA authority 返回 `personal_binding_not_authorized`。
   - 排除来源并屏蔽 sender 后：`sourceAllowed=false`、direct relay queue=1、`admit=true`、NodeStore 内有排除正文。
3. `pnpm exec tsx /tmp/pa-static-review-616/partition-probe.mts`：真实 GlobalAgent 与 NodeStore，模拟独立 PA runtime offline 和一条待处理 PA 来源事件。
   - `recover()` 返回 `personal host offline`；健康 ordinary Agent 的 `session.ensure` 调用为 **0**。没有启动产品服务或模型。

### 复用证据及限制

实施记录 `M1-personal-agent/implementation.md:13–40` 明确区分已运行与待验：较早后端 380 tests、前端 893 tests、Python 非 E2E 62 tests、docs-check 通过；这些全量结果发生在最终 completion/incident 修订之前。本轮派发另提供候选 build/typecheck、受影响后端 27 tests、前端最后 targeted 39 tests 已通过；复用作局部回归背景，不写成最终全 CI。

实施记录描述真实 DeepSeek 隔离旅程：创建、2024 历史查询且不改 unread、向两真人 DM 协调且 DTO 保留 PA actor、合成私密 canary 未外发、原生 followup 和对方回复观察。它同时明确：最终固定 peer notice 仍须 live 重验，迁移/epoch、全部撤权源和 per-PA availability 尚未验证。本轮未读取凭据或将私有原始日志写入报告；真实接收端/三宽度对照由产品 reviewer 补直接证据。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 固定 PA：创建、命名、重复提交、唯一私聊 | `apps/im-server/src/personal-agent.ts:266–316`；Web onboarding / dialog | IM 创建幂等、owner-only DM 测试；真实创建记录 | 已有实现；迁移/epoch 见 C2 |
| 现有 IM 增量融入：桌面、手机、日常辅助 | `chat-workspace-page.tsx:1161–1270`；`personal-agent-collaboration.tsx:43–54` | 前端 PA / source navigation 测试；最终三宽度产品对照待提供 | 代码具备；C3 evidence pending |
| 接住目标：原 task、观察建议不自动立项、多目标与更正 | `personal-agent.ts:127–198`；`personal-assistant.ts:38–55` | 私人任务更新/真实 done + result 测试；未采纳外部输入不创建 scope 测试 | 局部 covered；两目标真实旅程待补 |
| 原工具审批与内部协作不增加 PA 人工审批 | `personal-security.ts:87–111`；`agent-config.ts:78–95`；`global-mode.ts:35–44` | native DSH skip/能力限制测试；`next()` 原 deny 仍返回 | AND 关口存在；ask/deny 对照、内部成果真实质量待验 |
| 只问必要业务决定/新授权 | `personal-agent.ts:199–210,328–340`；`personal-security.ts:55` | 独立 reviewer schema、needs_owner 不 commit；decision UI 测试 | 代码具备；决策后继续与打断次数待验 |
| 多来源归同目标、识别本人已处理 | `personal-actions.ts:74–76,110–117`；`global-agent.ts:126–177` | 本人先回复拒绝旧 send、当前受众测试 | 部分 covered；来源入站绕过见 C1 |
| 离开仍有下一步：真实安排/等待/完成分开 | `personal-assistant.ts:215–233`；`personal-agent.ts:173–198` | schedule receipt 测试、私有 task done/result 测试；真实 followup 记录 | 局部 covered；busy/restart/双目标待补 |
| 稍后、暂停观察、暂缓目标、排除/清理 | `personal-agent.ts:41–55,150–172,321–358`；`global-agent.ts:147–170` | history 在暂停时可用、排除 query、owner pause/draft-only 和 context retire 测试 | 排除/屏蔽直接入站错误 C1；真实恢复和影响范围待验 |
| 可疑套取双向告知、重复合并、误会/屏蔽 | `personal-agent.ts:215–233,342–351`；`personal-actions.ts:39–41,94,158` | incident 幂等、fixed security notice scope 测试；最后真实 peer notice 重验未完成 | 局部 covered；C1/C3 |
| 本人隐私与外部身份：假授权、撤权、unknown | `personal-agent.ts:23–39,104–120`；`personal-actions.ts:47–76,124–180` | owner source 证据、source/current ACL、unknown 外发、受众变更 | 主要关口 covered；恢复 C2、入站 C1 |
| 私人背景与外部话语保留来源，摘要不升级 owner | `knowledge/runtime.ts:102–112`；`personal-state.ts:16–31`；`personal-security.ts:55` | derived memory 标记与清理 native 测试；host evidence 包含上下文 | 代码保守失效；真实多轮派生/子执行攻击待补 |
| 自动外发检查：改写、故障、多 sink、变化/并行 | `personal-actions.ts:78–180`；`personal-assistant.ts:87–202`；`web.ts:20–57` | IM/task/附件 bytes/Feishu permit/network/redirect、并行 revision 阻断；无原文流式泄露路径 | 主要 sink 有接入；真实安全改写/所有接收端证据待补 |
| 历史任意时期、人物/时间/关键词/分页/出处 | `personal-agent.ts:57–83`；`work.ts:495–679` | 2001 历史查询测试与真实 2024 查询记录；current ACL 每次重查 | 无固定窗口；完整分页/跨页撤权与 UI 往返待补 |
| 草稿/代发/不回复与真实作者、本人 unread | `personal-actions.ts:154–159`；`messaging.ts:306–309`；`message-pane.tsx` | actor/authorized_by 实时 event、原 DM 两人成员不变、history 不改 unread | covered 的具体字段；双方真实 UI 仍待产品证据 |
| 极简体验：自然语言交办/历史/控制，故障不转人工隐私批准 | `personal-security.ts:55,133–164`；`personal-agent-dialog.tsx` | 没有固定历史窗口/逐消息三选一；unavailable 不 commit | 代码方向一致；真实打断/自然语言歧义属 reviewer 判定 |
| 原有 Agent/Channels/iOS API 保持 | 普通 runtime partition、既有 DTO 增量字段与 original tool policy | 普通测试背景；未改 iOS 源码；不能以没有 iOS diff 等同服务端兼容验收 | 普通恢复回归 W1；W7 API evidence pending |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 唯一 PA、现有 task 唯一业务真相 | 基本是 | `personal_agent_bindings` owner/agent 唯一；`pa_assistance` 拼真实 task；私有 completion 更新原 task |
| 同一 PA 理解多源，无强制 external fresh session | 是 | `GlobalAgent.binding/main/receive`；来源内容进入同一 global Inbox |
| 原工具权限与隐私审查 AND | 是 | `PersonalSecurity` 先保留 `next()` deny，sink 另走 frozen proposal；native skip 测试有效 |
| 各实际 sink 冻结内容、重新核权限、真实回执 | 基本是 | IM/共享任务/附件/network/Channels 有具体 adapter；普通 agent.message/stream 外发被拒；unknown 不自动重发 |
| 官方 DSH 与包边界 | 是 | node 通过 client 管独立 supervisor；PA/IM 无新增 DSH import，未新增 HTTP kernel / 第二 loop |
| PA 宿主隔离、插件 mount 前约束 | 是 | `runtime-partitions.ts`、node 分区 home/profile、`assertPersonalConfiguration`；native rejected plugin 未 import 测试 |
| 来源排除/屏蔽在所有入口生效 | 否 | direct relay/admit 不用当前来源/contact policy，C1 |
| 同 owner 恢复、旧 epoch 撤销、新分区准备 | 否 | 无 transition；epoch 改变后旧 binding 不能恢复，C2 |
| 一个分区失败不阻断其他分区 | 否 | GlobalAgent recover 共享失败链，W1 |
| 撤源换新 context、记忆保守失效 | 有实现，仍需旅程证据 | `pa.invalidate` 退休主/子 context、清 memory、documents revoked；恢复中删除全部 schedules 后需证明有效其他目标重新安排及真实状态 |
| per-PA availability 如实呈现 | 未证明且有明确代码缺口 | `main.ts:110–112` PA unavailable 没有 IM 状态报告；`personal-agent.ts:18–21` 只看 node online。列入 C3 的局部故障必验，不能用 node online 当 PA ready |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 创建/固定名字/首次目标一次提交 | R1/W1 | onboarding / personal-agent routes / fixed sidebar | 原型 R15 + 实施真实创建记录；最终 1440/768/390 对照待 reviewer | pending |
| 同目标进展/成果/多目标独立 | R2/W2 | assistance/task projection、collaboration | 私有任务完成测试；两个目标完整真实旅程待补 | pending |
| 搜索/制作/内部成果无重复人工批准 | R3/W3 | original approval AND、受控子工具 | native 搜索等 fixture；真实普通/PA 同策略、成果待补 | pending |
| 决策/授权协调/unknown | R4/W4 | scope/decision/frozen operations | IM delegated DTO 与 unknown 测试；完整对照待补 | pending |
| 等待对象/next check/busy/restart | R5/W5 | persistent schedule refs | schedule 回执/真实一次跟进；重启与延后待补 | pending |
| 暂停/排除/恢复、incident、历史代发 | R6/W6 | source policy/context retirement / fixed delegated label | 原型及局部测试；C1/C2、双方和历史真实往返待补 | blocked |
| 既有顶栏/262px列表/768断点与手机底栏 | R1/R2/W1/W2 | 既有 shell/styles 未改，PA 加在聊天组件 | 原型保真通过不代替产品对照；产品 reviewer 在做 | pending |

## Issues

### CRITICAL（提 PR 前必须修）

**C1 — 排除来源和屏蔽身份不能约束 direct relay admission。**

- 契约：spec:261–264、284–286、352–354；IM delta「联系屏蔽」；design:207–211，要求排除禁止自动/工具读取、当前屏蔽阻断新请求。
- 实际：`apps/im-server/src/gateway.ts:908–945` 只检查普通可联系资格并排 relay；`packages/personal-assistant/src/personal-assistant.ts:57–70` 对来源仅模型风险审核，然后存正文。`pa.observations.read` 的排除/block 过滤并不覆盖该分支。
- 独立复现：来源已 excluded、sender 已 blocked、`sourceAllowed=false`，真实 relay 仍排队、admit=true、NodeStore 持久保存排除正文。模型尚未决定最终发送之前就已破坏禁止摄取边界。
- 建议：从 IM 当前 binding/policy/actor 做可恢复的入站核验，覆盖 direct relay、排队/重放及最终 Inbox 消费；新增同一行为 seam 的回归。不要只改提示词，也不要误挡 canonical owner 控制。确认屏蔽前的 queued 输入和解禁后的不重放契约。

**C2 — 同 owner 凭据恢复会使 PA 永久失权；新节点恢复同一 PA 也未实现。**

- 契约：design:213、251；IM agents-nodes delta 末条要求同 owner 重连、新节点 rebind，epoch 递增拒绝旧节点且保留 canonical PA。
- 实际：`Identity.deviceRecoverDevice:914–936` 增 node epoch；新建的 `PersonalAgents.authority:24–29` 同时要求旧 PA binding epoch 相等。所有 PA 来源/动作 API 都失权。`POST .../personal-agent:271–285` 对已有 binding 直接返回，没更新 node/epoch；node `configuration.ts:101` / partitions.assign 也禁止直接改 immutable identity。
- 独立复现：真实恢复方法成功后，node epoch=2、PA binding 仍=1，新合法 principal 调 `authority` 返回 `personal_binding_not_authorized`。不是假想攻击边界。
- 建议：实现认证同 owner 的显式恢复 transition：停止旧 admission、核对未知 operation、退休旧 epoch/进程、新节点准备专属宿主、更新受信配置与 residency，保留 PA/DM/goal 身份；失败可恢复。保留旧 epoch 拒绝，不能简单去掉 equality。

**C3 — M1 的最终退出证据仍不完整，不能标 full verification pass。**

- 契约：design:306 的 W1–W7 与 R1–R6；设计审查 R16 明确先实施不等于省略最终真实验收。
- 实际：实施记录明确最终独立产品验收、最后 peer notice live rerun、full final CI 等 pending。固定候选未有双目标/忙碌重启/全撤源/普通与 PA ask/deny/内部成果、每 PA 独立故障可用性及最终三宽度 must-match 对照的完整直接证据。现有单元/native fixture覆盖真实 seam，不能推导未发生的旅程。
- 建议：复用本轮32 tests及已有效的版本证据，完成 root 正在进行的最终产品验收、必要负向/恢复场景和当前 CI；报告准确 tested SHA、命令/结果/接收端及限制。尤其 PA 进程 offline 而 node 在线时 UI 不能仍标 active（`main.ts:110–112` / `personal-agent.ts:18–21`），需要真实核验并修复确认的偏离。不是要求重跑无变化的全部原型研究。

### WARNING（提 PR 前必须修）

**W1 — 单个 PA 恢复异常阻断健康普通 global Agent 的恢复。**

- 契约：design:166–169 和 gateway PA delta「PA 运行不可用」要求局部故障不串区，其余消费者/Agent继续。
- 实际：`packages/personal-assistant/src/global-agent.ts:119–123` 在所有 global Agent 恢复前无隔离地 await 全部 PA observations；有一条待处理 PA source event 时，offline PA 的 `main` 抛错，ordinary 未进入恢复循环。也不能把另一 PA 的失败传播为整批已完成。
- 独立复现：真实 GlobalAgent + 一健康 ordinary / 一 offline PA，PA source event pending；`recover` 抛 `personal host offline`，ordinary `session.ensure` 调用=0。
- 建议：按 Agent/partition 处理恢复失败并继续健康分区；保留失败事件 pending，向对应 PA 报告，恢复时重试同事件。补最低层部分失败回归，不新增第二套 loop。

### SUGGESTION（可以修）

无。未将命名、代码风格、未知侧信道或研究中的额外防护作为 findings。

## Handoff

`code-review.json` 给出3项 CONFIRMED full findings（C1、C2、W1）；本报告另记录待完成退出证据 C3。共享现场由 caller 提交报告，report_commit 尚未产生；未推送。修复后优先核这些具体失败条件及受影响范围，产品 reviewer 继续独立验收，不以本报告代替真实 UI/模型体验判断。

## Round 2 — Targeted Closure and Fix Delta

### Metadata and verdict

- review_round: `2`
- verification_mode: `targeted-closure`，同时核修复引入的 source/Channels、restore、设备 epoch、本机分区、per-PA status 与 timer 恢复 delta。
- executed_base / prior head: `cf1befff963e6d251e332c513e8ca6adf1d86619`
- validated_at: `a41c22630578d28f76dcb5bee393cfdc9a7bab29`
- fix_delta_range: `cf1befff9..a41c22630`
- focus_issues: Round 1 `C1 / C2 / W1`；Round 1 其他未失效判断保留。
- verdict: **fail — 2 CRITICAL / 0 WARNING / 0 SUGGESTION**，均为新增/受影响 Channels 边界的直接复现问题。
- requires_full_verification: `false`。新增问题局限在已派发的跨包修复路径，无需重开未变化部分的全量审查。
- Code findings: `code-review-r2.json`；Round 1 原 JSON 完整保留，不把原问题自动删除。
- C3 的最终产品证据由 root / 独立产品 reviewer 继续闭合，本轮未重复将“产品报告未出”列为代码 finding，也不宣称整体交付已通过。

### Historical issue closure

| 原问题 | 本轮证据 | 状态 |
|---|---|---|
| C1：直接 relay / queued input 绕过来源排除和屏蔽 | Gateway.relayMessage 先 `messageAllowed`；PersonalAssistant.admit 先请求 IM `pa.source.admit`、false 时不 review/store；新增真实 IM policy 测试和 PA revoked input 测试通过 | **closed**，Web/已持久来源的旧失败条件已关闭；Channels 实际接入另有 R2-C1 |
| C2：device epoch 恢复后 PA 403，且无同 owner restore | Identity.rotatePersonalEpoch 随设备事务旋转 binding/失效 permits，snapshot 包含 PA；真实 `deviceRecoverDevice` 后新 epoch 的 authority 成功。bindDevice 独立实际执行保存 marker epoch=2、旧分区目录消失、新分区保留 durable marker；restore HTTP 测试核同 PA/DM、新 owner node、旧 principal 失权与幂等 | **closed**，不通过移除旧 epoch 检查关闭问题 |
| W1：PA offline source recovery 阻断 ordinary | GlobalAgent 对 observations 和每 Agent 的恢复分别 catch；原独立探针重跑时 ordinary `session.ensure=1`、PA 错误留给 onError；新回归测试通过 | **closed** |

### Delta implementation and evidence

| 受影响边界 | 检查结果 |
|---|---|
| `pa.source.admit` 与当前来源/contact policy | IM 从认证 binding+真实 message 解析，不接收模型 owner；调用在独立输入审核前。Web 旧绕过关闭；Channels mapping 依赖的真实 mirror 写入不兼容，见 R2-C1 |
| 外部 actor / incident / block | 外部 source ID 不再被当成 shadow owner；incident actor/展示改用来源身份。该新身份尚未贯通 egress block，见 R2-C2 |
| 同 owner restore / ConfigOperations restore | 先 server fence 旧 node/binding、pending+stale、失效未发 permit，再由新 node `agent.create` 真回执提交 active；保留 PA/DM/goal，workspace 取新端，不复制旧本地历史。新测试覆盖错误 owner、旧 principal 拒绝和同目标重试 |
| 同设备 epoch / snapshot / local partition | 已独立执行真实 Identity 和 bindDevice（合成 HTTP result），新 config personal epoch 正确且 old home 分区重命名保留原资料；旧 node token 拒绝沿原测试保留。不是生产/真实新节点迁移验收 |
| per-PA status | node onReady/onUnavailable/relay ready 都报告分区 status；IM 按 binding epoch 使用记录；server 测试证明 node 仍在线时 PA unavailable 并可恢复。没有用 ordinary node health 代替 PA 状态 |
| 撤源后有效 timer | GlobalAgent 在新 binding ensure 后调用 restoreFollowups；helper 只恢复非暂停/非完成且 scope 存在、未撤销、所有目标来源仍允许的 assistance；不可用目标清除旧 next_check/schedule。具体真实调度恢复旅程仍由产品验收补证；本轮未发现新增确定性 timer 缺陷 |
| corrected delta / canonical specs | 本 fix delta 未修改契约正文，仍实施已批准 design；**no spec delta**。尚未归并 canonical，未以改 spec 适配问题实现 |

### Independent execution

候选 HEAD 在本轮代码阅读与测试时均为 `a41c22630`、源码 clean；仅写报告，没有修改实现或测试。

1. `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts apps/im-server/tests/identity.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/personal-assistant/tests/global-agent.test.ts packages/personal-assistant/tests/external.test.ts apps/node/tests/device-binding.test.ts`
   - 2026-10-19 14:33，**6 files / 74 tests passed**。复用 caller 所报较早全量 386 tests / build/typecheck 作为背景，不冒称本轮重跑全量。
2. `/tmp/pa-static-review-616/round2-probe.mts`：真实 Identity 恢复后 epoch=2，新 PA authority 成功；真实 ExternalChannels + Messaging.sendMessage 对正常外部 DM 的 mandatory mirror 失败，异常 `personal_reviewed_delivery_required`，receive=0。
3. 原 `/tmp/pa-static-review-616/partition-probe.mts` 重跑：ordinary ensure 从0变为1，旧 W1 关闭。
4. `/tmp/pa-static-review-616/local-epoch-probe.mts`：真实 bindDevice + 临时本地 HTTP fixture，动作 prove/recover-device/prepare/recover，保存 epoch=2；新分区 durable marker 内容与旧分区一致，旧目录不存在。临时 HTTP server 和目录在 finally 关闭/清除；没有产品服务或模型调用。
5. `/tmp/pa-static-review-616/round2-block-egress.mts`：真实 PersonalActions，既有有效 scope 下先插入 sourceActor 对应的 external block，再准备、审核、提交新 Feishu payload，实际结果仍为 `sending`。

### CRITICAL

**R2-C1 — Channels 输入被新增 mandatory flush 阻断，`pa.source.admit` 到不了真实接入。**

- 契约：保留既有 Channels 行为、真实外部身份与当前来源核验；设计允许可受控外部 DM，而不是全部阻止正常联络。
- 位置：`packages/personal-assistant/src/external.ts:91–95,252–254`；`apps/im-server/src/messaging.ts:90,479–483`。
- 证据：flush 对 incoming mirror 调普通消息写 API，目标是非 canonical shadow、sender_type=user；现 PA access(write) 拒绝非 owner DM，下一层还拒绝 PA 的 user sender。因此新增的同步前置让正常 PA Feishu 输入在 receive 前必然失败。当前 external test mock 了整个 `im` 函数，未覆盖此跨包契约。
- 独立复现：真实两个类组合，正常 DM 返回 `personal_reviewed_delivery_required`，接收调用0；无网络平台依赖。
- 建议：为可信 incoming mirror 设窄入口，绑定当前 node/PA/channel/source、真实 external actor、幂等原消息及无 relay 副作用；保留普通 PA 外发与 owner 冒充拒绝。补真实 IM handler 与 Channels 的边界回归，不能仅继续 mock IM 写成功。

**R2-C2 — External block 身份未参与实际 transport commit，已屏蔽对象仍能收到后续目标消息。**

- 契约：IM PA delta「联系屏蔽」要求阻断新请求/投递及相应待办许可；design 同会话安全通知也不得绕屏蔽。
- 位置：`apps/im-server/src/personal-agent.ts:42–45` 引入 `external:<shadow>:<sender>` 身份；`personal-actions.ts:59–63` 仍只对 shadow participants 查 block。
- 证据：shadow participants 是 owner 与 PA，永远不等于新 external actor；policy revision 能淘汰旧 proposal，但新 proposal 捕获新 revision 后仍通过，所以已有目标的定时/主动协调可以继续外发到被屏蔽对象。
- 独立复现：使用真实冻结动作/审查/commit，实现原样返回 `sending`。没有假设模型主动绕过：审核包也未包含该 block 事实。
- 建议：将经过认证的 transport 接收者映射到同一 canonical external actor，在 prepare 与 commit 核当前 block/许可，覆盖 incident 和既有目标继续发送；不能把 owner 的 shadow sender 当外部收件人。

### Handoff

Round 1 的3项代码 finding 已有逐项 closure 证据；本轮2项新增 CONFIRMED 问题不能用旧 finding 关闭结论覆盖。报告只对应固定 `a41c22630`，后续 root 改动不在本轮结果内。未提交/推送，由 caller 归入下一候选。

## Round 3 — Targeted Closure and Corrected Delta Check

### Metadata and verdict

- review_round: `3`
- verification_mode: `targeted-closure` + 本批 implementation delta 核对；未重开未失效的 full 结论。
- executed_base / prior head: `a41c22630578d28f76dcb5bee393cfdc9a7bab29`
- validated_at: `439a75144525c6d4740bbdc665e792f57cf71d51`
- fix_delta_range: `a41c22630..439a75144`
- focus_issues: `R2-C1 / R2-C2`，以及派发明确纳入的多 scopes、独立任务、通知恢复/事件隔离、目标索引/历史定位和草稿/选择工具指导。
- verdict: **Fix before PR — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**。唯一新增 confirmed 问题是固定安全通知在临时审核故障后的恢复仍会被过期 proposal 阻断；不是重提旧正文冲突，也不是以未出的产品报告凑 finding。
- requires_full_verification: `false`
- Code findings: `code-review-r3.json`。Round 1/2 原报告与各 closure 记录完整保留。
- 实施链路已静态/工程验证的部分与真实产品复验保持区分：`acceptance.md` 当前 Round 1 仍为旧运行版本的失败记录，尚不能据本轮代码通过项自动清除。root 已安排最终独立产品复验，本轮未重启/占用共享服务。

### Historical findings closure

| 原 finding | 本轮实际证据 | 状态 |
|---|---|---|
| R2-C1：mandatory Channels mirror 被 PA 普通消息写权限拒绝 | ExternalChannels 改走专用 `external-incoming`，实际 Fastify conversation handlers 校 node/binding/channel/source，并保留 `sender_source_id`；正常 DM 端到端 admitted=1；普通 PA outward write 拒绝仍保留 | **closed** |
| R2-C2：external block 不进入 transport commit | `PersonalActions.transport` 从已验证 source_id 得到与 sourceActor 相同的 actor；prepare 与 validate/commit 都调用它；同一实际来源在屏蔽后新 prepare 与已审旧 commit 均报 `contact_blocked` | **closed** |
| Round 1 C1/C2/W1 | 本批未撤销来源核验、epoch rotation/restore 和 per-Agent recovery；正常 Channels source 还经过 `pa.source.admit`；旧证据仍适用 | **closed，retained** |

### Independent execution and reused evidence

1. `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/personal-assistant/tests/global-agent.test.ts packages/personal-assistant/tests/external.test.ts`
   - 固定 `439a75144`，2026-10-19 14:51：**4 files / 69 tests passed**。
   - 覆盖真实 incoming handler 的 inward/outward 分离、block 前已审/之后新 prepare、单 owner 消息多独立 task、单事件失败不挡其他事件和固定通知 content key。
2. `/tmp/pa-static-review-616/round3-channel-http.mts`：真实 ExternalChannels → Fastify `registerConversationActions` handlers（inject，无监听产品服务）→ Messaging.incomingExternal → 实际持久消息 → IM `pa.source.admit`。
   - 正常 Feishu DM 接收调用 **1**；数据库正文与 `sender_source_id=sender` 正确；source admit `allowed=true`。
   - 从同一已持久消息计算 sourceActor 后屏蔽：原已审操作 commit=`contact_blocked`；新 prepare=`contact_blocked`；同源入站 allowed=false。
   - 没有 mock 掉 IM 写入或 PersonalActions 权限检查；平台连接/独立语义模型使用合成适配，不称为真实飞书平台验收。临时 Fastify app 在 finally close，无共享服务重启。
3. `/tmp/pa-static-review-616/round3-notice-retry.mts`：真实 incident / frozen proposal / review / commit。
   - 固定通知第一次 review=`unavailable`，随后另一目标向 owner 正常发送成功；同一 incident content-bound key 连续两次重试均为 `proposal_requires_review`；peer notice receipt 仍 null。确认 R3-W1。
4. 复用 caller 已提供并实际读取的窄 gate 输出：`/tmp/feat616-fixed-batch-tests.log`（69后端）、`/tmp/feat616-ui-location-tests.log`（2 files/105前端）、`/tmp/feat616-batch-typecheck.log`（全包 typecheck）、`/tmp/feat616-r3-frontend-build.log`（成功 frontend build）。这些只证明相应工程 gate，不代替需要真实模型选择/产品体验的结果。

### Implementation / corrected delta reconciliation

本批没有修改 active delta-spec 正文。以下变化均属于既有目标版 spec/design 的落实；**no new spec delta**，未静默放宽来源、身份或通知契约，尚未归并 canonical。

| 本批变化 / 对应契约 | 实现与测试证据 | Outcome |
|---|---|---|
| Channels 正常输入须能通过可信来源链，同时不开放 PA 任意写 | `messaging.ts:475–499` 专用 incoming source/mirror，`conversation-actions.ts:20` 注册；媒体入口仅 `external_incoming=1` 且同样校认证来源；真实 HTTP 组合证明正常输入和 block | aligned |
| External 屏蔽阻断新请求/外发 | `personal-actions.ts:19–20` canonical actor block，transport 在 prepare 和 commit 再核；真实组合结果和回归一致 | aligned |
| 一句话多个独立目标可分别跟进/暂停 | `personal-security.ts:55,72` scopes 数组协议；`personal-assistant.ts:48–63` 缓存独立审查并逐 scope 执行；IM goal_key 分离 create key、update key带task_ref；两任务分别pause回归 | aligned（模型是否正确拆分仍由产品复验） |
| 私人任务保留 PA 真实责任和进行状态 | `personal-agent.ts:137` create 传真实 PA assignee 与 doing，不更改外部共享任务 assignee | aligned |
| 固定安全告知内容变化不得修改已冻结操作 | `personal-assistant.ts:77–80` 将内容 SHA-256 加入 Web notice key；已有 peer receipt 不再重复发 | 内容变更路径 aligned；临时故障后恢复仍 implementation-mismatch，R3-W1 |
| 一个失败源不阻断其他来源/策略事件 | `global-agent.ts:140–182` 每事件 catch，失败保留 pending、继续本batch其他事件，停止无穷当前批重读；新增回归 | aligned |
| UI 目标标题索引/旧通知不常驻占屏 | `PersonalAgentGoals` 经 headerActions 装入 PA 标题，Incidents 折叠，原聊天 shell/导航未移动 | 静态契约 aligned；真实窄屏/操作质量不由代码审查代判 |
| 历史定位不被首屏自动滚底覆盖 | chat-workspace 将 locatorMessageId 传 MessagePane；focus 时禁 initial auto-bottom，已有关联 frontend 回归 | 静态契约 aligned；P2旧产品失败待实际复验 |
| 草稿可带回、选择须推荐/理由/后果、定时无变化安静 | 工具/系统提示补 source_message_id、draft/choice 与当前 scope 的明确用法；现有 decision API/回原输入框被复用；next_check 清理指导 | 接口/指导 aligned；不把 prompt 改动当真实 DeepSeek 行为已经通过 |

Corrected delta outcome: **implementation-mismatch**（唯一已确认不符 R3-W1）；未发现需要新增/放宽 delta-spec 的遗漏对外行为。

### WARNING — R3-W1

**固定安全通知第一次未发送后，其他正常交付使它永久卡在旧 disclosure revision。**

- 契约：spec「本人控制与通知失败」「目标必需的新授权与审核不可用」要求失败保留重试、恢复继续；design 的未知与未发送区分仍适用，不能把所有状态都当未知回执而丢失通知。
- 位置：新增固定 key `packages/personal-assistant/src/personal-assistant.ts:77–80`；同文件 `executeReviewed:137–143`；`apps/im-server/src/personal-actions.ts:63,99–101` 的 previous proposal validate。
- 机制：notice key只随incident/正文变化，不随重新审核 generation 变化。首次review unavailable 后 state未发送；任何正常 commit 都会递增 disclosure_revision。重试 prepare 命中同一旧proposal，validate直接抛 `proposal_requires_review`，到不了新的独立审查；事件虽保留pending，却每次相同失败。
- 直接证据：独立真实状态操作产生上述两个连续拒绝，peer_notice_message_id=null。旧正文 conflict 已修，这里是确定未发状态的证据版本恢复。
- 建议：对**确定未发送**的精确 payload 提案允许新一轮审查 generation/刷新当前完整证据；保留当前 ACL、scope、来源/受众及累计披露重审，不能沿用旧 allow。`sending / unknown / confirmed` 继续原操作核回执、禁止盲重发。补“审核暂不可用→其他正常交付→恢复通知”的最低层回归。

### Handoff

本轮所有结论只对应冻结 `439a75144`。仅修改 `code-review-r3.json` 与本报告；按 caller 本轮要求提交这两个报告，源码/测试/共享服务均未修改。提交号见 reviewer 最终交接消息。

## Round 4 — Unsent Review Recovery and Retired Work Context

### Metadata and verdict

- review_round: `4`
- verification_mode: `targeted-closure` + 明确派发的恢复/Work/UI delta。
- executed_base / prior candidate: `439a75144525c6d4740bbdc665e792f57cf71d51`
- validated_at: `f8edd7971768cae1decfc4ad62b2b9e06b4e618a`
- fix_delta_range: `439a75144..f8edd7971`
- focus_issues: `R3-W1`；新增真实 `main_session_conflict` 恢复缺陷、owner assignee、pending DTO/手机定位/标题修复。
- verdict: **Fix before PR — 1 CRITICAL / 0 WARNING / 0 SUGGESTION**。旧顺序恢复问题已关闭；刷新审查证据新增的晚到旧审核结果接受问题为 CONFIRMED，caller 已确认该直接复现有效。
- requires_full_verification: `false`。仅需修复/复验当前审查代际绑定，不扩展无关扫描。
- Code findings: `code-review-r4.json`。

### Closure and unchanged boundaries

| 范围 | 本轮判断与证据 | 状态 |
|---|---|---|
| R3-W1：unavailable 后其他消息推进 disclosure revision 导致通知永远不能重审 | 相同正文/目标的未发送 operation 重建当前 evidence/revisions，清 verdict/ref/expiry 后回 prepared；旧探针的两次 retry 都能 prepare，新增真实测试继续审核并记录一次 peer receipt | **closed**，顺序恢复失败已消除 |
| 已签旧 permit 必须失效 | 新测试在 allowed 后再次 prepare，旧 verdict_ref commit 拒绝；新审核后可完成 | **closed**，但晚到旧 reviewer result 是另一条未防住的路径 R4-C1 |
| confirmed/sending/unknown 不重建/不重发 | prepare 直接返回原状态与 receipt，不进入 evidence refresh；内容不匹配仍拒绝 | retained |
| deny/needs_owner 不刷新来重置拒绝预算 | 直接走原 op validate/return；新审查候选仍使用现有拒绝预算检查 | retained |
| 来源 invalidation 后重新准备 | 实际刷新分支也包括 `invalidated`；该状态只由先前 prepared/allowed 的未发操作失效产生。仍重核当前 ACL/scope/policy/受众、清旧permit，未见通过它恢复已消费操作的路径 | 实际边界已记录，不把代码概括成只有3个状态 |
| R2已关闭 Channels ingress/block | 本批不更改专用 incoming/transport block；此前真实HTTP跨包证据保留 | closed，retained |

### Work context replacement verification

真实故障是来源失效后 NodeStore 换新 main，但 IM Work 仍永久占用旧 main，导致 Work 上传与后续 owner admission 卡住。本批只允许**当前 active PA 的已归属 node**登记替代 main；普通 global Agent 的唯一 main 约束保留。

- `Work.append:103–109` 先用 Agent 当前 node/global/is_stale 身份限制 journal；`register:54–65` 只有 active personal binding 的 node 可将旧 main 标记 retired。
- retired payload 保留旧 Work 身份与历史；再次 register 已退休 main 拒绝。`Work.view` 只选未退休 main，并将旧 main 放 other_executions；`Work.query` 拒绝 retired scope。
- 独立 `/tmp/pa-static-review-616/round4-work.mts` 使用真实 Work.append + 内存 DB：
  - 旧main登记后，一批先登记新main再出现 invalid scope：整批失败，旧main仍 active，journal cursor仍1，证明 retirement 与 journal transaction 原子回滚。
  - 合法新main登记成功：through_seq=2，view选fresh，old.retired=true且历史可读。
  - old query拒绝 `scope_not_allowed`；其他node append拒绝 `scope_not_allowed`；binding置pending后再换main拒绝 `main_session_conflict`，fresh保持。
- 现有新增20项PA套件还覆盖 ordinary Agent main_session_conflict 保留、旧main不可复活。未发现该Work修复扩大其他owner/node或普通Agent权限。

### Independent execution and reused evidence

1. `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts`：2026-10-19 15:02，固定 `f8edd7971`，**20 tests passed**。包括真实 action恢复/旧permit拒绝/一次peerreceipt、Work.append事务替代及明确owner assignee。
2. 原 `/tmp/pa-static-review-616/round3-notice-retry.mts` 重跑：原先 `proposal_requires_review` 的两个 retry 现在均成功 prepare；该探针只核准备恢复，最终发送由新增套件证明，不把其尚未commit的null receipt误报为新失败。
3. `/tmp/pa-static-review-616/round4-review-generation.mts`：真实 frozen prepare/review/commit，确认晚到旧证据的审核结果可被错误接受，详见R4-C1。
4. `/tmp/pa-static-review-616/round4-work.mts`：上述事务/当前node/retired query/pending负向直接证据，无产品服务/模型。
5. 复用 caller恢复相关54测试、106前端与build/typecheck证据。实际读取 `/tmp/feat616-r3-all-tests.log`：全量为 **391 passed / 1 timeout**，失败是workspace-tools并发90s超时；`/tmp/feat616-workspace-retry.log` 单独 **1 passed / 34.85s**；`/tmp/feat616-r3-web-all-tests.log` 前端 **897 passed**。准确保留全量原运行的失败和隔离重跑结果，不写成一次全量全绿，不据此扩展本轮未变化功能测试。

### Corrected Delta Reconciliation

| Delta item / 原契约 | 实现与证据 | Outcome |
|---|---|---|
| 未发送审核故障恢复 | 当前权限下重建证据，清已有旧permit，正常恢复顺序测试通过 | aligned 的顺序恢复；并发代际 R4-C1 implementation-mismatch |
| 并行累计披露必须基于实际最新证据 | payload身份未变而evidence刷新；旧packet晚到allow仍可成功签发新permit | **implementation-mismatch** |
| 来源失效后新上下文继续工作，旧Work留历史不继续控制 | 当前active PA node替代main、retired历史投影、query拒绝，真实append原子回滚/成功均验证 | aligned |
| 本人明确负责的私人目标 | scope只在显式owner_responsible=true时用当前binding.owner_user_id assignee；默认仍PA；共享任务已有assignee不变 | aligned |
| 等待接收状态与真实DTO | DeliveryStatus纳入pending，界面按实际pending显示等待；不是把sent冒称模型执行 | aligned |
| 移动出处与标题 | focusMessageId期间抑制自动滚底；手机去重复PA badge以给标题空间；前端回归保留 | 静态aligned；真实产品复验由独立reviewer判断 |

Uncovered observable behavior: 本批Work旧main退役后仍可作为历史查看，属于原design“退休上下文/保留Work历史”的落实；没有新增读取旧来源的Agent权限。未发现应另外新建或放宽契约的对外行为。**no new spec delta**，canonical尚未归并。

Outcome: **implementation-mismatch**，唯一确认的不符为审查证据代际绑定。

### CRITICAL — R4-C1

**刷新提案证据后，晚到的旧证据审核仍能放行新一代操作。**

- 契约：spec「发送前内容或权限变化」「改变出口或逐步套取」，Gateway PA delta「连续披露与并行操作」要求当前受众/许可/累计披露进入独立审核，不能用旧历史全部放行。
- 位置：`apps/im-server/src/personal-actions.ts:126–129` 更新同一operation的evidence/revisions；`review:137–143` 只校proposal_ref/payload_digest，没有evidence generation绑定。host的review-result同样未携带其实际审查的证据代际。
- 独立直接复现：A prepare时disclosure_revision=0/previous_disclosures=0，A审核在途；B向同peer真实commit；A retry prepare刷新成revision=1/previous_disclosures=1；随后A旧packet晚到的allow仍被接受为allowed，commit=confirmed。没有更改正文或伪造不同payload，正是同一操作的恢复并发。
- 原因：清掉已签旧verdict_ref只能挡已经存在的permit；旧审核调用在刷新之后才返回时，当前服务会用刷新后的op做validate，却不知道这个allow从未看过该证据。
- 建议：prepare返回完整evidence及scope/policy/disclosure revisions的generation或digest；host将它与本次独立审核原样绑定回review-result，server要求与当前op完全匹配。旧代际返回需fresh review，不能签新permit。保留不确定发送的原receipt语义，新增“A旧review→Bcommit→A刷新→旧allow拒绝→新allow通过”的最低层回归。
- caller已确认该复现是有效阻断，并计划按evidence_digest闭合；本报告不提前覆盖后续未冻结改动。

### Handoff

仅写并提交 `code-review-r4.json` 与本报告。此前有效结论保留；R3-W1与本批Work修复的直接证据已记录，新审查代际绑定问题需修后定向闭合，不再扩展额外扫描。提交号见最终交接。

## Round 5 — Evidence Closure and Corrected Delta Reconciliation

### Metadata and separate verdicts

- review_round: `5`
- code_review_mode: `closure`，唯一 focus 为 R4-C1，不扩展代码扫描；`code-review-r5.json=[]`。
- verification_mode: `corrected-delta`，按本轮明确要求核全部 active delta 与最终统一PA设计、当前实现及既有有效证据。
- executed_base: `f8edd7971768cae1decfc4ad62b2b9e06b4e618a`
- validated_at: `8845a281517ddc72f8e084f915205e1783466138`（实现 commit `03fda087e`）。
- R4-C1 code closure: **Approved — closed，0 存活代码 finding**。
- corrected-delta outcome: **implementation-mismatch — 1 CRITICAL / 0 WARNING / 0 SUGGESTION**。任务 delta 的“owner当前资格∩来源策略读取任务”没有贯通现有 `task_graph get/list`；此结论来自明确派发的 delta 核对，不把真实实现缺口改写成更小的需求。
- requires_full_verification: `false`；未重开未失效部分。当前真实产品 R3 验收仍由独立 reviewer 执行，不据代码闭合自动通过产品或整个M1。

### R4-C1 closure evidence

`PersonalActions.project` 新增 evidence_digest，输入覆盖完整 evidence_json 及 scope/policy/disclosure revisions；`review` 先做原 validate，再要求提交digest与当前投影一致。未提供digest也拒绝。它与payload_digest分别绑定证据和精确动作，不依赖主模型自报。

Host 在 `PersonalAssistant.executeReviewed`、普通 `send` 与 `external` 三处实际审查/发送路径捕获原 proposal 的 digest，原样回传 `pa.action.review-result`，不在审核返回后重新请求新 digest。task/network/固定notice经executeReviewed复用同一关口，Channels经external；scope创建不伪造该回执。confirmed/sending/unknown的既有receipt分支与commit时最终版本核验未改变。

独立执行：

- `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts packages/personal-assistant/tests/personal-assistant.test.ts`，2026-10-19 15:08，固定候选 **2 files / 32 tests passed**。
- `/tmp/pa-static-review-616/round5-evidence-closure.mts` 使用真实 PersonalActions 重跑原失败序列：A旧证据revision=0/披露条数0 → B真实commit → A刷新revision=1/披露条数1 → 晚到旧allow拒绝 **review_evidence_changed** → 新证据allow及commit均成功。没有mock权限验证或改payload来制造通过。
- 复用 caller 的 IM/PA build 成功证据，不重复无关全量；上轮Work事务与Channels真实HTTP证据继续适用。

旧 finding **R4-C1 closed**。没有发现该digest修复扩大权限或恢复未知发送的路径。

### Delta corrections made in this round

按 caller 明确授权，仅纠正可由最终design和真实接口支持的旧目标文字；没有修改实现、测试、current canonical或design。

| Active delta | 陈旧文字与校正 | 证据 |
|---|---|---|
| `im/agents-nodes.md` | “外部交流按受限会话执行”改为统一私密主执行处理有来源的外部输入、外部仅获已授权/已审答复 | 最终design统一PA；GlobalAgent.main/receive与无外部业务session分支 |
| `im/agent-work.md` | “主/子及外部/观察执行”改为统一主/内部子执行及处理外部/观察来源产生的Work，不再暗示三类独立业务执行域 | final design:16、127；Work owner-only投影与真实主执行 |
| `gateway/task-graphs.md`、`im/conversations-messages.md` | 删除早期一次性入群批准/受众版本许可机制的承诺，准确写PA工具不自行create/join、owner经既有成员操作加入具体群；仍核当前资格且不授予私人披露权 | design:180“owner决定入群”；PersonalSecurity禁止conversations create/join；Messaging成员操作限制Agent归属 |
| `im/agents-nodes.md` residency段 | 校正“服务器和本机永久双marker”的未实现机制承诺：服务器持久node residency拒绝跨owner；本机仅在服务器绑定成功后保存新owner/token，普通配置不能改personal binding；不声称有独立本机永久marker | final design:213；PersonalAgent创建/restore写pa_node_residencies；Identity.checkTransferRecipient；bindDevice提交顺序和NodeConfiguration身份不可变 |
| `gateway/global-agent.md` | caller本轮已纠正外部session旧措辞；核统一私密执行和canonical owner控制限制一致 | 本轮文件diff与GlobalAgent ownerControl分支；该文件本reviewer未再修改 |

这些校正不改变真人/普通Agent的现有权限、不新增逐动作审批，也不把已排除的来源恢复给PA。服务器residency仍不因重命名本地runtime目录而消失；本轮只删除不存在的独立本机marker机制承诺。

### Corrected Delta Reconciliation

| Delta item | Implementation / retained test evidence | Outcome |
|---|---|---|
| gateway/global-agent：统一跨源私密执行、owner私聊控制与来源授权 | GlobalAgent.binding/main/receive、ownerControl、PA scopes；旧外部session文字已纠正 | aligned |
| gateway/agent-capabilities：受控能力、原工具审批AND、插件/子执行无旁路、来源派生 | PersonalSecurity/ConfigurationScopes/ToolSelection与此前native DSH真实进程证据；普通Agent条款按该文件PA特例前言解释 | aligned 的既有代码/工程范围，未将未测攻击外推通过 |
| gateway/personal-agent：来源/目标/动作/恢复/历史能力 | 既有固定binding、scope、历史ACL/排除、外发多sink、unknown不重发、Work退休与本轮digest闭合证据；任务读取仍有下列实质缺口 | **implementation-mismatch**（任务来源策略） |
| gateway/task-graphs：owner当前资格代表协助、任务capability/版本/真实actor | reviewed `executeDelegated` 写回仍核owner/source/版本并保留assignee；普通 `get/list` 未使用该owner/source入口 | **implementation-mismatch**，R5-C1 |
| im/task-graphs：源任务唯一真相、负责人不因协助改派 | 私有目标按明确owner_responsible或默认PA建原task；共享结果沿executeDelegated；owner源任务读取部分缺实现 | **implementation-mismatch**，R5-C1 |
| im/personal-agent：固定入口/目标/观察/历史/代发/告知/简洁 | 代码与已保留的工程/真实样本映射见前轮；最新产品复验尚在进行，不把旧P1–P7失败自动关闭 | 契约文字与目标对齐；产品退出判定保留 |
| im/agent-work：私密Work与内部成果自动返回 | owner-only ACL、partition消费者、历史退休投影；已校正统一主/子术语 | aligned |
| im/auth-tenancy：固定资源空间、数据面token/对象ACL与PA私密资产 | 现有identity/source/Work/trajectory ACL；允许联系PA不开放其私人资产；任务专用读取入口例外尚缺 | **implementation-mismatch**，同R5-C1，不另计重复问题 |
| im/agents-nodes：首个PA、同owner恢复、跨owner拒绝 | create/retry/rename/restore/epoch与perPAstatus既有证据；统一执行与residency文字已按实际最终机制纠正 | aligned 的工程范围；最终产品旅程不代判 |
| im/conversations-messages：真人/普通Agent群规则、owner决定PA成员关系、影子会话 | owner成员操作与Agent工具限制、private external incoming adapter；已移除旧一次性入群permit文字 | aligned |

### Uncovered Observable Behavior

本轮证据digest是host-only协议字段，不产生新用户权限；Work退休/源排除后的新main属于已批准恢复契约；专用external incoming用于入站private shadow而不是PA外发权限。未发现应新增一套用户流程的遗漏行为。

任务读取不符是既有delta明确要求而实现遗漏，不是需要缩减或删除的“新行为”。当前仍禁止声称全部corrected delta aligned或提前canonical归并。

### CRITICAL — R5-C1: Task reads do not follow owner/source authority

- 契约：`gateway/task-graphs.md:7`、`im/task-graphs.md:8,20` 要求PA按owner当前读取资格及有效观察/目标范围读取任务；`gateway/personal-agent.md` 排除/失权使受影响源API失效。最终design:79,117,197仍明确原任务协助与本人来源范围。
- 实际：`Gateway.handle task_graph.command:420–449` 对read仍直接 `TaskGraphService.execute(kind=agent,id=PA)`；`executeTransaction:478–481` 的get/list使用PA自己的user ID，不走owner/source policy。只有reviewed写回使用 `delegatedOwner`。
- 独立真实probe `/tmp/pa-static-review-616/round5-task-read.mts`：创建owner参加、PA未加入的私密群任务；`PersonalAgents.sourceAllowed=true`，但真实Gateway.get返回 `not_found_or_forbidden`。将源设为公开并在PA政策排除后，`sourceAllowed=false`，同一真实Gateway.get却 `ok=true` 返回完整图。不是只绕过Gateway直接调用私有helper所得的推断。
- 后果：PA不能读取本该协助的本人私密源任务；又可借普通公开群task工具重新摄取已排除来源，破坏来源例外。不能靠改小delta解释成当前预期。
- 建议：为PA get/list/activity等实际可用只读入口核trusted binding、owner当前task源资格∩PA source policy，同时保留task capability和普通Agent原路径。每次分页/图读取重核，并把确实读取的任务来源纳入可撤销来源证据；原reviewed写回/assignee边界保持。以最低层Gateway/TaskGraph seam补私密owner允许、排除/失权拒绝、普通Agent不扩权回归。

Outcome: **implementation-mismatch**。R4并发代码blocker已独立关闭；新增剩余问题仅来自本轮明确要求的corrected-delta核对。真实产品最终验收仍独立进行。

### Handoff

文档校验使用仓库既有Python环境：`PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs-check`，276 maintained Markdown sources / 64 required routes通过（默认系统Python缺PyYAML，未安装新依赖）。

本轮仅写R5报告、verification与上述4个active delta文件，未改实现/测试/服务。报告及delta校正一起提交，最终提交号见交接消息；canonical尚未归并。既有不相关证据保留，不重复开启全量实现审查。

## Round 6 — Personal Task Read Closure and Owner Decision/Control Delta

### Metadata and verdict

- review_round: `6`
- code_review_mode: `closure` + 本轮明确纳入的修复 delta；`code-review-r6.json=[]`。
- verification_mode: `corrected-delta`，保留R5其他已核对且未失效的条目，仅复验R5-C1及本批owner选择/控制修复。
- executed_base / prior candidate: `8845a281517ddc72f8e084f915205e1783466138`
- validated_at: `19458a27ef0aa4c78035a1879ed4ba3cbd4694a3`
- verdict: **Approved — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**（当前定向代码审查与corrected-delta gate）。
- corrected-delta outcome: **aligned**。
- requires_full_verification: `false`。
- R5-C1 **closed**；R4证据digest、R2来源/Channels边界、退休Work等未变化的有效结论继承。
- 该批准不代替真实产品验收。root另行安排的产品R4仍需给出实际旅程结果；此前产品fail/inconclusive不因本报告自动通过，不宣称M1已完成或可部署。

### R5-C1 closure — actual Gateway evidence

Gateway对PA的get/list/activity先以当前connection调用 `PersonalAgents.authority`，从binding取owner_user_id，不采信模型owner参数；随后进入 `TaskGraphService.readPersonal`。该只读适配仍经原execute校task capability、工具allowlist、Agent注册/节点/账号资格，再以owner当前会话资格∩sourceAllowed读取。

- 独立重跑上轮 `/tmp/pa-static-review-616/round5-task-read.mts`，使用真实注册Gateway.handle及真实TaskGraphService、PersonalAgents：
  - owner参与、PA未加入的私密源任务，sourceAllowed=true，原先get失败，本轮Gateway返回 **ok=true**。
  - 同源转公开并在PA政策排除，sourceAllowed=false，原先Gateway仍回完整图，本轮 **ok=false / not_found_or_forbidden**。
- 探针保留了对普通底层 `TaskGraphService.execute(actor=agent)` 的对照：它仍沿Agent自身成员/公开群规则处理。这不是PA工具旁路；PA模型调用已经由Gateway强制转入readPersonal，普通Agent行为未被扩大。
- 新回归覆盖get readonly projection、list limit=1时的items/total/next_cursor、排除后total=0、不允许通过readPersonal执行create，以及owner离群而PA仍在群也不能读取。

代码审查结果：

| 读取边界 | 核对证据 | 结果 |
|---|---|---|
| 当前binding与epoch | Gateway进入adapter前调用authority，不能拿旧PA node或模型owner读取 | aligned |
| owner源资格与PA排除 | adapter.chat每次先sourceAllowed，再conversationAccess(owner) | aligned |
| list计数/分页 | source过滤发生在map/sort、total、cursor/page计算前，不先分页再删项，也不泄漏被排除项统计 | aligned |
| activity与引用出处 | activity同时经chat核讨论来源与任务归属；get中的last_chat/provenance投影也经同一chat过滤 | aligned |
| 只读与写分离 | adapter仅准get/list/activity，execute对personalRead write拒绝；conversation.can_write=false及节点can_edit/delete/claim=false | aligned |
| task capability与普通Agent | 原execute主体/节点/task开关/allowlist校验保留，普通构造与路径不带personalRead | aligned |
| 原reviewed写回 | executeDelegated与冻结scope/owner write ACL/revision/真实actor/assignee不变 | retained |

### Owner decision / control delta

**已选方案可作为当前事实继续，不扩大原scope。** server私密UI决定入口仍核owner登录身份、decision归属、pending状态、expected_revision及option合法性，并持久化真实resolution。`owner.decision`系统唤醒现在明确要求主PA读取 `goals.authorization.owner_decisions` 的服务端记录；不把模型自建question/options、事件自由文本或未决选项当授权。reviewer同样只认可resolved option在既有目标约束内的后果；declined/snoozed不放行。`PersonalActions.prepare/validate` 的既有scope允许动作/对象、当前权限、证据digest和出站审核没有放宽。

这落实了原design“本人决定一次后继续”及IM delta的choice语义；不是新增可由system wake建立任意scope的能力。Gateway/global-agent delta对canonical owner DM新grant的限制仍适用，UI选择是在已记录目标范围内作已有业务决定，不能借此扩大受众/资料范围。

**旧控制冲突有界重新解释。** PersonalAssistant只在服务端返回assistance_revision_conflict/policy_revision_conflict时删除该消息缓存的审查结果，重新拉当前scope/assistance事实，以**同一已认证当前owner消息**重新解释一次；第二次冲突继续返回错误，不无限重试、不修改owner证据、不回落普通Agent权限。控制完成键绑定实际control内容；已达到目标状态的pause/resume由IM幂等返回，不再因旧revision重复改变状态。不是将历史消息重新当成新owner输入或自动重放owner叙述的过去操作。

新增回归证明：一次旧control冲突后fresh resolve/review各执行两次、旧control只尝试一次；owner消息最终admit成功；同消息再次进入不重新review。实际模型在产品中是否据此不重复确认仍须产品R4验证，提示词一致性不能替代该旅程。

### Independent validation

- `pnpm exec vitest run apps/im-server/tests/personal-agent.test.ts packages/personal-assistant/tests/personal-assistant.test.ts packages/personal-assistant/tests/global-agent.test.ts`
  - 固定 `19458a27e`，2026-10-19 15:15，**3 files / 68 tests passed**。
- 上述真实Gateway旧probe产生允许/拒绝的相反修复结果，闭合R5的两个直接失败条件。
- 复用caller本批全build/typecheck成功结果；没有重跑无关全量、启动模型或重启共享IM/Node服务。

### Corrected Delta Reconciliation

| 保留/修正条目 | 当前证据 | Outcome |
|---|---|---|
| gateway/task-graphs、im/task-graphs的owner资格∩源策略读取 | 本轮readPersonal与真实Gateway闭合，list统计/分页及provenance/readonly检查成立 | **aligned**，原R5-C1 closed |
| gateway/personal-agent、im/auth-tenancy的受影响源API不绕排除/失权 | PA task读取进入同一当前source策略，普通read不能经模型owner字段换身份 | aligned |
| 决定一次继续、无system伪授权 | 服务端resolution查询、事件指向server facts、reviewer+scope/commit仍约束 | aligned |
| 旧pending控制恢复，不重放过去动作 | 有界fresh facts复核、pause/resume幂等、真实owner source核验和回归 | aligned |
| R5已校正统一主/子执行、owner群成员操作、服务器residency真实边界 | 本批未改变对应实现和active delta，前轮证据继续有效 | aligned，retained |
| R4审查代际绑定、Work退休、R2Channels私密入站/屏蔽 | 本批未改变该权限关口，原直接复现与closure仍适用 | aligned，retained |
| 其他R5已对账delta与产品行为 | 目标契约未被本批缩减；产品退出证据留独立验收 | 文本/实现范围继承，不代判产品pass |

Uncovered Observable Behavior: 没有新增独立用户流程或扩展权限。readPersonal是现有task只读动作的可信owner适配；owner.decision事件纠正现有已选方案的执行说明；缓存冲突恢复仅重解释同一认证输入。**no new spec delta**，active delta与最终design保持，canonical尚未归并。

Outcome: **aligned**。当前代码与corrected-delta门禁无未关闭CRITICAL/WARNING；完整产品及M1交付结论仍由caller合并独立产品R4和适用证据后决定。

### Handoff

本轮仅提交 `code-review-r6.json` 和verification报告，未改实现/测试/设计/delta正文、未重启服务或推送。提交号见最终交接消息。

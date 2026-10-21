# feat-627 — 产品验收报告

> 对齐：[spec.md](spec.md) 的全部用户 Scenario；[design.md](design.md) Runbook for Reviewer。
> Round R1；mode=full；revalidation_mode=full；2026-10-21。
> Validation snapshot: `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28 → 31e47aab36782a99c17d709b6496f344892c55a1`。
> Nano 后续 HEAD 推进仅包含独立审查报告；受验实现未改变。插件固定 Release `dsh-agent-context@0.3.0-rc.1`，交接源 commit `7f0a2b78ec530075edd48452c2cf5499548ca99c`。

## Verdict

**fail**。3 项 major 可见问题，另有默认身份矩阵证据缺口。真实长任务完成了 12 份材料、同一 turn 13 次换窗与一次性测试消息，但最终报告合计错误，换窗后两次违背明确工具约束，插件模型列表与实际管理状态不一致。不能用正确的差额一列、切窗次数或工具调用成功替代整体交付正确性。

本报告仅陈述产品观察，不将这些现象归因为某段实现、插件算法或模型能力；未读实现定位根因，也未修改源码、测试或受版本控制配置。

## 用户旅程体验

真实登录隔离 Web IM `http://127.0.0.1:62224`，由其消息 API 发出用户任务，经过实际 Node/PA/DSH 和 `deepseek:deepseek-v4-flash` 模型，读取实际收到的 Agent 消息。浏览器以 1280×720 查看聊天、审批卡、最终报告和恢复回复。没有内部 submit、fixture 回复或空调用三次换窗。

用户先给“旧方案”，随后明确改为“最终验签审计”、丢弃 RC-OLD、只发一次测试确认、禁用 bash。12 份本地合成卷宗每份约 44k 字符，尾部为最终验签；Agent 按序实际读取全部文件（01 在前一阶段，02–12 在长任务 turn），工作量超过三窗。最终中文表格能按 incident 对照基线、投递、差额和凭据，确认消息为独立气泡，身份与时间清晰，整体排版沿用现有聊天设计，无遮挡或无法阅读的问题。

然而表格合计基线 **14353**、确认投递 **13308**、差额 **245** 彼此不相减成立。逐行原始值与独立 oracle 核算应为 **13482 / 13237 / 245**。用户看到“已完成”及正确外发回执，仍会拿到错误汇总。重启后要求独立复核，Agent 又声明与原始证据吻合并重复同一错误合计。这是交付内容错误，不是 UI 风格问题。

另一次旅程中，Agent 已成功使用 Notes，却从插件列表告诉用户“无已安装插件”；Web 管理接口同时显示默认插件 enabled。用户无法由模型入口可靠判断当前机制。使用准确包名的管理入口完成停用/恢复后，状态和实际工具行为正确。

关键画面保留在本机 `/tmp/feat627-acceptance/final-ui.png`、`peer-restored-ui.png`，未提交截图或原始日志。最终报告原件仍保留在隔离 workspace `acceptance627/final-report.md`，未替用户修正后冒充原始验收通过。

## 环境与证据索引

- 专用身份：`e2e` / `e2e-peer`，不同 workspace；仅隔离 IM，未触达生产或外部频道。
- 主聊天 `c_61rlhkes`，session `d21f31a1-755a-49f4-b9cf-25f21709791a`；peer 聊天 `c_zcmlq102`，session `837186c0-dad5-4923-9632-b112969bfdab`。
- E1 初始任务消息 `bfc99bb3bc754f4ea106f721e5d95d44`；最新纠正消息 `1ba8705f1ac445959d359b9a99e584c0`（native `:initial` item 103）；成品回复 `aa14662596554b0cac68caf78fbe494f`。
- E2 原始事件本机导出 `/tmp/feat627-acceptance/session-events.jsonl`；turn 5 的 compaction/start seq：135、172、210、260、310、360、413、457、495、529、563、597、638。13 次均成功提交；其中有材料处理、Notes 保存/恢复、History 恢复，不是连续空切窗。压力提醒 seq 154/446/620；fallback 包括 161/199/249/299/349/402/484/518/552/586/627。材料 02–12 read result seq 108、194、244、294、344、397、479、512、545、579、580。
- E3 原始模型请求本机目录 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_10-58-11_852_d21f31a1-755a-49f4-b9cf-25f21709791a/`。原日志与凭据不入 Git。
- E4 唯一确认消息 `f87d2153f3664417864e6241219b765d`，内容精确等于 `FEAT627_AUDIT_CONFIRMED`；重启续接完成后聊天 API 中精确匹配条数仍为 **1**。
- E5 正常重启由 `pnpm pa restart --config <本 worktree>/.gateway-config.yaml` 完成，PID 51847 → 53542，保持同一 session 与 DSH home，更新 `.gateway.pid`。续接用户消息 `1a0400a0091b4a368ddf850007a53168`，回复 `db854710b5b14c5fb6c3365c9aec34c3`。
- E6 续接 History `read :initial item 70`，`total_chars=94291`；先 offset 0 / limit 6000，再 offset **83291** / limit 11000，实际读出第 225/226 行 `valid=true`、`confirmed_deliveries=1005`、`RC-01-12934`、`PROOF-01-TAIL`、`discarded=RC-OLD-01; gap=14`。未重新读取 incident-01 源文件。用户纠正原文另由 History item 103 恢复，来源为 nano-human。
- E7 peer 无记录/越界结果回复 `28cf8e6d12ca4417a5c7a59098c6112e`；存储故障回复 `5b6a0d32bee9447887f197df1fd0fbce`；模型空列表回复 `f4af8d98ec7f4101ad5d7c37df5d8bda`；停用后未知工具回复 `6ec55e2349a14aec9ecb4f1125ef4d96`；恢复成功回复 `2bff1155e2994a7ea85fb45eb98e5492`。
- E8 完整消息响应本机 `/tmp/feat627-acceptance/c_61rlhkes.json`、`c_zcmlq102.json`；开关管理响应 `peer-disabled-after-restart.json`、`main-enabled-after-restart.json`、`peer-reenabled.json`。

### 临时环境修正与证据边界

只调整忽略的隔离配置。预算覆盖最终为 `agent-context` row config：`modelSurface: always, bufferTokens: 30000, reminderTokens: 6000`；C=65536、O=16384、W=19152。第一次临时 patch 遗漏 modelSurface 导致 Notes 未注册，补齐整段配置并正常重启后开始有效长任务；该前置错误不归为产品缺陷。

原隔离审批模型不支持固定 low effort，出现可见审批卡。广泛定位与违反用户限制的 bash 均拒绝；隔离插件只读/启停操作在具体动作上允许一次。长任务结束后的正常重启仅把隔离 `tool_approval_model` 改为支持 low 的 `codexOAuth:gpt-6-luna`，保留审批机制，主任务模型未变。前置修正不掩盖随后两次违反禁用 bash 指令的事实。

## Reference Artifacts Reviewed

N/A：本 unit 无前端变更、原型或 must-match 视觉契约。仍实际检查了受影响聊天流程，结果见用户旅程体验。

## 问题清单

| # | 严重度 | 现象与证据 | 处置 |
|---|---|---|---|
| R1-1 | major / blocking | 12 行明细全对，但成品合计 14353/13308 错误，正确为 13482/13237；245 差额正确。E1 成品和本地 final-report.md 均错。E5 重启“独立复核”仍重复错值并声称吻合。 | 交付内容正确性未通过；保留原成品，修复/重新冻结后复验完整交付。不得只修表格后宣称长任务原本通过。 |
| R1-2 | major / blocking | 最新用户原文明确“不用bash，不要做目录搜索”，且已从 History item 103 恢复。随后 seq 382 仍调用 bash `echo ok`；用户拒绝重申后，seq 654 又调用目录 `ls -la`。两次前均有 Notes 恢复，后一次 Notes 已保存“全程禁用 bash”。 | 最后确认约束未稳定保持；两次被拒绝而无实际 shell 副作用，但需要用户再介入，Scenario 不通过。仅报告观察，不预判根因。 |
| R1-3 | major / blocking | peer 实际可用 Notes；`plugin_manager list_bundles` 返回 `entries: [], diagnostics: []`，模型据此告诉用户未安装。与此同时 `GET /im/v1/agents/e2e-peer/plugins` 返回 dsh-agent-context rc.1 enabled。 | 既有模型管理入口不能正确展示默认插件；准确包名 set_bundle 可恢复成功，不能抵销列表误导。最初以 row id `agent-context` 调用的 not-installed 不另算包名正确时的失败。 |

## 验收标准覆盖

### Requirement: 多次换窗后能继续同一个任务 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 连续长任务 | spec 用户场景 1、3 | 12 份完整材料，同一 turn 13 次切窗，产出报告并一次 send_message | E1–E4；最终 UI | fail | 能推进和完成，明细与245正确，发送一次；但合计错误且两次需用户拒绝额外 shell 操作，不能判完整目标达成。 |
| 后续纠正覆盖旧方案 | spec 用户场景 1、2 | 初始旧方案→最新 valid=true 口径，并保留明确不用bash约束 | E1、E2 seq382/654 | fail | 标题、最终原因码和剔除 RC-OLD 正确；禁用 bash 约束两次被违背，不能以部分纠正有效判全通过。 |

### Requirement: 需要旧细节时能恢复可核对的原始依据 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户约束与长工具结果 | spec 用户场景 2 | 切窗后恢复 nano-human item103；重启后从94,291字符原工具结果分段读尾部 | E6、E5 | pass | 正确恢复原约束来源与01最终验签，没有让用户重新粘贴或重读源文件。错误合计另记R1-1，不影响原文恢复事实。 |
| 没有可恢复记录 | spec 用户场景 3 | 新peer会话 list为空，读取不存在文件/窗口 | E7首个回复 | pass | notes ENOENT、history not_found，明确没有取得内容，不虚构恢复成功。 |

### Requirement: 上下文压力不造成无说明的任务丢失 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 接近预算及强制换窗 | spec 用户场景 3；design压力路径 | 降低工作预算，实际材料触发reminder和fallback，Notes后new_context继续 | E2压力与13次边界 | pass | 任务未丢失，待办推进到12份。实际覆盖工作预算耗尽fallback；provider硬溢出不冒充实测，设计允许确定分支由实现层验证。 |

### Requirement: 已保存工作记录在重启后仍可恢复且访问范围不扩大 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 正常重启后继续 | spec 用户场景 4 | 同一聊天、同一session正常Node重启后恢复状态和长尾依据 | E5、E6、E4 | pass | 无需从头开始；已发送状态恢复，未重复发送。复核合计错误仍由R1-1阻塞整体交付。 |
| 其他 Agent 或 workspace 的记录 | spec 用户场景 4 | peer Notes `../../e2e/secret.md`、History指定主session window/item | E7首个回复 | pass | invalid note path / not_found；未获得主会话内容，未用业务文件工具绕过。 |

### Requirement: 所有 Agent 默认使用无摘要换窗且可显式回退 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新建与已有 Agent 无需手动配置 | spec 用户场景 5；design身份矩阵 | 交接的两普通Agent中实际调用恢复工具，新增peer聊天没有手工装包 | E1、E7 | inconclusive | 两普通身份可用；未交接独立Global、Personal、原生子Agent、升级前profile及空业务allowlist/Auto-off三规则的可操作测试身份/创建配置。版本绑定集成测试不替代这些未观察真实旅程。 |
| 停用状态在重启后保留 | spec 用户场景 5 | Web管理入口停用peer，再正常Node重启，查询状态并实际尝试notes | E8、E7停用回复 | pass | disabled跨重启保留；notes返回unknown tool，其他三工具不在当前集合；主workspace仍enabled且正在恢复。未把单独停用状态观测宣称为测过旧摘要模型的实际长任务压缩效果。 |

### Requirement: 通过现有插件入口控制生效与撤销 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 启用、停用和恢复 | spec 用户场景 5 | API停用、重启、模型以准确包名恢复并重新读取笔记；比较主workspace | E7、E8 | fail | 管理APIoff/on及状态隔离正确，恢复读回PEER627_PERSIST_SENTINEL；但模型list_bundles为空误导用户（R1-3），完整既有入口体验未通过。 |
| 加载或恢复失败 | spec 用户场景 5 | 先保存Notes，再可逆地模拟该路径为目录，实际read；随后还原 | E7 EISDIR回复、恢复回复 | pass | 明确未读出原文、给出EISDIR和修复后重读步骤，未覆盖或把记忆冒充读取。覆盖“已保存记录恢复失败”分支；未额外声明执行过坏包加载分支。 |

## 上层文档同步

- [x] `SPEC.md`：无需更新，当前未提出跨包架构变化。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要由 orchestrator 在通过门禁后校正并归并本 unit delta；本轮不应提前宣称已验收行为。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 环境收尾

未另起独立服务，使用 caller 交接栈，按交接要求留运行现场用于修复。当前Node PID53542；peer恢复enabled，主Agent仍enabled；临时存储故障已还原，原笔记和报告保留。隔离预算与审批模型配置保留在忽略文件，未触及生产、主checkout或共享LLM代理。只提交本 acceptance.md。

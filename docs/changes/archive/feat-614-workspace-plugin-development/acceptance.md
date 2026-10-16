# feat-614 — 独立产品验收

## Round 1 — fail

Validation snapshot: `46d3e8c8e → 7befe5a7971dbb85b37a73c46e409f18f1ca923d`。2026-10-16 00:07–00:20 +08:00。Full 验收，HTTP 代驱动 Web IM 同一登录、配置、聊天和工作轨迹入口；无视觉/iOS 验收声明。

专用栈 `http://127.0.0.1:62034`，运行根 `/private/tmp/feat614-review-stack`，启动 PID 34811、DSH 34814，ready=true。真实模型 DeepSeek V4 Flash 与 GPT-6 Astra；正常 Auto，审核模型为 GPT-6.1 Sol。所有数据均为专用合成业务资料。运行代码路径和启动进程已核对。期间 worktree 合入的 feat-615 首文档没有改变被测运行时代码。

### 用户旅程体验

Agent 自主发现随包 Skill、查询实际安装版本 API 并读取公开声明；Reviewer 没有在创作任务中提供 Skill 名、代码、工具参数或操作步骤。报销工具、报告格式、资料索引、压缩均由真实模型独立创作。提示词的初次创作与独立无历史聊天效果成立。报销原生调用最终以绝对路径得到正确的 315.00 元。索引实际检索得到 14 天退货政策，且资料变化能更新检索结果。

但是同名同版本更新报告 `application: applied` 后，工具仍按旧路径逻辑执行，提示词仍输出旧落款，索引服务仍返回已修正的旧值。用户无法依靠成功状态确认更新生效。Agent 自主识别失败并停用/启用恢复提示词及服务；该恢复不抵消更新缺陷。因已明确真实阻塞，00:20 左右通过产品 `/stop` 保留未完实验并转入修复版复验。

### Reference Artifacts Reviewed

N/A：design 明确没有 UI 变化，允许客户端同一 HTTP 接口驱动，不声称浏览器视觉或物理设备体验。

### 问题清单

| ID | Severity | Regression Relation | 期望与实际 / 证据 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| A1 | major | direct | 更新后实际贡献应切换。三种独立插件重装返回 applied 但旧贡献仍执行：`r614-deepseek` 相对路径持续按 DSH_HOME 查找；`r614-astra` 更新落款后新子任务仍输出“研究室报告”；`r614-library` 修复 watchError 后状态工具仍返回不合类型的旧 null。`round1/*-trace.json` 含安装和紧接实调，Astra聊天明确告知首次未通过。 | fix-implementation | 更新/恢复是必验生命周期，成功状态与实际行为不符，阻塞交付。 |

Side findings：DeepSeek 的纯边界问答进行了不必要环境及另一测试 workspace 文件读取，一次凭据探查被正常 Auto 拒绝；最终消息含 `</text></invoke>` 尾部残留。未修改设置/安装代码，范围与非强沙箱结论准确。此为模型样本质量观察，不据此推断本次实现根因。

### 验收标准覆盖

| Requirement / Scenario | 来源 | 真实证据 | 结果 |
|---|---|---|---|
| 获得开发指导 / 首次请求开发工具 | spec 用户场景1 | `r614-deepseek` 自主 skill→describe_api(tool)→公开声明→开发安装→原生 expense_summary。初次相对路径失败，绝对路径得到 Jan 240、Feb 75、合计315。修复更新受 A1 阻碍。 | fail |
| 获得开发指导 / 资料被禁用或接口不适用 | spec 场景1、5 | `r614-no-skills` explicit_allowlist=[]，不读取技能文件；通过当前 describe_api 返回五主题，准确区分 DSH 通用 MCP 字样与 Nano 尚未承诺挂载。聊天 `c_4h103jm5`。 | pass |
| 工具以外需求 / 报告格式与资料索引 | spec 场景2 | Astra 创建提示词；无历史同workspace peer `c_64z95zx6` 自动三个标题和落款；禁用后独立任务普通格式。索引首装 schema 失败后修复，原生 library_search=14天；版本甲→乙后查询乙；停用后文件改丙，数据库仍乙、统计2，数据保留。索引恢复/跨workspace补验及 A1 尚待闭环。 | inconclusive |
| 工具以外需求 / 自定义压缩与恢复 | spec 场景3 | `r614-compress` 自主读取 compaction API，安装 decision-compaction，调低自身阈值；已发送 `/compact`，本轮尚无完整人工、自动及恢复证据。 | inconclusive |
| 产品责任边界 / 业务插件与已有调度交付组合 | spec 场景4 | 尚未进入 Cron 旅程。 | inconclusive |
| 产品责任边界 / 请求客户端或宿主扩展 | spec 场景5 | `c_x6xqq8l1` 准确解释不能为 iPhone/Web IM 注入按钮、不能改审批或接管别workspace，并给报告/独立应用等替代。未执行这些变更。 | pass |
| 生命周期 / 更新、重启及撤销 | spec 场景6 | 三类 A1 更新失败；同workspace管理状态一致、其他workspace无安装。重启和最终撤销待后轮。 | fail |
| 生命周期 / 加载或功能验证失败 | spec 场景1、6 | 索引首装 `application:failed`，schema类型数组诊断可行动，Agent修复并实调；提示词更新旧落款被Agent明确判未通过后停启恢复。初始失败全部保留。 | pass |
| 生命周期 / 管理关闭与原有工具限制 | spec 场景5、6 | `r614-tool-peer` 共享报销workspace，仅read且无plugin_manager。聊天 `c_2ousopss` 只读取CSV，不获得自动插件工具、bash或管理；持久选择保持。空工具子集待补验。 | inconclusive |
| 信任范围 / 查询插件隔离承诺 | spec 场景5、6 | `c_x6xqq8l1` 明确可信本地代码、workspace作用域不是OS沙箱，不保证任意代码不能读外部文件。 | pass |

证据根：`/tmp/feat614-review-evidence/round1/`（配置、完整分页轨迹、消息；不提交）。主要会话：工具 `c_q4bzt7yp`、提示词 `c_5lqh38t8`、索引 `c_gnkh9qia`、压缩 `c_kd3jvw0g`。运行源码/数据库/生成插件均为本地证据，不纳入仓库。

### 上层文档同步

- [x] `SPEC.md`：无需新增架构边界；本次仍沿既有公开DSH接口。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要 orchestrator 在验收后校正并归并 unit delta。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## Round 2 — pass

修复版 `246c484ae`，targeted 复验 A1 并完成上轮未完成全部 Scenario。保留 Round 1 原结论，不以新版本冒充旧版本成功。

### 已取得的复验证据

2026-10-16 00:21 +08:00，专用 Node 重启为 PID 42849 / DSH 42853，ready=true。运行代码 `246c484aeba1c4905f902b40b52cb74a191e29b8`。重启前安装、资料、会话均保留；安装状态快照为 `*-plugins-after-restart.json`。后续 `972b047ac` 只补充 Cron pending 指导，未作为新的模型样本重新试验；以下 runtime 结论仍对应 246c484ae。

- **A1 已关闭**：DeepSeek 在已有 expense-summary 1.0.0 增加月份选择后，同轮重装 applied，首次原生调用即支持新能力。全目录结果343.20，2月筛选75.00，新增3月独立数据28.20（含负数冲销-2.10），均与人工计算一致。提示词同版本更新落款“青鹭分析中心”后首次独立子任务通过；同workspace peer经`/new`的新上下文亦使用新落款。服务consumer新增“资料库检索”说明后首次原生查询返回新说明及21天政策，未停启绕过。
- **提示词撤销**：`r614-astra` 停用后，peer插件管理也显示disabled。peer再次`/new`后给同一无格式要求的业务分析题，输出普通“季度业务简报”/“主要发现”/“建议”，无指定三标题及落款。`c_64z95zx6-messages.json`保留启用、更新和停用三次结果。
- **索引与局部监听**：此真实样本使用插件私有SQLite服务和资料目录文件监听（不是tools/result事件样本）。独立把政策14→21天，插件真实查询21天、累计3次。其他workspace读自己的库存文件42件，库的统计仍3、indexRevision仍6。停用后将政策改30天，等待超过一分钟，数据库仍21天/3次/revision6；资料、源码和数据库均保留。重新启用后原生查询30天、累计4次/revision7。对照快照 `library-before-cross-workspace.json`、`library-disabled-before-change.json`、`library-disabled-after-change.json`；`r614-library` turn4真实恢复结果。
- **正常调度与交付**：唯一daily计划 `schedule-2055c1e7-c3a9-4293-9019-f9701600b37d`，09:00 Asia/Shanghai，deliveryMode=host。主轮结束后turn3为`origin=system, trigger.kind=cron, trigger_kind=manual`，真实expense_summary(dir=expenses)后send_message投递343.20元完整汇总到原聊天。随后schedule_delete成功，schedule_list=[]，插件和CSV保留。没有自建定时循环。说明：此处实测为现有调度的立即执行入口，不冒称等到次日09:00自然触发。
- **Cron首次样本保留**：模型第一次schedule_run返回accepted/pending后在主轮sleep等待并重复触发一次。Reviewer只用自然消息要求结束当前回复，之后两个已排队轮次执行；第二次模型明确承认重复且没有重发整表。现有产品无暂停能力，Agent准确说明并在用户明确选择删除后清理。此样本验证了产品调度/交付链，仍有模型使用指导改进点；972b047ac新增指导尚未独立重做新样本。
- **能力选择**：同workspace `r614-tool-peer`仅read、无plugin_manager，真实聊天只读CSV并明确不能调用自动插件工具；`r614-empty`工具空集，真实聊天明确无任何工具，不读取文件、不猜统计。末态配置与创建时选择相同。技能空allowlist样本继承R1具体证据，不因更新修复失效。
- **自动压缩**：原生会话`b33ec9c2-65c1-41e9-a7a0-1ba7d9d45953`，首个完整事务`25dfc062-aac8-4981-85f1-02f9cb4bce20`的seq151(start)/152(summary)/154(end)，摘要保留青鹭、31800、离线优先、核对报价。后续同样完整事务亦保留这些事实。模型将阈值设0.01导致每轮约70秒重复压缩；用户自然要求恢复正常阈值后，先发生一次edit匹配失败，最终已自行改回0.8/retainRatio0.16。人工及回落结果见下节。


### 最终补验与裁决

- **人工压缩**：消息`65819530ddb148febd654fad373e13b3`从真实聊天发出`/compact`，回执`2254d7516f124a22962c7648b27931ed`为“已压缩17项较早上下文”；原生事务`150204d2-62af-45fc-aebe-556179c716fb`，seq321/322/324完整start/summary/end，sourceCommandId精确关联输入。随后要求“不查聊天历史或文件”回忆，Agent仅用当前上下文给出青鹭、31800元、离线优先、核对供应商报价，轨迹无回查工具。
- **停用回落**：decision-compaction停用applied、无警告。无需重启即再次从聊天发`/compact`（`9a5370b4bd234d23bc2d0fb34148d2f5`），默认路径回执再次压缩17项；原生事务`742c541b-80a1-44ac-95e1-d036d19095d6`，seq366/367/369，非no-op。随后不查历史/文件的对话再次正确回答四项。另一workspace无该插件，正常默认压缩38项；因此未扩大到其他workspace。
- **真正计时触发**：进一步用自然任务“一分钟后汇总、只发一次、不留重复计划”创建一次性计划`schedule-36ea8226-7ac3-404a-bfd7-451be4452062`。没有schedule_run，计时到点后turn8为cron，原生expense_summary一次，send_message一次，消息`df1cc37acf9a422db7d9c40825cf2996`完整投递343.20元；schedule_list=[]。该样本无重复调度/投递。模型仍在创建轮做了75秒等待，属于可优化的使用行为，未伪装为准点低延迟保证。
- **最终持久化**：全部任务idle后再重启专用Node，PID50668 / DSH50672，ready=true。expense-summary及workspace-library仍enabled；research-lab-report-format及decision-compaction仍disabled；同workspace peers看到相同状态，r614-isolate仍无插件。`*-plugins-before-final-restart.json`与`*-plugins-after-final-restart.json`逐项对账。源码、CSV、政策资料和索引保留；定时计划已清空。

**Verdict: pass。Highest Required Action: pass。** A1 major已在修复版独立关闭；无开放blocking/major。首次创作与修复完整保留，不宣称四类全部一遍成功，也不以此单组样本推断所有模型/任意插件成功率。无UI视觉、真实iPhone或生产部署验收。

### 全 Scenario 最终覆盖

| Requirement / Scenario | 来源 | Round 2证据或继承依据 | 结果 |
|---|---|---|---|
| 获得开发指导 / 首次请求开发工具 | spec用户场景1 | 自主随包Skill、describe_api及公开声明；原生新工具实调两组数据315.00与28.20；更新后月份筛选75.00，不改人工工具白名单。 | pass |
| 获得开发指导 / 资料被禁用或接口不适用 | spec场景1、5 | 继承R1 r614-no-skills具体证据；热更新实现不触及禁用发现策略，末态配置仍explicit_allowlist=[]。 | pass |
| 工具以外需求 / 报告格式与资料索引 | spec场景2 | 独立同workspace新上下文有格式，更新即时生效，关闭后普通格式；索引14→21→停用改30仍21→启用30；统计3→4，无跨workspace串计数、停用保留数据。 | pass |
| 工具以外需求 / 自定义压缩与恢复 | spec场景3 | 自动完整事务、人工命令关联完整事务、无回查事实保留、停用后默认完整事务、另一workspace默认压缩成立。 | pass |
| 产品责任边界 / 业务插件与已有调度交付组合 | spec场景4 | daily可查看/删除、manual cron轮真实实调与原聊天交付；补充一次性真正计时触发只有一轮/一份结果且末态无重复计划。 | pass |
| 产品责任边界 / 请求客户端或宿主扩展 | spec场景5 | 继承R1准确范围及替代方案；其他workspace持续正常读文件/默认压缩，无客户端或权限修改。 | pass |
| 生命周期 / 更新、重启及撤销 | spec场景6 | 三类同名同版本更新即时业务生效；两次真实Node重启，最后enabled/disabled选择保留；同workspace状态一致，其他workspace不变。 | pass |
| 生命周期 / 加载或功能验证失败 | spec场景1、6 | 首轮schema加载失败、路径实调失败、更新旧贡献均可见；模型识别未成功并修复/恢复后再声明可用；修复版原生实调成功。 | pass |
| 生命周期 / 管理关闭与原有工具限制 | spec场景5、6 | 管理关闭/read-only peer不获得自动工具；显式空工具Agent不读文件/不调用插件；配置保留。初次提示词子任务仅生成文本，不取得文件/管理能力。 | pass |
| 信任范围 / 查询插件隔离承诺 | spec场景5、6 | 继承R1明确可信代码、非OS沙箱；无此次实现变化使该结论失效。 | pass |

### 样本与耗时

下列是整个连续验收窗口（含用户追加目标、修复版重启和Reviewer等待），不是模型纯推理延迟。

| 类型 | 模型 / 会话 | 时间窗口(+08:00) | 首轮和修复情况 |
|---|---|---|---|
| 工具＋Cron | DeepSeek V4 Flash / c_q4bzt7yp | 00:07–00:41，约34分钟 | 相对路径初次失败；自主修源码后遇A1，绝对路径可用；宿主修复/重启后同版本更新与业务通过。Cron首次手动重复触发保留，后续真正一次性计时样本通过。 |
| 提示词 | GPT-6 Astra / c_5lqh38t8 | 00:07–00:25，约18分钟 | 初创通过；第一次更新A1失败，自主停启恢复；修复版再次更新首次通过。 |
| 服务＋文件监听 | GPT-6 Astra / c_gnkh9qia | 00:08–00:28，约20分钟 | 首装schema类型数组失败，改schema后A1旧provider输出失败，自主停启恢复；修复版新业务字段更新及监听撤销通过。 |
| 压缩 | GPT-6 Astra / c_kd3jvw0g | 00:09–00:40，约31分钟 | 初装通过；低阈值导致反复自动压缩，恢复配置一次edit匹配失败后自修；日志复制被Auto拒绝，Agent如实报告，Reviewer独立只读核实事务。人工及停用回落通过。 |

所有创作样本均实际读取nano-plugin-development。实际describe_api主题：工具tool/service，提示词prompt，索引service/events/tool，压缩compaction；全部读取了返回的当前安装包公开资料。没有由Reviewer手工编写成功插件。

### 资源与交付

报告只修改本文件，未提交。证据均在`/tmp/feat614-review-evidence/`；原失败快照在`round1/`，最终完整轨迹为各`r614-*-trace.json`，消息为`c_*-messages.json`，压缩原生解码快照为`compress-session-after-manual.jsonl`、`compress-session-after-default.jsonl`。证据含测试会话原文，保持本地不提交。

按caller要求保留专用栈供复查：IM62034、Node50668、DSH50672；测试Agent前缀r614-，所有一次性/日报任务已清空。共享代理4000及生产服务均未操作。由caller最终执行e2e-down清理。

Caller cleanup：验收交接后已停止62034测试栈及自己的tmux，Node50668/DSH50672已退出、端口关闭；上述本地证据保留。

## Round 3 — targeted native-semantics revision

Validation snapshot: `f56e5e6d89cd496ef0bcdf75816db37313281a63`。2026-10-17，独立 reviewer，按首文档 2026-10-16 修订约束和 design 的 Runbook 驱动真实 IM。运行代码由 caller 构建并集中启动，开始/结束核对 HEAD 未变；未读实现定位根因、未修改源码/测试/受版本控制配置、未提交。

### 用户旅程与证据边界

本轮用全新 global Agent、默认 Skill discovery、正常 Auto，DeepSeek V4 Flash 与 GPT-6 Astra 两种模型，输入只给自然业务目标，不提供 Skill 名、API 或实现代码。IM `62632` 的独占资源 `/tmp/feat614-r2-review`，测试身份 nano，所有数据为合成数据；无生产或 Feishu 外发。无客户端 UI 改动，按 runbook 使用与客户端相同的聊天/管理/压缩 HTTP 入口；不声称浏览器视觉或实体设备验收。Reference Artifacts Reviewed：N/A。

主要证据为本地完整分页 Work 轨迹、聊天和输入，根目录 `/tmp/feat614-r2/review-evidence/`。同一 owner 的原始索引样本读取了另一 Agent 本次自建的 `nano-plugin-authoring-pitfalls`，因此不把它作为只靠随包指导的独立证据；原样本与首次失败均保留。caller 另起全新 owner/数据的独占索引对照 `/tmp/feat614-r2-index`、IM `64783`，只运行一个 Astra，重复同一自然输入；对照证据 `/tmp/feat614-r2/index-evidence/`。这是明确控制共享资料污染的对照，不抹除前样本或用重跑覆盖失败。

| 旅程 | Agent / 聊天 | 首轮实际时间（+08:00） | 首轮结果 |
|---|---|---|---|
| 订单工具 | `s614-deepseek` / `c_k0oqwtjy` | 00:11:19–00:19:58，8.6 分钟，66次工具调用 | 先读 Skill、tool API/安装包公开资料；首装 applied，实际汇总失败；自修后准确交付 restart-required。 |
| 周报格式 | `s614-astra` / `c_v1dk2v0i` | 00:11:19–00:15:00，3.7分钟，27次工具调用 | 首装与独立子任务格式生效；停用后的独立子任务恢复普通格式，最终恢复启用。 |
| 原索引（共享资料污染） | 同上 | 00:15:53–00:23:11，7.3分钟，48次工具调用 | 实际查询14天通过，但读取同owner新生成Skill；只作原始产品轨迹，不替代独立指导验收。 |
| 独立索引对照 | 新owner `s614-astra` / `c_ko0zdgni` | 00:23:50–00:29:23，5.6分钟，42次工具调用 | 仅读取一次 nano-plugin-development，service/events/tool API及公开资料；首装及真实查询通过，无工具错误。 |
| 决策压缩 | `s614-isolate` / `c_k7erl9mc` | 00:12:36–00:29:11，16.6分钟，99次工具调用 | 读取Skill、compaction API及公开资料；基于Basic引擎summarize钩子，保留默认阈值；安装启停通过，但准确报告尚未发生压缩。 |

以上时间来自 Work turn started_at/finished_at，不是纯模型推理延迟。

### 新真实结果

- **工具首次失败与修复**：首装 `store-recon` applied 后，Work seq298 的 `reconcile_store_csv {}` 返回 `INVALID_TOOL_OUTPUT`：输出 `dateRange` 未声明；seq396 `list_recon_csvs(dir=recon-data)` 把相对路径解析到 DSH runtime home 并报 ENOENT。两者均由 Agent 自修，未由 reviewer 代写插件。更新返回 restart-required，旧调用继续失败，最终交付明确“当前仍失败、待正常重启”，没有用反复 toggle/reinstall 绕过。caller 第一次正常重启后，原生全量100+80=180、10月2日起80-20=60、负额与相对路径均通过。
- **普通业务更新**：用户再要求只汇总指定店铺，Agent更新到1.0.2。`install_bundle` 返回 restart-required，当前原生 `store=东店` 仍输出2店180；最终准确报告当前未生效，等待正常重启，并结束本轮。
- **提示词生效与撤销**：`songlin-weekly-report` 首装 applied；未重复格式指令的独立子任务输出“本周成果/待解决/下周行动”和“松林团队”。停用后相同独立子任务改为“团队周报/本周工作/下周计划”，无落款；重新启用 applied。没有写个人记忆或全局提示。
- **索引独立对照**：`team-policy-index` 使用私有服务及本地 watcher，最初原生查询14天。reviewer从外部改为21天并新增设备政策，后续只用原生搜索得到“21天”与“超过6000元需两份报价”，累计4次。停用applied后，reviewer再把原文改30天，间隔超过一分钟，索引仍21天且queries逐字不变，文档与索引保留。重新启用后原生查询30天、累计5次。可复查 `disabled-before-index.json`、`disabled-after-index.json`、`disabled-before-queries.jsonl`、`s614-astra-trace.json`。
- **真实人工压缩**：首轮交付后，reviewer在idle从原聊天发送 `/compact`，用户收到“已压缩186项较早上下文”。原生session `a7bb34f0-0623-46f8-8a55-713ab344446a` 的seq464 start /465 summary /467 end，事务 `caae168a-92da-4a3d-a9e5-f6810115ac7e`；摘要保留28600、首版离线、周五报价planned、云同步undecided。继续对话准确区分已定/计划/未定，未把未来动作写为完成。原始事务保存 `manual-compaction-events.json`。单次摘要本身不能证明插件指引的因果增益，因为事实本就存在于原对话；安装、离线stub也不计作真实摘要证据。
- **默认自动压缩**：没有调整0.8/0.16默认值或制造压力；截至人工压缩前没有任何compaction事务。自动路径未观测，不能复用前轮0.01阈值压力样本给新指导放行。

### 轨迹中的首次错误与边界观察

这些是实际样本观察，不能据此推断本次宿主实现根因。

- DeepSeek工具错误schema和cwd均保留；普通更新还出现三次“先读文件再edit”的工具拒绝，均自行读取后修复。
- DeepSeek两个样本额外探查DSH环境/managed目录；压缩首轮进一步读Nano/DSH实现、preset/scope及进程cwd，直到99次工具调用才收口。它始终未声称尚未发生的压缩成功，但普通开发任务的调查负担明显。
- 工具Agent把自建踩坑Skill写入owner技能根，却对用户称“工作区技能”；另一workspace Astra随后发现并读取，真实表明该经验跨Agent传播。独立索引对照隔离了此因素。
- 原索引样本因试图移除 `assertCaller` 被正常Auto拒绝；污染样本仍保留，不用它证明新指导独立通过。
- 压缩首轮删除一个未证明本轮创建的临时目录被Auto拒绝，随后换新目录；继续轮seq807试图扫描/复制全部session日志到临时目录被拒绝，之后收窄当前session；seq849另存摘要又被拒绝，之后直接检查。没有人工放行这些操作，也没有凭据值外泄证据。

### 后续正常重启与撤销（`f09df0d25`）

caller在下一版 `f09df0d25` 完成第二次正常Node重启（PID40258）；相对冻结版仅压缩参考说明及design解释共4行新增，运行时代码未变。以下不冒称运行于旧HEAD：

- `store-recon` 1.0.2 原生 `store=东店` 输出1店2笔100元，默认全量仍180。随后用户要求停用，`set_bundle` applied、工具撤下，样例和源码保留。
- `workspace-decision-compaction` 停用 applied，插件管理显示disabled、工具撤下，台账hash与源码保留。用户再发送 `/compact`，收到“已压缩52项”；同一session seq599 start /600 summary /602 end，证据 `default-compaction-events.json`。继续普通聊天回答预算28600、云同步未定正确，未再读取日志。
- 各workspace的插件列表仅包含自身安装，未出现他workspace插件：`astra-plugins-final.json`、`isolate-plugins-enabled.json`与独立索引`plugins-final.json`。这里的插件隔离与owner技能共享是两件不同事实。

### Verdict — fail（必验自动路径证据仍 inconclusive）

工具、格式、私有服务/监听、原生更新待重启及人工压缩/停用恢复已取得真实结果；不能把它们扩写为新指导下自动压缩也已验收。首文档“自定义压缩与恢复”要求自动及人工两条路径，正常默认阈值样本没有触发自动，按reviewer规则该Scenario为inconclusive，整体不能写pass。除此以外未确认新的宿主实现阻塞；模型首次错误、过度探索与Auto拦截保留为事实，不凭轨迹推断代码根因。

| ID | Severity | Regression Relation | 期望与实际 / 复查定位 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| R3-E1 | major（验收证据缺口） | direct | spec“自定义压缩与恢复”要求自动/人工；本轮默认阈值从未自动触发，只有两次用户手动事务。 | 补真实自动路径证据或由owner明确收口本次必验范围；不要为过门禁降低阈值制造压力 | 不把未观测写成pass，也不把前轮低阈值压力测试描述为本轮普通体验。 |

Side findings：上节列出的schema/cwd初次失败均自修并闭环；压缩长时间源码探索、跨会话复制被Auto拒绝、owner共享Skill误称workspace等保留给owner判断，不在本报告擅自派修复或扩大实现范围。

### 验收标准覆盖（targeted，逐Scenario）

| Scenario | 来源 | 证据 / 保留依据 | 结果 |
|---|---|---|---|
| 首次请求开发工具 | spec用户场景1 | 新DeepSeek从Skill/API到创建安装，首错修复后原生180/60通过，完整首次失败保留。 | pass |
| 资料被禁用或所需接口不适用 | spec场景1、5 | retain Round1 `r614-no-skills` explicit_allowlist=[]，不读技能、正确拒绝未支持MCP；本次变动没有改选择机制，未把旧样本当新指导创作样本。 | pass |
| 报告格式与资料索引 | spec场景2 | 新Astra独立子任务启停格式；全新owner索引对照14→21/新增设备→停用不更新→恢复30、次数保留。 | pass |
| 自定义压缩与恢复 | spec场景3 | 新真实人工事务、继续对话、停用后默认事务通过；自动默认阈值未触发。 | inconclusive |
| 业务插件与已有调度交付组合 | spec场景4 | retain Round2既有schedule创建/查看/手动与一次性真实交付/删除的具体产品链；本轮不强造Cron压力，未把该证据声明为新指导模型重跑。 | pass |
| 请求客户端或宿主扩展 | spec场景5 | retain Round1 `c_x6xqq8l1`不能加iOS/Web按钮、改审批或接管workspace的明确边界回答；本次没有改变这些支持边界。 | pass |
| 更新、重启及撤销 | spec场景6 | 新工具修复+普通指定店铺更新均restart-required；正常重启后100、随后停用撤工具；格式/索引/压缩启停；workspace插件集合不同。共享workspace一致性retain Round2 peer管理状态及重启保留证据，本次无该实现变动。 | pass |
| 加载或功能验证失败 | spec场景1、6 | 原生schema/cwd错误未冒充成功，Agent自修并准确交付待重启，重启实调闭环。 | pass |
| 管理关闭与原有工具限制 | spec场景5、6 | retain Round2 `r614-tool-peer`只read、`r614-empty`空工具集，无法使用安装工具且选择不变；本次未改选择/子任务限制。 | pass |
| 查询插件隔离承诺 | spec场景5、6 | retain Round1可信本地扩展而非OS沙箱结论；新样本安装作用域信息不替代强沙箱证明。 | pass |

### 上层文档同步与资源

- [x] `SPEC.md`：无需更新跨包架构边界。
- [x] `docs/specs/gateway/agent-capabilities.md`：由orchestrator确认原生restart-required契约和本次验收证据边界已归并；自动路径缺口不得伪写通过。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

本轮仅追加acceptance报告，不提交。原始输入、消息、完整轨迹、runtime数据均在上述临时证据根，不纳入仓库。index独占栈由caller清理（PID38228/38233退出、64783关闭）；review栈收尾后已交回caller集中清理。共享proxy4000和生产服务未操作。

## Round 4 — targeted manual-compaction handoff clarification

Validation snapshot：`f09df0d25`。运行时代码与Round3完全相同，本轮只补压缩reference中的Nano必要差异：人工 `/compact` 是用户聊天命令，Agent先结束当前轮、交接给用户触发，不用shell/RPC重构控制，也不读取其他会话取证。caller集中创建全新owner/data的 `/tmp/feat614-r2-compact`（IM50958），仅运行 fresh `s614-isolate` / DeepSeek V4 Flash；其他Agent未接任务。使用Round3逐字相同的原始压缩输入，未给API、源码或额外指导。实际安装reference SHA-256由caller核实为 `0554e8733d11803fa5a0e0ab2cc803e7f73af0e8049673de3aa2861707ef09f7`，Work seq19实际读到新增说明。

### 实际旅程与剩余问题

- 会话 `c_nvho5bwk`，session `3a17dd48-6c58-4696-b0e3-25c40d8a9855`。首轮00:43:15–00:59:24（+08:00），16.2分钟、129次工具调用；对比旧样本16.6分钟、99次调用，**不能宣称效率改善**。仍大量阅读Nano/DSH宿主源码；唯一工具错误是seq41调用不存在的 `run_in_background`，随后改用bash，首次错误未删除。没有修改宿主，没有shell/RPC手动压缩尝试，没有读取其他session内容；曾列session目录以定位当前会话。
- 首装 `nano-project-decisions-compaction` applied，无诊断；基于Basic引擎公开summarize钩子、默认0.8/0.16/headroom65536，新增台账工具原生list/append通过（临时验证项随后还原）。停用/再启用均applied、工具随生命周期撤销/恢复，台账保留。
- 首轮最终交付明确“没有一次真实压缩”“只有静态/单元证据，不等于E2E”；明确 `/compact` 是用户命令、自己不能代触发，然后结束为idle。这项Nano交接清晰；不能据此认为模型不再过度探索。
- reviewer在idle通过原聊天发送 `/compact`。用户收到“已压缩247项较早上下文”；seq618 start /619 summary /621 end，事务 `c2fc39a8-c9ee-456f-a114-0ccecfbda75d`。真实summary含普通摘要文本块，另有独立第二块 `## 项目决策（本地台账，逐条原样保留）`，逐条包含28600元已定、首版离线已定、周五报价待办尚未发生、云同步未决。这直接观察到插件定义的摘要贡献，不能用首装/离线测试替代该证据。完整事务在 `/tmp/feat614-r2/compact-evidence/manual-events.json`。
- 正常默认自动阈值未触发，仍为 **inconclusive / 未观察**；不制造压力、不将旧低阈值历史事务改称本轮结果。

### 明确 acceptance bar

采用caller在 [spec.md“本轮验收方法与证据边界”](spec.md#本轮验收方法与证据边界2026-10-17-owner-裁决) 明确的owner裁决：此次新指导按常规默认阈值试用，人工压缩/继续对话/停用回落仍须真实新证据；自动在普通运行未触发则保留未观察，在其他必验通过、无实现阻塞时允许pass-with-issues。自动/人工支持契约不变，Round3原始fail不覆盖，R3-E1不改写pass。

Reference Artifacts Reviewed：N/A，无客户端UI变化。Round3的工具/格式/独立索引/正常更新重启及撤销结果保留；只有压缩reference一段变化，不重做不受影响样本或用新轮抹掉原始模型失败。

### 续聊结果与最终裁决

普通续聊输入仅为“压缩完成了。继续告诉我青禾项目哪些已定、哪些未定，下一步做什么；简短回答即可”。Agent最终正确回答预算28600与离线已定、云同步未决、周五报价尚未发生，并准确确认真实摘要的独立台账段落；已恢复idle。续聊仍用了4.6分钟、28次工具调用：主动检查当前会话日志，seq416尝试解压复制到 `/tmp/sess614.jsonl` 被Auto拒绝，随后改直接读取；Python缺zstandard后使用现有zstd。没有人工放行，没有其他session内容访问。此额外调查和拒绝同样保留，不能把文案修改描述为消除了全部模型摩擦。

**Verdict：pass-with-issues。** 依据上述明确owner acceptance bar，新指导下的真实人工压缩、插件摘要贡献与继续对话通过；停用回落、工具/提示词/服务与正常更新生命周期有Round3新证据。R3-E1自动路径新样本证据缺口仍为inconclusive，并未关闭或伪写pass。没有发现新的宿主实现阻塞；DeepSeek过度调查仍是使用体验问题，不建议继续增加DIY教程追逐零模型错误。

| ID | Severity | Regression Relation | 期望与实际 / 证据 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| R3-E1（保留） | major / owner明确接受的证据缺口 | direct | 默认自动阈值未触发；本轮只有人工完整事务。 | 按spec明确bar披露后收口，不制造压力，不称自动已验过 | 自动支持契约不变，历史压力证据仍只属于其原配置；本轮评价普通新指导。 |
| R4-S1 | minor | unclear（模型样本） | 同输入首轮16.2分钟129次工具调用，续聊4.6分钟28次；仍读大量宿主源码，并有未知工具调用及当前日志另存被Auto拒绝。 | 保留轨迹与成本观察，不追加实现循环；不能宣传效率改善或零误导 | 交付与用户命令交接准确、真实摘要与续聊成立，但完成过程不够直接。未凭轨迹推断代码根因。 |

### 验收标准覆盖（最终targeted）

| Scenario | 来源 | 当前证据 / retain范围 | 结果 |
|---|---|---|---|
| 首次请求开发工具 | spec场景1 | retain Round3新DeepSeek首错修复后原生180/60；新reference只涉及压缩交接。 | pass |
| 资料被禁用或所需接口不适用 | spec场景1、5 | retain Round3所列Round1禁用Skill/不适用接口实证，选择机制未变。 | pass |
| 报告格式与资料索引 | spec场景2 | retain Round3新提示词启停、独立owner索引14→21/新增→停用保留→恢复30。 | pass |
| 自定义压缩与恢复 | spec场景3及本轮明确bar | 新manual摘要有插件独立台账块、续聊正确；Round3 f09停用后默认真实事务及续聊通过。默认automatic仍未观察。 | inconclusive（仅自动缺口；依明确bar允许pass-with-issues） |
| 业务插件与已有调度交付组合 | spec场景4 | retain Round3所列Round2既有真实调度交付链，不冒称本轮新样本。 | pass |
| 请求客户端或宿主扩展 | spec场景5 | retain Round3所列Round1明确产品边界实证，边界未变。 | pass |
| 更新、重启及撤销 | spec场景6 | retain Round3新普通业务更新restart-required→正常重启东店100→停用，及私有索引/提示词撤销；新压缩启停实测。 | pass |
| 加载或功能验证失败 | spec场景1、6 | retain Round3真实schema/cwd自修闭环，新未知工具/日志拒绝亦保留，没有把失败当成功。 | pass |
| 管理关闭与原有工具限制 | spec场景5、6 | retain Round3所列Round2只read/空工具实证，未改限制实现。 | pass |
| 查询插件隔离承诺 | spec场景5、6 | retain Round3所列可信本地扩展而非OS沙箱实证。 | pass |

上层文档同步沿用Round3结论；spec新增本轮证据边界由caller独立复核。报告仅追加、未提交；R3 fail及原始样本均保留。新对照完整输入/轨迹/消息/事务在 `/tmp/feat614-r2/compact-evidence/`，不提交日志、凭据或业务文件。review/index栈已由caller集中清理；compact栈本轮完成后交回caller清理，当前Agent idle。共享proxy与生产未操作。

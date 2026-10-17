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

## Round 5A — targeted 当前问答范围独立产品验收（2026-10-17）

Validation snapshot：`0d23eb7e5f240551ac2cebb0d9572a4a941f8d61`，基线 `c839d6777`，主干祖先 `481467ac1`。reviewer确认worktree HEAD及初始clean；运行产物由caller冻结并交接，未重启共享Node。隔离环境 `/tmp/feat614-r3-product`、IM `127.0.0.1:64068`，专用 `s614-deepseek`，DeepSeek V4 Flash / High，Codex审批 + Luna reviewer。真实入口为公开IM登录/聊天/Work/插件API；CUA创建可见IAB返回“visibility is not supported in a subagent thread”，因此依design runbook使用同客户端API，**没有浏览器视觉或iOS验收**。未人工放行拒绝、未改源码/测试/设计/配置、未访问生产。

### 独立自然旅程与真实结果

会话 `c_wy2y81xr`，原生session `8d6ae60c-58ef-41ce-a31d-93043bd73ee3`。原始自然输入均在 `/tmp/feat614-r3/reviewer-*.txt`，没有给Skill名、API参数或正确实现。完整分页Work、消息、管理状态在 `/tmp/feat614-r3/reviewer-evidence/`；保留 `create-trace.json`、`followup-trace.json`、`verify-trace.json` 及三份watch日志，未删首错或重跑筛样本。

- **普通输出格式插件**：请求工作区周报固定“已完成 / 待推进 / 待决定”，末尾“云杉项目组”，不改个人记忆/聊天提示词。样例事实为预算18400元已定、桌面首版已定、下周三询价未做、企微接入未定。Agent自行读取Skill和API，创建并安装 `weekly-report-format`，以 `project_weekly_report` 工具实现格式能力。首轮23:29:00–23:31:16（+08:00），约136秒、29次工具调用；原生seq146/174生成三节与落款，四项业务状态正确。seq162停用调用报unknown tool属于真实撤销对照，不是被隐藏的创作失败。没有发生安装失败或更新待重启；本样本不是system-prompt section插件贡献的独立证明。
- **进行中询问进度**：插件实调后、最终交付前发送“现在进展怎样？简单说一下就行。”（`a23cb923…`）。原send_message被held后，Agent重新读取消息，并以seq200实际sent进度+原周报交付（消息 `a55dac90…`），没有把原任务交付丢弃。到达时执行工作已基本完成，因此只覆盖交付阶段，不能推导长任务中途都会继续执行；不为补证据另造完整开发任务。
- **简短业务续问**：输入“预算定了多少？企业微信已经决定要接了吗？两句话回答就好。”（`dd8976a6…`）。turn3，23:32:14–23:32:19，约4.7秒，只有inbox check/read与send_message三次调用。seq248实际sent两句：“项目预算已定为18400元。企业微信是否接入还没有决定，仍挂在待决定里。”没有技术读取、无请求的验证/后续工作、路由推断或把未决改写为既定；随后idle。
- **明确继续验证**：输入要求继续验证启停/实际效果并最终保持启用（`b3775a96…`）。turn4，23:33:14–23:34:09，约55秒、11次工具调用。seq294停用applied；seq305真实工具调用unknown tool；seq311恢复applied；seq317原生成功生成同事实三节周报；seq324管理状态enabled、无diagnostics；seq330实际sent复验结果和周报。reviewer随后经公开插件API独立核实enabled且无diagnostics（`plugins-final.json`），最终idle。此次明确执行没有被“简短续问收口”限制误伤。

本样本未修改个人记忆或聊天提示词的可见依据是全部写入/调用轨迹及profile检查，不把Agent自述当额外证明。两次unknown tool均为主动停用对照；一次held投递保留并由重读消息后sent闭环，没有人工绕过。

### 覆盖、保留项与证据边界

| Scenario | 来源 | 独立结论及证据 | 结果 |
|---|---|---|---|
| 已有上下文足以回答 | 本次delta `specs/gateway/global-agent.md` | turn3直接两句业务答案、无技术调查、idle | pass |
| 明确继续验证 | 同上 | turn4真实停用失败/恢复成功/持久化状态与sent交付 | pass |
| 简短进度询问不丢已授权任务 | caller补充边界 | 原交付held后重读并实际交付；只覆盖开发末尾交付阶段 | pass（有限覆盖） |
| 普通插件创建安装与实调 | spec场景1/2及本次targeted目标 | 首轮真实创建/安装/原生格式输出；使用工具式格式实现 | pass |
| 提示词section、服务/监听、模板、生命周期更新/重启/共享与工具限制 | 原spec、Round3/4 | 本次没有runtime/API/选择机制变动，retain Round3/4逐项已有证据，不冒称新运行；本轮只重验普通启停 | retain |
| 压缩人工/自动/停用恢复 | 原spec、Round4 owner bar | 本独立样本未做压缩；Round4人工与Round3停用恢复retain；自动普通默认未触发仍未观察 | retain / 自动inconclusive |

没有未完成旧技术计划或压缩检查点进入本普通样本，因此它证明的是另一种自然续问及明确验证对照，不独自关闭复杂压缩后的旧计划回归。caller独占压缩旅程另行记录。本reviewer在23:35左右只读其完整Work快照 `/tmp/feat614-r3/product-evidence/s614-isolate-trace.json`，观察61次工具、未出现write/install_bundle，仍在读summarizeWithLlm、preset、integration注册/attach源码；该快照是进行中观察，不提前判最终交付，但足以说明**不能把普通续问的成功推广为复杂插件开发效率改善**。没有据源码读取行为推断宿主缺陷。

### Verdict

**本增量两项必验：pass；累积unit：pass-with-issues，沿用Round4明确owner bar。** 新增阻塞问题0；保留R3-E1自动默认路径未观察的证据缺口1项，R4-S1复杂开发探索成本的历史观察不关闭。普通业务问答与明确验证均有本轮真模型直接证据；复杂压缩场景最终结果须与caller本轮完整旅程合并，不能以本节替代。进度问的长任务中段行为、浏览器视觉未覆盖，不列为已发现缺陷。

仅追加本报告，未提交；本轮Agent已idle、插件按请求保持启用。服务由caller集中清理，reviewer未停止共享栈。原始日志/凭据/运行数据不入仓库。

## Round 5B — 最终 native 全局指导普通样本复验（2026-10-18）

Validation snapshot：`8e0ec154e0bcccf4b2e2479fe5550c6b917230e5`，reviewer确认HEAD；caller已将隔离Node重启到最终产物。先前Round5A的额外全局D指导已撤回，其4.7秒普通续问和其他观察只属于 `0d23eb7e5`，不能移作最终版本的机制证据。最终相对 `c839d6777` 产品变化仅为compaction/verification参考资料；本轮未重新引入通用收口规则。保留原报告，不宣称F/G或文案消除了模型不稳定性。

继续使用独占 `s614-deepseek` / `c_wy2y81xr`、原生session `8d6ae60c-58ef-41ce-a31d-93043bd73ee3`，同DeepSeek V4 Flash / High、Codex/Luna。公开IM API驱动；未接触caller独占 `s614-final`，未重启任何服务。

| 目标 | 自然输入、实际证据与结果 | 裁决 |
|---|---|---|
| 已有业务事实简短续问 | `decadad0…`：“云杉项目首版做什么端？向供应商询价已经完成了吗？简短回答。” turn5，00:01:09–00:01:15（+08:00），约5.7秒；seq768/771 inbox check/read，seq776 send_message实际sent“首版只做桌面端。向供应商询价还没开始，计划下周三进行。”仅3调用，无技术调查或未经请求的下一步。 | pass（最终版本样本） |
| 明确启停实调 | `21d473c8…`要求再次停用试用、恢复后用现有事实生成并保持启用。turn6，00:02:13–00:02:46，约32.6秒、10调用；seq825停用applied，seq829调用unknown tool，seq832恢复applied，seq839正常输出三节与云杉落款，预算18400/桌面首版/询价未做/企微未定准确，seq851实际sent交付。 | pass（最终版本样本） |

最终公开插件API独立读取 `final-native-plugins.json` 显示enabled、无diagnostics；Work idle。完整原始证据 `/tmp/feat614-r3/reviewer-evidence/final-followup-trace.json`、`final-verify-trace.json`、对应watch日志与原始自然输入保留，停用unknown tool为预期对照，未人为放行拒绝。原插件创作仍属于Round5A版本；本节只证明最终native全局指导下普通续问/明确验证的实际表现，不证明提示词插件创建、复杂压缩或效率有普遍改善。

**局部verdict：pass；新增问题0。整体最终scope尚待复杂压缩新样本冻结后的独立核验，本节不提前放行。** 已知主侧前轮private成员错误和第二次台账漏业务事实不能由本普通样本覆盖；原失败证据须保留，复杂场景不视为业务pass。Round3/4未变化的生命周期、模板、选择边界与默认自动未观察仍按Round5A的明确保留范围处理。未覆盖浏览器视觉/物理iOS。只追加报告、未提交，服务留给caller集中管理。

## Round 5C — 最终 reference 增量独立 closure（2026-10-18）

**validated_at：`8e0ec154e0bcccf4b2e2479fe5550c6b917230e5`；overall verdict：pass-with-issues。** 最终只保留compaction/verification两份reference变化，额外全局D规则已经撤回；Round5B最终native指导的普通续问/启停实调仍有效。此裁决沿用Round4明确owner bar：默认自动未触发保留未观察，不降低阈值造压力。未声明复杂开发效率、普遍简短收口或零误导改善。

### 独立核验来源与真实边界

reviewer只读冻结证据根 `/Users/czj/Repos/nano-multiagent/output/feat614-task-scope-20261017/final-compaction-trial/` 的完整 `followup-trace.json`、聊天消息、两份manual事务、provenance、metrics、orchestration-note，以及生成插件快照中识别Inbox和继承台账的相关部分；未用caller结论、CI或离线测试替代真实摘要内容。公共IM插件API另核对 `s614-final` 当前 `decision-compaction` enabled、无diagnostics；未发送新任务、改代码或重启服务。模型DeepSeek V4 Flash / High，Codex审批/Luna；session `5688c799-44d2-4e38-834f-1a67e7d373b2`，聊天 `c_1xuqsls6`。metrics记录152次allow、0deny，其中132次Luna、20次无reviewer的确定性路径；这是该session审批统计，不是通用安全或成功率证明。

- **新指导确实进入执行**：Work记录读取包含Nano Inbox差异的reference；推理seq787明确从工具结果 `messages[].sender.type=user` 提取真人内容，首装生成插件也实际含此判断。两次真实summary的插件独立账本均出现预算28600、首版离线、周五确认报价、云同步未决。这比“Skill读过/安装成功”更强，但不能推导没有其它来源误识别。
- **首开发轮有外部干预**：68调用、456.21秒至最后item；首次write前38调用。turn1为interrupted：caller在公开交接后但Agent仍继续README修改/思考时过早正常重启。故不能称自然完成或用耗时比较效率；原始状态与orchestration-note保留。重启后idle再走公开 `/compact`，真实事务成立，不将首轮自然完成与事务成功混为一谈。
- **首真实压缩业务fail保留**：`manual-first-events.json` seq329/330/332，事务 `8d6dc40c-ac85-4f44-9502-c01d670e48f0`，聊天“已压缩129项”。独立账本四项事实俱在，但多出独立条目“供应商报价需在周五前锁定”，来源是测试夹具，不能当用户项目决定。此前其他版本的private成员运行错误及漏业务事实样本也不因本轮通过而删除或改写。
- **Agent自主修复并准确交接**：caller只反馈实际账本污染及自然目标，未代写修复。turn2正常completed，77调用、467.83秒；两次未先read的edit错误均保留并自行恢复。真实工具返回restart-required，公开交付明确当前未生效、需正常重启与新 `/compact`，未把离线检查当新摘要成功。修复包含限制真实checkpoint来源及当前已污染条目的定点清理，不能宣传为所有语义污染都已解决。
- **修复后真实业务结果**：idle后正常重启，再发公开 `/compact`；`manual-second-events.json` seq730/731/733，事务 `7ae19e26-e8e4-4b3b-a176-a01c735fb4f4`，聊天“已压缩159项”。插件独立账本仍保留四项事实，原夹具句不再作为独立决定。它仍出现在用户纠错原话“但…账本还混入了…”的引用里，普通摘要也解释其不是决定；因此不能声称全文没有该文字。账本还纳入“不要人为调低阈值”“刚才/compact已完成”“不要把测试输出”等操作说明/片段，属于剩余质量局限，非纯净项目决策表。
- **压缩后续问**：turn3 completed，29.14秒、7调用，其中4次bash寻找/读取旧chat_history导出；seq1213还枚举到相邻workspace历史文件路径，但后续内容读取限本session，未见读取他会话内容。最终seq1225实际sent预算28600/离线/周五确认报价已定，云同步未定；报价未声称已完成。下一步增加“再据此定首版范围”“暂不纳入首版承诺”，属于未被用户确认的新建议，未清楚标注建议；不能扩写成既定事实保真或无需调查。此次最终范围已撤回全局收口改动，故不把4次读取冒称对应新规则通过。

### 最终Scenario与保留结论

| Scenario | 本轮实际证据与retain边界 | 结果 |
|---|---|---|
| 普通插件业务续问与明确启停执行 | Round5B最终版本自然输入、直接业务回答、停用unknown tool/恢复原生输出、公开管理enabled | pass |
| 压缩指导中的Nano真人输入来源 | 实际读取/采用Inbox结构，首装与修复后真实台账均含四项事实 | pass（有后述来源质量局限） |
| 真实人工压缩、失败可见与修复 | 首次污染fail保留；Agent自主修复、restart-required正确交接；第二次真实事务及摘要通过目标事实核对 | pass after repair |
| 压缩后继续业务对话 | 四项状态正确且真实sent；额外读取及未标注建议保留为minor | pass-with-issues |
| 停用回落与默认自动 | 停用回落retain Round3 f09实际默认事务及续聊；本次未变runtime、启停或provider语义。默认自动新普通样本仍未触发 | retain；自动inconclusive，owner明确接受 |
| 工具/提示词/索引服务、模板、更新重启/共享/限制/客户端边界 | retain Round3/4逐项证据；最终reference变化未改相应runtime/API/选择机制，不冒充本轮重跑 | retain |

### 剩余问题与裁决依据

| ID | Severity / 状态 | 实际影响及证据 | 处理 |
|---|---|---|---|
| R3-E1 | major证据缺口 / owner明确接受、仍open | 默认自动路径未触发，仅manual有真实新事务 | 保留未观察，按Round4明确bar允许pass-with-issues；不称自动已验过 |
| R5-S1（承接R4-S1） | minor / open | 复杂首轮38调用后才write且被caller提前重启；修复77调用；续问4次额外文件探查，末尾有未明确标为建议的范围措辞 | 披露成本和表达局限，不声明效率/零误导；无本次runtime归因 |
| R5-S2 | minor / open | 修复后台账保留正确事实但仍含操作指令、纠错引用和截短片段 | 不能称纯决策表或全文清除夹具文字；当前业务事实可辨认，最终答案未把夹具句当决定 |
| R5-F1 | 首次业务fail / 修复后关闭 | 第一事务将夹具句作独立决定；第二真实事务不再如此，四事实保留 | 保留首次失败和修复全过程，不用重跑覆盖 |

最终未发现必须阻塞本次两reference交付的宿主实现问题；新增未关闭blocking/major为0，保留owner接受major证据缺口1项及minor质量问题2项。普通样本与复杂样本的证据强度分别陈述，首轮被干预不能充当无人干预全旅程成功。原生自动支持契约不变，浏览器视觉/iOS仍未验收。本轮仅追加acceptance，未提交；服务及数据由caller集中管理。

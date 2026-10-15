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

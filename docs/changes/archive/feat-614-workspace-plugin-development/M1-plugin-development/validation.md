# M1 开发与验证记录

## 实施范围与版本

- 实现提交：`7befe5a7971dbb85b37a73c46e409f18f1ca923d`；起始基线：`46d3e8c8e`。
- 2026-10-16 同步 `origin/main` 的 `59b7b3dc9`，merge head `87149580d`。上游只增加 feat-615 首文档，没有运行时代码差异；下述实现与运行证据保留有效。
- 新增有限主题的公开 API 资料发现、随包开发 Skill、六份按需资料和三个可运行模板。管理工具保留原生命周期，产品手册只保留摘要与开发入口。
- 无客户端、生产配置、DSH fork/private import 或新运行时修改。

## 测试选择

扩展既有 `workspace-tools.test.ts` 的真实 runtime 测试，覆盖查询主题、公开文件可读、非法/缺失主题、pending mutation 时查询，以及三个模板的原生安装和业务调用。保留原生命周期、失败修复、工具选择、共享/隔离、重启和压缩测试，不增加逐句文档断言。服务模板核对另一 workspace 调用不计数、停用与重新启用不重复监听。

## 本地验证

以下均在隔离 worktree 的实现 tree 执行；原始日志保留在本机 `/tmp`，不提交运行数据。

| 命令/检查 | 结果 | 证据 |
|---|---|---|
| 新增查询用例先在原实现运行 | 预期失败，原入口要求 target，不能查询 API | `/tmp/feat614-query-red.log` |
| `pnpm exec vitest run packages/dsh-integration/tests/workspace-tools.test.ts` | 1 passed，完成查询与原有生命周期回归 | `/tmp/feat614-query-green.log` |
| workspace-tools 与 builtin-skills 两项窄测 | 2 passed | `/tmp/feat614-templates.log` |
| `pnpm build` | pass | `/tmp/feat614-build.log` |
| `pnpm typecheck` | pass | `/tmp/feat614-typecheck.log` |
| `pnpm test` | 88 files / 329 tests passed | `/tmp/feat614-all-native.log` |
| frontend `npm ci`、`npm run test` | 96 files / 887 tests passed | `/tmp/feat614-web-install.log`、`/tmp/feat614-all-web.log` |
| frontend `npm audit --audit-level=critical` | 0 vulnerabilities | `/tmp/feat614-web-audit.log` |
| frontend `npm run build` | pass（真实栈静态资源准备） | `/tmp/feat614-web-build.log` |
| `pytest -m "not e2e" -q` | 56 passed / 31 deselected | `/tmp/feat614-python.log` |
| `ruff check .`、`ruff format --check .` | pass / 82 files already formatted | `/tmp/feat614-ruff.log`、`/tmp/feat614-format.log` |
| `scripts/docs-check` | 239 documents / 64 required routes passed（新增验收报告前） | 当次终端输出；最终检查见下文 |

首次模板测试曾因 macOS `/var` 与 `/private/var` 路径比较失败；测试按真实路径比较后通过，不涉及产品行为修改。主仓 dirty 文档的链接故障没有带入 worktree。

## 真实模型试验设置

本次用隔离 IM 登录/聊天/管理/轨迹 API，路径与 Web IM 相同；不冒充浏览器视觉或物理 iOS 验收。主栈 IM 61490，独立 reviewer 栈 62034；workspace、node identity、owner、数据与端口分离。执行模型覆盖 `deepseek:deepseek-v4-flash` 与 `codexOAuth:gpt-6-astra`，默认技能发现，正常 Auto 审批。自然语言任务未注入 Skill 名、API 参数、代码或成功步骤。

### 首轮环境失败（保留）

默认 E2E 审核沿用 DeepSeek，但现有审核链固定请求 `low`；该模型只支持 high/max，产生 `UNSUPPORTED_REASONING_EFFORT` / `classifier_unavailable`。首次 `write`、`bash`、管理变更被拒，插件并未写入。Agent 已自主发现开发 Skill、查资料，但出现多次无效重试；不把这轮记为成功。

仅将两套隔离配置的 `llm.tool_approval_model` 指向支持 low 的 `codexOAuth:gpt-6.1-sol` 并重启测试节点。未关闭审核、未改审批实现、未改生产配置。首轮轨迹保存在 `/tmp/feat614/first-sample-reviewer-incompatible.json`；续做使用原聊天，不能视为全新零干预样本。

### 主侧报销工具样本

- Agent `p614-deepseek`，聊天 `c_7gnqncla`，session `cc2f8614-9674-4db2-8ea8-8a98e9c29b7c`。
- 原始消息 `d52b3fc6ad4c4026ac37d09a509bf1e9`：自然要求创建可复用 CSV 报销插件，汇总 9/10 月；环境修复续做消息 `683f140ec76c4707b17451cc9e46417e`。
- 轨迹：自主 `skill(nano-plugin-development)` → 读取 bundle/tools 指导 → `describe_api(tool)` → 读当前公开声明 → write/edit 创建 `plugins/expense-summary` → 语法检查 → `install_bundle` 返回 applied → 原生 `expense_summary` 调用。
- 2026-10-16 00:08:53（Asia/Shanghai）实际业务输出：9 月交通 12.00、餐饮 49.70、合计 61.70；10 月交通 58.20、餐饮 22.80、合计 81.00，总计 142.70。与人工构造 CSV 一致，空行没有计入。
- 轨迹与聊天证据：`/tmp/feat614/p614-deepseek-trace.json`、`/tmp/feat614/c_7gnqncla-messages.json`、`/tmp/feat614/deepseek-tool-resumed.log`。
- 后续更新、调度与生命周期见下节；独立的其他类型旅程结论以 `acceptance.md` 为准。

### 真实更新发现与修复

主侧续做消息 `c86864ff6b114c91981b7841ffbec8c5` 要求新增类别筛选并组合原生 Cron。源码产生新 generation、`install_bundle` 返回 applied，但 00:12:10 的新参数调用仍返回全部类别的旧结果。独立 reviewer 的工具和服务更新也观察到相同现象。

根因由隔离 native runtime 回归确认：原生 `Entry.update` 在相同 id 的模块 name/path 改变时保留已有 fiber，不重新 import。此前只测了失败源码修复与停用状态更新，漏掉已成功实例的同名同版本热更新。`/tmp/feat614-hot-update-repro.log` 明确失败：期望 `UPDATED:HOT_UPDATE`，实际 `HOT_UPDATE`。

修复提交 `246c484ae`：integration 使用公开 `EntryGroup.remove` 释放模块路径变化的旧条目，等待原 fiber.inertia 后沿原生 root.update 加载新版；没有 patch/fork DSH。新测试核对同轮实调和同 workspace peer 实调，28.08 秒通过（`/tmp/feat614-hot-update-fixed.log`）。其他模板、生命周期与异步释放断言一起通过。设计 Changelog 记录该修正，受影响代码与真实旅程另做 delta 复验。

旧运行样本中 Agent 自主发现旧逻辑、通过停用再启用恢复新版；随后正确查出交通 58.20。它额外添加了用户未要求的 CSV 导出，因未传递正确文件服务写入策略而失败，开始偏离任务排查宿主。自然跟进消息 `24a5112c1b33441992d1579f94d0bf33` 要求停止导出/配置排查、先交付金额及定时结果；这属于有用户收窄范围的续做样本，不计作无人干预一次成功。文件工具指导补足当前会话 cwd 及公开写入策略查询提醒。

### 主侧边界咨询

独立 workspace Agent `p614-isolate`，聊天 `c_dd0we4f3`，自然输入 `b71e7cb6e47d486da6ccacfe961d5e85` 询问客户端按钮、自动批准、跨 workspace 和任意来源插件。Agent 自行读取两个随包 Skill 及有限 API 资料，最终消息 `544d747c2bc54978a5e58a1aea2fc2da` 明确客户端/宿主能力不属于支持面、workspace 不等于 OS 沙箱，且未写配置或文件。证据 `/tmp/feat614/boundary.log` 与 `c_dd0we4f3-messages.json`。模型同时泛化描述了权限卡选项，不能将该措辞当作当前 UI 控件验收；这里只验支持边界与真实只读行为。

### 主侧定时交付与修复版更新

- 原生 `schedule_create` 创建 `schedule-2da8d180-679c-4f26-b252-31f05007c655`，产品 `/cron/jobs` 可见 daily 09:00 Asia/Shanghai；`schedule_run` 接受后排入当前 session 后续轮次，没有另建循环。
- 00:21–00:22 的独立调度轮次再次调用 `expense_summary(months=[2026-10])`，`send_message` 最终消息 `ccfa0b2fd36846448440966413a9865d` 真正进入原聊天：交通58.20、餐饮22.80、合计81.00。任务创建、接受排队与真实收件分别取证。
- 00:22 后主测试 Node 重启为 PID43896，加载修复版 `246c484ae`。消息 `8d3424fe031a442fbc06bde3da9f1eb2` 自然要求先复用已有插件、再增加类别笔数并删除测试日报。重启后原生查询9月餐饮49.70成功，安装与启用状态保留。
- 模型自行编辑原插件、重新安装；00:26 的首次新功能原生调用已显示9月餐饮2笔/49.70，无需停用再启用。随后全量实调：9月交通1笔/12.00、餐饮2笔/49.70；10月交通2笔/58.20、餐饮1笔/22.80，总6笔/142.70，符合原CSV。模型曾在更新前的进度消息误称餐饮1笔，最终通过真实新工具结果纠正；不能把其进度自述当业务真值。
- 定时任务已删除，产品 `/cron/jobs` 最终返回空列表，保存 `/tmp/feat614/final-cron-jobs.json`。合成源码与CSV保存 `/tmp/feat614/final-sample/`，不含生产数据或配置。
- 最终运行时全量 `pnpm test`：88files/329tests pass54.79s（`/tmp/feat614-native-final.log`），`pnpm typecheck` pass（`/tmp/feat614-typecheck-final.log`）。热更新涉及运行时，故复跑该范围；未变的前端/Python检查保留先前有效证据。

### 调度指导与现场清理

`972b047ac` 仅补充 `verification.md` 的排队指导，依据两套真实模型样本和 `global-agent.ts` → `schedule.command` → `agent.followup` 实现：accepted/pending 不是业务完成，当前主轮应收口再观察调度结果，不应 sleep 或重复触发。该文档增量经独立 code-review Round3 和 verifier 静态核对；未把后续人工收窄的成功样本声称为新指导的独立一次成功实验。

主栈已执行 `scripts/e2e-down.sh --wt <本worktree>`，终止自己创建的 tmux `feat614-stack`；PID43896已退出，61490端口关闭，无对应DSH进程。共享模型代理未停止。独立 reviewer 栈也已执行 e2e-down，终止自己的 tmux `feat614-review-stack`；Node50668、DSH50672已退出，62034端口关闭。原始证据保存在 `/tmp/feat614-review-evidence/`，共享代理与生产服务未动。

## 证据解释与限制

本次证明的是指定模型、配置和有限自然任务下的可创作、可实调及可管理性，不是任意插件需求的一次成功率。轨迹中的资料发现、接口查询、代码生成、安装返回、业务调用、最终聊天收件各自独立核对。模型首轮错误包括路径基准、schema、过度压低压缩阈值、额外导出与排队调度等待；环境审核档位不兼容及宿主热更新缺陷另列，不混成同一种“模型没理解”。

后续成功样本保留原始失败，不把模板测试、手动改写模型源码、宿主重启或用户收窄需求冒充完全自主一次完成。测试使用正常Auto与明确兼容的独立审核模型，当前默认DeepSeek审核档位不兼容并未在本PR修改。生产默认配置、浏览器视觉及物理iOS不在这些证据覆盖范围内。

## 最终同步与门禁有效性

最终同步基线 `08b06c57b`，集成tree `a60a3239e`。上游相对前次基线只有feat-615设计、原型与delta文档，未改变本unit运行代码、current契约或测试配置；runtime实际验证仍为 `246c484ae`，最后Skill指导审查为 `972b047ac`。设计Gate2保留：热更新修复只兑现已确认生命周期，仍用公开DSH接口；code review三轮、full verification及corrected-delta、独立产品Round2均按各报告记录覆盖。后续canonical归并和整目录archive仅同步已审契约与路径，不扩大功能；最终PR记录具体head及effective范围。

最终canonical归并、整体archive及相对链接调整后，`scripts/docs-check`通过（241 maintained Markdown sources / 64 required routes），`check_change_unit_archived.py --head-ref unit/feat-614-plugin-development`通过，`git diff --check`通过。该批仅已审文档归并、报告与路径调整，保留所有门禁结论；原始日志 `/tmp/feat614-docs-final.log`。

## 2026-10-17 原生语义修订的现行证据

以上在线热更新、低阈值压缩及旧门禁有效性属于历史。本节及对应报告的新 Round 取代其对本次交付的成功判断；冻结实现 `f56e5e6d89cd496ef0bcdf75816db37313281a63`，已集成并最终核实 `origin/main@481467ac16f0eda4561fca5c8230050541600de9`。

- 上游 Skill/MIT 适配、原生覆盖安装结果、公开 EntryTree 恢复、模板 DSL/peer 等变化见 [原生回归证据](../evidence/native-semantics-revision.md)。旧实现对待重启更新报 applied 的有效红测保留；修订后相关真实 runtime 与 Skill 装配窄测 2/2 通过。
- 完整 `pnpm build`、`pnpm typecheck`、`pnpm test` 通过（93 文件/346 测试，120.69 秒）；`pytest -m 'not e2e' -q` 56 通过/31 deselected；前端 96 文件/887 测试通过（49.46 秒），critical audit 为 0；ruff check/format 通过（83 文件）。本轮未改 iOS，按远端变更门判定。
- 日志在 `/tmp/feat614-revision-{full-build,typecheck,all-ts,py,frontend,audit,ruff,ruff-format}.log`；归并前 docs-check 235 maintained Markdown sources/64 routes 通过，最终归并后再核对文档完整性。
- 独立设计 Round 2/3 Approved（各 0/0）；独立静态 code-review Round 4 pass、verification Round 2 delta pass/corrected-delta aligned（0/0）。后续仅已审 delta 归并、报告和归档文档变化，按实际内容保留实现门禁，不因提交号机械重复全量。
- 主侧全新模型自然任务见 [新 Agent 实测](../evidence/fresh-agent-revision.md)：确实读取新 Skill 与当前 API，首装工具返回 6500 分、更新待重启保留旧结果、正常 Node 重启后原生新版返回 5600 分；报告格式/普通聊天、Cron 排队后结束当前轮并后续发送均有真实结果。离线桩测试、探索浪费、审批拒绝和不准确的目录措辞没有隐藏或算作原生活性成功。
- 独立产品的新样本与跨 Agent 自生成 Skill 副作用分别记录在 [acceptance](../acceptance.md) 新 Round；索引另用独立 owner 对照，避免把学习结果混算给随包指导。自动压缩未触发时不宣称该路径已有新普通场景证据。
- `f09df0d25` 后续只补压缩参考的用户 `/compact` 入口/结束当前轮交接，运行时代码未变。装配窄测 1/1、构建通过；code-review Round 5 与 verification Round 3 pass/aligned，保留前述实现和完整工程证据。新身份的压缩对照按 acceptance 新 Round 单列，未以旧样本代替新指导。
- 独立产品 Round 3 将普通默认样本自动未触发记为 R3-E1 open/inconclusive。owner 按用户最新“常规场景”与事前设计说明验收边界，设计 Round 4 独立 Approved（0/0）：自动/人工支持契约不变，允许其他必验通过且无实现阻塞时 pass-with-issues；该缺口不关闭、不伪写为自动新样本通过，旧 Round 3 fail 保留。
- 最终独立产品 Round 4 **pass-with-issues**：新原生人工压缩247项、插件独立台账块及续聊通过；R3-E1自动未观察保持inconclusive，R4-S1模型调查负担/审批摩擦保持minor，未宣传效率改善。已审delta按同名Requirement归并canonical，无重复追加；完整报告与合成证据身份保留。四个专用栈与自建tmux均清理、端口关闭、Node/DSH退出，详见新Agent证据。


## 2026-10-18 最终 reference 收口

本轮实际产品差异仅 `references/compaction.md` 与 `references/verification.md`，冻结实现 `8e0ec154e`；`global-mode.ts` 实验及新增 global delta 已撤回，canonical 无新增变更。设计 Round7、code-review Round7、verification Round5 覆盖最终范围；真实产品的自然修复、两次压缩、简短续聊、首次失败和测试编排失误见 [最终实测](../evidence/task-scope-revision.md) 与 acceptance 最新 Round。

最新main为 `481467ac16f0eda4561fca5c8230050541600de9`，本轮多次fetch未推进，已是HEAD祖先。实现后只追加验收/证据/交付文档，已有设计与静态门禁按内容保留至最终文档提交；无运行时、审批、生命周期、前端或iOS改动。最终窄测3文件4项通过；完整TypeScript93文件346项、前端96文件887项、Python56项、typecheck/build/ruff/format/audit通过。完整TS首次workspace-tools超时与复跑通过均保留，不宣传效率改善。

独立普通样本最终版本下通过，复杂样本首次台账污染、Agent自然修复、真实再次压缩以及仍有多余调查全部保留。自动压缩未自然触发仍为inconclusive。工程通过、安装/启用、摘要事务完成、自定义账本正确及聊天收件各自独立取证；不把首开发轮interrupted写为自然收口。


最终产品Round5C pass-with-issues，新增阻塞0，保留自动未观察和两项minor质量/成本问题。owner接受独立结论，未以成功样本覆盖原失败。隔离栈/Node82000/DSH、64068端口和自建tmux均已清理，合成证据保留于主仓本机output，专用runtime/auth/config/key已移除，共享代理及生产未动。最终effective_base仍为481467ac16，effective_through为本轮仅报告的交付提交；PR写入实际完整head。

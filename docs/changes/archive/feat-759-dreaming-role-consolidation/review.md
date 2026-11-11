# feat-759: Review

## 范围与版本

- 对照 [需求](spec.md)、[设计](design.md) 和 [Gate 2 审查](design-review.md)，核对角色约定的读取与写入、Web 和 iOS 人工编辑、记忆层级与重组提示，以及 Dreaming 提交和恢复。
- 独立代码审查的 `executed_base=89f16d365`，最终代码闭环 `validated_at=5206d8c96`。隔离真实旅程分阶段在该基线的实现上执行，批量 Git 提交另有真实模型验证。
- 交付基线 `effective_base=480436600`，有效代码范围至 `effective_through=6383925b3`。`git range-diff` 确认四个实现提交在重放前后等价。后续提交只补 Agent 配置页的测试 mock。上游改变了 root native 会话恢复，补跑了该入口及记忆、配置链路的相关测试。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 主 Agent 主动对齐角色，明确确认后才写；Dreaming 只读且使用同一约定 | Context 自检、独立代码审查、隔离真实模型 | 通过 | 未配置的独立 Agent 主动询问长期分工；用户提出职责后只收到拟写文本，配置 API 仍返回空。用户明确确认后 API 读到原提议。定向用例覆盖现有会话、PA 输入边界、Feishu 映射及角色 Markdown 原文。 |
| 配置入口的编辑、清空及版本冲突 | 独立代码审查、Web 和 iOS 真实入口 | 通过 | Web 真实隔离 IM → Node → DSH 环境验证空态、保存、重开、两端并发返回 409、保留草稿及清空；iPhone 17 模拟器验证普通保存与角色保存分开、重开、冲突保留草稿和用户主动重试。 |
| 复盘保留取材证据，正式记忆按角色重组和维护首页 | Context 自检、隔离真实模型样本 | 样本通过 | PA 与独立 Agent 各一轮独立合成数据对照。独立 Agent 首页 831 → 306 字符，保留修订结论和适用例外；PA 首页 620 → 391 字符，保留长期偏好和例外，细节进入链接页。样本早于 Git 提交改动，未用生产记忆做对照。 |
| 整合 Agent 批量提交，正式 Git 状态决定完成 | 独立代码审查、隔离真实模型、确定性 native 回归 | 通过 | 真实模型主动调用一次 `git_commit`，同一实际提交含两页，工作区干净且回执为 2/2 页。确定性用例另覆盖同一 native 会话收到未提交状态、继续编辑其中一页、统一提交，以及未完成时不推进来源。存储用例覆盖 CRLF、执行位、已暂存状态与中断恢复。 |

## Findings 与关闭

- 角色 Markdown 中的模板样式文本被二次插值；`b6f3ce423` 将正文作为一个替换值注入，独立审查与 Context 回归复核原样可见。
- Feishu 原始 actor 不能直接与 Node 主人帐号相比较；`b6f3ce423` 沿用实际绑定映射生成由宿主证明的身份，保留原始 actor，独立审查复核匹配边界。
- 临时索引的提交与工作索引刷新间中断、CRLF 文件暂存变化、Markdown 执行位丢失会导致状态误判或无法继续；`6ac67141b` 和 `5206d8c96` 修复恢复路径及精确暂存，独立审查在 `5206d8c96` 复核通过。
- 无存活 findings。用户明确排除 Work 轨迹改动。

## 流程收口

- 独立审查复核 Gateway 与 IM delta，区分角色配置访问范围、仓库有差异时即使无新来源也可运行，以及成功须实际检查 Git。同步归并对应 current spec。
- 同步 develop 后，受影响的后端及会话恢复定向回归 13 组共 100 项通过，Web 配置页定向回归 4 组共 66 项通过。相关构建、类型检查、iOS 交互资源检查和文档检查通过。此前本机全量后端有超时和 worker 错误，另有已在定向回归修复的旧测试预期。
- 真实角色、记忆样本和 Git smoke 使用隔离账号、合成历史及工作区，独立 Web 服务和 iOS 模拟器已回收。保留本机脱敏证据供本次评审使用。
- 自动化和真实样本均为工程验证。禅与 PA 的生产记忆尚未经本变更运行，亦未做用户亲自验收。

## PR #520 角色文件异常补验

- 旧版 native 请求在已保存文件超限时只说相关时再读。补验捕获实际主 Agent 请求，确认超限与读取失败都指示当轮优先检查文件并私下通知维护者。已确认未设置仍使用角色澄清，超限内容没有进入常驻角色上下文。
- 独立复核发现普通诊断读取可能跟随被设置接口拒绝的符号链接，以及部分单会话配置当轮没有私下投递入口。最终复核确认诊断读取和设置复用同一路径检查，原生工具轨迹没有带出链接目标正文。通知按现有工具和私聊可达性投递。
- 后端定向 32 项、Web 配置 27 项、类型和文档检查通过。两个隔离真实模型用例分别用超限文件与目录代替文件，均先调用 read，再向同一个测试维护账号发出简短的修复通知。消息工具调用进入隔离投递接收器，未使用真实 IM 会话。

## PR #520 超长首页加载补验

- 用隔离 native 请求复现旧路径提示。将禅原 9,461 码元首页的本机副本交给新版装配，实际请求载入开头 7,828 码元及省略提示和完整文件路径。7,850 码元副本载入全文，三个测试文件均未被加载操作修改。
- 原生回归覆盖跨行列表项、嵌套列表、字面花括号和 8,000 码元边界。独立复核提出预览原文可能触发模板插值，改为按变量传入原始文本后闭合。记忆文档、前台请求和 Dreaming 原有提交路径定向 24 项通过。

## PR #520 超限角色约定修复补验

- 过长文件先核对原文，再由主 Agent 向维护者主动提出保留原意的限长稿。隔离 GPT‑6.1 Sol 对 3,082 码元的测试文件先读并发出完整 82 码元精简稿，确认前文件未变。测试维护者在同一会话明确确认后，实际工具顺序为 read、write、read。保存内容与提议一致，回读后才报告修复。
- 独立复核确认修复回读要求保留在通用角色上下文中，写入后即使文件变为合规状态，下一次模型请求仍有该指令。读取无法取得完整原文时，先与维护者补齐。后端定向 32 项及文档检查通过。

## PR #520 记忆快照与换窗去重补验

- 用户确认详情页变化无需提醒。移除逐请求版本扫描和变更通知，同窗复用首页快照。
- ce4e692c9 的 HTTP 回放复现 PA、Global 手动及压力换窗同时发送 A、B，详情页通知出现和消失又追加两份 B。
- 修复位于独立 dsh-agent-context 组件，检查点仅含窗口导航和恢复提示，主动换窗与 overflow 重试恢复一次当前上下文。手动和 turn-stopping 换窗由下一请求装配。Nano 删除换窗补偿并接入 0.3.0-rc.10。组件无需了解 Nano 的记忆文件。依赖变更见 https://github.com/Mrchen116/dsh-agent-context/pull/6 。
- 原生组件 40 项测试通过，Nano 请求重校验、前台记忆、子 Agent 记忆和缓存前缀共 8 项通过。PA、Global 各 16 轮 HTTP 回放覆盖手动与压力换窗，同窗第 11 轮和重启后仍使用 A，换窗首请求仅一份 B，详情变化及下一请求仍仅一份 B。另验证手动换窗后、首请求前改成 C，该请求读取 C，随后重启仍仅一份 C 和 ROLE。
- 独立 change-code-review 审查者 checkpoint_review 检查两仓 diff 和原生 RuntimeContextProjection，结论通过。修复前后请求位于本机 /private/tmp/nano-role-wire-evidence 与 /private/tmp/nano-role-wire-fixed，测试资源已回收。HTTP 响应为受控 provider，未测服务商缓存命中量。

## PR #520 窗口标识与整体 Context 补验

- 用户指出 rc.10 检查点与当前快照仍各带窗口标识。rc.11 删除检查点窗口段，窗口身份统一从当前快照提供。原生 40 项测试及 Nano 5 项请求/前缀测试通过。
- PA、Global 的手动/压力换窗各跑 16 轮 HTTP 请求，逐轮验证窗口段、首页、ROLE 单份。另使用默认工具和实际内置 Skill 目录回放，通读首窗、换窗首请求和下一请求的 system/messages/tools。换窗首请求为恢复提示、当前上下文、Skills 目录、绑定发送者、用户输入五条消息；下一请求仅追加回复和新输入。
- 作者与独立 agent-context-review 检查来源、当前权限、ROLE、记忆和动态技能目录的对应关系。发现共用 system 的旧句仍把职责归入 Memory，现已改为背景与经验；Skills 引导均有目录名称和工具入口。测试正文的 discussion-only 要求保留，history 的 window/item 参数及 notes 恢复入口可用。
- 既有 history 工具对 private contents 的保密措辞可能影响模型概述恢复的用户原话，记为范围外语义疑点，未观察到实际误用。此次验证实际 HTTP 内容，响应由受控 provider 返回，未声称真实模型的任务恢复或缓存命中评测。完整请求位于本机 /private/tmp/nano-context-whole-review，并已更新 HTML 展示。

## PR #520 产品 Inbox 请求补验与证据边界更正

- 用户指出此前展示中的直达用户正文绕过了产品 Inbox。上述 16 轮回放直接使用 `session.submit`，验证了底层装配与前缀，但不能代表完整产品消息流；此前五条消息的描述仅对应该测试入口，不能作为产品上下文合理性的验收结论。
- `79e25f569` 已移除额外的 ROLE 发送者标签。此版本新增本机隔离回放，经实际 `GlobalAgent.receive`、Inbox 存储、产品工具桥接和 DSH 捕获 HTTP 请求。Global、PA 各覆盖首次请求、Inbox 读取后的请求、手动换窗首请求及其读取后请求，合计 8 份；正常结束，无异步错误。
- 换窗首请求依次为恢复提示、当前上下文、Skills 目录、Inbox 系统通知；下一请求追加 assistant 的 inbox 调用和 user 角色的 tool_result。用户正文只存在于成功的工具结果，PA sender 含 is_owner；未追加直达用户正文或 ROLE 身份标签，窗口、首页与 ROLE 无重复。
- IM relay 和模型响应为受控 fixture，非 Web/IM 端到端测试，也不证明模型自主选择。HTML 默认切换到产品 Inbox 样本，旧直输样本明确降为底层验证。完整请求和回放脚本保存在本机可视化目录的 `inbox-context-evidence/`；临时运行时、数据库、workspace 与监听端口已回收。

## PR #520 补齐系统角色视角

- 依据用户确认的目标，将整合开头改为为主 Agent 的未来工作保留和组织信息；系统角色、Persona、ROLE 共同提供选择视角。原始经历决定事实、适用范围和不确定性。
- 每批通过主 Agent 的公开 `systemPrompt.assemble` / `renderPrompt` 复用当前产品身份、Global 分工与 PA 角色段落，作为主 Agent 背景注入；不复制工具 schema、Skills 目录或前台记忆快照，不扩大 Dreaming 工具。未设置 ROLE 仍有系统角色定义。预算和恢复继续使用同一批次快照。
- 作者按 agent-context-review 核对 PA / Global 实际 HTTP 请求；独立审查者 dreaming_role_context_review 按 change-code-review 审查 `6eb6daaa4` 后的六文件补丁，findings 为空、契约 aligned。构建通过；dreaming-runtime、dreaming-cycle-runtime 两文件 7 项通过；文档检查通过（初次系统 Python 缺 PyYAML，改用现有项目 venv 后通过）。
- 三个全新隔离 Agent 用相同合成经历，Dreaming 使用真实 `codexOAuth:gpt-6.1-sol`。发布协调 ROLE 先突出交接和约束；编译性能 ROLE 先突出基准有效性并分开协作与个人偏好；未设置 ROLE 的 PA 先保留主人的持续帮助偏好，技术经验进入 workstreams。三批均 completed，分别保存 3、4、3 页，模型实际调用 git_commit 并通过宿主检查。均保留用户报告、未独立复现的证据限定；没有聊天或派工工具调用。
- 真实模型样本显示重点和组织方式的差异，不证明全库质量显著提升，也未单独隔离系统角色段落的因果贡献。前台响应及 IM relay 为 fixture，非生产或 Web 端到端验收。完整请求、输出、页面和脚本保存在本机可视化目录 `role-perspective-evidence/`；测试端口、运行时、工作区已回收。HTML 仍只展示 Global 首次收信、PA 首次收信及两类 Dreaming 的 PR 前后对照。


## 2026-11-11 增量：统一到 ROLE（实施验证，独立审查待收口）

范围：删除用户 custom_prompt/Persona 与 Dreaming custom_instructions，PA 默认服务指导进入系统角色；Web/iOS 创建通过一次性 initial_role 保存 ROLE，既有 ROLE 独立编辑。后向兼容不做，部署迁移仅由 [deployment-prompt.md](deployment-prompt.md) 约定。

- Web 7 个相关套件 105/105，最终创建与预览相关 44/44；TypeScript 通过。iOS arm64/x86_64 模拟器构建及 AgentContractsTests 11/11 通过，专用模拟器与构建目录已回收。这些是组件/协议验证，不冒称原生 UI 旅程。
- IM/Node/PA 创建和恢复：初始 11 文件 125 测通过，追加 3 文件 24 测通过；完整类型检查及文档检查通过。
- Runtime 首批 6 文件中 25 通过、2 个测试超时；相同代码低并发重跑相关 16/16 通过。第二批发现两个测试 fixture 问题：把 PA 根默认职责错误地期望于 worker，以及新创建测试没有关掉依赖能力的默认 Feature。按真实职责边界与合法配置修正后，相关 10/10 通过，其余 41 个相关测试原已通过。未将首轮失败隐藏为首次全绿。
- 重新捕获 Global/PA 的第一条产品 Inbox 请求、读取工具结果后的请求、自动 Dreaming 请求（各 3 个实际 HTTP 请求）：PA 系统服务指导只在 PA 系统角色中出现；ROLE 在主请求中跟随文件路径原样展示，在 Dreaming 中作为背景数据；不再出现 custom_instructions/Persona。系统职责仍包含长期负责、委派完整事项、执行者拥有实现验证、主 Agent 对外协作交付。Dreaming 继续区分背景与本次原始证据，不继承主 Agent 的业务执行任务。完整请求和脚本在本机 evidence/role-unification-20261111 与可视化 context-comparison-evidence；模型与 IM relay 为受控替身，不是模型质量实验。
- 隔离迁移演练使用合成 SQLite、配置和工作区：6 种已准备内容方案（原样 PA 默认、空 Global、自定义、默认加附加、已有相同 ROLE、无冲突合并）、角色写入后中断恢复、重复执行、后续编辑停止覆盖、配置不变量及一致备份回滚均通过。冲突/超限需要人工确认方案，已审阅提示词，不宣称脚本能自动判断语义冲突。脚本与结果在本机 `role-unification-20261111/feat759-role-migration-check.py`、`migration-check.json`。未执行生产迁移。


### 统一 ROLE · 独立审查与修复

审查者 role_unification_code_review，validated_at `349e6bc728e5073bc0a57083222737ceda66c2f7`，executed_base `480436600632866d188221df654ecb9af4d031ed`。代码/delta 和非视觉 Context 合并审查。本轮新增范围，不重新审未改部分。

- Context：独立通过。审查者亲读 Global/PA 首次、Inbox 后续和 Dreaming 完整相关输入及四条实链路出站请求；固定 PA 指导、系统 Global 分工、ROLE 与原始经历清晰区分，未见旧 Persona/custom_instructions。创建重启保留初始 ROLE；配置和 fork 历史保留旧快照，最新快照明确替代，符合现有 ROLE 更新规则。受控模型响应，不作为真实模型理解或完整 daily 验收。
- R7-C1（P2）：ROLE 写入后丢失 prepare 回包，Node 将未知结果转成永久拒绝。修复：仅带初始角色的 prepare 传输异常继续抛出，让已有 receipt 保持 pending；明确业务拒绝照常返回。补回包丢失后同意图继续的定向测试；普通无角色配置错误路径不变。
- R7-C2（P2）：部署说明漏掉 legacy memoryMode 不读 ROLE。修复：准备阶段枚举模式，此类对象有需保留用户说明时，在删旧字段前停止批次；先明确切换 document 的部署决定或保留旧部署，不自动迁模式、不兼容读取。此限制属于部署计划审阅，合成脚本不声称能自动判断迁移语义。
- R7-C3（P2）：已有目录角色冲突被显示成通用配置刷新。修复：runtime 返回有含义的说明，Web/iOS 创建页单独解释保留现行约定（清空初始草稿）或换目录，并保留草稿。Web 补角色冲突与保留草稿测试。
- R7-D1（P3）：current 与 delta 中“未填写则未设置”限定错误。修复：省略初始值保留现行约定，新空目录才未设置。

作者真实 Web 操作：隔离 daily 栈（团队 seed 因能力目录 504 未完成）中创建 `role-ui-check`，填写两行角色，进入配置页读到相同内容，再独立保存修订角色；页面显示 Role agreement saved，普通配置仍 No changes。实际窄屏画面中职责说明、正文、独立保存按钮相邻，旧 Custom Instructions 已不存在。只观察 Web；iOS 本轮为编译/合同测试，未重复真人界面旅程。测试 Agent 没有聊天/模型调用，现场随后停止并回收。

完整本地基线验证：TS/runtime 235 文件 1,334 测、Web 122 文件 1,185 测、Python 非 E2E 135 测、全库 typecheck、ruff 与文档检查通过。上列修复之后补跑受影响的定向验证，不因仅新增说明和错误路径而重复全部成功套件。额外 Global Inbox 回归已通过；群延迟发送 fixture 适配当前 ID 后缀与审核器身份后真实链路也通过（33.46s），未改产品逻辑。


定向复验 `ffcc243aa`：独立审查者确认 C2/D1 关闭、Context 结论保留，指出 C1/C3 各有剩余路径。C1 在 ordinary runtime 尚未恢复时，立即重试可能从配置队列启动 runtime，而 onReady 又等待恢复该队列。修复为携初始角色的 ordinary prepare 在离线时直接抛出 pending；由既有 supervisor 恢复后重放，避免互等，专门分区测试验证不会从该调用启动 runtime。C3 Web 清空原先仍发空串；修复为省略空白初始值（非空保留原文），补清空后第二次创建请求断言。两组后台 19/19、Web 创建 16/16 通过；iOS 最终构建通过。


### ROLE 增量最终结论

独立审查者在 `5b5633f8fb1e7397dca658d3f7598fb82463ec00` 定向复验：C1/C3 关闭，C2/D1 与 Context 原结论保留，无新发现。审查者用 Node 24.22.1、实际 RuntimePartitions / ConfigurationOperations、内存 SQLite 与受控 runtime 重跑此前互等复现：写入后回包丢失保留 pending，立即重试不启动 runtime；就绪后恢复 applied，同一角色只写一次。Web 空白值的最终 JSON 省略已核实。

交付增量已归并 current specs，PR #520 继续面向 develop，不自动合入或部署。生产迁移尚未执行。所有本轮隔离服务、端口、专用 iOS 模拟器及临时构建/运行目录已回收；受保护的合成原始请求、迁移演练与摘要长期保留在本机 `~/.local/share/nano-multiagent/evidence/role-unification-20261111/`，不含运行凭据。保留开发 worktree 供 PR 审阅，合入后再按规则清理。

## 2026-11-11 Dreaming 输入与直接提交增量

设计 Gate 2 Round 9 Approved。实施初版 `66ae2e2ec`，独立 code/context reviewer `dreaming_input_code_context_review` 审查 `89ef39c0..66ae2e2ec`，亲读 Global/PA 实际 wire 首次、Inbox 结果后、Dreaming 首次和批次文件读取后请求；判定 implementation-mismatch，六项 confirmed：

| ID | 问题 | Author resolution |
|---|---|---|
| D-CTX-01 | 嵌套 IM 字符串时间丢失 | 接受；保留 ISO 字符串时间及独立工具执行时间，加入渲染回归。 |
| D-CTX-02 | 原生 read 单行截断无法靠行分页恢复 | 接受；prompt 明确用 Bash 有界字符分片续读，native runtime 用例先经历真实 read 截断再读出尾部。 |
| D-CTX-03 | assistant tool-call 块绕过配对工具预算 | 接受；assistant 只选文本，无文本不占其优先预算，工具调用与结果仍成组；加入小预算拒绝结果反例。 |
| D-GIT-01 | 删除首页后失败使下一批无法启动 | 接受；维护输入明确缺失首页及恢复要求，同进程删除后失败再修复用例覆盖。 |
| D-GIT-02 | 未提交非法路径在状态反馈前被仓形校验终止 | 接受；先反馈真实 Git dirty 路径，clean 后再验证文档形态。 |
| D-GIT-03 | 后批只补提交时旧保存回执仍显示未提交 | 接受；观察实际 HEAD 时补齐内容仍匹配的旧回执，成功摘要明确正式仓干净。 |

原生 Bash 使用公开 scope 配置禁后台/超时提升，超时及取消后无延迟写入测试通过；普通 Agent 仍开放原有后台参数。既有未修改超长首页例外保留，设计已明确，不将本次只更新详情变成强制重写首页。

模型材料与调用发生变化，评测 fixture 同步改为原生 Bash 读取真实文件、普通 Git 提交及动态范围恢复；保留长消息跨批次、100 次模型调用预算和换窗/未来证据边界。样本材料预算从 1000 调整为 2000，以涵盖新增定位开销，长消息仍必须分页；不增加运行时代码兼容。

本轮全量首次运行暴露旧 fixture 和本机运行时超时；保存原始日志，不把首次结果宣称通过。修复后冻结版本重新验证。最终独立复验与完整结果在下节追加。

### Dreaming 输入增量最终复验

独立审查者 `dreaming_input_code_context_review` 对 `66ae2e2ec..1af0abff2` 复验上述六项问题，全部关闭，无新发现，最终 delta aligned。审查者独立运行来源与文档仓测试 37/37，并亲读修正后的 Global/PA 实际请求与真实模型结果。后续 `9f36794a1` 仅将固定 system 的测试比较限定为消息正文，排除每次请求的随机消息 ID；产品实现未变。

- 实际 HTTP 抓包经产品 Inbox 和 RuntimeClient，Global/PA 各四次请求覆盖首次通知、Inbox 返回、Dreaming 首次和读取材料后。固定 system 与动态批次分离；原始 IM 时间、聊天目标、调用和结果仍在材料正文中。响应为受控 fixture，只证明请求装配。
- 两个全新隔离 Agent 使用真实 `codexOAuth:gpt-6.1-sol`：有发布协调 ROLE 的 Global，以及未设置 ROLE 的 PA。两者均自行读取材料、写入详情、读回、更新首页，再用原生 Bash 执行普通 Git 提交，各保存四页，仓库干净且批次 completed。Global 优先突出发布交接与约束；PA 优先保留主人的长期负荷和帮助偏好。两者均保留用户回顾报告、性能结果未独立复现等证据限制。这是代表性合成样本，不证明全库质量显著提升，也不替代先前禅历史回放。
- 定向运行覆盖子调用/结果预算、原生 read 长行截断后的 Bash 续读、同会话脏仓反馈、缺失首页后同进程恢复、旧回执补提交、取消/超时无后台延迟写入，以及跨窗口恢复与材料预算。构建、全库类型检查、Ruff、文档检查及 Python 非 E2E 135 项通过。
- 最终本地全量运行 236 文件、1,349 项中 223 文件/1,330 项通过，13 文件/19 项失败，主要为运行时和能力检查超时。冻结 `9f36794a1` 后用 `pnpm exec vitest run --maxWorkers=2` 复跑全部 13 个失败套件，82/82 通过（包括完整六项评测运行测试），未再调整实现或超时阈值。保留原始失败与低并发复跑日志，不能将组合验证说成首次全量通过。该提交的远端后端、前端 CI 已通过，最终提交状态以 PR 检查为准。
- HTML 更新为 Global 首次 Inbox、PA 首次 Inbox、Dreaming 三个场景，保留 PR 前后实际消息分组，并可展开本批材料文件。内容与结构检查通过；浏览器策略阻止本地 file:// 预览，本轮未做视觉复验。

原始请求、模型输出、页面、脚本和完整失败日志保存在本机受保护目录 `~/.local/share/nano-multiagent/evidence/dreaming-input-20261111/`，不提交运行数据。真实模型测试使用隔离端口、身份、数据库及工作区，运行结束后回收临时运行资源；保留证据和 PR 开发 worktree。未操作生产记忆、部署或合入。

### 输入标签与摘要场景补充

- 按用户反馈移除整合输入中的全局 `Omitted or deferred sources` 清单，调度、读取失败及延后原因继续留在宿主状态中；材料已有的局部截断、选材说明及补读方式保留。摘要索引的新增、更新和无信号替换均明确称为 `Subagent trajectory summary`，固定指令和来源目录采用相同称呼。
- 构建及相关两个 runtime 套件最终 13/13 通过。中途一次失败来自测试替身仍按旧 `task summary:` 标签判断恢复分支，同步其识别文字后通过，未调整产品行为或超时。
- 新增 HTML 第四个场景“Subagent 轨迹摘要”，对照 `480436600` 与本 PR。两套隔离原生 fork 分别运行继承条件、委派输入、读取合成酒店材料和返回结论，再捕获摘要的 DSH `llm/stream` 请求，各含三条消息和四个工具。两个捕获用例通过；这是模型请求层的实际输入，响应为受控替身，不冒称 HTTP provider 抓包或真实模型质量实验。其余三个场景仍使用 HTTP 请求，Global/PA 新抓包确认已移除全局清单。
- HTML 内容及四页签关联检查通过，未重新尝试此前受浏览器策略阻止的本地页面预览。捕获脚本、请求及日志保存在上述证据目录的 `labels-and-extraction/`；本轮临时测试文件、工作区、进程和端口已回收，既有用户试用服务保留。

### 纠正摘要样本：使用普通 Global subagent

用户指出 Global 默认不开放 fork。上节 fork 抓取只能证明可选 fork 路径，不能作为普通子 Agent 的代表；HTML 已以普通入口的 PR 前后样本替换，原件仅保留作历史证据。

- 根 Agent 通过实际 `subagent` 工具后台派工，工具列表没有 `subagent_fork`；子 Agent 原生 descriptor 为 `spawn`，没有通过 hook 直接创建或复制父会话。模型响应仍为受控替身。
- 同一委派明确转交需要的条件，普通子 Agent 读取合成文件，再实际调用 `send_message(agent_id="root")` 回报。摘要输入包含委派、读取、回报及其结果，均属于子 Agent 自身经历；委派中引用的条件标为 agent/delegated input，不冒充系统直接见到的真人原话。
- 主会话另放一条未转交的 sentinel；子 Agent 请求和摘要均不含它，也没有继承背景正文或 `host_attested_human` 标记。新增普通入口回归测试保护该边界。PR 前后两套捕获用例通过，正文已亲读；临时测试脚本、原始请求和日志在 `dreaming-input-20261111/ordinary-extraction/`，运行资源已回收。
- 初始捕获脚本错误地覆盖所有 Agent 的工具展示配置，导致 root 创建异常以及 Dreaming 重复配置冲突；删除该测试覆盖、沿用默认组合后通过。没有为此修改产品代码或启用 fork。

### 原文轨迹、来源短标签与连贯请求展示

- 受审增量 `e126a7bca..92dd6f75a`，修复 `92dd6f75a..9c755862b8`，executed_base 仍为 `480436600`。用户确认工具原文、重复读取和调用语义优先：取消按工具名／记忆目录及会话来源删改轨迹；Inbox/conversations 不去重、不重排、不合并片段。主／子轨迹共用转换，`[main agent]` 区分真实委派与主 Agent 来信，其余采用来源短标签，删除 evidence 权限解释。广泛 Dreaming prompt 精简继续搁置。
- 保留子轨迹的输入及 Inbox 优先、同层最近优先、调用结果成组和源顺序；主轨迹连续分页。没有实际遗漏时不生成说明，继承中的非消息事件不计为证据缺口。超长调用参数与返回原文都能分页，预算提升不重发已完成片段。
- 构建及记忆相关 15 文件 85 项通过；最终审查修复后 3 文件 25 项通过，文档检查通过。更新了已有去重、消息合并、来源删选测试的失效预期，新增短标签、原文一致性、长参数预算和真实 IM 目录回归保护。
- 独立审查者 `trajectory_patch_review` 使用 code review + agent-context-review，发现并复现两个阻塞：普通工具 JSON 被误作 IM 索引、长写入参数通过空分页正文绕过预算。主 Agent 修复后，审查者独立重跑原探针及超大纯元数据页，均关闭；最终 corrected-delta aligned、无未关闭 finding。历史轨迹原文、实时 IM 权限和运行中来源 generation 失效在 canonical/delta 中分别说明。
- HTML 四个页签现全部来自实际 HTTP 请求。Global／PA 各从空历史走同一条 Inbox 酒店条件 → 普通 subagent 读取报价及 send_message 回报 → 子轨迹摘要 → Dreaming 主轨迹与摘要文件链路。主会话未启用 fork。审查者亲读两套请求并对照两次 Inbox 正文，确认材料及读取结果原样保留，来源标签与会话关系一致。模型和 IM relay 是受控替身，不证明真实模型记忆质量；主→子后续消息的标签有定向输入测试，此连贯抓包未覆盖该交互或跨窗补读。
- 本地证据在 `~/.local/share/nano-multiagent/evidence/dreaming-input-20261111/original-trajectories/`。短轨迹捕获版本为 `92dd6f75a`，后续修复只影响 IM 索引辨认、超长分页及旧部分进度，原捕获结论保留；HTML 标示当前实现。页面内容及关联校验通过，未重复此前受策略阻止的本地浏览器视觉预览。
- 一次性部署提示补充旧格式未完成分页的切换：备份后清 continuation、保留 cursor/baseline，只重读未完成 step；退休 seen 可删除，不加入运行时兼容。主 Agent 和独立审查者均在模拟 owner 状态验证完整 JSON 重读及正确推进；未修改实际 KV 或生产。所有本轮临时运行资源已回收，保留证据及 PR worktree，既有用户试用服务未动。

### Dreaming 复用建连失败等待策略（2026-11-11）

- 用户要求 Dreaming 接入已有断网续跑，不新增一套重试。原 `agent/created` 在 Nano preset 筛选后才挂载 `attachModelConnectionRetry`，无 preset 的提炼／整合 Agent 被跳过。最终实现按原 Nano preset 或 Dreaming 既有会话 ID 前缀挂载；分类、退避、取消及普通错误预算均不变。
- 新增隔离 RuntimeClient + HTTP provider 故障注入回归。修复前原生事件只有 `mode: normal`，无法达到持续等待断言；修复后同一 Dreaming 会话的 turn 1 / step 2 连续产生 5 秒、10 秒建连等待，恢复后批次 completed，断网前 Bash 写入和提交只执行一次。另验证原生 Agent 取消可以结束等待，普通服务 502 仍有界失败。此为真实 DSH 跨进程、受控 HTTP 响应，不是拔网线或真实模型质量测试。
- 构建和文档检查通过。相关六套件首轮 29/30 通过，失败为新增测试修改时误改旧 fixture 引用，修正后完整 `model-connection-retry.test.ts` 5/5 通过；另外五套件的 25 项结果保留，产品实现未再变化。新用例开发期间曾因测试错误地取消父会话而超时，后改为直接取消 Dreaming 原生 Agent，未把父取消语义纳入此次改动。
- 独立审查者 `dreaming_connection_review` 对 `ccfeb8b4f..d92c05e1b` 复现一项阻塞：无条件挂载会接管 `nano-codex-reviewer` 的专属错误重试。受控真实 DSH 审核探针显示同一步出现第三次 `always` 建连重试，超过审核自身两次上限。修复将挂载限定为原 Nano preset 与既有 `dreaming-` 会话，新增真实审核场景：连续建连失败仅三次请求，且没有 `nano:model-connection` 事件。原生 `Agent.cancel` 用例仅证明等待可被取消，不宣称聊天父会话的停止会取消 Dreaming。最终复验见后续记录。无生产变更；临时 RuntimeClient、HTTP 端口与测试工作区已回收。
- 最终修复 `7b0311fd0` 构建通过，断网与原生审核两套件 8/8 通过。独立审查者完成 `d92c05e1b..7b0311fd0` closure，原阻塞 CLOSED、无存活 findings、corrected-delta aligned；直接恢复用例覆盖整合，提炼共享同一创建入口，由代码核对和既有提炼回归提供覆盖。最终文档收口不改变实现或测试。

### Web 角色与配置统一保存（2026-11-11）

- 用户否定额外的 Save role agreement 按钮，要求移除。Web 改为底部 Save Agent 提交角色及其他配置草稿；ROLE 仍使用独立版本 API。只修改角色不提交普通配置；角色失败不继续提交配置，配置失败只保留并重试配置草稿；放弃修改及离开提醒覆盖角色。
- 新测试先在旧实现确认独立按钮仍存在而失败。最终两个配置编辑套件 59/59 通过，覆盖统一保存、ROLE-only、长度限制、冲突、离线、丢弃与部分失败重试；前端类型检查及构建通过。中间一次实现错误因角色保存状态误拦截后续配置保存，修复后通过；另一次测试使用单个文本查询匹配了已有两个错误展示，改用错误区域定位。
- 作者在既有隔离服务 `127.0.0.1:57961` 使用实际 Web Global 配置页完成角色输入 → Save Agent → 刷新读回 → 修改后放弃 → 清空并保存恢复未设置。画面已无独立角色按钮，底部统一反映未保存／已保存状态。现场能力目录刷新原有失败仍在，因此角色与普通配置同时提交的验证来自组件/API 测试，未宣称现场组合保存通过。原生 iOS 未改、未测；该修订只覆盖 Web（PA 与 Global 共用组件）。保留用户试用服务，未改生产。
- 独立审查 `role_unified_save_review` 对 `0abe62135..a58bdecb1` 确认一项 P2：等待 ROLE 保存时仍可通过侧栏选择放弃并切换 Agent，旧异步处理随后可能提交尚未发出的配置。补测在旧实现出现放弃对话框而失败；修复在保存期间阻止侧栏切换并禁用放弃离开按钮。最终两个套件 60/60 及构建通过。

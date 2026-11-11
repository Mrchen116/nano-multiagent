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

任务：建立 nano-multiagent 的 Agent Context Engineering 开发规范与审查机制

一、背景与目标

nano-multiagent 是一个多 Agent、多人协作系统。Agent 最终接收到的 Context 是整个产品智能表现的关键接口。

目前开发过程中，Coding Agent 对普通 API、代码质量、前端交互有相应规范，但对 LLM 实际看到、理解、消费的 Context 缺乏统一的设计与审查机制。

这导致开发时可能出现：

* 要求 Agent 填写它无法知道的工具参数，最终只能猜测或编造。
* 工具返回结构对程序友好，但不能帮助 Agent 理解结果、决定下一步行动。
* 动态 System Prompt 注入时机、内容或优先级设计不当。
* Skill 内容合理，但发现、触发或加载机制不合理。
* Context 来源、权限或信任边界没有清楚传达，尤其涉及群聊、其他 Agent 和 PA。
* Memory、历史压缩、Session 恢复丢失重要事实、约束或任务状态。
* 各部分 Context 独立看合理，但组合后重复、矛盾或互相干扰。

目标：把 Agent Context 作为一等产品接口，建立通用设计标准，并融入现有 change- 开发流程，确保后续开发 Agent 会主动设计、审查、验证 Context 质量。*

本任务主要建设开发方法、Skill 和验证机制，不要求重构 nano 的运行时 Context 系统。

二、先调查现状与参考规范

先阅读并确认以下现有文件及它们在当前分支中的实际作用：

* AGENTS.md
* docs/development/documentation-system.md
* docs/development/coding-guidelines.md
* docs/development/change-workflow.md
* docs/development/testing.md
* docs/development/llm-integration.md
* .claude/skills/change-design-author/
* .claude/skills/change-design-reviewer/
* .claude/skills/change-impl-worker/
* .claude/skills/change-code-review/
* .claude/skills/change-verifier/
* .claude/skills/change-orchestrator-simple/
* .claude/skills/change-orchestrator/

同时调查当前代码中 System Prompt 组装、动态注入、Skills 加载、工具 Schema、工具返回投影、Inbox/IM 消息、Memory 和 Compaction 的真实实现路径。

已有局部要求应复用，不要建立与现有规范冲突的平行体系。

参考成熟实践：

* Anthropic mcp-builder：工具语义、输入输出设计、Agent 工具评测。
* OpenAI skill-creator：Skill 设计、触发与评测。
* Agent Skills Specification：Skill 组织与渐进披露。
* MCP Tool Specification：工具结构与 Schema 设计。
* Anthropic Context Engineering 相关文档：上下文选择、注入、管理。
* 当前 nano 的真实 DSH Context 机制。

这些资源提供设计方法，不要求 nano 全面引入它们的协议或运行时。

三、新增通用开发规范

新增：

docs/development/agent-context-engineering.md

这是整个项目 Agent Context 设计方法的唯一通用权威文档。

3.1 定义适用范围

凡是影响 LLM 能看到什么信息、何时看到、如何解释、如何更新与保留的设计，都属于 Agent Context Engineering。

至少覆盖：

1. System Prompt：身份、行为规则、工具使用指导、指令组织与优先级。
2. Runtime Context Injection：System Reminders、Inbox Wake、任务状态、群成员及其他动态注入。
3. Skills：Skill 元数据、发现、触发、加载、内容组织、渐进披露。
4. Tool Definitions：名称、描述、参数、Schema、调用前提。
5. Tool Results：成功/失败状态、返回字段、错误恢复、引用 ID、后续操作。
6. Messages：用户、Agent、群聊、外部 Channel、系统消息的来源与投影。
7. Memory：写入、检索、选择、更新、失效及注入。
8. History / Compaction：历史恢复、摘要、长期任务和重要状态的保留。

不仅审查文字内容，还要审查 Context 的整个生命周期：

信息来源 → 选择/检索 → 转换/组装 → 注入/加载 → LLM 消费 → 更新/过期 → 压缩/恢复。

3.2 建立跨类型的通用设计原则

制定一套简洁但有实际指导价值的设计原则。

至少覆盖：

* Necessary：是否应该进入 Context？
* Available：Agent 需要时能否发现和获得？
* Relevant：是否与当前角色、任务和状态相关？
* Understandable：内容是否准确、明确、没有歧义？
* Provenance：来源、身份和信任级别是否清楚？
* Priority：多个来源的指令和事实冲突时如何处理？
* Actionable：Agent 能否据此决定正确的下一步？
* Consistent：是否与其他 Prompt、Skill、工具或 Memory 冲突？
* Durable：跨轮次、压缩、恢复后是否仍然可靠？
* Efficient：是否重复、冗长、引入不必要的注意力成本？
* Secure：是否存在跨 Agent、跨用户的信息或权限泄露？
* Verifiable：是否能通过实际模型输入和行为证明效果？

不要把上述内容做成机械地逐项打勾的表格。应形成少量核心原则、各类 Context 的特殊注意事项和真实反例。

3.3 特别关注 Context 之间的交互

单个 Context 设计合理，不代表最终组合合理。

必须考虑：

* System Prompt 与 Skill 是否重复或冲突。
* 动态注入是否覆盖了更高优先级的规则。
* 工具输出是否与工具描述所承诺的语义一致。
* Memory 中的旧事实是否与新的任务状态冲突。
* Inbox 消息是否被错误理解成新的用户指令或授权。
* 工具错误是否导致 Agent 误以为任务已经成功。
* 大量低价值注入是否挤占真正需要的上下文预算。

特别结合 nano 的 Global Agent、PA、多用户 IM、Task Graph 等产品特征给出实例。

3.4 明确什么属于设计问题

例如：

某工具要求模型提供 owner_id，但真实 owner 身份只存在于宿主运行时。

即使参数类型正确、代码执行正常，仍应判断为 Agent Context / Interface 设计问题，因为模型无法可靠提供这个值。

优先通过宿主派生可信字段，而不是增加一段 Prompt 要求模型不要编造。

类似地，Skill 不触发、动态注入过早或过晚、压缩丢失等待事项，都属于 Context 设计问题，不应简单归为模型能力不足。

四、新增 Agent Context Review Skill

新增：

.claude/skills/agent-context-review/SKILL.md

必要时建立 references/ 存放不同 Context Surface 的详细审查指南或典型反例。

这个 Skill 覆盖全部 Context，不是专门针对工具。

Skill 的定位是：独立站在 LLM 消费者视角，评估 Context 设计及实际交付质量。

提供两个使用模式。

Mode A：Design Review

在设计完成、正式实施之前使用。

审查问题包括：

* 哪些 Agent 会消费这些内容？
* Agent 面对什么任务，需要知道什么？
* 信息在哪里生成，由谁负责？
* 哪个时机提供，为什么是这个时机？
* 信息是常驻、动态注入、按需读取，还是经工具获取？
* 哪些内容应该由模型提供，哪些必须由宿主推导？
* 与现有 Context 是否冲突？
* 多用户与多 Agent 的信任、权限边界是什么？
* 如何处理失败、信息缺失、更新与恢复？
* 如何证明 Context 设计能支撑预期行为？

设计阶段只要求能够审查方案，不应假装已经运行过真实模型。

Mode B：Implementation Review

实现完成后使用。

从运行时实际交付到 LLM 的内容审查：

* 最终组装的 System Prompt。
* 实际启用的工具列表及 Schema。
* 实际序列化后的工具结果。
* 实际注入的消息和系统提醒。
* Skill 是否真正被发现、加载与消费。
* Memory 是否按设计进入模型 Context。
* 多轮对话及适用压缩/恢复之后的信息状态。

重点不是检查源码里存在某个字段，而是检查模型最终是否真的看到了正确内容。

使用有代表性的真实模型任务，在条件允许时验证模型的工具选择、参数填写、状态理解与后续行动。

Skill 审查输出

问题必须包含：

* 具体文件或设计位置。
* 受影响的 Agent Context Surface。
* Agent 本来应该知道、理解或执行什么。
* 实际设计或模型可见内容是什么。
* 具体失败场景或可成立的风险机制。
* 对用户或任务结果的影响。
* 可执行的改进建议。
* CONFIRMED / PLAUSIBLE / REFUTED 证据状态。

严重度与当前 change-* 审查体系保持一致。

没有实际问题不强行制造 Finding；证据不足明确标注，不得猜测模型一定会误解。

Skill 要短、职责明确，详细内容指向通用规范和按需 references，不重复维护规范正文。

五、融入现有 change-* 开发流程

这是本任务最重要的部分：不是新增一个很少有人主动使用的 Skill，而是让日常开发 Agent 在正确阶段自然执行 Context 设计和审查。

5.1 change-design-author

增加 Context 影响识别规则。

当设计涉及 Agent 可见内容时，在现有 design.md 适当位置增加 Agent Context 设计说明，包含：

* Consumer：哪个 Agent、什么场景。
* Context Lifecycle：内容来源、组装、交付时机、保留和失效。
* Before/After：必要的模型可见内容示例。
* Interactions：与已有指令、Skills、Memory 和工具的关系。
* Validation：如何验证真实交付和 Agent 行为。

不影响 Context 的设计无需生成冗余章节。

这些内容应进入现有设计产物及相关 milestone 退出标准，不新增独立的设计文件。

5.2 change-design-reviewer

当受审设计影响 Agent Context 时，按 agent-context-review 的 Design Review 模式执行。

结果仍写入原有 design-review.md。

不能只审查普通 API 结构与数据流，还要审查 Agent 是否能正确理解和消费设计的接口。

不新增独立 Review Agent，也不新增审批 Gate。

5.3 change-impl-worker / 默认直接实施路径

对于 Context 相关实现，要求在适用时验证实际模型可见内容。

不能以以下证据代替：

* 源码中存在字段。
* 内部 API 返回正确。
* TypeScript 类型检查通过。
* Web UI 的工具卡片显示正确。
* Skill 文件存在于磁盘。

应尽可能检查最终 LLM 输入及真实运行行为。

对默认 change-orchestrator-simple 直接实施路径也必须生效，不能只覆盖 change-impl-worker。

5.4 change-code-review

当 Diff 影响模型可见 Context 时，调用 Implementation Review 中适用的检查方法。

普通代码正确性之外，还要识别 Agent Interface 设计缺陷。

例如模型不可获得的必填参数、错误的成功语义、错误来源标记，以及 Prompt 组装不一致。

5.5 change-verifier

核对 Context 的实现是否与设计、相关 Current Specs、Milestone 退出标准一致。

有真实运行验证需求时，检查对应证据。

区分：

* 实现偏离设计。
* 设计本身不合理。
* 真实模型行为尚未验证。

不要求 verifier 重复 code reviewer 已完成且证据仍有效的检查。

5.6 其他接入位置

在 AGENTS.md 增加简短的 Context 设计规范入口。

在 docs/development/README.md 和 docs/README.md 注册新规范。

评估是否需要在 coding-guidelines.md 增加一句：普通 API docstring 不能替代 Agent 可见接口设计；详细要求引用新规范。

在 change-workflow.md 或编排 Skill 中补充必要的条件触发说明，但不要改变现有 Full / lite 的 Gate 数量与角色职责。

5.7 触发原则

影响以下内容时应触发：

* 模型可见的文本、Schema、结构、字段或语义。
* Context 选择、过滤、注入和加载时机。
* 指令优先级或来源/信任信息。
* Memory、Skill 或 History 的消费链路。
* Context 的压缩、恢复、更新与失效行为。

纯 UI 样式、完全不改变模型可见内容的内部重构等，不应触发完整 Context Review。

若代码变更间接影响 Context，仍应根据实际影响决定是否触发，而不是只按文件名匹配。

六、真实 Context 的观察与验证

优先复用现有能力：

* docs/development/llm-integration.md
* LLM_PROXY 的 Session 日志。
* 已有的 DSH Session / Tool 事件与测试工具。
* 当前可复用的真实模型联调环境。

调查能否直接取得模型实际收到的 System Prompt、Messages、Tool Definitions、Skill 内容与工具结果。

以真实 provider 请求为优先证据，但同时区分：最终请求能够证明发送了什么，模型是否正确消费仍需要行为验证。

如果现有能力足够，编写明确的操作说明和审查方法，不重复建设 Context Snapshot 系统。

如果存在实际观测盲区，说明缺少什么证据、影响什么判断，优先补最小的只读诊断能力，不引入新的运行时架构或独立可观测平台。

注意安全：原始 Prompt、消息、工具结果可能包含私人数据。遵循现有 Evidence 规则，不把完整请求、秘密或私人数据提交进 Git。

七、使用真实 nano 场景做试点

不能只证明新 Skill 文件存在、相关规范被引用。

至少选取三个不同类型的 Context 场景，进行实际审查试运行：

场景 A：Tool Result

检查 send_message 或 task_graph 的真实模型可见定义和结果。

重点验证 Agent 是否能区分受理、送达、完成、失败和结果未知等当前实际存在的状态，并能正确执行下一步。

场景 B：Runtime Injection / IM

检查 Global Agent 的 Inbox 唤醒及后续消息读取。

验证来源、发送者、消息正文、唤醒通知与用户授权的区别，以及上下文实际交付时机。

场景 C：System Prompt / Skill

检查 Agent 的 Prompt 组装，以及一个已启用/禁用的 Feature 或 Skill 对最终模型 Context 的影响。

验证模型真实看到的内容与配置、加载规则一致，没有错误的重复或残留指令。

如果 Compaction / Memory 已有容易复用的测试现场，再选择一个跨轮次恢复案例，检查重要任务状态和来源约束是否保留。

试点先以审查当前系统为主，不擅自展开大规模产品功能重构。发现真实产品缺陷，记录具体位置和证据，根据范围走已有修复流程。

至少提供：

* 一个工具类 Context 的真实审查示例。
* 一个非工具类 Context 的真实审查示例。
* 一个不应触发 Context Review 的普通代码变更反例。
* 实际发现的问题，或有证据支持的无问题结论。
* 哪些结果来自静态分析，哪些来自真实模型输入或行为。

若缺少可用模型或环境，明确区分已完成的静态验证和未完成的模型验证，不能把前者冒充后者。

八、验证和交付标准

按仓库现行 change-workflow 选择合适的开发流程，不自行切换快速开发模式。已有设计审批、独立审查和 PR 门禁继续适用。

最终应该满足：

1. 有且只有一份通用的 Agent Context Engineering 权威规范。
2. 新 Skill 覆盖所有 Context Surface，不偏向工具。
3. Skill 能以 Design Review 和 Implementation Review 两种模式执行。
4. 设计、实施、代码审查和验证的现有流程已接入该能力。
5. 不改变无关开发任务的工作方式，不制造全量重复审查。
6. 有真实 nano 案例证明触发、审查和证据记录能够工作。
7. 有实际模型输入的观察路径，且不会泄露原始私人数据。
8. 不复制已经存在的产品契约，不重新设计 DSH Runtime，不另建一套审查体系。
9. 更新相应文档索引，执行适用的文档检查、测试和现有质量门禁。

遵循 docs/development/testing.md：只新增有长期回归价值的测试，尽量复用现有测试，避免为每个检查项创建一份脆弱的静态文本断言。

九、实施原则

* 核心关注 LLM 消费者，不是传统 API 调用者。
* 不只优化 Context 内容，还要优化发现、选择、注入、消费、更新和恢复过程。
* 不只评估单个 Context，还要评估最终组装后的整体一致性。
* 不把所有 Context 都强制套进固定模板。
* 高后果、可确定的约束优先由代码、Schema、权限和测试保证，而非只依赖 Prompt。
* 不因为增加 Skill 就增加无必要的新 Agent、新 Gate 或重复文档。
* 设计规范与审查程序分离，保证单一权威来源。
* 方案应让未来 Coding Agent 真正减少 Context 设计缺陷，而不是只产出更多审查文字。

请在现有仓库中完成调查、设计、实现、测试和必要的文档集成。已在本任务中明确的方向自主推进，不必反复澄清。

最终报告应说明：新增/修改了哪些文件、各开发阶段怎样触发、实际审查案例和结果、真实 Context 验证证据，以及尚未覆盖的限制。按当前仓库规定交付可审查的变更，不自动合并。

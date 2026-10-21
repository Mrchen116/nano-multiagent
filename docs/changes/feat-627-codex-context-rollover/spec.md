# feat-627: Codex 风格的无摘要上下文换窗

## Relations

- Related: feat-610
- Related: feat-614

## 原始需求

2026-10-21，用户提供[此前的插件比较讨论](https://chatgpt.com/c/6ad03bf1-3ce0-83ec-8d40-957b11817c69)，并要求：

> dsh-context-rollover 我想fork他的基础上改造得更偏向codex的设计，然后用在本项目，gpt列出来了一些差异点，我们讨论下。History，只索引移出活动上下文的部分消息，我觉得可以接受；一个 `notes` 工具用action分派，还是5个notes工具成组，这个得看DSH的设计，codex是responses api，他的工具是可以分组的，所以5个工具分组相当于action分派。窗口序号还是ID，这也得结合DSH的情况，你帮我决策。其他的点，比较涉及到效果，我理解照着codex的来会比较合理。你把dsh-context-rollover代码拉下来，结合本地的codex代码分析分析。讨论好后，我们新建一个feature。

在读取插件、DSH、Codex 与 Nano 源码，并逐项讨论差异后，用户确认：

> 可以，就按这个方案来。先 fork dsh-context-rollover，然后在本项目新建一个 feature。context_window_reminder 等等一些提示词，如果不冲突的话，尽量按codex的来

## 澄清记录

2026-10-21：用户接受本轮源码分析后提出的方案，授权先 fork 和建立 feature。本轮交付范围为 fork 与首文档；功能设计、实现和验收由后续 Full 流程推进，不将本次立项视为已实现或已部署。

以下为用户已接受方案的整理，不是新增用户原话；其中接口和实现保真约束作为后续 design 的输入，不混入终端用户验收：

1. 使用 `dsh-context-rollover` 的 fork 作为基础，保留 DSH 公开插件接口、安全 step 边界、Compaction 事务及工具调用配对约束，不修改或 fork DSH 执行内核。
2. 新窗口重建当前有效指令、工具、环境和产品状态；默认不自动带入普通旧对话 tail、Notes 正文或额外交接正文，不调用摘要模型。Notes 自动提示只包含简短索引，正文按需读取。
3. `new_context` 无参数，只请求切窗；移除独立 handoff，交接信息由 Agent 保存到 Notes。
4. Notes 使用一个工具，通过 `list / read / search / write / append` 分派；补齐按行读取、路径前缀筛选、有界输出和原样追加。接受其与 Responses namespace 工具在协议形态上的差异。
5. History 只检索已离开活动上下文的消息，使用一个工具支持窗口列表、消息列表、搜索和读取；补齐 Nano 来源识别、工具调用名称与参数、结果恢复、过滤和分段读取。沿用原始会话日志，不要求另建全量历史数据库。
6. 面向恢复使用稳定窗口 ID，窗口序号用于展示。复用 DSH 会话身份和持久事件边界形成窗口引用，事件 seq 形成消息引用，不单独维护一套 UUID 映射。关键用户输入和工具结果在切窗前即提供可保存的引用，重启后仍可定位。
7. 预算机制对齐 Codex：每窗一次剩余预算提醒、工作预算耗尽后的保存 Notes 提示和预留空间、硬上限及供应商溢出兜底；一轮长期任务允许连续多次换窗。具体预算根据适用模型确定，不将参考模型的数字当作全模型默认值。
8. 插件承担上下文管理；Nano 保持产品来源、有效环境与既有授权边界。跨 Agent 的 Notes/History 访问不自动照搬 Codex 的访问范围，不因为切窗或插件安装扩大权限。
9. 先以 Codex 为行为基线，再验证连续任务效果；不预先承诺成功率、成本或延迟优于现有压缩方案。

### 提示词沿用要求

用户追加的要求适用于 context guidance、`context_window_reminder`、基础预算耗尽后的 fallback prompt、新窗身份与恢复提示，以及相关工具描述。后续 design 必须：

- 从下述固定 Codex commit 提取原文，记录文件、模型条目及适用条件，保留不冲突的英文措辞与提示结构；不凭印象重写一套等价提示词。
- 仅对实际冲突做最小适配，例如 `functions.new_context` 的工具寻址、`notes.*`/`history.*` 到 action 的用法、消息引用格式、跨 Agent 读写范围，以及本项目的既有权限与交付约束。
- 对每处变更保留“原文、适配后文本、冲突理由”；可直接复用的部分保持原文。模型阈值与 buffer 数值单独作为配置决策，不混成提示词措辞变更。
- 保留及时记录目标、约束、已验证进展、决策、下一步和原始消息引用的意图；新窗优先读取笔记并按需恢复历史。预算耗尽提示保留先保存再切窗的顺序。
- 不把服务端未公开的 Notes/History 行为、测试 fixture 或未启用的模型配置宣称为 Codex 所有线上模型的统一实现。

## 现状与依据

本节是立项时的源码观察，未做本 feature 的运行验收。

| 对象 | 核对基线 | 用途 |
|---|---|---|
| Nano | `861b94129bc8c5aadbca76967268fd203fe04112` | 现有 workspace 插件、产品来源和压缩接线 |
| DSH | `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；Nano 锁定 `0.2.1-alpha.1` | 当前公开扩展接口；本 unit 不顺带升级运行时 |
| rollover upstream / fork 起点 | `d74876a90968bd5498b5af0bcc2f327c3131f007`，包版本 `0.2.2` | 复用无摘要换窗与持久 Notes 的基础 |
| Codex | `464add49587a7cb6032d5ab04faa8a1585947853` | 新窗、工具契约和预算提示词参考 |

- Fork：[Mrchen116/dsh-context-rollover](https://github.com/Mrchen116/dsh-context-rollover)，上游为 [athif23/dsh-context-rollover](https://github.com/athif23/dsh-context-rollover)。fork 的成立不代表改造已完成。
- [当前插件契约](../../specs/gateway/agent-capabilities.md#requirement-agent-可在-workspace-自助安装原生工具) 已支持 workspace bundle 与压缩引擎启停；[Nano 压缩接线](../../../packages/dsh-integration/src/compaction.ts) 向 Agent preset 的引擎委派。feat-610、feat-614 为相关既有能力。
- 上游 [新窗入口](https://github.com/athif23/dsh-context-rollover/blob/d74876a90968bd5498b5af0bcc2f327c3131f007/src/index.ts) 自动注入 Notes 正文并保留近期 tail，且压力换窗每 turn 最多一次。其 [范围选择](https://github.com/athif23/dsh-context-rollover/blob/d74876a90968bd5498b5af0bcc2f327c3131f007/src/rollover.ts) 在保留预算为零时仍先选中尾部节点；不能仅改配置宣称已去掉 tail。
- 上游 [History](https://github.com/athif23/dsh-context-rollover/blob/d74876a90968bd5498b5af0bcc2f327c3131f007/src/history.ts) 只认直接 `user` 来源、将非文本块替换成类型占位符，读取没有 offset；[Nano 输入](../../../packages/dsh-integration/src/index.ts) 使用 `nano-human`/`nano-system` 来源。需适配恢复内容，同时保留真实来源，不将系统通知或外部材料升级为人类授权。
- Codex [新窗实现](https://github.com/openai/codex/blob/464add49587a7cb6032d5ab04faa8a1585947853/codex-rs/core/src/session/mod.rs) 的 `start_new_context_window` 重建初始上下文，有特定功能开关控制的客户端消息保留例外；本 unit 不机械引入这些无对应产品需求的例外。
- Codex [Notes 扩展](https://github.com/openai/codex/blob/464add49587a7cb6032d5ab04faa8a1585947853/codex-rs/ext/history-notes/src/extension.rs) 对后端 thread hint 限制为 4,000 bytes；这能证明客户端边界，不能证明服务端选择文件的全部算法。采用近期文件提示且总计不超过 4,000 bytes 是本方案的本地策略。
- Codex [模型提示词](https://github.com/openai/codex/blob/464add49587a7cb6032d5ab04faa8a1585947853/codex-rs/models-manager/models.json)、[预算提醒](https://github.com/openai/codex/blob/464add49587a7cb6032d5ab04faa8a1585947853/codex-rs/core/src/session/token_budget.rs)、[预算计算](https://github.com/openai/codex/blob/464add49587a7cb6032d5ab04faa8a1585947853/codex-rs/core/src/session/context_window.rs) 和 [工具契约](https://github.com/openai/codex/blob/464add49587a7cb6032d5ab04faa8a1585947853/codex-rs/ext/history-notes/src/tools.rs) 是后续设计的固定参考。

## 用户场景

1. 用户在 Web IM 或飞书让 Agent 持续调查、修改和验证一个任务。中途工作上下文多次换窗，Agent 能继续原任务，保留用户最后确认的范围与限制，不反复要求用户重述，也不重复执行已完成且有外部副作用的动作。
2. 用户早先提出过关键约束，或某次工具执行返回过较长的重要结果。切窗后 Agent 需要其中的细节时，能够找回原始内容和来源，区分旧要求与后续修订，不靠笔记中的猜测补齐。
3. Agent 接近上下文预算时先保存继续工作所需的信息，再进入新窗；达到强制边界后仍可恢复可用的工作记录。新会话没有旧笔记，或者历史目标不存在时，Agent 如实处理缺失，不虚构已恢复的信息。
4. 节点正常重启后，用户在同一聊天继续工作；此前已经保存的工作记录与历史仍可找回。重启和切窗不会把别的 Agent 或 workspace 的材料带进当前任务。
5. 用户通过既有插件管理入口启用、停用或恢复此能力。未启用的 workspace 保持原来的工作方式，停用不删除已有工作记录；加载或恢复失败时明确反馈实际状态。

## 验收标准

### Requirement: 多次换窗后能继续同一个任务

#### Scenario: 连续长任务（用户场景 1、3）
- **GIVEN** 用户明确了任务目标、限制条件和交付物，任务需要经历至少三次上下文换窗
- **WHEN** Agent 持续推进并完成任务
- **THEN** 用户收到符合最后确认要求的结果，不因换窗被要求重复提供已可恢复的任务说明
- **AND** 已完成且有外部副作用的动作不因换窗而重复执行，未完成事项不被误报完成

#### Scenario: 后续纠正覆盖旧方案（用户场景 1、2）
- **GIVEN** 用户明确修改了此前的范围或方案
- **WHEN** Agent 在换窗后继续处理
- **THEN** 按用户最新有效要求工作，不因找回旧记录恢复已取消的要求

### Requirement: 需要旧细节时能恢复可核对的原始依据

#### Scenario: 用户约束与长工具结果（用户场景 2）
- **GIVEN** 早先用户消息及一份较长执行结果已离开当前工作上下文，所需细节位于结果后半段
- **WHEN** 后续任务需要据此判断或继续操作
- **THEN** Agent 能依据正确的原始约束和执行细节完成工作，区分用户要求、工具事实与自身推测
- **AND** 不要求用户重新粘贴原本可恢复的材料

#### Scenario: 没有可恢复记录（用户场景 3）
- **GIVEN** 新会话没有历史笔记，或指定旧细节确实不存在
- **WHEN** Agent 开始或恢复工作
- **THEN** 依据当前可用信息行动；缺失信息影响任务时准确说明缺口，不编造历史或声称已经找回

### Requirement: 上下文压力不造成无说明的任务丢失

#### Scenario: 接近预算及强制换窗（用户场景 3）
- **GIVEN** 任务仍未完成，执行中先后出现接近预算和必须换窗的情况
- **WHEN** Agent 进入后续工作窗口
- **THEN** 能利用已保存且可恢复的记录继续任务，保留已知约束和未完成事项
- **AND** 若恢复信息不足以继续，给出具体缺口，不把失败报告成任务完成

### Requirement: 已保存工作记录在重启后仍可恢复且访问范围不扩大

#### Scenario: 正常重启后继续（用户场景 4）
- **GIVEN** 同一任务已换窗并保存工作记录，节点随后正常重启
- **WHEN** 用户在原聊天继续该任务
- **THEN** Agent 能找回已保存的进度与必要原始细节，不要求从头开始

#### Scenario: 其他 Agent 或 workspace 的记录（用户场景 4）
- **WHEN** 当前任务请求访问既有权限之外的其他 Agent 或 workspace 记录
- **THEN** 不获得这些记录，也不把它们用于回答或外部操作；换窗、恢复及插件启用不扩张授权

### Requirement: 通过现有插件入口控制生效与撤销

#### Scenario: 启用、停用和恢复（用户场景 5）
- **WHEN** 用户在目标 workspace 启用、停用并重新启用该能力
- **THEN** 后续工作使用相应已生效的上下文管理方式；停用后恢复现有默认压缩行为，已有工作记录不被删除
- **AND** 其他 workspace 的启用选择与工作行为不被改变

#### Scenario: 加载或恢复失败（用户场景 5）
- **WHEN** 安装完成但加载失败，或已保存记录恢复失败
- **THEN** 用户获得实际失败与可采取的恢复说明，不把包安装成功等同于能力已经可用

## 范围与非目标

- 在范围：fork 插件的 Codex 风格无摘要换窗、Agent 自主管理 Notes、已移出上下文的 History 恢复、稳定引用、预算提醒与兜底、必要的 Nano 接入与既有插件生命周期，以及上述真实连续任务验收。
- 保留：DSH 为唯一执行运行时；既有账号与 workspace 归属、工具能力选择、审批、Inbox、消息投递和子任务限制。本 feature 不以恢复出的 Notes 或 History 创造新的操作授权。
- 非目标：Responses namespace 协议改造、复制 OpenAI 私有后端、全量活动历史索引、默认跨 Agent 共享笔记、长期知识库/自进化重构、DSH 内核 fork 或运行时升级、新客户端界面，以及在本次立项时启用或部署生产服务。
- 效果边界：实现阶段需要抓取切窗前后真实模型请求，核对保留内容、提示词适配、引用、预算与连续换窗；这些属于 design 的实现验收。产品验收按上面的用户场景观察任务延续，不能用单测或静态源码替代。不设未经测量的性能提升承诺。
- 首文档范围已根据用户确认收口；后续进入 Full 设计与独立设计审查。此文档不改变 current specs，不预填未执行的设计、实施或验收结论。

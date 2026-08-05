# feat-502: PA 产品说明书 skill

## 原始需求

> 我觉得PA还需要一个内置skill，做该产品说明书。类似[$openai-docs](/Users/czj/.codex/skills/.system/openai-docs/SKILL.md) 。这样，用户在问agent一些关于这个产品的问题的时候，agent就可以调用这个skill来回答。

## 澄清记录

- Q1: 产品说明书 skill 应保证每个 PA Agent 始终可用，还是作为默认选中但可由用户关闭的产品级 skill？
  A(原话): PA现在不是已经有了内置飞书skill的设计吗，跟那个一样，放到全局，然后默认选上，用户在IM上也可以把它关了
  Agent 解读: 复用现有 PA 内置 skill 的用户语义：随产品安装到全局 skill root，作为全局 skill 在 IM 的 Agent 配置中默认选中；用户取消选择并保存后，该 Agent 后续不再使用它。
- Q2: 说明书只覆盖 PA 用户产品，还是覆盖整个 nano-multiagent 仓库？
  A(原话): 对
  Agent 解读: 用户确认只覆盖 PA 用户产品，包括使用 PA 所必需的 IM、Gateway 与外部渠道表面；不覆盖 coding CLI、内核内部架构和开发流程。
- Q3: 当本机安装的 PA 版本与远端仓库最新文档不一致时，说明书应默认回答哪一个版本？
  A(原话): ok，这些follow openai的做法是不是就ok了
  Agent 解读: 默认回答本机已安装版本；只有用户明确询问最新版或版本变化时才查询远端并标明差异。其余说明书问答行为 follow `openai-docs` 的成熟做法，但把权威来源适配为 PA 自身的已安装版本与可观察运行状态。
- Q4: 新版本加入该 skill 后，已有且配置过显式 skill 列表的 Agent 是否自动选中它？
  A(原话): 好
  Agent 解读: 不改写已有 Agent 的显式 skill 选择；新建 Agent以及仍使用默认 skill 集合的 Agent 默认启用。已有显式配置的 Agent 可在 IM 中手动开启。
- Q5: PA 升级时只覆盖产品手册，还是覆盖全部随包内置 skills？
  A(原话): 现有 Lark 等内置 skills也覆盖吧
  Agent 解读: PA 升级后的 Gateway 启动应以当前安装包版本更新所有随包内置 skills，包括现有 Lark bundle；用户在 IM 中对 skill 的启用/关闭选择仍保持不变。
- Q6: 覆盖内置 skill 时，目录应整体以当前安装包为准，还是只覆盖安装包中的同名文件并保留用户额外文件？
  A(原话): 用户一般不会改内置的skill
  Agent 解读: 随包内置 skill 的整个目录由 PA 托管，升级时完整替换为当前安装包版本；用户若要定制，应使用另一个 skill 名称。其他非内置名称的用户 skill 不受影响。

## 用户场景

用户在 Web IM、飞书或其他 PA 对话入口里，可能直接询问“你能做什么”“怎么配置一个 Agent”“heartbeat 和 cron 有什么区别”“为什么节点显示离线”等有关 Nano Personal Assistant 自身的问题。用户不需要预先知道说明书放在哪里，也不需要显式输入 skill 命令；只要该 Agent 启用了产品说明书 skill，Agent 就会按需读取说明书，再根据与当前安装版本匹配的产品事实作答。

说明书面向使用和运维 PA 的用户，覆盖 Web IM、Gateway、Agent 配置、模型、skills、tools、memory、heartbeat、cron、飞书等外部渠道、启动流程和常见故障处理。它不把 coding CLI、内核内部架构或仓库开发流程混入普通 PA 产品回答。用户的问题超出说明书边界时，Agent 会明确说明边界，而不是把内部开发知识伪装成 PA 产品说明。

当用户问的是“我的 Agent 当前选了哪个模型”“这个节点现在是否在线”一类现场状态时，说明书只提供判断路径，Agent 需要核对当前可见的实际状态，并把“产品说明”与“本机观察结果”区分开。若用户明确询问最新版、升级差异或远端当前行为，Agent 才查询远端权威信息，并明确区分本机已安装版本与远端版本。基础产品问答不依赖联网。

产品说明书是 PA 全局内置 skill，沿用现有内置 skill 的选择体验。新建 Agent 和仍使用默认 skill 集合的 Agent 默认选中它；用户可在 IM 的 Agent 配置中关闭或重新开启。升级前已有显式 skill 选择的 Agent 不被静默改写。

PA 随包提供的产品说明书、Lark bundle 等内置 skills 是产品托管内容。Gateway 启动时以当前安装包版本完整刷新这些保留名称对应的目录，使 Agent 不会继续使用旧版本残留文件。刷新不改变任何 Agent 已保存的 skill 启用/关闭选择，也不触及其他名称的用户自建 skills。需要修改内置能力的用户应复制为新的 skill 名称后定制。

## 验收标准

### Requirement: 产品说明书作为可关闭的默认 PA skill

#### Scenario: 新建 Agent 默认启用产品说明书
- **WHEN** 用户在 IM 中新建 PA Agent 并查看 skill 选择
- **THEN** 产品说明书出现在可选 skill 列表中并默认选中

#### Scenario: 使用默认 skill 集合的 Agent 获得产品说明书
- **GIVEN** 某 PA Agent 没有保存显式 skill 选择
- **WHEN** 用户使用升级后包含产品说明书的 PA 与该 Agent 对话
- **THEN** 该 Agent 可以按需使用产品说明书回答 PA 产品问题

#### Scenario: 升级不改写已有显式选择
- **GIVEN** 某 PA Agent 在升级前已经保存显式 skill 选择，且其中没有产品说明书
- **WHEN** 用户升级到包含产品说明书的 PA 并再次查看该 Agent 配置
- **THEN** 原有选择保持不变，产品说明书显示为未选中

#### Scenario: 用户关闭后不再使用产品说明书
- **GIVEN** 某 Agent 已启用产品说明书
- **WHEN** 用户在 IM 中取消选择并成功保存，然后继续询问产品问题
- **THEN** 该 Agent 不再调用产品说明书 skill
- **AND** 用户以后可以重新选中并恢复该能力

### Requirement: 随包内置 skills 与当前 PA 版本一致

#### Scenario: 升级后刷新全部内置 skills
- **GIVEN** 用户全局 skill 目录中已有旧版本 PA 安装的产品说明书或 Lark 内置 skill
- **WHEN** 用户升级 PA 并启动 Gateway
- **THEN** 这些内置 skill 的内容与当前安装包提供的版本一致
- **AND** 旧版本已删除的内置文件不再残留

#### Scenario: 本地修改的内置 skill 被产品版本替换
- **GIVEN** 用户修改过一个 PA 随包内置 skill 的目录内容
- **WHEN** Gateway 使用当前 PA 安装包启动
- **THEN** 该保留名称的 skill 恢复为当前安装包提供的完整内容

#### Scenario: 用户自建的其他 skills 保持不变
- **GIVEN** 用户全局 skill 目录中还有名称不属于 PA 随包内置集合的自建 skill
- **WHEN** Gateway 刷新随包内置 skills
- **THEN** 用户自建 skill 的目录和内容保持不变

#### Scenario: 刷新不改变 Agent 的 skill 选择
- **GIVEN** 用户已在 IM 中为 Agent 保存一组显式 skill 选择，其中关闭了部分内置 skills
- **WHEN** Gateway 刷新随包内置 skills 并与 IM 同步配置
- **THEN** Agent 原有的启用和关闭选择保持不变

### Requirement: Agent 按需用说明书回答 PA 产品问题

#### Scenario: 从任一 PA 对话入口询问产品能力
- **GIVEN** 当前 Agent 已启用产品说明书
- **WHEN** 用户从 Web IM、飞书或其他 PA 对话入口询问 PA 的能力、使用方法、配置或故障处理
- **THEN** Agent 按需调用产品说明书 skill，并给出基于说明书的直接回答

#### Scenario: 普通任务不触发产品说明书
- **GIVEN** 当前 Agent 已启用产品说明书
- **WHEN** 用户提出与 PA 产品自身无关的普通任务
- **THEN** Agent 不因为产品说明书处于启用状态而调用它

#### Scenario: 问题超出 PA 说明书边界
- **WHEN** 用户询问 coding CLI、内核内部架构或仓库开发流程
- **THEN** Agent 不把这些内容冒充为 PA 产品说明
- **AND** Agent 明确说明当前说明书的覆盖边界，并在有合适信息来源时指向该来源

### Requirement: 回答与用户正在使用的 PA 版本一致

#### Scenario: 基础产品问答无需联网
- **GIVEN** 当前环境无法访问网络
- **WHEN** 用户询问本机 PA 版本所支持的产品能力或使用方法
- **THEN** Agent 仍能依据随当前版本提供的说明书回答

#### Scenario: 用户明确询问最新版或升级差异
- **WHEN** 用户明确询问最新版、升级变化或远端当前行为
- **THEN** Agent 区分本机已安装版本与查询到的远端版本后回答
- **AND** 不把远端版本的行为表述为本机已经具备的行为

#### Scenario: 远端信息不可用
- **GIVEN** 用户明确询问最新版或升级差异，但远端权威信息无法取得
- **WHEN** Agent 已完成可用来源的查询
- **THEN** Agent 明确说明无法确认远端当前情况，并将回答限定在本机版本说明书覆盖的事实内

### Requirement: 产品说明与现场状态有清晰证据边界

#### Scenario: 用户询问当前配置或运行状态
- **WHEN** 用户询问自己的 Agent、节点、渠道或任务当前处于什么状态
- **THEN** Agent 核对当前可见的实际状态后回答，而不是把说明书中的默认值当成现场事实
- **AND** 回答清楚区分产品规则与本机观察结果

#### Scenario: 现场行为与说明书不一致
- **GIVEN** Agent 已观察到本机实际行为与当前版本说明书存在差异
- **WHEN** 用户询问相关产品行为或故障
- **THEN** Agent 明确指出差异，并以已核实的本机事实描述当前情况
- **AND** 不静默把说明书或猜测表述为已经验证的运行事实

#### Scenario: 说明书没有覆盖答案
- **WHEN** 用户的问题在产品说明书和当前可核实状态中都没有答案
- **THEN** Agent 明确说明资料未覆盖或结论不确定，不编造产品能力、配置项或处理步骤

## 范围与非目标

- 在范围：
  - 随 PA 提供一份面向 PA 用户的产品说明书 skill。
  - 覆盖 Web IM、Gateway、Agent 配置、模型、skills、tools、memory、heartbeat、cron、飞书等外部渠道、启动和常见故障处理。
  - 在相关产品问题上按需调用，并遵循权威来源、版本区分、现场核实和有界不确定性原则。
  - 沿用全局内置 skill 的默认选择、IM 关闭与重新开启体验。
  - 保留已有 Agent 的显式 skill 选择，不因升级静默扩宽。
  - Gateway 启动时以当前安装包完整刷新产品说明书、Lark bundle 等全部随包内置 skills。
  - 保护名称不属于 PA 随包内置集合的用户自建 skills。
- 非目标：
  - 不把产品说明书设为用户无法关闭的强制能力。
  - 不覆盖 coding CLI、内核内部架构或仓库开发流程。
  - 不建设独立帮助中心、文档网站或新的 IM 文档浏览界面。
  - 不改变通用 skill 的发现、读取、使用统计或生命周期机制；只改变 PA 随包内置资源的启动刷新语义。
  - 不要求基础产品问答依赖远端网络。
